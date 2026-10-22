"""Small statistics helpers (standard library only)."""

from __future__ import annotations

import math
from typing import Iterable, List, Optional, Tuple


def wilson(k: int, n: int, z: float = 1.959964) -> Tuple[float, float]:
    """Wilson score interval for a proportion k/n (95% by default)."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (max(0.0, centre - half), min(1.0, centre + half))


def mean(values: Iterable[float]) -> Optional[float]:
    vals = [v for v in values if v is not None and not (isinstance(v, float) and math.isnan(v))]
    return sum(vals) / len(vals) if vals else None


def quantile(values: Iterable[float], q: float) -> Optional[float]:
    vals: List[float] = sorted(v for v in values if v is not None)
    if not vals:
        return None
    pos = (len(vals) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    return vals[lo] + (vals[hi] - vals[lo]) * (pos - lo)
