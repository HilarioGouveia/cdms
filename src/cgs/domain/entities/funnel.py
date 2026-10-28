"""Entidades de Funil e Avaliação de Oportunidade Financeira do CGS."""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Optional


class FunnelStage(str, Enum):
    """Etapas da jornada do funil avaliadas para identificação de gargalos."""
    NONE = "NONE"                # Nenhuma quebra crítica identificada frente à baseline
    ATTENTION = "ATTENTION"      # Quebra ou déficit inicial em volume de exposição/alcance
    INTENTION = "INTENTION"      # Quebra no CTR / cliques em anúncios ou conteúdos
    CONVERSION = "CONVERSION"    # Quebra genérica na conversão para venda direta
    LEAD_CAPTURE = "LEAD_CAPTURE" # Quebra na taxa de captura de leads (opt-in sobre cliques)
    LEAD_CLOSING = "LEAD_CLOSING" # Quebra no fechamento comercial (vendas sobre leads)


class ConversionType(str, Enum):
    """Tipo da ação de conversão avaliada no funil."""
    DIRECT_SALE = "DIRECT_SALE"  # Venda direta com ticket médio comercial
    LEAD = "LEAD"                # Geração de lead (requer taxa obrigatória lead -> venda)


@dataclass(frozen=True)
class FunnelBaseline:
    """Parâmetros de comparação e referência esperada de saúde do funil."""
    ticket_price: Decimal
    expected_ctr_pct: Decimal
    expected_conversion_rate_pct: Decimal
    conversion_type: ConversionType = ConversionType.DIRECT_SALE
    lead_to_sale_rate_pct: Optional[Decimal] = None

    def __post_init__(self):
        # Validação estrita do ticket médio
        if isinstance(self.ticket_price, bool) or not isinstance(self.ticket_price, Decimal):
            raise TypeError("ticket_price deve ser do tipo Decimal.")
        if self.ticket_price.is_nan() or self.ticket_price.is_infinite() or self.ticket_price <= Decimal("0"):
            raise ValueError("ticket_price deve ser finito e estritamente positivo.")

        # Validação das taxas de referência percentuais
        for name, val in [
            ("expected_ctr_pct", self.expected_ctr_pct),
            ("expected_conversion_rate_pct", self.expected_conversion_rate_pct),
        ]:
            if isinstance(val, bool) or not isinstance(val, Decimal):
                raise TypeError(f"{name} deve ser do tipo Decimal.")
            if val.is_nan() or val.is_infinite() or not (Decimal("0") < val <= Decimal("100")):
                raise ValueError(f"{name} deve ser finito e estar no intervalo (0, 100].")

        # Regra de negócio para funil de dois passos (LEAD)
        if self.conversion_type == ConversionType.LEAD:
            if self.lead_to_sale_rate_pct is None:
                raise ValueError("lead_to_sale_rate_pct é obrigatório quando conversion_type for LEAD.")
            if isinstance(self.lead_to_sale_rate_pct, bool) or not isinstance(self.lead_to_sale_rate_pct, Decimal):
                raise TypeError("lead_to_sale_rate_pct deve ser do tipo Decimal.")
            if self.lead_to_sale_rate_pct.is_nan() or self.lead_to_sale_rate_pct.is_infinite() or not (Decimal("0") < self.lead_to_sale_rate_pct <= Decimal("100")):
                raise ValueError("lead_to_sale_rate_pct deve ser finito e estar no intervalo (0, 100].")


@dataclass(frozen=True)
class FunnelOpportunityAudit:
    """Resultado imutável do diagnóstico de oportunidade de receita frente à linha de base."""
    source_cycle_id: str
    primary_bottleneck: FunnelStage
    intention_opportunity_reais: Decimal
    conversion_opportunity_reais: Decimal
    total_opportunity_reais: Decimal
    diagnosis_summary: str
    calculation_version: str = "2.0.0"
    leads_opportunity_reais: Optional[Decimal] = None
    closing_opportunity_reais: Optional[Decimal] = None

    def __post_init__(self):
        for name, val in [
            ("intention_opportunity_reais", self.intention_opportunity_reais),
            ("conversion_opportunity_reais", self.conversion_opportunity_reais),
            ("total_opportunity_reais", self.total_opportunity_reais),
        ]:
            if isinstance(val, bool) or not isinstance(val, Decimal):
                raise TypeError(f"{name} deve ser do tipo Decimal.")
            if val.is_nan() or val.is_infinite() or val < Decimal("0"):
                raise ValueError(f"{name} deve ser finito e não negativo.")

        for name, val in [
            ("leads_opportunity_reais", self.leads_opportunity_reais),
            ("closing_opportunity_reais", self.closing_opportunity_reais),
        ]:
            if val is not None:
                if isinstance(val, bool) or not isinstance(val, Decimal):
                    raise TypeError(f"{name} deve ser do tipo Decimal se informado.")
                if val.is_nan() or val.is_infinite() or val < Decimal("0"):
                    raise ValueError(f"{name} deve ser finito e não negativo.")