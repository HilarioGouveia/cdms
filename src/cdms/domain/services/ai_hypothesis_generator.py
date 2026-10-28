"""Serviço puro de raciocínio heurístico e síntese estruturada de hipóteses via IA/LLM."""

from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional
from cgs.domain.entities.funnel import FunnelOpportunityAudit, FunnelStage
from cgs.domain.entities.hypothesis import MetricDirection, VariableType


@dataclass(frozen=True)
class AIHypothesisSuggestion:
    action_description: str
    tested_variable: VariableType
    target_metric_key: str
    target_metric_unit: str
    metric_direction: MetricDirection
    suggested_target: Decimal
    invalidation_floor: Decimal
    rational_explanation: str
    suggested_impact: int
    suggested_confidence: int
    suggested_ease: int


class AIHypothesisGenerator:
    """Gera sugestões de testes operacionais a partir da auditoria de funil e cenário heurístico."""

    @classmethod
    def generate_suggestions(
        cls,
        audit: FunnelOpportunityAudit,
        current_ctr_pct: Decimal = Decimal("3.0"),
        current_conv_rate_pct: Decimal = Decimal("2.0"),
    ) -> List[AIHypothesisSuggestion]:
        suggestions = []

        if audit.primary_bottleneck == FunnelStage.INTENTION:
            # Gargalo em CTR / Atenção
            suggestions.append(
                AIHypothesisSuggestion(
                    action_description="Inserir gancho provocativo em formato de pergunta nos primeiros 3s",
                    tested_variable=VariableType.HOOK,
                    target_metric_key="ctr_pct",
                    target_metric_unit="%",
                    metric_direction=MetricDirection.HIGHER_IS_BETTER,
                    suggested_target=(current_ctr_pct * Decimal("1.25")).quantize(Decimal("0.1")),
                    invalidation_floor=(current_ctr_pct * Decimal("0.90")).quantize(Decimal("0.1")),
                    rational_explanation=(
                        f"Gargalo primário em Intenção detectado com desperdício de R$ {audit.intention_opportunity_reais:,.2f}. "
                        "Aumentar a retenção nos primeiros 3s eleva a taxa de clique no CTA principal."
                    ),
                    suggested_impact=8,
                    suggested_confidence=8,
                    suggested_ease=9,
                )
            )
            suggestions.append(
                AIHypothesisSuggestion(
                    action_description="Refatorar CTA verbal com comando de ação único e indicação clara de link na bio",
                    tested_variable=VariableType.CTA,
                    target_metric_key="ctr_pct",
                    target_metric_unit="%",
                    metric_direction=MetricDirection.HIGHER_IS_BETTER,
                    suggested_target=(current_ctr_pct * Decimal("1.20")).quantize(Decimal("0.1")),
                    invalidation_floor=(current_ctr_pct * Decimal("0.95")).quantize(Decimal("0.1")),
                    rational_explanation="Reduzir dispersão de cliques alinhando o gatilho final de fechamento ao link oficial.",
                    suggested_impact=7,
                    suggested_confidence=9,
                    suggested_ease=9,
                )
            )
        elif audit.primary_bottleneck in (FunnelStage.CONVERSION, FunnelStage.LEAD_CAPTURE, FunnelStage.LEAD_CLOSING):
            # Gargalo de Conversão / Checkout / Leads
            suggestions.append(
                AIHypothesisSuggestion(
                    action_description="Adicionar bônus exclusivo de onboarding para fechamentos no mesmo dia",
                    tested_variable=VariableType.OFFER,
                    target_metric_key="conversions",
                    target_metric_unit="un",
                    metric_direction=MetricDirection.HIGHER_IS_BETTER,
                    suggested_target=(current_conv_rate_pct * Decimal("1.30")).quantize(Decimal("0.1")),
                    invalidation_floor=(current_conv_rate_pct * Decimal("0.95")).quantize(Decimal("0.1")),
                    rational_explanation=(
                        f"Gargalo crítico de conversão com oportunidade recuperável de R$ {audit.conversion_opportunity_reais:,.2f}. "
                        "Urgência e valor agregado reduzem a fricção de compra no checkout."
                    ),
                    suggested_impact=9,
                    suggested_confidence=7,
                    suggested_ease=7,
                )
            )
            suggestions.append(
                AIHypothesisSuggestion(
                    action_description="Simplificar o formulário da Landing Page para apenas Nome e WhatsApp",
                    tested_variable=VariableType.LANDING_PAGE,
                    target_metric_key="lead_capture_pct",
                    target_metric_unit="%",
                    metric_direction=MetricDirection.HIGHER_IS_BETTER,
                    suggested_target=Decimal("25.0"),
                    invalidation_floor=Decimal("12.0"),
                    rational_explanation="Menor quantidade de campos reduz atrito cognitivo e taxa de abandono do visitante.",
                    suggested_impact=8,
                    suggested_confidence=8,
                    suggested_ease=8,
                )
            )
        else:
            # Equilíbrio / Alavancagem
            suggestions.append(
                AIHypothesisSuggestion(
                    action_description="Testar novo ângulo criativo para expansão de novos públicos semelhantes",
                    tested_variable=VariableType.CREATIVE,
                    target_metric_key="reach",
                    target_metric_unit="un",
                    metric_direction=MetricDirection.HIGHER_IS_BETTER,
                    suggested_target=Decimal("15000"),
                    invalidation_floor=Decimal("8000"),
                    rational_explanation="Operação equilibrada permite testes arrojados de escala no topo de funil.",
                    suggested_impact=8,
                    suggested_confidence=6,
                    suggested_ease=6,
                )
            )

        return suggestions