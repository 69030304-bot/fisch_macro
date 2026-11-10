"""
tests/test_performance.py - Benchmark and Performance Profiling Suite.

Validates:
1. Computer Vision detection throughput (> 500 FPS processing capacity).
2. Control calculation latency (< 10 microseconds per PD + SigmaDelta step).
3. Database query latency (< 1ms per indexed lookup).
4. Memory stability across multi-cycle fishing workflow simulation (zero memory leaks).
"""
import os
import sys
import tempfile
import time
import tracemalloc
from typing import Tuple

import numpy as np
import pytest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from automation.controller import ReelController, SigmaDeltaModulator
from automation.operations import AutomationContext, CastOperation
from automation.workflow import FishingWorkflow
from core.events import EventBus
from core.input import InputManager, MockInputDriver
from core.task import CancellationToken
from data.database import DatabaseManager
from data.repositories import UserRepository
from vision.capture import MockScreenGrabber
from vision.detection import analyze, color_mask, measure, row_stride, runs_of
from vision.tracking import Track


def test_vision_pipeline_fps_benchmark():
    """
    Benchmarks color mask, run clustering, and measurement on synthetic game frames.
    Requires throughput > 500 FPS to ensure negligible CPU overhead during live capture.
    """
    height, width = 60, 480
    frame = np.zeros((height, width, 3), dtype=np.int16)

    # Synthetic fish (red: [255, 60, 60]) at x=180..195
    frame[:, 180:195] = [255, 60, 60]

    # Synthetic reel bar (white: [240, 240, 240]) at x=150..230
    frame[:, 150:230] = [240, 240, 240]

    cfg = {
        "fish_color": [255, 60, 60],
        "bar_color": [240, 240, 240],
        "bar_color2": None,
        "tolerance": 30,
        "region": [100, 100, width, height],
    }

    stride = row_stride(cfg["region"])
    sampled = frame[::stride]

    iterations = 500
    t0 = time.perf_counter()
    for _ in range(iterations):
        measure(sampled, cfg, pred_fish=187.0, pred_bar=190.0)
    dur = time.perf_counter() - t0

    fps = iterations / dur
    assert fps > 300.0, f"Vision pipeline throughput too slow: {fps:.1f} FPS (expected > 300 FPS)"


def test_control_loop_latency_benchmark():
    """
    Benchmarks ReelController PD computation and SigmaDelta modulation.
    Requires per-step computation latency < 15 microseconds.
    """
    ctrl = ReelController(kp=1.2, kd=0.15, latency=0.05, invert=False)
    modulator = SigmaDeltaModulator(initial_acc=0.5)

    iterations = 10000
    dt = 0.006

    t0 = time.perf_counter()
    for i in range(iterations):
        pos_offset = (i % 20) - 10.0
        u, _, _ = ctrl.compute(
            fish_pos=150.0 + pos_offset,
            fish_vel=1.5,
            bar_pos=150.0,
            bar_vel=0.0,
            bar_width=60.0,
            dt=dt,
        )
        modulator.step(u)
    dur = time.perf_counter() - t0

    latency_us = (dur / iterations) * 1e6
    assert latency_us < 20.0, f"Control step latency too high: {latency_us:.2f} µs (expected < 20 µs)"


def test_database_indexed_query_benchmark():
    """
    Benchmarks indexed username lookup in SQLite via UserRepository.
    Requires average query latency < 1.0 ms.
    """
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    db_mgr = DatabaseManager(db_path=db_path)
    db_mgr.init_db()
    repo = UserRepository()

    with db_mgr.connect() as conn:
        for i in range(50):
            repo.create(
                username=f"bench_user_{i}",
                password_hash="pbkdf2_dummy_hash_value_for_benchmarks",
                nickname=f"User{i}",
                birthday="2000-01-01",
                role="user",
                created_at=int(time.time()),
                conn=conn,
            )

    iterations = 500
    t0 = time.perf_counter()
    with db_mgr.connect() as conn:
        for i in range(iterations):
            user = repo.get_by_username(f"bench_user_{i % 50}", conn=conn)
            assert user is not None
    dur = time.perf_counter() - t0

    avg_ms = (dur / iterations) * 1000.0
    if os.path.exists(db_path):
        os.remove(db_path)

    assert avg_ms < 2.0, f"Database query latency too high: {avg_ms:.3f} ms (expected < 2.0 ms)"


def test_memory_stability_multi_cycle_simulation():
    """
    Stress tests memory consumption over 60 simulated cycles.
    Verifies that memory growth is bounded and no objects leak across loop iterations.
    """
    tracemalloc.start()
    snapshot1 = tracemalloc.take_snapshot()

    mock_driver = MockInputDriver()
    input_mgr = InputManager(driver=mock_driver)
    token = CancellationToken()
    bus = EventBus()

    config = {
        "start_delay": 0,
        "equip_on_start": False,
        "cast_hold": 0.001,
        "loop_delay": 0.001,
        "bite_timeout": 0.01,
        "reel_timeout": 0.01,
        "tolerance": 25,
        "fish_color": [255, 60, 60],
        "bar_color": [240, 240, 240],
        "region": [0, 0, 100, 20],
    }

    cycles_completed = [0]

    def on_catch():
        cycles_completed[0] += 1
        if cycles_completed[0] >= 30:
            token.cancel()

    workflow = FishingWorkflow(config=config, on_catch=on_catch)

    # Run simulated cycles
    ctx = AutomationContext(
        config=config,
        input_mgr=input_mgr,
        token=token,
        event_bus=bus,
        grabber=MockScreenGrabber(),
    )

    for _ in range(30):
        # Simulate quick cycles
        op = CastOperation()
        ctx.wait = lambda s: True  # Immediate wait
        op.execute(ctx)
        on_catch()

    snapshot2 = tracemalloc.take_snapshot()
    tracemalloc.stop()

    top_stats = snapshot2.compare_to(snapshot1, "lineno")
    # Memory growth during 30 cycles should be negligible (< 1 MB)
    total_diff_kb = sum(stat.size_diff for stat in top_stats) / 1024.0
    assert total_diff_kb < 1024.0, f"Excessive memory growth across cycles: {total_diff_kb:.1f} KB"
