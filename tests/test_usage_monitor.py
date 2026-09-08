from datetime import date

import pytest

from views.usage_monitor import _baseline_for_period, _daily_spend, _monthly_totals, normalize_key_info


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


_AUGUST_RESET_HISTORY = [
    {"checked_at": "2026-07-31T17:00:00-03:00", "spend": 53.05},
    {"checked_at": "2026-08-01T09:00:00-03:00", "spend": 53.05},
    {"checked_at": "2026-08-13T14:34:00-03:00", "spend": 151.58},
    {"checked_at": "2026-08-20T18:46:00-03:00", "spend": 0.0},
    {"checked_at": "2026-08-27T09:00:00-03:00", "spend": 22.98},
]


def test_baseline_for_period_uses_the_reset_after_a_mid_month_drop():
    """Same real incident, for the 'Budget this month' / burn-rate baseline
    instead of the monthly chart: a row checked *after* the reset (27/08) must
    use the reset's own post-drop value (0) as its baseline, not July's last
    value (53) — the latter is what made period spend compute negative and
    clamp to 0 for the rest of August, before this fix."""
    daily = _daily_spend(_AUGUST_RESET_HISTORY)

    baseline = _baseline_for_period(daily, date(2026, 8, 1), date(2026, 8, 27))

    assert baseline == pytest.approx(0.0, abs=0.01)


def test_baseline_for_period_ignores_a_reset_that_hasnt_happened_yet():
    """A row checked *before* the reset (13/08) must not borrow the later
    reset's baseline just because it exists somewhere in the full history —
    only resets at or before `as_of` count."""
    daily = _daily_spend(_AUGUST_RESET_HISTORY)

    baseline = _baseline_for_period(daily, date(2026, 8, 1), date(2026, 8, 13))

    assert baseline == pytest.approx(53.05, abs=0.01)


# ── Stale gateway key ────────────────────────────────────────────────────────
# Windows copies environment variables into a process at creation and never
# refreshes them. On 2026-09-08 "Refresh balance" answered 401 because the app
# process still carried a key rotated days earlier; both keys were 25 characters
# starting with "sk-", so nothing looked wrong. The hint is what turns that plain
# "Unauthorized" into something actionable.

def _patch_registry(monkeypatch, stored):
    r"""Stand in for HKCU\Environment without touching the real registry."""
    import types
    fake = types.SimpleNamespace()

    class _Key:
        def __enter__(self): return self
        def __exit__(self, *a): return False

    fake.HKEY_CURRENT_USER = 0
    fake.OpenKey = lambda root, sub: _Key()
    if stored is None:
        fake.QueryValueEx = lambda key, name: (_ for _ in ()).throw(OSError("missing"))
    else:
        fake.QueryValueEx = lambda key, name: (stored, 1)
    monkeypatch.setitem(__import__("sys").modules, "winreg", fake)


def test_hint_fires_when_process_key_differs_from_stored(monkeypatch):
    from views.usage_monitor import _stale_key_hint
    _patch_registry(monkeypatch, "sk-eUXlNEWkeyvaluehere_wsgw")
    hint = _stale_key_hint("sk-GWtyOLDkeyvaluehere_K_lw")
    assert "K_lw" in hint and "wsgw" in hint
    assert "Restart the app" in hint


def test_hint_never_exposes_more_than_the_last_four_characters(monkeypatch):
    from views.usage_monitor import _stale_key_hint
    _patch_registry(monkeypatch, "sk-eUXlNEWkeyvaluehere_wsgw")
    hint = _stale_key_hint("sk-GWtyOLDkeyvaluehere_K_lw")
    assert "sk-GWty" not in hint and "sk-eUXl" not in hint
    assert "OLDkeyvaluehere" not in hint and "NEWkeyvaluehere" not in hint


def test_no_hint_when_keys_agree(monkeypatch):
    from views.usage_monitor import _stale_key_hint
    _patch_registry(monkeypatch, "sk-same")
    assert _stale_key_hint("sk-same") == ""


def test_no_hint_without_a_key_or_registry(monkeypatch):
    from views.usage_monitor import _stale_key_hint
    _patch_registry(monkeypatch, None)
    assert _stale_key_hint(None) == ""
    assert _stale_key_hint("sk-anything") == ""
