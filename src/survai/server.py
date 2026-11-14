import asyncio
import json
import re
import socket
from collections.abc import AsyncIterator
from contextlib import AbstractContextManager
from dataclasses import asdict
from pathlib import Path
from threading import Thread
from time import monotonic, sleep

import uvicorn
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, StreamingResponse

from .llm import write_summary
from .state import State


class Dashboard(AbstractContextManager[State]):
    def __init__(self, directory: Path, port: int) -> None:
        self.state = State()
        self.socket = socket.socket()
        try:
            self.socket.bind(("127.0.0.1", port))
        except OSError:
            self.socket.close()
            raise
        app = create_app(self.state, directory, summary_model=None)
        self.server = uvicorn.Server(uvicorn.Config(app, access_log=False, log_level="warning", timeout_graceful_shutdown=1))
        self.thread = Thread(target=self.server.run, kwargs={"sockets": [self.socket]}, name="dashboard")

    def __enter__(self) -> State:
        self.thread.start()
        deadline = monotonic() + 5
        while not self.server.started and self.thread.is_alive() and monotonic() < deadline:
            sleep(0.02)
        if not self.server.started:
            self.__exit__(None, None, None)
            raise RuntimeError("The dashboard could not start")
        return self.state

    def __exit__(self, *_args: object) -> None:
        self.server.should_exit = True
        self.thread.join()
        self.socket.close()


def create_app(state: State, directory: Path, summary_model: str | None) -> FastAPI:
    app = FastAPI(title="Surveillance.ai")

    @app.get("/")
    def dashboard() -> FileResponse:
        return FileResponse(Path(__file__).with_name("dashboard.html"))

    @app.get("/api/status")
    def status() -> dict[str, str | bool | int]:
        with state.lock:
            return {
                "status": state.status,
                "alert_active": state.alert_active,
                "total_alerts": state.counts.total(),
            }

    @app.get("/api/alerts")
    def history() -> list[dict[str, object]]:
        with state.lock:
            return [asdict(event) for _, event in reversed(state.events)]

    @app.get("/api/visits")
    def active_visits() -> list[dict[str, object]]:
        with state.lock:
            return [
                {
                    "track_id": profile.track_id,
                    "first_seen": profile.first_seen,
                    "last_seen": profile.last_seen,
                    "state": profile.state,
                    "visible": profile.visible,
                    "photo_path": f"/api/visits/{profile.track_id}/photo" if profile.photo else None,
                    "photo_taken_at": profile.photo_taken_at,
                }
                for profile in state.profiles.values()
            ]

    @app.get("/api/visits/{track_id}/photo")
    def visit_photo(track_id: int) -> Response:
        with state.lock:
            profile = state.profiles.get(track_id)
            if profile is None or profile.photo is None:
                raise HTTPException(404, headers={"Cache-Control": "no-store"})
            return Response(profile.photo, media_type="image/jpeg", headers={"Cache-Control": "no-store"})

    @app.delete("/api/alerts/{alert_id}", status_code=204)
    def delete_alert(alert_id: str) -> None:
        if not re.fullmatch(r"[0-9a-f]{32}", alert_id):
            raise HTTPException(404)
        state.delete_alert(alert_id)

    @app.get("/api/summary")
    def summary() -> dict[str, object]:
        metrics = state.metrics()
        busiest = metrics["busiest_period_start_seconds"]
        period = f"{busiest}s into this session" if busiest is not None else "unavailable"
        fallback = (
            f"This session recorded {metrics['total_alerts']} alerts. "
            f"The peak queue held {metrics['peak_queue']} people. "
            f"The busiest minute starts at {period}." if busiest is not None
            else "The session has no camera observations yet."
        )
        return {**metrics, "summary": write_summary(summary_model, metrics, fallback) if summary_model else fallback}

    @app.get("/snapshots/{name}")
    def snapshot(name: str) -> FileResponse:
        path = directory / name
        if not re.fullmatch(r"[0-9a-f]{32}\.jpg", name) or not path.is_file():
            raise HTTPException(404)
        return FileResponse(path, media_type="image/jpeg")

    @app.get("/clips/{name}")
    def clip(name: str) -> FileResponse:
        path = directory / name
        if not re.fullmatch(r"[0-9a-f]{32}\.mp4", name) or not path.is_file():
            raise HTTPException(404)
        return FileResponse(path, media_type="video/mp4")

    @app.get("/video")
    async def video(request: Request) -> StreamingResponse:
        async def frames() -> AsyncIterator[bytes]:
            seen = 0
            while not await request.is_disconnected():
                with state.lock:
                    index, frame = state.frame_id, state.frame
                if frame is not None and index != seen:
                    seen = index
                    yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
                await asyncio.sleep(0.025)

        return StreamingResponse(frames(), media_type="multipart/x-mixed-replace; boundary=frame")

    @app.get("/events")
    async def events(request: Request) -> StreamingResponse:
        async def messages() -> AsyncIterator[str]:
            cursor = request.headers.get("last-event-id", "")
            seen = int(cursor) if cursor.isdecimal() and len(cursor) < 20 else 0
            idle = 0
            yield ": connected\n\n"
            while not await request.is_disconnected():
                with state.lock:
                    pending = [(index, event) for index, event in state.changes if index > seen]
                for index, event in pending:
                    seen = index
                    if isinstance(event, str):
                        yield f"id: {index}\nevent: alert-deleted\ndata: {event}\n\n"
                    else:
                        yield f"id: {index}\ndata: {json.dumps(asdict(event))}\n\n"
                idle = 0 if pending else idle + 1
                if idle == 150:
                    yield ": keep-alive\n\n"
                    idle = 0
                await asyncio.sleep(0.1)

        return StreamingResponse(messages(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    return app
