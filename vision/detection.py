"""
vision/detection.py - Computer vision routines for color segmentation, clustering, and detection.
"""
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

BAR_GAP = 60   # Maximum pixel gap allowed within the bar cluster (when fish/icons occlude the bar)
FISH_GAP = 2   # Maximum pixel gap allowed within the fish cluster


def color_mask(arr: np.ndarray, color: List[int], tol: int) -> np.ndarray:
    """Returns a boolean 2D mask where pixel RGB values are within tolerance of color."""
    target = np.array(color, dtype=np.int16)
    return np.all(np.abs(arr - target) <= tol, axis=2)


def runs_of(mask: np.ndarray, gap: int) -> List[Tuple[int, int, float, int, int]]:
    """
    Groups matching pixel columns into horizontal clusters.
    Returns list of: (left_col, right_col, center_of_mass, total_weight, col_count)
    """
    counts = mask.sum(axis=0)
    cols = np.nonzero(counts)[0]
    if cols.size == 0:
        return []
    out = []
    # Split where distance between adjacent columns exceeds gap + 1
    for g in np.split(cols, np.nonzero(np.diff(cols) > gap + 1)[0] + 1):
        w = counts[g]
        total_w = int(w.sum())
        if total_w == 0:
            continue
        center = float((g * w).sum() / total_w)
        out.append((int(g[0]), int(g[-1]), center, total_w, int(g.size)))
    return out


def choose(
    runs: List[Tuple[int, int, float, int, int]],
    pred: Optional[float],
    min_cols: int = 3,
) -> Optional[Tuple[int, int, float, int, int]]:
    """
    Filters small clusters and selects the best candidate:
    - If pred is None: picks the largest / heaviest cluster.
    - If pred is provided: picks the candidate closest to the predicted coordinate.
    """
    candidates = [r for r in runs if r[4] >= min_cols]
    if not candidates:
        return None
    max_w = max(r[3] for r in candidates)
    # Consider clusters having at least 40% of the maximum weight
    plausible = [r for r in candidates if r[3] >= 0.4 * max_w]
    if not plausible:
        return max(candidates, key=lambda r: r[3])
    if pred is None:
        return max(plausible, key=lambda r: r[3])
    return min(plausible, key=lambda r: abs(r[2] - pred))


def analyze(
    arr: np.ndarray,
    cfg: Dict[str, Any],
    tol: Optional[int] = None,
) -> Tuple[Optional[Tuple], Optional[Tuple], np.ndarray, np.ndarray, Optional[np.ndarray]]:
    """
    Used for calibration and preview:
    Returns (fish_cluster, bar_cluster, fish_mask, bar_mask_white, bar_mask_brown).
    """
    tolerance = cfg["tolerance"] if tol is None else tol
    fm = color_mask(arr, cfg["fish_color"], tolerance)
    bm1 = color_mask(arr, cfg["bar_color"], tolerance)
    bm2 = color_mask(arr, cfg["bar_color2"], tolerance) if cfg.get("bar_color2") else None
    bm = (bm1 | bm2) if bm2 is not None else bm1
    fish_cand = choose(runs_of(fm, FISH_GAP), None)
    bar_cand = choose(runs_of(bm, BAR_GAP), None)
    return fish_cand, bar_cand, fm, bm1, bm2


def measure(
    arr: np.ndarray,
    cfg: Dict[str, Any],
    pred_fish: Optional[float] = None,
    pred_bar: Optional[float] = None,
) -> Tuple[Optional[Tuple], Optional[Tuple]]:
    """
    Used in macro reel loop:
    Measures fish and bar clusters using forward-projected position hints.
    """
    tol = cfg["tolerance"]
    fm = color_mask(arr, cfg["fish_color"], tol)
    bm = color_mask(arr, cfg["bar_color"], tol)
    if cfg.get("bar_color2"):
        bm |= color_mask(arr, cfg["bar_color2"], tol)
    return (
        choose(runs_of(fm, FISH_GAP), pred_fish),
        choose(runs_of(bm, BAR_GAP), pred_bar),
    )


def centers(f: Optional[Tuple], b: Optional[Tuple]) -> Tuple[Optional[float], Optional[float]]:
    """Extracts horizontal centers: fish center of mass, and bar geometric midpoint."""
    fish_center = f[2] if f else None
    bar_center = (b[0] + b[1]) / 2.0 if b else None
    return fish_center, bar_center


def row_stride(region: List[int]) -> int:
    """Calculates row stride sampling based on region height to optimize capture bandwidth."""
    return max(1, region[3] // 24)


def detect(cfg: Dict[str, Any], grabber: Any) -> Tuple[Optional[float], Optional[float]]:
    """Captures the configured region and detects fish and bar center positions."""
    arr = grabber.grab(cfg["region"], row_stride(cfg["region"]))
    f, b = measure(arr, cfg)
    return centers(f, b)
