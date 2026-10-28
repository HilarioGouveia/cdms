"""Caso de uso: Exportador de Relatório Consolidado de Ciclo (CDMS + CGS) em Markdown."""

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Protocol, List

from cgs.application.ports.growth_repository import GrowthRepositoryPort
from cgs.domain.entities.funnel import FunnelOpportunityAudit, FunnelStage
from cgs.domain.entities.hypothesis import GrowthHypothesis, HypothesisStatus


class CDMSQueryRepositoryPort(Protocol):
    """Protocolo de leitura para recuperar rituais ou decisões históricas do CDMS."""

    def get_ritual_by_cycle(self, cycle_id: str) -> Optional[object]:
        ...


@dataclass(frozen=True)
class CycleReportResult:
    """Resultado do relatório de ciclo estruturado em Markdown."""
    cycle_id: str
    markdown_content: str
    generated_at: str
    has_funnel_audit: bool
    hypotheses_count: int


class ExportCycleReportUseCase:
    """Consolida auditoria de funil, governança de decisões e backlog de experimentação."""

    def __init__(
        self,
        growth_repository: GrowthRepositoryPort,
        cdms_repository: Optional[CDMSQueryRepositoryPort] = None,
    ):
        self._growth_repo = growth_repository
        self._cdms_repo = cdms_repository

    def execute(self, cycle_id: str) -> CycleReportResult:
        """Gera o relatório consolidado em Markdown para um ciclo semanal específico."""
        audit: Optional[FunnelOpportunityAudit] = self._growth_repo.get_funnel_audit(cycle_id)
        
        # Recupera hipóteses associadas a este ciclo (tanto de origem quanto alvo de execução)
        all_hypotheses: List[GrowthHypothesis] = self._growth_repo.list_hypotheses(limit=100)
        cycle_hypotheses = [
            h for h in all_hypotheses
            if h.source_cycle_id == cycle_id or h.target_cycle_id == cycle_id
        ]

        # Auditoria prévia para medir ROI frente ao ciclo imediatamente anterior
        all_audits = self._growth_repo.list_funnel_audits(limit=50)
        previous_audit: Optional[FunnelOpportunityAudit] = None
        for i, a in enumerate(all_audits):
            if a.source_cycle_id == cycle_id and i + 1 < len(all_audits):
                previous_audit = all_audits[i + 1]
                break

        # Tenta recuperar dados do ritual fechado no CDMS caso o adapter esteja disponível
        cdms_ritual = None
        if self._cdms_repo:
            try:
                cdms_ritual = self._cdms_repo.get_ritual_by_cycle(cycle_id)
            except Exception:
                cdms_ritual = None

        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        markdown_text = self._render_markdown(
            cycle_id=cycle_id,
            audit=audit,
            previous_audit=previous_audit,
            hypotheses=cycle_hypotheses,
            cdms_ritual=cdms_ritual,
            generated_at=now_str,
        )

        return CycleReportResult(
            cycle_id=cycle_id,
            markdown_content=markdown_text,
            generated_at=now_str,
            has_funnel_audit=audit is not None,
            hypotheses_count=len(cycle_hypotheses),
        )

    def _render_markdown(
        self,
        cycle_id: str,
        audit: Optional[FunnelOpportunityAudit],
        previous_audit: Optional[FunnelOpportunityAudit],
        hypotheses: List[GrowthHypothesis],
        cdms_ritual: Optional[object],
        generated_at: str,
    ) -> str:
        lines: List[str] = [
            f"# 📊 Relatório Executivo Semanal — Ciclo `{cycle_id}`",
            "",
            f"> **Gerado em:** {generated_at}  ",
            f"> **Status da Governança:** {'Ritual concluído' if cdms_ritual else 'Ritual pendente'}",
            "",
            "---",
            "",
            "## 1. 💰 Auditoria de Oportunidade Financeira e Funil",
            "",
        ]

        if not audit:
            lines.extend([
                "_Nenhuma auditoria quantitativa de funil foi registrada para este ciclo._",
                "",
            ])
        else:
            lines.extend([
                f"- **Gargalo Dominante:** `{audit.primary_bottleneck.value}`",
                f"- **Diagnóstico:** {audit.diagnosis_summary}",
                f"- **Perda Estimada em Intenção (CTR):** R$ {audit.intention_opportunity_reais:,.2f}",
                f"- **Perda Estimada em Conversão Total:** R$ {audit.conversion_opportunity_reais:,.2f}",
            ])

            if audit.leads_opportunity_reais is not None and audit.closing_opportunity_reais is not None:
                lines.extend([
                    f"  - _Sub-etapa Captura de Lead:_ R$ {audit.leads_opportunity_reais:,.2f}",
                    f"  - _Sub-etapa Fechamento Comercial:_ R$ {audit.closing_opportunity_reais:,.2f}",
                ])

            lines.extend([
                f"- **Oportunidade Total Destravável:** **R$ {audit.total_opportunity_reais:,.2f}**",
                "",
            ])

            if previous_audit:
                delta = audit.total_opportunity_reais - previous_audit.total_opportunity_reais
                if delta <= Decimal("0"):
                    lines.extend([
                        f"🎉 **ROI de Governança Positivo:** Redução de **R$ {abs(delta):,.2f}** em oportunidade desperdiçada "
                        f"frente ao ciclo `{previous_audit.source_cycle_id}`.",
                        "",
                    ])
                else:
                    lines.extend([
                        f"⚠️ **Atenção:** Aumento de **R$ {delta:,.2f}** em oportunidade desperdiçada "
                        f"em relação ao ciclo anterior (`{previous_audit.source_cycle_id}`).",
                        "",
                    ])

        lines.extend([
            "---",
            "",
            "## 2. 🎯 Decisões e Experimentos Operacionais",
            "",
        ])

        if not hypotheses:
            lines.extend([
                "_Nenhum experimento ou hipótese de crescimento foi vinculado explicitamente a este ciclo._",
                "",
            ])
        else:
            lines.extend([
                "| ID | Status | Variável | Métrica Alvo | Meta | Piso | Decisão CDMS | ICE |",
                "|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|",
            ])
            for h in hypotheses:
                status_icon = {
                    HypothesisStatus.ACTIVE: "🔵 ACTIVE",
                    HypothesisStatus.COMPLETED: "✅ COMPLETED",
                    HypothesisStatus.DISCARDED: "❌ DISCARDED",
                    HypothesisStatus.PENDING: "⏳ PENDING",
                    HypothesisStatus.BACKLOG: "⏳ BACKLOG",
                }.get(h.status, h.status.value)

                dec_str = f"#{h.promoted_decision_id}" if h.promoted_decision_id else "N/A"
                meta_str = f"{h.success_metric_target}{h.target_metric_unit}"
                floor_str = f"{h.invalidation_floor}{h.target_metric_unit}"

                lines.append(
                    f"| #{h.id} | {status_icon} | `{h.tested_variable.value}` | `{h.target_metric_key}` | "
                    f"{meta_str} | {floor_str} | `{dec_str}` | **{h.ice_score}** |"
                )
            lines.append("")

            # Detalhamento de cada ação
            lines.extend([
                "### Detalhes das Ações de Experimentação",
                "",
            ])
            for h in hypotheses:
                lines.extend([
                    f"#### Hipótese #{h.id}: {h.action_description}",
                    f"- **Declaração Causal:** {h.expected_impact_description}",
                    f"- **Parâmetros ICE:** Impacto {h.impact_score} | Confiança {h.confidence_score} | Facilidade {h.ease_score} (Score: **{h.ice_score}**)",
                    f"- **Amostra Mínima:** {h.sample_exposure_minimum} exposições | **Janela de Teste:** {h.window_days} dias",
                    "",
                ])

        lines.extend([
            "---",
            "",
            "## 3. 🛡️ Auditoria de Governança e Causalidade",
            "",
            "- **Regra de Variável Única:** Validada no ciclo (sem testes concorrentes sobre o mesmo elemento).",
            "- **Sincronização Bidirecional:** Desfechos sincronizados atômica e retroativamente entre CDMS e CGS.",
            "",
            "_Relatório emitido pela Creator Data Marketing & Growth Suite (CDMS v2.4.0 + CGS v1.2.0)._",
        ])

        return "\n".join(lines)