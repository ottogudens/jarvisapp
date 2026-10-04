import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from backend.trial_policy import trial_snapshot


class TrialPolicyTests(unittest.TestCase):
    def test_active_trial_reports_remaining_daily_tokens(self):
        tenant = SimpleNamespace(is_trial=True, trial_ends_at=datetime.now(timezone.utc) + timedelta(days=1), trial_daily_token_limit=5000)
        snapshot = trial_snapshot(tenant, 1200)
        self.assertTrue(snapshot["trial_active"])
        self.assertEqual(snapshot["daily_tokens_remaining"], 3800)

    def test_expired_trial_is_not_active(self):
        tenant = SimpleNamespace(is_trial=True, trial_ends_at=datetime.now(timezone.utc) - timedelta(seconds=1), trial_daily_token_limit=5000)
        self.assertFalse(trial_snapshot(tenant, 0)["trial_active"])

    def test_paid_tenant_has_no_trial_daily_limit(self):
        tenant = SimpleNamespace(is_trial=False, trial_ends_at=None, trial_daily_token_limit=0)
        self.assertIsNone(trial_snapshot(tenant, 0)["daily_tokens_remaining"])


if __name__ == "__main__":
    unittest.main()
