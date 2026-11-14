from pathlib import Path

import numpy as np
import pytest

from survai.config import load_walkout_config
from survai.detectors.walkout import VisitState, WalkoutDetector
from survai.identity import PersonIdentities
from survai.tracks import Track


@pytest.mark.parametrize("foreground_id", [20, 10])
def test_hidden_diner_returns_with_same_id_even_if_tracker_renumbers(foreground_id: int) -> None:
    config = load_walkout_config(Path(__file__).parents[1] / "src/survai/walkout.demo.yaml")
    identities = PersonIdentities(config.lost_grace_seconds, config.reassociation_distance, config.occlusion_seconds)
    detector = WalkoutDetector(config)

    def step(now: float, *people: tuple[int, float, tuple[int, int, int]]) -> list[int]:
        frame = np.zeros((200, 400, 3), dtype=np.uint8)
        tracks = []
        for raw_id, x, color in people:
            left, right = x - 0.07, x + 0.07
            frame[40:160, round(left * 400):round(right * 400)] = color
            tracks.append(Track(raw_id, "person", (left, 0.2, right, 0.8)))
        visible = identities.update(frame, tracks, now)
        assert not detector.update(visible, now, occluded_ids=identities.hidden_ids)
        return [track.id for track in visible]

    red, blue = (0, 0, 255), (255, 0, 0)
    for now in (0, 1, 2, 3):
        assert step(now, (10, 0.42, red), (20, 0.73, blue)) == [1, 2]
    assert detector.visits[1].state == VisitState.DINING
    assert detector.visits[2].state == VisitState.NEW
    assert step(3.2, (10, 0.42, red), (20, 0.62, blue)) == [1, 2]
    assert step(3.4, (10, 0.42, red), (20, 0.54, blue)) == [1, 2]
    assert step(3.6, (foreground_id, 0.42, blue)) == [2]
    assert identities.hidden_ids == {1}
    for now in (4, 4.4, 4.8, 5.2, 5.6):
        assert step(now, (foreground_id, 0.43, blue)) == [2]
    assert step(5.8, (77, 0.32, red), (foreground_id, 0.48, blue)) == [1, 2]
    assert detector.visits[1].state == VisitState.DINING
    assert detector.visits[2].state == VisitState.NEW


def test_unobstructed_departure_does_not_keep_id_past_grace() -> None:
    identities = PersonIdentities(lost_grace=1.5, distance=0.08, occlusion_seconds=5)
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    track = Track(7, "person", (0.8, 0.2, 0.98, 0.8))
    assert identities.update(frame, [track], 0)[0].id == 1
    assert not identities.update(frame, [], 1)
    assert not identities.hidden_ids
    assert identities.update(frame, [track], 2)[0].id == 2
