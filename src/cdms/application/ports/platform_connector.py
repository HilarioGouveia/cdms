"""Porta abstrata para conectores de plataformas oficiais de mídia."""

from abc import ABC, abstractmethod
from typing import Dict, Any


class PlatformConnectorPort(ABC):
    @abstractmethod
    def fetch_weekly_metrics(self, account_id: str, cycle_id: str) -> Dict[str, Any]:
        """Consulta métricas canônicas do período diretamente da API da plataforma."""
        pass

    @abstractmethod
    def validate_connection(self, account_id: str) -> bool:
        """Verifica validade de token de acesso e permissões de leitura."""
        pass