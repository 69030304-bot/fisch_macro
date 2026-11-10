"""
tests/test_vision_math.py - Tests for vision algorithms and predictive tracking from fisch_macro.
"""
import sys
import os
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import fisch_macro as fm


def test_color_mask():
    arr = np.array([
        [[100, 100, 100], [90, 90, 90], [50, 50, 50]],
    ], dtype=np.int16)

    mask = fm.color_mask(arr, [90, 90, 90], tol=15)
    # [100, 100, 100] is within tol=15 (diff is 10) -> True
    # [90, 90, 90] is exact match (diff is 0) -> True
    # [50, 50, 50] is outside tol=15 (diff is 40) -> False
    assert mask[0, 0] == True
    assert mask[0, 1] == True
    assert mask[0, 2] == False


def test_runs_of():
    # 2 rows, 10 columns
    mask = np.zeros((2, 10), dtype=bool)
    # First cluster: columns 1, 2
    mask[:, 1] = True
    mask[:, 2] = True
    # Second cluster: columns 6, 7, 8
    mask[:, 6] = True
    mask[:, 7] = True
    mask[:, 8] = True

    runs = fm.runs_of(mask, gap=2)
    assert len(runs) == 2
    # Cluster 1: start=1, end=2, center=1.5
    assert runs[0][0] == 1
    assert runs[0][1] == 2
    assert abs(runs[0][2] - 1.5) < 1e-4

    # Cluster 2: start=6, end=8, center=7.0
    assert runs[1][0] == 6
    assert runs[1][1] == 8
    assert abs(runs[1][2] - 7.0) < 1e-4


def test_choose():
    # runs: list of (left, right, center, weight, count)
    runs = [
        (1, 2, 1.5, 4, 2),    # small cluster (< min_cols=3)
        (10, 20, 15.0, 50, 11),  # large cluster
        (30, 42, 36.0, 48, 13),  # large cluster
    ]

    # Without pred: picks heaviest candidate
    best = fm.choose(runs, pred=None, min_cols=3)
    assert best[0] == 10  # weight 50

    # With pred: picks candidate closest to predicted position
    best_pred = fm.choose(runs, pred=35.0, min_cols=3)
    assert best_pred[0] == 30  # center 36.0 is closer to 35.0 than 15.0


def test_track_ema():
    track = fm.Track()
    assert track.pos(1.0) is None
    assert not track.fresh(1.0)

    # First update
    track.update(100.0, 1.0)
    assert track.x == 100.0
    assert track.v == 0.0
    assert track.fresh(1.05)

    # Second update moving right at 200 px/sec
    track.update(120.0, 1.1)
    assert track.x == 120.0
    assert track.v > 0.0

    # Predicted future position (0.05s later)
    pred_pos = track.pos(1.15)
    assert pred_pos > 120.0


def test_centers():
    fish_run = (10, 14, 12.0, 20, 5)
    bar_run = (40, 80, 60.0, 100, 41)

    fc, bc = fm.centers(fish_run, bar_run)
    assert fc == 12.0
    assert bc == 60.0  # (40 + 80) / 2

    fc_none, bc_none = fm.centers(None, None)
    assert fc_none is None
    assert bc_none is None


if __name__ == "__main__":
    test_color_mask()
    print("[PASS] test_color_mask")
    test_runs_of()
    print("[PASS] test_runs_of")
    test_choose()
    print("[PASS] test_choose")
    test_track_ema()
    print("[PASS] test_track_ema")
    test_centers()
    print("[PASS] test_centers")
    print("\nAll vision math tests passed!")
