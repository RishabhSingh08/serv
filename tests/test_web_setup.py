from pathlib import Path
from time import monotonic, sleep
from unittest.mock import patch

import cv2
import numpy as np
import yaml
from fastapi.testclient import TestClient

from survai.config import MultiCameraConfig, load_walkout_config
from survai.main import DEMO_CONFIG
from survai.server import create_app
from survai.state import State
from survai.web import WebSession, install_web_routes


def test_browser_previews_and_starts_with_saved_camera_layout(tmp_path: Path) -> None:
    config = MultiCameraConfig(cameras=[
        {"id": "mac", "name": "MacBook", "source": 0},
        {"id": "phone", "name": "iPhone", "source": 1, "walkout_enabled": False},
    ])
    state = State()
    path = tmp_path / "setup.yaml"
    session = WebSession(path, config, load_walkout_config(DEMO_CONFIG), state, tmp_path, None, False)
    app = create_app(state, tmp_path, None)
    install_web_routes(app, session)
    closed = []

    class Camera:
        live = False

        def first_frame(self):
            return np.full((80, 160, 3), 140, np.uint8)

        def close(self):
            closed.append(True)

    def monitor(config, defaults, **runtime):
        assert len(closed) == 2
        assert config.cameras[0].layout(defaults).dining_zone[0] == (0.1, 0.1)
        assert not config.cameras[1].walkout_enabled
        assert runtime["headless"]
        runtime["state"].publish(b"test frame", [], 0, 0, 0)
        assert runtime["stop"].wait(timeout=3)

    with TestClient(app, base_url="http://127.0.0.1") as client:
        def wait_for(status: str) -> None:
            deadline = monotonic() + 3
            while monotonic() < deadline:
                if client.get("/api/status").json()["status"] == status:
                    return
                sleep(0.01)
            raise AssertionError(f"Dashboard never reported {status!r}")

        try:
            settings = client.get("/api/setup").json()
            assert client.post("/api/session/stop", headers={"Origin": "https://example.org"}).status_code == 403
            with patch("survai.web.open_calibration_capture", side_effect=lambda *_: Camera()):
                response = client.post("/api/session/preview", json={"cameras": settings["cameras"]})
                assert response.status_code == 202
                deadline = monotonic() + 3
                while client.get("/api/session").json()["previews"].get("phone") != "Ready":
                    assert monotonic() < deadline
                    sleep(0.01)
                frame = client.get("/api/session/preview/phone")
                assert frame.status_code == 200
                assert cv2.imdecode(np.frombuffer(frame.content, np.uint8), cv2.IMREAD_COLOR).shape == (80, 160, 3)
                assert client.post("/api/session/start", json={}).status_code == 409

                corners = [[.1, .1], [.9, .1], [.9, .9], [.1, .9], [.45, .5]]
                settings["calibration"] = {"landmarks": [{"mac": point, "phone": point} for point in corners]}
                settings["cameras"][0]["zones"]["dining_zone"] = corners[:4]
                assert client.put("/api/setup", json=settings).status_code == 204
                assert yaml.safe_load(path.read_text())["calibration"]["landmarks"] == settings["calibration"]["landmarks"]
                assert client.post("/api/session/stop").status_code == 202
                wait_for("Monitoring stopped")
            with patch("survai.multi_camera.run_multi", side_effect=monitor):
                assert client.post("/api/session/start", json={}).status_code == 202
                wait_for("Monitoring")
                assert client.post("/api/session/pay").status_code == 202
                assert session.pay.is_set()
                assert client.post("/api/session/stop").status_code == 202
                wait_for("Monitoring stopped")
        finally:
            session.close()
