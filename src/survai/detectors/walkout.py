from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from math import dist
from typing import Literal

from ..config import WalkoutConfig
from ..tracks import Track
from ..zones import Point, crosses, inside, side

ExitType = Literal["line", "track_lost"]


class VisitState(StrEnum):
    NEW = "NEW"
    DINING = "DINING"
    PAID = "PAID"
    EXITED = "EXITED"


@dataclass
class Visit:
    point: Point
    last_seen: float
    missing: bool = False
    occluded: bool = False
    state: VisitState = VisitState.NEW
    history: list[tuple[float, VisitState]] = field(default_factory=list)
    dining_since: float | None = None
    pay_since: float | None = None
    dining_seconds: float = 0.0
    qualified: bool = False
    line_point: Point | None = None

    def transition(self, state: VisitState, now: float) -> None:
        if self.state != state:
            self.state = state
            self.history.append((now, state))

    def interrupt_dwell(self) -> None:
        self.dining_since = None
        self.pay_since = None
        self.line_point = None
        if not self.qualified:
            self.dining_seconds = 0


@dataclass(frozen=True)
class WalkoutEvent:
    track_id: int
    timestamp: datetime
    source_seconds: float
    dwell_seconds: float
    exit_type: ExitType
    message: str
    last_seen_seconds: float


class WalkoutDetector:
    def __init__(self, config: WalkoutConfig) -> None:
        self.config = config
        self.visits: dict[int, Visit] = {}
        self.last_alert: float | None = None

    def reset(self) -> None:
        self.visits.clear()
        self.last_alert = None

    def mark_dining_zone_paid(self, now: float) -> None:
        for visit in self.visits.values():
            if (
                not visit.missing and visit.state != VisitState.EXITED
                and inside(visit.point, self.config.dining_zone)
            ):
                visit.transition(VisitState.PAID, now)

    def update(
        self, tracks: list[Track], now: float, *, occluded_ids: set[int] | None = None,
    ) -> list[WalkoutEvent]:
        points = {track.id: self._anchor(track) for track in tracks if track.kind == "person"}
        events: list[WalkoutEvent] = []
        for track_id, visit in list(self.visits.items()):
            if track_id in points and not visit.missing:
                continue
            if occluded_ids is not None and track_id in occluded_ids:
                visit.occluded = True
                if not visit.missing:
                    visit.missing = True
                    visit.interrupt_dwell()
                continue
            if now - visit.last_seen >= self.config.lost_grace_seconds and (
                track_id not in points or occluded_ids is None
            ):
                band = self.config.exit_band
                if not visit.occluded and band is not None and inside(visit.point, band, include_boundary=True):
                    self._exit(track_id, visit, now, "track_lost", events)
                del self.visits[track_id]
            elif track_id not in points and not visit.missing:
                visit.missing = True
                visit.interrupt_dwell()

        if occluded_ids is None:
            self._reassociate(points)
        for track_id, point in points.items():
            visit = self.visits.get(track_id)
            if visit is None:
                visit = Visit(point, now, history=[(now, VisitState.NEW)])
                self.visits[track_id] = visit
            visit.point, visit.last_seen, visit.missing = point, now, False
            visit.occluded = False
            if visit.state == VisitState.EXITED:
                continue
            self._update_dwell(visit, now)
            line = self.config.exit_line
            if line is not None and side(*line, point) != 0:
                previous = visit.line_point
                if (
                    previous is not None and side(*line, previous) > 0
                    and crosses(previous, point, line)
                ):
                    self._exit(track_id, visit, now, "line", events)
                visit.line_point = point
        return events

    def _anchor(self, track: Track) -> Point:
        if self.config.anchor == "bottom_center":
            return track.point
        left, top, right, bottom = track.box
        return (left + right) / 2, (top + bottom) / 2

    def _update_dwell(self, visit: Visit, now: float) -> None:
        if inside(visit.point, self.config.dining_zone):
            if visit.dining_since is None:
                visit.dining_since = now
            visit.dining_seconds = max(visit.dining_seconds, now - visit.dining_since)
            if visit.dining_seconds >= self.config.min_dwell_seconds:
                visit.qualified = True
                if visit.state == VisitState.NEW:
                    visit.transition(VisitState.DINING, now)
        else:
            visit.dining_since = None
            if not visit.qualified:
                visit.dining_seconds = 0

        if inside(visit.point, self.config.pay_zone):
            if visit.pay_since is None:
                visit.pay_since = now
            if now - visit.pay_since >= self.config.pay_dwell_seconds:
                visit.transition(VisitState.PAID, now)
        else:
            visit.pay_since = None

    def _reassociate(self, points: dict[int, Point]) -> None:
        # Transfer a visit only if both IDs have a single plausible match.
        candidates = {
            track_id: [
                old_id for old_id, visit in self.visits.items()
                if old_id not in points and visit.state != VisitState.EXITED
                and dist(point, visit.point) <= self.config.reassociation_distance
            ]
            for track_id, point in points.items() if track_id not in self.visits
        }
        for track_id, matches in candidates.items():
            if len(matches) == 1:
                old_id = matches[0]
                if sum(old_id in options for options in candidates.values()) == 1:
                    self.visits[track_id] = self.visits.pop(old_id)

    def _exit(
        self, track_id: int, visit: Visit, now: float, exit_type: ExitType,
        events: list[WalkoutEvent],
    ) -> None:
        should_alert = visit.state == VisitState.DINING
        visit.transition(VisitState.EXITED, now)
        if not should_alert:
            return
        if self.last_alert is not None and now - self.last_alert < self.config.alert_cooldown_seconds:
            return
        self.last_alert = now
        events.append(WalkoutEvent(
            track_id=track_id,
            timestamp=datetime.now(timezone.utc),
            source_seconds=now,
            dwell_seconds=visit.dining_seconds,
            exit_type=exit_type,
            message=f"Possible walk-out: guest dined for {visit.dining_seconds:.1f}s "
            "and exited without a payment confirmation.",
            last_seen_seconds=visit.last_seen,
        ))
