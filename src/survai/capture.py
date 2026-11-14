import sys

import cv2
from numpy.typing import NDArray
from numpy import uint8

Frame = NDArray[uint8]


class Capture:
    def __init__(self, source: str) -> None:
        self.live = source.isdecimal()
        if self.live:
            backend = cv2.CAP_AVFOUNDATION if sys.platform == "darwin" else cv2.CAP_ANY
            self.device = cv2.VideoCapture(int(source), backend)
            self.device.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.device.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        else:
            self.device = cv2.VideoCapture(source)
        if not self.device.isOpened():
            self.close()
            hint = ""
            if self.live and sys.platform == "darwin":
                hint = " Grant your terminal or IDE access in System Settings > Privacy & Security > Camera."
            raise RuntimeError(f"Could not open source {source!r}.{hint}")
        fps = self.device.get(cv2.CAP_PROP_FPS)
        self.fps = fps if 0 < fps < 1000 else 30.0

    def read(self) -> Frame | None:
        ok, frame = self.device.read()
        return frame if ok else None

    def close(self) -> None:
        self.device.release()
