import numpy as np

from survai.apron import ApronColor, EmployeeLabels
from survai.doorway import DoorCounter
from survai.tracks import Track


def test_door_counts_both_directions_without_jitter_or_lost_track_crossings():
    door = DoorCounter(((0.5, 0.8), (0.5, 0.2)))  # Inside is to the right.
    door.update({1: (0.4, 0.5), 2: (0.4, 0.1), 3: (0.4, 0.5)}, 0)
    door.update({1: (0.499, 0.5), 2: (0.6, 0.1)}, 0.1)
    door.update({1: (0.508, 0.5)}, 0.2)
    assert (door.came_in, door.left) == (0, 0)
    door.update({1: (0.6, 0.5)}, 0.3)
    door.update({1: (0.601, 0.5), 3: (0.6, 0.5)}, 0.9)
    assert (door.came_in, door.left) == (1, 0)
    door.update({1: (0.4, 0.5)}, 1.0)
    door.update({1: (0.39, 0.5)}, 1.1)
    assert (door.came_in, door.left) == (1, 1)


def test_apron_match_requires_torso_coverage_and_consistent_observations():
    frame = np.full((200, 200, 3), 135, np.uint8)
    employee = Track(1, "person", (0, 0, 0.5, 1))
    guest = Track(2, "person", (0.5, 0, 1, 1))
    apron = ApronColor("#dd3020")
    frame[65:163, 25:75] = (32, 48, 221)
    frame[65:100, 125:175] = (32, 48, 221)  # A matching accent on the shirt.
    assert apron.matches(frame, employee) is True
    assert apron.matches(frame, guest) is False
    labels = EmployeeLabels()
    for tick in range(3):
        labels.update({employee.id: True, guest.id: False}, tick * 0.1)
    assert labels.employees == {employee.id}
    labels.update({employee.id: False}, 0.3)
    labels.update({}, 1)
    assert labels.employees == {employee.id}
    labels.update({}, 6)
    assert not labels.employees
