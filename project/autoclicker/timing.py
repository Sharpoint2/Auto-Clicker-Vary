from __future__ import annotations

import math
import random


def next_interval(base_seconds: float, variation_percent: float, rng: random.Random | None = None) -> float:
    if not math.isfinite(base_seconds) or base_seconds <= 0:
        raise ValueError("Base interval must be greater than zero")
    if not math.isfinite(variation_percent) or not 0 <= variation_percent <= 100:
        raise ValueError("Variation must be between 0 and 100")

    generator = rng or random
    spread = base_seconds * variation_percent / 100
    if spread == 0:
        return base_seconds

    offset = generator.triangular(-spread, spread, 0)
    return max(0.001, base_seconds + offset)
