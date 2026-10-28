"""Caso de uso: Gestão e Priorização do Backlog de Hipóteses."""

from decimal import Decimal
from typing import List, Optional

from cgs.application.ports.growth_repository import GrowthRepositoryPort
from cgs.domain.entities.hypothesis import (
    ConflictingActiveVariableError,
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
        """Cria e persiste uma hipótese no status PENDING com pontuação ICE calculada."""
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
            status=HypothesisStatus.PENDING,
        )
        return self._repository.save_hypothesis(hypothesis)

    def get_ranked_backlog(self, limit: int = 20) -> List[GrowthHypothesis]:
        """Retorna as hipóteses pendentes priorizadas estritamente por ICE score decrescente."""
        return self._repository.list_hypotheses(status=HypothesisStatus.PENDING, limit=limit)

    def list_by_status(self, status: HypothesisStatus, limit: int = 50) -> List[GrowthHypothesis]:
        """Lista hipóteses por qualquer status do ciclo de vida."""
        return self._repository.list_hypotheses(status=status, limit=limit)

    def activate_hypothesis(
        self,
        hypothesis_id: int,
        target_cycle_id: Optional[str] = None,
        promoted_decision_id: Optional[int] = None,
    ) -> GrowthHypothesis:
        """Aplica a regra de variável única e ativa uma hipótese para teste operacional no ciclo."""
        hypo = self._repository.get_hypothesis_by_id(hypothesis_id)
        if not hypo:
            raise ValueError(f"Hipótese com ID {hypothesis_id} não encontrada.")

        # Validação de isolamento causal: verificar se já existe hipótese ACTIVE testando a mesma variável
        conflicting_hypo = self._repository.get_active_hypothesis_by_variable(
            tested_variable=hypo.tested_variable,
            target_cycle_id=target_cycle_id,
        )
        if conflicting_hypo and conflicting_hypo.id != hypo.id:
            raise ConflictingActiveVariableError(
                variable=hypo.tested_variable,
                target_cycle_id=target_cycle_id,
                active_hypothesis_id=conflicting_hypo.id,
            )

        hypo.activate(target_cycle_id=target_cycle_id, promoted_decision_id=promoted_decision_id)
        return self._repository.update_hypothesis_status(
            hypothesis_id=hypothesis_id,
            status=hypo.status,
            target_cycle_id=hypo.target_cycle_id,
            promoted_decision_id=hypo.promoted_decision_id,
        )

    def complete_hypothesis(self, hypothesis_id: int) -> GrowthHypothesis:
        """Aplica regra de negócio e conclui uma hipótese após auditoria do ciclo."""
        hypo = self._repository.get_hypothesis_by_id(hypothesis_id)
        if not hypo:
            raise ValueError(f"Hipótese com ID {hypothesis_id} não encontrada.")
        hypo.complete()
        return self._repository.update_hypothesis_status(
            hypothesis_id=hypothesis_id,
            status=hypo.status,
        )

    def discard_hypothesis(self, hypothesis_id: int) -> GrowthHypothesis:
        """Aplica regra de negócio e descarta/invalida uma hipótese."""
        hypo = self._repository.get_hypothesis_by_id(hypothesis_id)
        if not hypo:
            raise ValueError(f"Hipótese com ID {hypothesis_id} não encontrada.")
        hypo.discard()
        return self._repository.update_hypothesis_status(
            hypothesis_id=hypothesis_id,
            status=hypo.status,
        )