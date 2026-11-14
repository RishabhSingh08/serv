import logging
from dataclasses import dataclass
from time import monotonic

import cv2
import numpy as np
import torch
from ultralytics import YOLO

from .capture import Frame
from .config import Config
from .zones import Point

LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class Track:
    id: int
    kind: str
    box: tuple[float, float, float, float]

    @property
    def point(self) -> Point:
        left, top, right, bottom = self.box
        return ((left + right) / 2, bottom if self.kind == "person" else (top + bottom) / 2)


class Vision:
    def __init__(self, config: Config) -> None:
        self.weights = config.weights
        self.image_size = config.image_size
        self.model = YOLO(self.weights)
        self.device = "mps" if torch.backends.mps.is_available() else "cpu"
        self.started = monotonic()
        self.frames = 0

    def track(self, frame: Frame) -> list[Track]:
        options = dict(
            persist=True, tracker="bytetrack.yaml", classes=[0, 24, 26, 28],
            imgsz=self.image_size, verbose=False,
        )
        try:
            result = self.model.track(frame, device=self.device, **options)[0]
        except (RuntimeError, NotImplementedError):
            if self.device != "mps":
                raise
            LOG.warning("MPS inference failed. Restarting tracker on CPU.", exc_info=True)
            self.device = "cpu"
            self.model = YOLO(self.weights)
            self.reset_tracks = True
            result = self.model.track(frame, device=self.device, **options)[0]
        self.frames += 1
        boxes = result.boxes
        ids = boxes.id
        if ids is None:
            return []
        return [
            Track(int(track_id), result.names[int(kind)], (x1, y1, x2, y2))
            for track_id, kind, (x1, y1, x2, y2) in zip(
                ids.tolist(), boxes.cls.tolist(), boxes.xyxyn.tolist(), strict=True
            )
        ]

    reset_tracks = False

    @property
    def fps(self) -> float:
        return self.frames / max(monotonic() - self.started, 0.001)


def annotate(frame: Frame, tracks: list[Track], config: Config, status: str) -> Frame:
    height, width = frame.shape[:2]
    for track in tracks:
        left, top, right, bottom = track.box
        start = (int(left * width), int(top * height))
        cv2.rectangle(frame, start, (int(right * width), int(bottom * height)), (90, 230, 100), 2)
        cv2.putText(frame, f"{track.kind} #{track.id}", start, 0, 0.55, (90, 230, 100), 2)
    polygon = np.array([(x * width, y * height) for x, y in config.counter_zone], np.int32)
    cv2.polylines(frame, [polygon], True, (255, 180, 60), 2)
    a, b = [(int(x * width), int(y * height)) for x, y in config.exit_line]
    cv2.line(frame, a, b, (60, 140, 255), 2)
    cv2.putText(frame, status, (12, 26), 0, 0.65, (255, 255, 255), 2)
    return frame
