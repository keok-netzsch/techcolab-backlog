from views.usage_monitor import normalize_key_info


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
