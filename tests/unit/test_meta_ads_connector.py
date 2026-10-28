"""Contratos HTTP do Meta Ads, com respostas locais e sem contas externas."""
from datetime import date
import json
from unittest.mock import Mock

import pytest
import requests
from cdms.adapters.connectors.meta_ads import MetaAdsConnector, closed_week
from cdms.application.ports.platform_connector import PlatformError

TOKEN = "test-only-meta-secret"


def connector(payload, status=200):
    response = Mock(status_code=status)
    response.json.return_value = payload
    session = Mock()
    session.get.return_value = response
    return MetaAdsConnector(TOKEN, session=session, timezone_name="America/Sao_Paulo"), session


def report():
    return {"data": [{"account_id": "123", "account_currency": "USD", "date_start": "2026-10-19",
                      "date_stop": "2026-10-25", "reach": "1500", "impressions": "3000", "inline_link_clicks": "90",
                      "spend": "123.45", "actions": [{"action_type": "offsite_conversion.fb_pixel_purchase", "value": "4"},
                                                       {"action_type": "purchase", "value": "4"},
                                                       {"action_type": "link_click", "value": "90"}]}]}


def test_weekly_account_aggregate_and_non_overlapping_conversion_mapping():
    client, session = connector(report())
    result = client.fetch_weekly_metrics("act_123", "2026-10-19")
    assert result["metrics"] == {"reach": 1500, "impressions": 3000, "clicks": 90, "ctr_pct": 3.0,
                                 "conversions": 4, "avg_retention_pct": None, "spend": "123.45"}
    assert result["currency"] == "USD"  # Não rotular dinheiro da conta como reais.
    assert result["unavailability_reasons"]["avg_retention_pct"] == "NOT_SUPPORTED"
    args, kwargs = session.get.call_args
    assert args[0] == "https://graph.facebook.com/v26.0/act_123/insights"
    assert TOKEN not in args[0] and TOKEN not in json.dumps(kwargs["params"])
    assert kwargs["headers"]["Authorization"] == "Bearer " + TOKEN
    assert kwargs["timeout"] == (5, 30) and kwargs["allow_redirects"] is False
    assert kwargs["params"]["level"] == "account"
    assert kwargs["params"]["time_increment"] == "all_days"
    assert json.loads(kwargs["params"]["time_range"]) == {"since": "2026-10-19", "until": "2026-10-25"}


def test_validate_account_metadata():
    client, _ = connector({"account_id": "123", "currency": "BRL", "timezone_name": "America/Sao_Paulo"})
    assert client.validate_account("act_123") == {"currency": "BRL", "timezone_name": "America/Sao_Paulo"}


@pytest.mark.parametrize("payload,code", [
    ({"account_id": "456", "currency": "BRL", "timezone_name": "UTC"}, "ACCOUNT_MISMATCH"),
    ({"account_id": "123", "currency": "BRL", "timezone_name": "bad/timezone"}, "INVALID_RESPONSE"),
])
def test_reject_inconsistent_account_metadata(payload, code):
    client, _ = connector(payload)
    with pytest.raises(PlatformError, match=code):
        client.validate_account("act_123")


@pytest.mark.parametrize("status,error_code,retryable", [(401,190,False),(403,200,False),(400,4,True),(429,0,True),(503,0,True)])
def test_errors_are_sanitized_and_classified(status, error_code, retryable):
    client, _ = connector({"error": {"code": error_code, "message": TOKEN}}, status)
    with pytest.raises(PlatformError) as caught:
        client.fetch_weekly_metrics("act_123", "2026-10-19")
    assert caught.value.retryable is retryable
    assert TOKEN not in str(caught.value)


def test_transport_timeouts_are_retryable_without_exposing_request():
    client, session = connector({})
    session.get.side_effect = requests.Timeout(TOKEN)
    with pytest.raises(PlatformError) as caught:
        client.fetch_weekly_metrics("act_123", "2026-10-19")
    assert caught.value.retryable
    assert TOKEN not in str(caught.value)


def test_empty_result_does_not_invent_zero_metrics():
    client, _ = connector({"data": []})
    result = client.fetch_weekly_metrics("act_123", "2026-10-19")
    assert all(value is None for value in result["metrics"].values())
    assert result["unavailability_reasons"]["reach"] == "NO_DATA"


def test_zero_impressions_and_absent_conversion_field_are_unavailable():
    payload = report()
    payload["data"][0].update(impressions="0", inline_link_clicks="0")
    del payload["data"][0]["actions"]
    client, _ = connector(payload)
    result = client.fetch_weekly_metrics("act_123", "2026-10-19")
    assert result["metrics"]["conversions"] is None
    assert result["metrics"]["ctr_pct"] is None
    assert result["unavailability_reasons"]["ctr_pct"] == "ZERO_IMPRESSIONS"


@pytest.mark.parametrize("case", ["account", "period", "multiple_rows", "pagination", "negative", "fractional", "nan", "duplicate_action"])
def test_invalid_reports_are_rejected_before_persistence(case):
    payload = report()
    row = payload["data"][0]
    if case == "account": row["account_id"] = "456"
    elif case == "period": row["date_stop"] = "2026-10-24"
    elif case == "multiple_rows": payload["data"].append(dict(row))
    elif case == "pagination": payload["paging"] = {"next": "https://untrusted.example/?access_token=" + TOKEN}
    elif case == "negative": row["reach"] = "-1"
    elif case == "fractional": row["reach"] = "1.5"
    elif case == "nan": row["spend"] = "NaN"
    else: row["actions"].append(dict(row["actions"][0]))
    client, _ = connector(payload)
    with pytest.raises(PlatformError):
        client.fetch_weekly_metrics("act_123", "2026-10-19")


def test_period_and_endpoint_validation():
    assert closed_week("2026-10-19", "UTC", today=date(2026,10,26)) == (date(2026,10,19),date(2026,10,25))
    with pytest.raises(ValueError, match="encerrada"):
        closed_week("2026-10-19", "UTC", today=date(2026,10,25))
    with pytest.raises(ValueError, match="segunda-feira"):
        closed_week("2026-10-20", "UTC")
    client, session = connector({})
    with pytest.raises(ValueError): client.validate_account("https://untrusted.example")
    session.get.assert_not_called()
    with pytest.raises(ValueError): MetaAdsConnector(TOKEN, api_version="../../x")


def test_optional_appsecret_proof_matches_official_sdk_contract():
    import hmac
    import hashlib
    client, session = connector({"account_id": "123", "currency": "BRL", "timezone_name": "UTC"})
    client._app_secret = "test-only-app-secret"
    client.validate_account("act_123")
    params = session.get.call_args.kwargs["params"]
    assert params["appsecret_proof"] == hmac.new(b"test-only-app-secret", TOKEN.encode(), hashlib.sha256).hexdigest()
    assert "test-only-app-secret" not in json.dumps(params)
