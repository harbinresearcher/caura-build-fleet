import pytest

from retry import backoff_delay


def test_backoff_delay_scales_attempts_with_injected_jitter():
    midpoint = lambda low, high: (low + high) / 2

    assert [backoff_delay(5, attempt, jitter=midpoint) for attempt in range(3)] == [5, 10, 20]


def test_backoff_delay_rejects_negative_attempt():
    with pytest.raises(ValueError, match="non-negative"):
        backoff_delay(5, -1)
