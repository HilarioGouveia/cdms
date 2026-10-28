"""Prepara uma proposta CGS; a decisão real nasce no fechamento do ritual CDMS."""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from cgs.application.ports.growth_repository import GrowthRepositoryPort
from cgs.domain.entities.hypothesis import (
    ConflictingActiveVariableError, GrowthHypothesis, HypothesisStatus,
)


@dataclass(frozen=True)
class CDMSProposalResult:
    hypothesis_id: int
    target_cycle_id: str
    formal_hypothesis: str
    variable_tested: str
    target_metric: str
    success_target: Decimal
    invalidation_floor: Decimal


class PrepareCDMSProposalUseCase:
    """Reserva o ciclo da proposta sem criar decisões incompletas ou IDs fictícios."""

    def __init__(self, growth_repository: GrowthRepositoryPort):
        self._growth_repo = growth_repository

    def execute(self, hypothesis_id: int, target_cycle_start: date) -> CDMSProposalResult:
        if target_cycle_start.weekday() != 0:
            raise ValueError("O ciclo alvo deve começar numa segunda-feira.")
        hypo = self._growth_repo.get_hypothesis_by_id(hypothesis_id)
        if not hypo:
            raise ValueError(f"Hipótese #{hypothesis_id} não encontrada.")
        if hypo.status not in (HypothesisStatus.PENDING, HypothesisStatus.BACKLOG):
            raise ValueError("Apenas hipóteses pendentes podem ser preparadas para o ritual.")
        cycle_id = target_cycle_start.isoformat()
        conflict = self._growth_repo.get_active_hypothesis_by_variable(hypo.tested_variable, cycle_id)
        if conflict:
            raise ConflictingActiveVariableError(hypo.tested_variable, cycle_id, conflict.id)
        self._growth_repo.update_hypothesis_status(
            hypothesis_id=hypothesis_id, status=HypothesisStatus.PENDING, target_cycle_id=cycle_id,
        )
        return CDMSProposalResult(
            hypothesis_id=hypothesis_id, target_cycle_id=cycle_id,
            formal_hypothesis=self._render_formal_markdown(hypo, cycle_id),
            variable_tested=hypo.tested_variable.value, target_metric=hypo.target_metric_key,
            success_target=hypo.success_metric_target, invalidation_floor=hypo.invalidation_floor,
        )

    def _render_formal_markdown(self, hypo: GrowthHypothesis, target_cycle_id: str) -> str:
        """Estrutura o texto da proposta no formato canônico aceito pelo ritual do CDMS."""
        return (
            f"### 🎯 Proposta de Decisão Operacional (CGS -> CDMS)\n\n"
            f"- **Ciclo Alvo:** `{target_cycle_id}`\n"
            f"- **Variável Única Testada:** `{hypo.tested_variable.value}`\n"
            f"- **Ação Prática:** {hypo.action_description}\n"
            f"- **Métrica Alvo:** `{hypo.target_metric_key}` ({hypo.target_metric_unit})\n"
            f"- **Referência Inicial (Baseline):** `{hypo.baseline_reference_value}{hypo.target_metric_unit}`\n"
            f"- **Meta de Confirmação:** `{hypo.success_metric_target}{hypo.target_metric_unit}`\n"
            f"- **Piso/Teto de Invalidação:** `{hypo.invalidation_floor}{hypo.target_metric_unit}`\n"
            f"- **Janela de Teste:** `{hypo.window_days} dias` | Amostra Mínima: `{hypo.sample_exposure_minimum}`\n"
            f"- **ICE Score:** `{hypo.ice_score}` (Impacto: {hypo.impact_score}, Confiança: {hypo.confidence_score}, Facilidade: {hypo.ease_score})\n\n"
            f"> **Declaração Causal:** Se executarmos *{hypo.action_description}*, "
            f"esperamos destravar a métrica `{hypo.target_metric_key}` para `{hypo.success_metric_target}{hypo.target_metric_unit}`, "
            f"pois: {hypo.expected_impact_description}."
        )
