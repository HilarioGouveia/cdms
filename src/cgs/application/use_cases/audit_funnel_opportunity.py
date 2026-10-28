"""Caso de uso: Auditoria de Oportunidade de Receita de Funil."""

from typing import List, Optional

from cgs.application.ports.growth_repository import GrowthRepositoryPort
from cgs.domain.entities.funnel import ConversionType, FunnelBaseline, FunnelOpportunityAudit
from cgs.domain.services.funnel_analyzer import FunnelOpportunityAnalyzer


class AuditFunnelOpportunityUseCase:
    """Orquestra a validação, cálculo e recuperação do diagnóstico de oportunidade de funil."""

    def __init__(self, repository: GrowthRepositoryPort):
        self._repository = repository

    def execute(
        self,
        source_cycle_id: str,
        impressions: int,
        clicks: int,
        conversions: int,
        leads: Optional[int] = None,
        custom_baseline: Optional[FunnelBaseline] = None,
    ) -> FunnelOpportunityAudit:
        """Executa a auditoria de oportunidade e persiste o resultado."""
        baseline = custom_baseline or self._repository.get_active_baseline()
        if not baseline:
            raise ValueError(
                "Nenhuma linha de base (FunnelBaseline) ativa encontrada. "
                "Cadastre uma baseline antes de rodar a auditoria."
            )

        # Validações de integridade dos dados observados
        for name, val in [
            ("impressions", impressions),
            ("clicks", clicks),
            ("conversions", conversions),
        ]:
            if isinstance(val, bool) or not isinstance(val, int) or val < 0:
                raise ValueError(f"{name} deve ser um número inteiro maior ou igual a zero.")

        # Validação estrita para modelo de funil de dois passos (LEAD)
        if baseline.conversion_type == ConversionType.LEAD:
            if leads is None:
                raise ValueError("O parâmetro 'leads' é obrigatório para funis do tipo LEAD.")
            if isinstance(leads, bool) or not isinstance(leads, int) or leads < 0:
                raise ValueError("leads deve ser um número inteiro maior ou igual a zero.")
            if conversions > leads:
                raise ValueError(
                    f"Inconsistência operacional: conversões ({conversions}) não podem superar leads captados ({leads})."
                )

        if clicks > impressions:
            raise ValueError(
                f"Inconsistência operacional: cliques ({clicks}) não podem superar impressões ({impressions})."
            )

        audit = FunnelOpportunityAnalyzer.calculate_opportunity(
            source_cycle_id=source_cycle_id,
            impressions=impressions,
            clicks=clicks,
            conversions=conversions,
            leads=leads,
            baseline=baseline,
        )

        return self._repository.save_funnel_audit(audit)

    def get_audit_history(self, limit: int = 50) -> List[FunnelOpportunityAudit]:
        """Recupera o histórico cronológico de auditorias gravadas."""
        return self._repository.list_funnel_audits(limit=limit)