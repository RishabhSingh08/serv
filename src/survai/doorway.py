from dataclasses import dataclass
from math import dist

from .zones import Point, crosses, side


@dataclass
class Observation:
    stable: Point | None
    seen_at: float


class DoorCounter:
    """Count crossings of the drawn segment. Its positive side faces inside."""

    def __init__(self, line: tuple[Point, Point]) -> None:
        self.line = line
        self.band = dist(*line) * 0.015
        self.observations: dict[int, Observation] = {}
        self.came_in = 0
        self.left = 0

    def update(self, points: dict[int, Point], now: float) -> None:
        self.observations = {key: value for key, value in self.observations.items() if now - value.seen_at <= 0.75}
        for guest, point in points.items():
            offset = side(*self.line, point)
            previous = self.observations.get(guest)
            if abs(offset) <= self.band:
                if previous is not None:
                    previous.seen_at = now
                continue
            if previous is not None and previous.stable is not None and crosses(previous.stable, point, self.line):
                if offset > 0:
                    self.came_in += 1
                else:
                    self.left += 1
            self.observations[guest] = Observation(point, now)
