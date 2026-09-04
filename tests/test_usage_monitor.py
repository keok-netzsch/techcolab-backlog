import pytest

from views.usage_monitor import _daily_spend, _monthly_totals, normalize_key_info


def test_normalize_key_info_supports_litellm_info_wrapper():
    payload = {
        "info": {
            "spend": 12.5,
            "max_budget": 50,
            "budget_reset_at": "2026-08-01T00:00:00Z",
            "rpm_limit": 100,
            "tpm_limit": 500000,
        }
    }

    result = normalize_key_info(payload)

    assert result["spend"] == 12.5
    assert result["max_budget"] == 50
    assert result["budget_reset_at"] == "2026-08-01T00:00:00Z"
    assert result["rpm_limit"] == 100
    assert result["tpm_limit"] == 500000


def test_monthly_totals_survives_a_mid_month_reset():
    """Regression for the real August 2026 incident: NBS reset the key mid-month
    (after it blew past budget) instead of on the 1st as usually communicated. The
    old algorithm diffed each month's last recorded `spend` against the previous
    month's last value — August's last value (23) minus July's (53) went negative,
    floored to 0, and silently erased the ~$98 actually spent before the reset."""
    history = [
        {"checked_at": "2026-07-31T17:00:00-03:00", "spend": 53.05},
        {"checked_at": "2026-08-01T09:00:00-03:00", "spend": 53.05},
        {"checked_at": "2026-08-13T14:34:00-03:00", "spend": 151.58},
        {"checked_at": "2026-08-20T18:46:00-03:00", "spend": 0.0},
        {"checked_at": "2026-08-31T17:00:00-03:00", "spend": 22.98},
    ]

    monthly = _monthly_totals(_daily_spend(history))
    august_total = monthly.loc[monthly["month"].astype(str) == "2026-08-01", "total"].iloc[0]

    assert august_total == pytest.approx(151.58 - 53.05 + 22.98, abs=0.01)
