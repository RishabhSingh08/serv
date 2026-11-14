from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient

from survai.config import load_walkout_config
from survai.detectors.walkout import WalkoutDetector
from survai.main import DEMO_CONFIG
from survai.profiles import VisitProfiles
from survai.server import create_app
from survai.state import State
from survai.synthetic import person


def test_paid_visit_uses_earlier_photo_and_removes_it_after_exit(tmp_path: Path) -> None:
    config = load_walkout_config(DEMO_CONFIG)
    detector = WalkoutDetector(config)
    profiles = VisitProfiles()
    state = State()
    camera = np.full((100, 200, 3), 100, dtype=np.uint8)
    start = datetime(2026, 11, 13, tzinfo=timezone.utc)

    def step(seconds, tracks):
        assert not detector.update(tracks, seconds, occluded_ids=set())
        profiles.update(camera, tracks, detector.visits, start + timedelta(seconds=seconds))
        state.publish_profiles(profiles.active)

    with TestClient(create_app(state, tmp_path, None)) as client:
        step(0, [person(4, 0.4)])
        assert client.get("/api/visits").json()[0]["state"] == "NEW"
        assert client.get("/api/visits/4/photo").status_code == 404
        step(3, [person(4, 0.4)])
        detector.mark_dining_zone_paid(3.1)
        step(3.1, [person(4, 0.4)])
        profile, = client.get("/api/visits").json()
        assert profile["state"] == "PAID"
        assert datetime.fromisoformat(profile["photo_taken_at"]) == start + timedelta(seconds=3)
        photo = client.get(profile["photo_path"])
        assert photo.status_code == 200 and photo.headers["cache-control"] == "no-store"
        step(4, [person(4, 0.94)])
        step(5.6, [])
        assert client.get("/api/visits").json() == []
        assert client.get(profile["photo_path"]).status_code == 404
