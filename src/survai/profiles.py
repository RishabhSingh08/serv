from dataclasses import dataclass
from datetime import datetime

import cv2

from .capture import Frame
from .detectors.walkout import Visit, VisitState
from .tracks import Track


@dataclass
class Profile:
    track_id: int
    first_seen: datetime
    last_seen: datetime
    state: VisitState
    visible: bool = True
    photo: bytes | None = None
    photo_taken_at: datetime | None = None


class VisitProfiles:
    def __init__(self) -> None:
        self.active: dict[int, Profile] = {}
        self._candidates: dict[int, tuple[datetime, bytes]] = {}

    def clear(self) -> None:
        self.active.clear()
        self._candidates.clear()

    def update(
        self, frame: Frame, tracks: list[Track], visits: dict[int, Visit], captured_at: datetime,
    ) -> None:
        visible = {track.id: track for track in tracks}
        for track_id in list(self.active):
            if track_id not in visits or visits[track_id].state == VisitState.EXITED:
                del self.active[track_id]
                self._candidates.pop(track_id, None)
        for track_id, visit in visits.items():
            if visit.state == VisitState.EXITED:
                continue
            track = visible.get(track_id)
            profile = self.active.setdefault(
                track_id, Profile(track_id, captured_at, captured_at, visit.state),
            )
            profile.state = visit.state
            profile.visible = track is not None
            if track is not None:
                profile.last_seen = captured_at
            if profile.state == VisitState.PAID:
                candidate = self._candidates.pop(track_id, None)
                if candidate is not None:
                    profile.photo_taken_at, profile.photo = candidate
            elif track is not None:
                previous = self._candidates.get(track_id)
                if previous is None or (captured_at - previous[0]).total_seconds() >= 0.5:
                    photo = crop_photo(frame, track)
                    if photo is not None:
                        self._candidates[track_id] = (captured_at, photo)


def crop_photo(frame: Frame, track: Track) -> bytes | None:
    height, width = frame.shape[:2]
    left, top, right, bottom = track.box
    crop = frame[max(0, round(top * height)):round(bottom * height),
                 max(0, round(left * width)):round(right * width)]
    if crop.size == 0:
        return None
    scale = min(1, 320 / max(crop.shape[:2]))
    if scale < 1:
        crop = cv2.resize(crop, (max(1, round(crop.shape[1] * scale)),
                                 max(1, round(crop.shape[0] * scale))), interpolation=cv2.INTER_AREA)
    ok, encoded = cv2.imencode(".jpg", crop)
    return encoded.tobytes() if ok else None
