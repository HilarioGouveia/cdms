"""Caso de uso: Preparação de Proposta de Decisão Única para o CDMS."""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

from cgs.application.ports.growth_repository import GrowthRepositoryPort
from cgs.domain.entities.hypothesis import GrowthHypothesis, HypothesisStatus


@dataclass(frozen=True)
class CDMSDecisionProposal:
    """Estrutura desacoplada compatível com o formulário de Decisão Única do CDMS."""
    hypothesis_id: int
    target_cycle_id: str
    action_summary: str
    formal_hypothesis: str
    success_criterion: str
    evaluation_due_date: date
    owner: str = "Creator"


class PrepareCDMSProposalUseCase:
    """Prepara a hipótese vencedora do CGS para submissão no formulário do CDMS."""

    def __init__(self, repository: GrowthRepositoryPort):
        self._repository = repository

    def execute(
        self,
        hypothesis_id: int,
        target_cycle_date: date,
        owner: str = "Creator",
    ) -> CDMSDecisionProposal:
        """Valida e monta a proposta formal para o próximo ritual do CDMS."""
        hypo = self._repository.get_hypothesis_by_id(hypothesis_id)
        if not hypo:
            raise ValueError(f"Hipótese com ID {hypothesis_id} não encontrada.")

        if hypo.status not in (HypothesisStatus.BACKLOG, HypothesisStatus.PROPOSED):
            raise ValueError(
                f"Apenas hipóteses em BACKLOG ou PROPOSED podem ser promovidas. "
                f"Status atual: {hypo.status.value}."
            )

        target_cycle_id = target_cycle_date.isoformat()
        evaluation_due_date = target_cycle_date + timedelta(days=hypo.window_days)

        formal_hypothesis = (
            f"Se isolarmos a variável [{hypo.tested_variable.value}] com a ação: '{hypo.action_description}', "
            f"então a métrica [{hypo.target_metric_key}] deve atingir a meta de {hypo.success_metric_target}{hypo.target_metric_unit} "
            f"(Piso de invalidação: {hypo.invalidation_floor}{hypo.target_metric_unit}) na janela de {hypo.window_days} dias."
        )

        success_criterion = (
            f"Meta atingida se {hypo.target_metric_key} >= {hypo.success_metric_target}{hypo.target_metric_unit} "
            f"com no mínimo {hypo.sample_exposure_minimum} exposições. "
            f"Invalidação se < {hypo.invalidation_floor}{hypo.target_metric_unit}."
            if hypo.metric_direction.value == "HIGHER_IS_BETTER"
            else f"Meta atingida se {hypo.target_metric_key} <= {hypo.success_metric_target}{hypo.target_metric_unit}. "
                 f"Invalidação se > {hypo.invalidation_floor}{hypo.target_metric_unit}."
        )

        self._repository.update_hypothesis_status(
            hypothesis_id=hypothesis_id,
            status=HypothesisStatus.PROPOSED,
            target_cycle_id=target_cycle_id,
        )

        return CDMSDecisionProposal(
            hypothesis_id=hypo.id or hypothesis_id,
            target_cycle_id=target_cycle_id,
            action_summary=hypo.action_description,
            formal_hypothesis=formal_hypothesis,
            success_criterion=success_criterion,
            evaluation_due_date=evaluation_due_date,
            owner=owner,
        )

    def confirm_promotion(
        self,
        hypothesis_id: int,
        persisted_decision_id: int,
    ) -> GrowthHypothesis:
        """Transiciona a hipótese para ACTIVE após confirmação de persistência no CDMS."""
        return self._repository.update_hypothesis_status(
            hypothesis_id=hypothesis_id,
            status=HypothesisStatus.ACTIVE,
            promoted_decision_id=persisted_decision_id,
        )