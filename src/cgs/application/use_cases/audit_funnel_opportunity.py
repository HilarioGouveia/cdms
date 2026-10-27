"""Caso de uso: Auditoria de Oportunidade de Receita de Funil."""

from decimal import Decimal
from typing import Optional

from cgs.application.ports.growth_repository import GrowthRepositoryPort
from cgs.domain.entities.funnel import FunnelBaseline, FunnelOpportunityAudit
from cgs.domain.services.funnel_analyzer import FunnelOpportunityAnalyzer


class AuditFunnelOpportunityUseCase:
    """Orquestra o cálculo e persistência do diagnóstico de oportunidade de funil."""

    def __init__(self, repository: GrowthRepositoryPort):
        self._repository = repository

    def execute(
        self,
        source_cycle_id: str,
        impressions: int,
        clicks: int,
        conversions: int,
        custom_baseline: Optional[FunnelBaseline] = None,
    ) -> FunnelOpportunityAudit:
        """Executa a auditoria de oportunidade e persiste o resultado."""
        baseline = custom_baseline or self._repository.get_active_baseline()
        if not baseline:
            raise ValueError(
                "Nenhuma linha de base (FunnelBaseline) ativa encontrada. "
                "Cadastre uma baseline antes de rodar a auditoria."
            )

        audit = FunnelOpportunityAnalyzer.calculate_opportunity(
            source_cycle_id=source_cycle_id,
            impressions=impressions,
            clicks=clicks,
            conversions=conversions,
            baseline=baseline,
        )

        return self._repository.save_funnel_audit(audit)