"""Uzbek TIN (ИНН) generator.

Per swagger examples (Manzil API), TIN is a 12-digit numeric string starting
with `200` (e.g. `200123456789`, `200987654321`). The real registry algorithm
includes a checksum, but the dev backend's validation rules are not yet
documented — see open question #4.

Strategy:
- If `tin_checksum=False` (default), produce a 12-digit string with the `200`
  prefix and 9 random digits. The dev backend currently accepts this.
- If/when backend confirms the checksum, implement the algorithm here gated by
  the same `tin_checksum` flag, so existing callers don't need to change.
"""

from __future__ import annotations

import os
import random
import time

_RNG = random.Random(time.time_ns() ^ (os.getpid() << 32))


def generate_tin(*, with_checksum: bool = False, seed: int | None = None) -> str:
    """Return a 12-digit Uzbek TIN.

    `seed` lets a test pin a deterministic value when reproducibility matters
    (e.g. asserting collision behaviour on /api/v1/auth/web/registrations/*).
    """
    rng = random.Random(seed) if seed is not None else _RNG
    body = "".join(str(rng.randint(0, 9)) for _ in range(9))
    tin = f"200{body}"
    if with_checksum:
        # TODO(open-question-4): real checksum algorithm. For now tin_checksum=True
        # is rejected so callers don't silently get a non-validated value.
        raise NotImplementedError(
            "TIN checksum algorithm is not yet specified — see open question #4.",
        )
    return tin
