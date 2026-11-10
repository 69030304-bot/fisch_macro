"""
tests/test_vision.py - Unit tests for vision package (ScreenGrabber, detection, analysis, and tracking).
"""
import sys
import os
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from vision.capture import MockScreenGrabber, ScreenGrabber
from vision.detection import (
    color_mask,
    runs_of,
    choose,
    analyze,
    measure,
    centers,
    row_stride,
    detect,
    BAR_GAP,
    FISH_GAP,
)
from vision.tracking import Track


def test_mock_screen_grabber():
    grabber = MockScreenGrabber()
    # Should produce blank frame of requested dimensions [x, y, w, h]
    frame = grabber.grab((0, 0, 100, 48), stride=2)
    assert frame.shape == (24, 100, 3)
    assert np.all(frame == 0)

    # Injecting synthetic frame
    synthetic = np.full((50, 200, 3), 128, dtype=np.int16)
    grabber.set_frame(synthetic)
    frame2 = grabber.grab((0, 0, 200, 50), stride=1)
    assert frame2.shape == (50, 200, 3)
    assert np.all(frame2 == 128)


def test_synthetic_minigame_detection():
    # 30 rows, 400 columns
    # Background: dark blue [20, 20, 40]
    frame = np.full((30, 400, 3), [20, 20, 40], dtype=np.int16)

    # White reel bar: columns 150 to 230 [255, 255, 255]
    frame[:, 150:231] = [255, 255, 255]

    # Fish icon: columns 180 to 190 [90, 90, 90]
    frame[:, 180:191] = [90, 90, 90]

    cfg = {
        "region": [0, 0, 400, 30],
        "fish_color": [90, 90, 90],
        "bar_color": [255, 255, 255],
        "bar_color2": None,
        "tolerance": 20,
    }

    # Test measure
    fish_res, bar_res = measure(frame, cfg)
    assert fish_res is not None
    assert bar_res is not None

    fc, bc = centers(fish_res, bar_res)
    # Fish center should be ~185.0
    assert abs(fc - 185.0) <= 1.0, f"Expected fish center ~185, got {fc}"
    # Bar center should be ~190.0 (150 + 230) / 2
    assert abs(bc - 190.0) <= 1.0, f"Expected bar center ~190, got {bc}"

    # Test analyze (used for preview & calibration)
    f_cand, b_cand, fm, bm1, bm2 = analyze(frame, cfg)
    assert f_cand is not None
    assert b_cand is not None
    assert bm2 is None
    assert fm.shape == (30, 400)
    assert bm1.shape == (30, 400)


def test_synthetic_brown_bar_detection():
    frame = np.full((30, 400, 3), [20, 20, 40], dtype=np.int16)
    # Brown bar: columns 100 to 160 [180, 120, 70]
    frame[:, 100:161] = [180, 120, 70]

    cfg = {
        "region": [0, 0, 400, 30],
        "fish_color": [90, 90, 90],
        "bar_color": [255, 255, 255],
        "bar_color2": [180, 120, 70],
        "tolerance": 25,
    }

    fish_res, bar_res = measure(frame, cfg)
    assert fish_res is None  # No fish in this frame
    assert bar_res is not None
    _, bc = centers(fish_res, bar_res)
    assert abs(bc - 130.0) <= 1.0  # (100 + 160) / 2


def test_row_stride():
    assert row_stride([0, 0, 500, 24]) == 1
    assert row_stride([0, 0, 500, 48]) == 2
    assert row_stride([0, 0, 500, 120]) == 5
    assert row_stride([0, 0, 500, 10]) == 1  # max(1, ...)


def test_track_reset_and_expiry():
    track = Track()
    track.update(50.0, 1.0)
    assert track.fresh(1.05) is True
    # Seen 0.20s ago (> max_age 0.15s) -> False
    assert track.fresh(1.25) is False

    # Gap > 0.3s resets velocity to 0
    track.update(100.0, 2.0)
    assert track.v == 0.0

    track.reset()
    assert track.x is None
    assert track.v == 0.0


if __name__ == "__main__":
    test_mock_screen_grabber()
    print("[PASS] test_mock_screen_grabber")
    test_synthetic_minigame_detection()
    print("[PASS] test_synthetic_minigame_detection")
    test_synthetic_brown_bar_detection()
    print("[PASS] test_synthetic_brown_bar_detection")
    test_row_stride()
    print("[PASS] test_row_stride")
    test_track_reset_and_expiry()
    print("[PASS] test_track_reset_and_expiry")
    print("\nAll vision tests passed!")
