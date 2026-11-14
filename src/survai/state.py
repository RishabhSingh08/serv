from collections import Counter, deque
from dataclasses import dataclass, replace
from threading import Lock

from .events import Event
from .profiles import Profile


@dataclass(frozen=True)
class CameraFeed:
    name: str
    status: str
    fps: float = 0
    jpeg: bytes | None = None


class State:
    def __init__(self) -> None:
        self.lock = Lock()
        self.frame: bytes | None = None
        self.frame_id = 0
        self.events: deque[tuple[int, Event]] = deque(maxlen=500)
        self.changes: deque[tuple[int, Event | str]] = deque(maxlen=1000)
        self.event_id = 0
        self.counts: Counter[str] = Counter()
        self.people_by_minute: dict[int, tuple[int, int]] = {}
        self.peak_queue = 0
        self.peak_queue_at = 0.0
        self.status = "Starting camera and model"
        self.alert_active = False
        self.profiles: dict[int, Profile] = {}
        self.cameras: dict[str, CameraFeed] = {}
        self.floor: dict[str, object] | None = None
        self.door_counts: dict[str, int] | None = None

    def publish_door_counts(self, came_in: int, left: int) -> None:
        with self.lock:
            self.door_counts = {"came_in": came_in, "left": left}

    def publish_floor(self, guests: list[dict[str, object]], coverage: dict[str, object]) -> None:
        with self.lock:
            self.floor = {"guests": guests, "coverage": coverage}

    def publish_cameras(self, cameras: dict[str, CameraFeed]) -> None:
        with self.lock:
            self.cameras = cameras.copy()

    def publish_profiles(self, profiles: dict[int, Profile]) -> None:
        with self.lock:
            self.profiles = {track_id: replace(profile) for track_id, profile in profiles.items()}

    def publish(
        self, frame: bytes, events: list[Event], now: float, people: int, queue: int,
        alert_active: bool = False,
    ) -> None:
        with self.lock:
            self.frame = frame
            self.frame_id += 1
            self.status = "Monitoring"
            self.alert_active = alert_active
            for event in events:
                self.event_id += 1
                self.events.append((self.event_id, event))
                self.changes.append((self.event_id, event))
                self.counts[event.type] += 1
            if queue > self.peak_queue:
                self.peak_queue = queue
                self.peak_queue_at = now
            minute = int(now // 60)
            total, frames = self.people_by_minute.get(minute, (0, 0))
            self.people_by_minute[minute] = (total + people, frames + 1)

    def delete_alert(self, alert_id: str) -> None:
        with self.lock:
            for position, (_, event) in enumerate(self.events):
                if event.id == alert_id:
                    del self.events[position]
                    self.counts[event.type] -= 1
                    # New dashboard tabs should never receive a deleted card.
                    self.changes = deque(
                        ((index, change) for index, change in self.changes
                         if not isinstance(change, Event) or change.id != alert_id),
                        maxlen=self.changes.maxlen,
                    )
                    self.event_id += 1
                    self.changes.append((self.event_id, alert_id))
                    return

    def finish_clip(self, event: Event) -> None:
        with self.lock:
            for position, (index, previous) in enumerate(self.events):
                if previous.id == event.id:
                    updated = replace(previous, clip_status=event.clip_status, clip_path=event.clip_path)
                    self.events[position] = (index, updated)
                    self.event_id += 1
                    self.changes.append((self.event_id, updated))
                    return

    def expire_evidence(self, deleted: set[str]) -> None:
        with self.lock:
            for position, (index, event) in enumerate(self.events):
                snapshot_expired = event.snapshot_path in deleted
                clip_expired = event.clip_path in deleted
                if snapshot_expired or clip_expired:
                    updated = replace(
                        event,
                        snapshot_path=None if snapshot_expired else event.snapshot_path,
                        clip_path=None if clip_expired else event.clip_path,
                        clip_status="expired" if clip_expired else event.clip_status,
                    )
                    self.events[position] = (index, updated)
                    self.event_id += 1
                    self.changes.append((self.event_id, updated))

    def metrics(self) -> dict[str, object]:
        with self.lock:
            periods = self.people_by_minute
            busiest = max(periods, key=lambda minute: periods[minute][0] / periods[minute][1],
                          default=None)
            return {
                "total_alerts": self.counts.total(),
                "counts": dict(self.counts),
                "peak_queue": self.peak_queue,
                "peak_queue_at_seconds": round(self.peak_queue_at, 1),
                "busiest_period_start_seconds": busiest * 60 if busiest is not None else None,
            }
