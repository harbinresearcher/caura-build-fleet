"""Shared exponential backoff policy for external service retries."""

import random
from collections.abc import Callable

MAX_ATTEMPTS = 4
MEMCLAW_MAX_ATTEMPTS = 3
LLM_RATE_LIMIT_BASE_SECONDS = 20
LLM_CONNECTION_BASE_SECONDS = 10
MEMCLAW_BASE_SECONDS = 5


def backoff_delay(
    base_seconds: float,
    attempt: int,
    *,
    jitter: Callable[[float, float], float] = random.uniform,
) -> float:
    """Return exponential backoff with multiplicative jitter."""
    return base_seconds * (2**attempt) * jitter(0.8, 1.2)
