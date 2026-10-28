"""Entidades e Máquina de Estados de Hipóteses Operacionais do CGS."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Optional


class VariableType(str, Enum):
    """Variável única isolada para o teste operacional de 7 dias."""
    CREATIVE = "CREATIVE"        # Visual, edição, paleta de cores ou formato
    HOOK = "HOOK"                # Primeiros 3 segundos / Headline de abertura
    CTA = "CTA"                  # Chamada para ação e direcionamento de destino
    OFFER = "OFFER"              # Preço, bônus, garantia ou condição comercial
    LANDING_PAGE = "LANDING_PAGE" # Página de destino, velocidade ou formulário


class MetricDirection(str, Enum):
    """Direção desejada para considerar a meta da métrica atingida."""
    HIGHER_IS_BETTER = "HIGHER_IS_BETTER"
    LOWER_IS_BETTER = "LOWER_IS_BETTER"


class HypothesisStatus(str, Enum):
    """Ciclo de vida auditável da hipótese experimental."""
    BACKLOG = "BACKLOG"        # Estado legado equivalente a PENDING
    PENDING = "PENDING"        # Registrada no backlog aguardando priorização/execução
    PROPOSED = "PROPOSED"      # Pré-selecionada / proposta para ciclo
    ACTIVE = "ACTIVE"          # Em teste operacional no ciclo corrente
    COMPLETED = "COMPLETED"    # Teste finalizado e auditado
    DISCARDED = "DISCARDED"    # Descartada, invalidada ou rejeitada no ritual
    CANCELLED = "CANCELLED"    # Descartada antes da execução (legado)
    ARCHIVED = "ARCHIVED"      # Histórico de aprendizados concluídos (legado)


class ConflictingActiveVariableError(ValueError):
    """Lançada ao tentar ativar hipótese cuja variável isolada já está ativa no mesmo ciclo."""

    def __init__(self, variable: VariableType, target_cycle_id: Optional[str], active_hypothesis_id: Optional[int] = None):
        cycle_label = target_cycle_id if target_cycle_id else "ciclo corrente"
        hypo_ref = f" (Hipótese #{active_hypothesis_id})" if active_hypothesis_id is not None else ""
        msg = (
            f"Violação da Regra de Variável Única: já existe teste ativo{hypo_ref} "
            f"para a variável '{variable.value}' no ciclo '{cycle_label}'. "
            "Conclua ou descarte o teste concorrente antes de ativar uma nova hipótese para mitigar ruído causal."
        )
        super().__init__(msg)
        self.variable = variable
        self.target_cycle_id = target_cycle_id
        self.active_hypothesis_id = active_hypothesis_id


@dataclass
class GrowthHypothesis:
    """Declaração formal de experimento operacional estruturado em janela de 7 dias."""
    id: Optional[int]
    source_cycle_id: Optional[str]
    target_cycle_id: Optional[str]
    promoted_decision_id: Optional[int]
    action_description: str
    tested_variable: VariableType
    target_metric_key: str
    target_metric_unit: str
    metric_direction: MetricDirection
    baseline_reference_value: Decimal
    success_metric_target: Decimal
    invalidation_floor: Decimal
    expected_impact_description: str
    impact_score: int
    confidence_score: int
    ease_score: int
    sample_exposure_minimum: int = 100
    window_days: int = 7
    status: HypothesisStatus = HypothesisStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        for name, score in [
            ("impact", self.impact_score),
            ("confidence", self.confidence_score),
            ("ease", self.ease_score),
        ]:
            if isinstance(score, bool) or not isinstance(score, int):
                raise TypeError(f"{name}_score deve ser um número inteiro.")
            if not (1 <= score <= 10):
                raise ValueError(f"{name}_score deve estar estritamente entre 1 e 10.")

        for name, val in [
            ("baseline_reference_value", self.baseline_reference_value),
            ("success_metric_target", self.success_metric_target),
            ("invalidation_floor", self.invalidation_floor),
        ]:
            if isinstance(val, bool) or not isinstance(val, Decimal):
                raise TypeError(f"{name} deve ser do tipo Decimal.")
            if val.is_nan() or val.is_infinite():
                raise ValueError(f"{name} deve conter um valor Decimal finito.")

        if self.metric_direction == MetricDirection.HIGHER_IS_BETTER:
            if self.invalidation_floor >= self.success_metric_target:
                raise ValueError(
                    f"Para HIGHER_IS_BETTER, invalidation_floor ({self.invalidation_floor}) "
                    f"deve ser estritamente menor que success_metric_target ({self.success_metric_target})."
                )
        else:
            if self.invalidation_floor <= self.success_metric_target:
                raise ValueError(
                    f"Para LOWER_IS_BETTER, invalidation_floor ({self.invalidation_floor}) "
                    f"deve ser estritamente maior que success_metric_target ({self.success_metric_target})."
                )

        if isinstance(self.sample_exposure_minimum, bool) or not isinstance(self.sample_exposure_minimum, int) or self.sample_exposure_minimum < 0:
            raise ValueError("sample_exposure_minimum deve ser um inteiro não negativo.")

    @property
    def ice_score(self) -> Decimal:
        score = (Decimal(self.impact_score) * Decimal(self.confidence_score) * Decimal(self.ease_score)) / Decimal("10")
        return score.quantize(Decimal("0.01"))


    def activate(self, target_cycle_id: Optional[str] = None, promoted_decision_id: Optional[int] = None) -> None:
        if self.status not in (HypothesisStatus.PENDING, HypothesisStatus.BACKLOG, HypothesisStatus.PROPOSED):
            raise ValueError(f"Apenas hipóteses PENDING podem ser ativadas. Status atual: {self.status.value}")
        self.status = HypothesisStatus.ACTIVE
        if target_cycle_id:
            self.target_cycle_id = target_cycle_id
        if promoted_decision_id:
            self.promoted_decision_id = promoted_decision_id


    def complete(self) -> None:
        if self.status != HypothesisStatus.ACTIVE:
            raise ValueError(f"Apenas hipóteses ACTIVE podem ser concluídas. Status atual: {self.status.value}")
        self.status = HypothesisStatus.COMPLETED

    def discard(self) -> None:
        if self.status in (HypothesisStatus.COMPLETED, HypothesisStatus.DISCARDED, HypothesisStatus.ARCHIVED):
            raise ValueError(f"Hipótese já encerrada com status {self.status.value}.")
        self.status = HypothesisStatus.DISCARDED