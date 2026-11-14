from dataclasses import dataclass
from datetime import datetime, timezone

from .config import WalkoutConfig
from .detectors.walkout import ExitType, Visit, VisitState, WalkoutEvent
from .zones import Point


@dataclass(frozen=True)
class Sighting:
    camera: str
    point: Point
    dining: bool = False
    pay: bool = False
    exit: ExitType | None = None
    observed_at: float | None = None


class RoomVisits:
    def __init__(self, config: WalkoutConfig) -> None:
        self.config = config
        self.visits: dict[int, Visit] = {}
        self.exits: dict[int, tuple[float, Sighting]] = {}
        self.absent_since: dict[int, float] = {}
        self.dining: set[int] = set()
        self.previous: float | None = None
        self.last_alert: dict[int, float] = {}

    def mark_paid(self, now: float) -> None:
        for guest_id in self.dining:
            self.visits[guest_id].transition(VisitState.PAID, now)

    def update(
        self, sightings: dict[int, list[Sighting]], now: float, *, coverage_ok: bool,
    ) -> list[tuple[str, WalkoutEvent]]:
        elapsed = 0 if self.previous is None else now - self.previous
        self.previous = now
        dining = set()
        alerts = []
        for guest_id, views in sightings.items():
            visit = self.visits.setdefault(guest_id, Visit(views[0].point, now))
            visit.last_seen = now
            self.absent_since.pop(guest_id, None)
            if any(view.dining for view in views):
                dining.add(guest_id)
                if guest_id in self.dining:
                    visit.dining_seconds += elapsed
                if visit.dining_seconds >= self.config.min_dwell_seconds and visit.state == VisitState.NEW:
                    visit.transition(VisitState.DINING, now)
            if any(view.pay for view in views):
                if visit.pay_since is None:
                    visit.pay_since = now
                if now - visit.pay_since >= self.config.pay_dwell_seconds:
                    visit.transition(VisitState.PAID, now)
            else:
                visit.pay_since = None
            exits = [view for view in views if view.exit is not None]
            if exits:
                def observation_time(view: Sighting) -> float:
                    return now if view.observed_at is None else view.observed_at

                latest = max(exits, key=observation_time)
                self.exits[guest_id] = (observation_time(latest), latest)
            else:
                self.exits.pop(guest_id, None)
        self.dining = dining
        for guest_id in self.visits.keys() - sightings.keys():
            visit = self.visits[guest_id]
            visit.pay_since = None
            if not coverage_ok:
                self.absent_since.pop(guest_id, None)
                continue
            first_absence = self.absent_since.setdefault(guest_id, now)
            if now - first_absence < self.config.lost_grace_seconds:
                continue
            exit_sighting = self.exits.pop(guest_id, None)
            del self.visits[guest_id]
            del self.absent_since[guest_id]
            if exit_sighting is None or visit.state != VisitState.DINING:
                continue
            if now - self.last_alert.get(guest_id, float("-inf")) < self.config.alert_cooldown_seconds:
                continue
            self.last_alert[guest_id] = now
            last_seen, sighting = exit_sighting
            assert sighting.exit is not None
            alerts.append((sighting.camera, WalkoutEvent(
                guest_id, datetime.now(timezone.utc), now, visit.dining_seconds, sighting.exit,
                f"Possible walk-out: Guest #{guest_id} left without a payment confirmation "
                f"(last exit sighting: {sighting.camera}).", last_seen,
            )))
        self.last_alert = {key: at for key, at in self.last_alert.items()
                           if now - at < self.config.alert_cooldown_seconds}
        return alerts
