from __future__ import annotations

import random
import time
from typing import Callable, TypeVar

T = TypeVar("T")


def retry_with_backoff(
    fn: Callable[[], T],
    retries: int = 5,
    base: float = 0.5,
    max_backoff: float = 30,
    jitter: str = "full",
) -> T:
    """Execute fn with exponential backoff and optional jitter."""
    if retries < 0:
        raise ValueError("retries must be >= 0")

    attempt = 0
    while True:
        try:
            return fn()
        except Exception:
            if attempt >= retries:
                raise

            backoff = min(max_backoff, base * (2 ** attempt))
            if jitter == "full":
                sleep_for = random.random() * backoff
            elif jitter in {"none", "off"}:
                sleep_for = backoff
            else:
                raise ValueError("unsupported jitter strategy")

            time.sleep(max(0.0, sleep_for))
            attempt += 1
