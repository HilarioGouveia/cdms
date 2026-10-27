"""Serviço puro de cálculo de oportunidade de receita e diagnóstico de gargalo de funil."""

from decimal import Decimal, ROUND_HALF_UP

from cgs.domain.entities.funnel import (
    ConversionType,
    FunnelBaseline,
    FunnelOpportunityAudit,
    FunnelStage,
)


class FunnelOpportunityAnalyzer:
    """Motor analítico de oportunidade de receita frente à linha de base de referência."""

    CALCULATION_VERSION: str = "1.1.0"

    @classmethod
    def calculate_opportunity(
        cls,
        source_cycle_id: str,
        impressions: int,
        clicks: int,
        conversions: int,
        baseline: FunnelBaseline,
    ) -> FunnelOpportunityAudit:
        """Calcula de forma determinística a oportunidade estimada de receita frente à baseline."""
        # Validação de integridade de contagens
        for name, val in [
            ("impressions", impressions),
            ("clicks", clicks),
            ("conversions", conversions),
        ]:
            if isinstance(val, bool) or not isinstance(val, int) or val < 0:
                raise ValueError(f"{name} deve ser um inteiro não negativo.")

        if clicks > impressions:
            raise ValueError(f"Cliques ({clicks}) não podem exceder o total de impressões ({impressions}).")

        # Conversão de entradas para Decimal
        dec_impressions = Decimal(str(impressions))
        dec_clicks = Decimal(str(clicks))
        dec_conversions = Decimal(str(conversions))

        # 1. Taxas observadas com guarda contra divisão por zero
        observed_ctr_pct = (dec_clicks / dec_impressions * Decimal("100")) if impressions > 0 else Decimal("0")
        observed_conv_rate_pct = (dec_conversions / dec_clicks * Decimal("100")) if clicks > 0 else Decimal("0")

        # 2. Gaps frente à baseline (não negativos)
        ctr_gap_fraction = max(Decimal("0"), (baseline.expected_ctr_pct - observed_ctr_pct) / Decimal("100"))
        conv_gap_fraction = max(Decimal("0"), (baseline.expected_conversion_rate_pct - observed_conv_rate_pct) / Decimal("100"))

        # 3. Fator de conversão lead -> venda se aplicável
        lead_multiplier = Decimal("1")
        if baseline.conversion_type == ConversionType.LEAD and baseline.lead_to_sale_rate_pct is not None:
            lead_multiplier = baseline.lead_to_sale_rate_pct / Decimal("100")

        expected_conv_fraction = (baseline.expected_conversion_rate_pct / Decimal("100")) * lead_multiplier

        # 4. Cálculo de oportunidade estimada em moeda
        intention_opportunity = (
            dec_impressions
            * ctr_gap_fraction
            * expected_conv_fraction
            * baseline.ticket_price
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        conversion_opportunity = (
            dec_clicks
            * conv_gap_fraction
            * lead_multiplier
            * baseline.ticket_price
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        total_opportunity = (intention_opportunity + conversion_opportunity).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        # 5. Diagnóstico de Gargalo com regra de precedência unificada e desempate estável
        if conversion_opportunity > Decimal("0") and conversion_opportunity >= intention_opportunity:
            stage = FunnelStage.CONVERSION
            summary = (
                f"Gargalo primário identificado em CONVERSÃO. "
                f"Oportunidade estimada de receita de R$ {conversion_opportunity} frente à referência esperada."
            )
        elif intention_opportunity > Decimal("0"):
            stage = FunnelStage.INTENTION
            summary = (
                f"Gargalo primário identificado em INTENÇÃO. "
                f"Oportunidade estimada de receita de R$ {intention_opportunity} por cliques qualificados não captados."
            )
        elif impressions == 0:
            stage = FunnelStage.ATTENTION
            summary = "Sem exposição no ciclo (0 impressões). Déficit crítico na etapa de ATENÇÃO."
        else:
            stage = FunnelStage.NONE
            summary = "Funil operando dentro ou acima dos parâmetros da linha de base de referência."

        return FunnelOpportunityAudit(
            source_cycle_id=source_cycle_id,
            primary_bottleneck=stage,
            intention_opportunity_reais=intention_opportunity,
            conversion_opportunity_reais=conversion_opportunity,
            total_opportunity_reais=total_opportunity,
            diagnosis_summary=summary,
            calculation_version=cls.CALCULATION_VERSION,
        )