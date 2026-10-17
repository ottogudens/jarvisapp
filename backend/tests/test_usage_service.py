from backend.usage_service import resolved_token_usage


def test_resolved_token_usage_prefers_recorded_usage_when_legacy_counter_is_stale():
    assert resolved_token_usage(0, 7473) == 7473


def test_resolved_token_usage_does_not_double_count_mirrored_counters():
    assert resolved_token_usage(42520, 294880) == 294880
