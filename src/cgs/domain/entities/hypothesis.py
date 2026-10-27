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
    HIGHER_IS_BETTER = "HIGHER_IS_BETTER"  # Ex: CTR, Taxa de Conversão, Vendas
    LOWER_IS_BETTER = "LOWER_IS_BETTER"    # Ex: CPA, CPC, Taxa de Rejeição


class HypothesisStatus(str, Enum):
    """Ciclo de vida auditável da hipótese experimental."""
    BACKLOG = "BACKLOG"      # Registrada na esteira de priorização
    PROPOSED = "PROPOSED"    # Pré-selecionada para preencher a decisão do ciclo
    ACTIVE = "ACTIVE"        # Formalizada e gravada com sucesso no ritual do CDMS
    COMPLETED = "COMPLETED"  # Ciclo executado e avaliado
    CANCELLED = "CANCELLED"  # Descartada antes da execução
    ARCHIVED = "ARCHIVED"    # Histórico de aprendizados concluídos


@dataclass
class GrowthHypothesis:
    """Declaração formal de experimento operacional estruturado em janela de 7 dias."""
    id: Optional[int]
    source_cycle_id: Optional[str]         # Ciclo que motivou o teste
    target_cycle_id: Optional[str]         # Ciclo em que o teste será executado
    promoted_decision_id: Optional[int]    # Vínculo com a Decision persistida no CDMS
    action_description: str                # Ação prática concreta
    tested_variable: VariableType          # Variável única isolada
    target_metric_key: str                 # Chave da métrica canônica ou observada
    target_metric_unit: str                # Unidade da métrica (%, R$, un)
    metric_direction: MetricDirection      # Direção da otimização
    baseline_reference_value: Decimal      # Valor de referência na baseline
    success_metric_target: Decimal         # Meta para confirmação de sucesso
    invalidation_floor: Decimal            # Piso ou teto numérico de invalidação
    expected_impact_description: str       # Expectativa qualitativa/quantitativa
    impact_score: int                      # Escala 1 a 10 (rejeita bool e float)
    confidence_score: int                  # Escala 1 a 10
    ease_score: int                        # Escala 1 a 10
    sample_exposure_minimum: int = 100     # Exposição mínima requerida (impressões/visitas)
    window_days: int = 7                   # Janela operacional de 7 dias
    status: HypothesisStatus = HypothesisStatus.BACKLOG
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        # Validação das notas do ICE
        for name, score in [
            ("impact", self.impact_score),
            ("confidence", self.confidence_score),
            ("ease", self.ease_score),
        ]:
            if isinstance(score, bool) or not isinstance(score, int):
                raise TypeError(f"{name}_score deve ser um número inteiro.")
            if not (1 <= score <= 10):
                raise ValueError(f"{name}_score deve estar estritamente entre 1 e 10.")

        # Validação numérica de metas
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
        """Calcula o score de priorização ICE: (I * C * E) / 10."""
        score = (Decimal(self.impact_score) * Decimal(self.confidence_score) * Decimal(self.ease_score)) / Decimal("10")
        return score.quantize(Decimal("0.01"))