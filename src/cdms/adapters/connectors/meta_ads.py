"""Adaptador HTTP de leitura da Meta Marketing API, sem credenciais em URLs."""
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
import json
import hashlib
import hmac
import re
from zoneinfo import ZoneInfo

import requests
from cdms.application.ports.platform_connector import PlatformConnectorPort, PlatformError


def closed_week(cycle_id, timezone_name, today=None):
    start = date.fromisoformat(cycle_id)
    if start.weekday() != 0:
        raise ValueError("O ciclo deve começar numa segunda-feira.")
    end = start + timedelta(days=6)
    current = today or datetime.now(ZoneInfo(timezone_name)).date()
    if end >= current:
        raise ValueError("A sincronização exige uma semana completa, já encerrada no fuso da conta.")
    return start, end


def number(value, *, integer=False):
    try:
        result = Decimal(str(value))
        if not result.is_finite() or result < 0 or (integer and result != result.to_integral_value()):
            raise ValueError
        return int(result) if integer else result
    except (ValueError, InvalidOperation, TypeError):
        raise PlatformError("INVALID_RESPONSE") from None


class MetaAdsConnector(PlatformConnectorPort):
    def __init__(self, access_token, *, api_version="v26.0", timezone_name="UTC",
                 conversion_action_type="offsite_conversion.fb_pixel_purchase", session=None, app_secret=None):
        if not re.fullmatch(r"v[0-9]{1,3}\.[0-9]{1,2}", api_version):
            raise ValueError("Versão da API Meta inválida.")
        if not re.fullmatch(r"[A-Za-z0-9_.]{1,200}", conversion_action_type):
            raise ValueError("Tipo de evento de conversão inválido.")
        self._token = access_token
        self._app_secret = app_secret
        self.api_version = api_version
        self.timezone_name = timezone_name
        self.conversion_action_type = conversion_action_type
        self.session = session

    @staticmethod
    def account_id(value):
        if not re.fullmatch(r"act_[0-9]{1,32}", value):
            raise ValueError("Use o ID da conta no formato act_123456.")
        return value

    def _get(self, account_id, suffix="", params=None):
        account_id = self.account_id(account_id)
        url = f"https://graph.facebook.com/{self.api_version}/{account_id}{suffix}"
        params = dict(params or {})
        if self._app_secret:
            params["appsecret_proof"] = hmac.new(self._app_secret.encode("utf-8"), self._token.encode("utf-8"), hashlib.sha256).hexdigest()
        try:
            # Não seguir URLs de paginação ou redirects que poderiam receber o token.
            request = self.session.get if self.session else requests.get
            response = request(url, params=params or {}, headers={"Authorization": f"Bearer {self._token}"},
                               timeout=(5, 30), allow_redirects=False)
        except (requests.Timeout, requests.ConnectionError):
            raise PlatformError("PLATFORM_UNAVAILABLE", retryable=True) from None
        except requests.RequestException:
            raise PlatformError("PLATFORM_REQUEST_FAILED") from None
        try:
            payload = response.json()
        except (ValueError, TypeError):
            if response.status_code == 429 or response.status_code >= 500:
                raise PlatformError("PLATFORM_UNAVAILABLE", retryable=True) from None
            raise PlatformError("INVALID_RESPONSE") from None
        if not isinstance(payload, dict):
            raise PlatformError("INVALID_RESPONSE")
        error = payload.get("error")
        if error or response.status_code >= 300:
            code = error.get("code") if isinstance(error, dict) else None
            if response.status_code == 429 or response.status_code >= 500 or code in (1, 2, 4, 17, 32, 613) or (isinstance(error, dict) and error.get("is_transient") is True):
                raise PlatformError("PLATFORM_UNAVAILABLE", retryable=True)
            if response.status_code in (401, 403) or code in (10, 190, 200):
                raise PlatformError("PLATFORM_ACCESS_DENIED")
            raise PlatformError("PLATFORM_REQUEST_FAILED")
        return payload

    def validate_account(self, account_id):
        result = self._get(account_id, params={"fields": "account_id,currency,timezone_name,account_status"})
        if str(result.get("account_id")) != account_id.removeprefix("act_"):
            raise PlatformError("ACCOUNT_MISMATCH")
        timezone_name = result.get("timezone_name")
        currency = result.get("currency")
        try:
            ZoneInfo(timezone_name)
        except (KeyError, TypeError, ValueError):
            raise PlatformError("INVALID_RESPONSE") from None
        if not isinstance(currency, str) or not re.fullmatch(r"[A-Z]{3}", currency):
            raise PlatformError("INVALID_RESPONSE")
        return {"timezone_name": timezone_name, "currency": currency}

    def validate_connection(self, account_id):
        self.validate_account(account_id)
        return True

    def fetch_weekly_metrics(self, account_id, cycle_id):
        start, end = closed_week(cycle_id, self.timezone_name)
        payload = self._get(account_id, "/insights", {
            "fields": "account_id,account_currency,date_start,date_stop,reach,impressions,inline_link_clicks,spend,actions",
            "level": "account", "time_increment": "all_days", "limit": 1,
            "time_range": json.dumps({"since": start.isoformat(), "until": end.isoformat()}),
            "use_account_attribution_setting": "true",
        })
        rows = payload.get("data")
        if not isinstance(rows, list) or len(rows) > 1:
            raise PlatformError("INVALID_RESPONSE")
        paging = payload.get("paging") or {}
        if not isinstance(paging, dict):
            raise PlatformError("INVALID_RESPONSE")
        if paging.get("next"):
            raise PlatformError("UNEXPECTED_PAGINATION")
        metrics = {key: None for key in ("reach", "impressions", "clicks", "ctr_pct", "conversions", "avg_retention_pct", "spend")}
        reasons = {"avg_retention_pct": "NOT_SUPPORTED"}
        if rows:
            row = rows[0]
            if not isinstance(row, dict) or row.get("account_id") != account_id.removeprefix("act_"):
                raise PlatformError("ACCOUNT_MISMATCH")
            if row.get("date_start") != start.isoformat() or row.get("date_stop") != end.isoformat():
                raise PlatformError("PERIOD_MISMATCH")
            currency = row.get("account_currency")
            if not isinstance(currency, str) or not re.fullmatch(r"[A-Z]{3}", currency):
                raise PlatformError("INVALID_RESPONSE")
            for field, target in (("reach", "reach"), ("impressions", "impressions"), ("inline_link_clicks", "clicks")):
                if field in row:
                    metrics[target] = number(row[field], integer=True)
            if "spend" in row:
                metrics["spend"] = str(number(row["spend"]))
            if metrics["impressions"] and metrics["clicks"] is not None:
                metrics["ctr_pct"] = float((Decimal(metrics["clicks"]) * 100 / Decimal(metrics["impressions"])).quantize(Decimal("0.000001")))
            if "actions" in row:
                if not isinstance(row["actions"], list):
                    raise PlatformError("INVALID_RESPONSE")
                selected = []
                for action in row["actions"]:
                    if not isinstance(action, dict):
                        raise PlatformError("INVALID_RESPONSE")
                    if action.get("action_type") == self.conversion_action_type:
                        selected.append(number(action.get("value"), integer=True))
                if len(selected) > 1:
                    raise PlatformError("INVALID_RESPONSE")
                metrics["conversions"] = selected[0] if selected else 0
            # Persiste somente campos permitidos; descarta paging, URLs e erros da plataforma.
            raw = {key: row[key] for key in ("account_id", "account_currency", "date_start", "date_stop", "reach", "impressions", "inline_link_clicks", "spend") if key in row}
            raw["selected_conversion_action"] = {"action_type": self.conversion_action_type, "value": metrics["conversions"]}
        else:
            currency, raw = None, {}
        for key, value in metrics.items():
            if value is None and key not in reasons:
                reasons[key] = "ZERO_IMPRESSIONS" if key == "ctr_pct" and metrics["impressions"] == 0 else ("NO_DATA" if not rows else "NOT_RETURNED")
        return {"platform": "META_ADS", "account_id": account_id, "cycle_id": cycle_id,
                "period_start": start.isoformat(), "period_end": end.isoformat(), "timezone_name": self.timezone_name,
                "currency": currency, "api_version": self.api_version, "conversion_action_type": self.conversion_action_type,
                "click_definition": "inline_link_clicks", "attribution": "account_setting", "metrics": metrics, "unavailability_reasons": reasons, "raw": raw}
