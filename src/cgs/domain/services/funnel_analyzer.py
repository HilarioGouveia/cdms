"""Serviço de domínio para cálculo e diagnóstico financeiro de funil."""

from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from cgs.domain.entities.funnel import (
    ConversionType,
    FunnelBaseline,
    FunnelOpportunityAudit,
    FunnelStage,
)


class FunnelOpportunityAnalyzer:
    """Calcula oportunidades financeiras e identifica gargalos de funil."""

    @staticmethod
    def calculate_opportunity(
        source_cycle_id: str,
        impressions: int,
        clicks: int,
        conversions: int,
        baseline: FunnelBaseline,
        leads: Optional[int] = None,
    ) -> FunnelOpportunityAudit:
        """Executa a auditoria de gargalos financeiros comparando dados reais com a baseline."""
        # Validações estritas esperadas nos testes unitários
        if impressions < 0 or clicks < 0 or conversions < 0:
            raise ValueError("Métricas de funil devem ser números inteiros maiores ou iguais a zero.")
        if clicks > impressions:
            raise ValueError(f"Cliques ({clicks}) não podem exceder impressões ({impressions}).")

        # Topo de funil zerado: gargalo de atenção
        if impressions == 0:
            return FunnelOpportunityAudit(
                source_cycle_id=source_cycle_id,
                primary_bottleneck=FunnelStage.ATTENTION,
                intention_opportunity_reais=Decimal("0.00"),
                conversion_opportunity_reais=Decimal("0.00"),
                total_opportunity_reais=Decimal("0.00"),
                diagnosis_summary="Gargalo crítico em ATENÇÃO (0 impressões). Exposição nula no ciclo.",
                calculation_version="2.0.0",
            )

        dec_impressions = Decimal(str(impressions))
        dec_clicks = Decimal(str(clicks))
        dec_conversions = Decimal(str(conversions))

        expected_ctr = baseline.expected_ctr_pct / Decimal("100")
        ticket = baseline.ticket_price

        # Se for LEAD e houver leads explícitos passados, usa cálculo em 2 passos
        if baseline.conversion_type == ConversionType.LEAD and leads is not None:
            dec_leads = Decimal(str(leads))
            return FunnelOpportunityAnalyzer._calculate_lead_funnel(
                source_cycle_id=source_cycle_id,
                baseline=baseline,
                impressions=dec_impressions,
                clicks=dec_clicks,
                leads=dec_leads,
                conversions=dec_conversions,
                expected_ctr=expected_ctr,
                ticket=ticket,
            )
        else:
            return FunnelOpportunityAnalyzer._calculate_direct_sale_funnel(
                source_cycle_id=source_cycle_id,
                baseline=baseline,
                impressions=dec_impressions,
                clicks=dec_clicks,
                conversions=dec_conversions,
                expected_ctr=expected_ctr,
                ticket=ticket,
            )

    @staticmethod
    def _calculate_direct_sale_funnel(
        source_cycle_id: str,
        baseline: FunnelBaseline,
        impressions: Decimal,
        clicks: Decimal,
        conversions: Decimal,
        expected_ctr: Decimal,
        ticket: Decimal,
    ) -> FunnelOpportunityAudit:
        expected_conv_rate = baseline.expected_conversion_rate_pct / Decimal("100")

        # 1. Intenção (Cliques perdidos)
        expected_clicks = impressions * expected_ctr
        click_gap = max(Decimal("0"), expected_clicks - clicks)
        
        # Se for LEAD no modo legado direto, pondera por lead_to_sale_rate_pct
        effective_sales_rate = expected_conv_rate
        if baseline.conversion_type == ConversionType.LEAD and baseline.lead_to_sale_rate_pct:
            effective_sales_rate = expected_conv_rate * (baseline.lead_to_sale_rate_pct / Decimal("100"))

        intention_opp = (click_gap * effective_sales_rate * ticket).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        # 2. Conversão
        expected_conversions = clicks * expected_conv_rate
        conv_gap = max(Decimal("0"), expected_conversions - conversions)
        
        if baseline.conversion_type == ConversionType.LEAD and baseline.lead_to_sale_rate_pct:
            conv_opp = (conv_gap * (baseline.lead_to_sale_rate_pct / Decimal("100")) * ticket).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        else:
            conv_opp = (conv_gap * ticket).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

        total_opp = intention_opp + conv_opp

        if intention_opp == Decimal("0") and conv_opp == Decimal("0"):
            stage = FunnelStage.NONE
            summary = "Funil operando dentro ou acima da baseline ativa."
        elif intention_opp > conv_opp:
            stage = FunnelStage.INTENTION
            summary = f"Gargalo crítico em INTENÇÃO (CTR). Oportunidade recuperável: R$ {intention_opp:,.2f}."
        else:
            stage = FunnelStage.CONVERSION
            summary = f"Gargalo crítico em CONVERSÃO. Oportunidade recuperável: R$ {conv_opp:,.2f}."

        return FunnelOpportunityAudit(
            source_cycle_id=source_cycle_id,
            primary_bottleneck=stage,
            intention_opportunity_reais=intention_opp,
            conversion_opportunity_reais=conv_opp,
            total_opportunity_reais=total_opp,
            diagnosis_summary=summary,
            calculation_version="2.0.0",
        )

    @staticmethod
    def _calculate_lead_funnel(
        source_cycle_id: str,
        baseline: FunnelBaseline,
        impressions: Decimal,
        clicks: Decimal,
        leads: Decimal,
        conversions: Decimal,
        expected_ctr: Decimal,
        ticket: Decimal,
    ) -> FunnelOpportunityAudit:
        expected_click_to_lead = baseline.expected_conversion_rate_pct / Decimal("100")
        expected_lead_to_sale = (baseline.lead_to_sale_rate_pct or Decimal("10.0")) / Decimal("100")
        full_effective_conv_rate = expected_click_to_lead * expected_lead_to_sale

        expected_clicks = impressions * expected_ctr
        click_gap = max(Decimal("0"), expected_clicks - clicks)
        intention_opp = (click_gap * full_effective_conv_rate * ticket).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        expected_leads = clicks * expected_click_to_lead
        lead_gap = max(Decimal("0"), expected_leads - leads)
        lead_capture_opp = (lead_gap * expected_lead_to_sale * ticket).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        expected_sales_from_leads = leads * expected_lead_to_sale
        sales_gap = max(Decimal("0"), expected_sales_from_leads - conversions)
        lead_closing_opp = (sales_gap * ticket).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        total_conv_opp = lead_capture_opp + lead_closing_opp
        total_opp = intention_opp + total_conv_opp

        gaps = [
            (intention_opp, FunnelStage.INTENTION, f"Gargalo crítico em INTENÇÃO (CTR). Oportunidade: R$ {intention_opp:,.2f}."),
            (lead_capture_opp, FunnelStage.LEAD_CAPTURE, f"Gargalo crítico na Captação de Leads (Opt-in). Oportunidade: R$ {lead_capture_opp:,.2f}."),
            (lead_closing_opp, FunnelStage.LEAD_CLOSING, f"Gargalo crítico no Fechamento Comercial. Oportunidade: R$ {lead_closing_opp:,.2f}."),
        ]
        gaps.sort(key=lambda x: x[0], reverse=True)

        if total_opp == Decimal("0.00"):
            primary_stage = FunnelStage.NONE
            summary = "Funil de Leads operando dentro ou acima da baseline ativa."
        else:
            primary_stage = gaps[0][1]
            summary = gaps[0][2]

        return FunnelOpportunityAudit(
            source_cycle_id=source_cycle_id,
            primary_bottleneck=primary_stage,
            intention_opportunity_reais=intention_opp,
            conversion_opportunity_reais=total_conv_opp,
            total_opportunity_reais=total_opp,
            diagnosis_summary=summary,
            calculation_version="2.0.0",
            leads_opportunity_reais=lead_capture_opp,
            closing_opportunity_reais=lead_closing_opp,
        )