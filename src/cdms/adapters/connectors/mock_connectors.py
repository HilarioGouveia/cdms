"""Conectores simulados para Meta Ads e YouTube Data API com contratos de resposta realistas."""

from typing import Dict, Any
from cdms.application.ports.platform_connector import PlatformConnectorPort
from cdms.domain.entities.integrations import PlatformType


class MockMetaAdsConnector(PlatformConnectorPort):
    def fetch_weekly_metrics(self, account_id: str, cycle_id: str) -> Dict[str, Any]:
        return {
            "platform": PlatformType.META_ADS.value,
            "account_id": account_id,
            "cycle_id": cycle_id,
            "reach": 18450,
            "impressions": 25400,
            "clicks": 860,
            "conversions": 34,
            "spend_reais": 540.20,
            "ctr_pct": 3.38,
        }

    def validate_connection(self, account_id: str) -> bool:
        return bool(account_id and not account_id.startswith("invalid_"))


class MockYouTubeStudioConnector(PlatformConnectorPort):
    def fetch_weekly_metrics(self, account_id: str, cycle_id: str) -> Dict[str, Any]:
        return {
            "platform": PlatformType.YOUTUBE_STUDIO.value,
            "account_id": account_id,
            "cycle_id": cycle_id,
            "reach": 14200,
            "impressions": 31000,
            "clicks": 1240,
            "conversions": 48,
            "avg_retention_pct": 42.5,
            "ctr_pct": 4.0,
        }

    def validate_connection(self, account_id: str) -> bool:
        return bool(account_id and not account_id.startswith("invalid_"))