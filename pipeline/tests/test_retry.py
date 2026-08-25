from retry import MAX_ATTEMPTS, MEMCLAW_MAX_ATTEMPTS, backoff_delay


def test_backoff_delay_scales_attempts_with_injected_jitter():
    def midpoint(low, high):
        return (low + high) / 2

    assert [backoff_delay(5, attempt, jitter=midpoint) for attempt in range(3)] == [5, 10, 20]


def test_retry_budgets_are_service_specific():
    assert MAX_ATTEMPTS == 4
    assert MEMCLAW_MAX_ATTEMPTS == 3
