"""Caso de uso: Gestão e Priorização do Backlog de Hipóteses."""

from decimal import Decimal
from typing import List, Optional

from cgs.application.ports.growth_repository import GrowthRepositoryPort
from cgs.domain.entities.hypothesis import (
    GrowthHypothesis,
    HypothesisStatus,
    MetricDirection,
    VariableType,
)


class ManageHypothesesUseCase:
    """Gerencia o ciclo de vida, inclusão e listagem de hipóteses prioritárias por ICE."""

    def __init__(self, repository: GrowthRepositoryPort):
        self._repository = repository

    def create_hypothesis(
        self,
        action_description: str,
        tested_variable: VariableType,
        target_metric_key: str,
        target_metric_unit: str,
        metric_direction: MetricDirection,
        baseline_reference_value: Decimal,
        success_metric_target: Decimal,
        invalidation_floor: Decimal,
        expected_impact_description: str,
        impact_score: int,
        confidence_score: int,
        ease_score: int,
        source_cycle_id: Optional[str] = None,
        sample_exposure_minimum: int = 100,
        window_days: int = 7,
    ) -> GrowthHypothesis:
        """Cria e persiste uma hipótese no status BACKLOG com pontuação ICE calculada."""
        hypothesis = GrowthHypothesis(
            id=None,
            source_cycle_id=source_cycle_id,
            target_cycle_id=None,
            promoted_decision_id=None,
            action_description=action_description,
            tested_variable=tested_variable,
            target_metric_key=target_metric_key,
            target_metric_unit=target_metric_unit,
            metric_direction=metric_direction,
            baseline_reference_value=baseline_reference_value,
            success_metric_target=success_metric_target,
            invalidation_floor=invalidation_floor,
            expected_impact_description=expected_impact_description,
            impact_score=impact_score,
            confidence_score=confidence_score,
            ease_score=ease_score,
            sample_exposure_minimum=sample_exposure_minimum,
            window_days=window_days,
            status=HypothesisStatus.BACKLOG,
        )
        return self._repository.save_hypothesis(hypothesis)

    def get_ranked_backlog(self, limit: int = 20) -> List[GrowthHypothesis]:
        """Retorna o backlog priorizado estritamente por ICE score decrescente."""
        return self._repository.list_hypotheses(status=HypothesisStatus.BACKLOG, limit=limit)

    def archive_hypothesis(self, hypothesis_id: int) -> GrowthHypothesis:
        """Move uma hipótese para status ARCHIVED."""
        hypo = self._repository.get_hypothesis_by_id(hypothesis_id)
        if not hypo:
            raise ValueError(f"Hipótese com ID {hypothesis_id} não encontrada.")
        return self._repository.update_hypothesis_status(
            hypothesis_id=hypothesis_id,
            status=HypothesisStatus.ARCHIVED,
        )