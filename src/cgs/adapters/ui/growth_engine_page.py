"""Página Streamlit do Creator Growth System (CGS) - Gestão de Gargalos, Hipóteses e Relatórios."""

from datetime import date, timedelta
from decimal import Decimal
import streamlit as st

from cgs.adapters.persistence.sqlite_growth_repo import SQLiteGrowthRepository
from cdms.adapters.persistence.sqlite_repo import SQLiteRepository
from pathlib import Path
from cgs.application.use_cases.audit_funnel_opportunity import AuditFunnelOpportunityUseCase
from cgs.application.use_cases.export_cycle_report import ExportCycleReportUseCase
from cgs.application.use_cases.manage_hypotheses import ManageHypothesesUseCase
from cgs.application.use_cases.prepare_cdms_proposal import PrepareCDMSProposalUseCase
from cgs.domain.entities.funnel import ConversionType, FunnelBaseline
from cgs.domain.entities.hypothesis import (
    ConflictingActiveVariableError,
    HypothesisStatus,
    MetricDirection,
    VariableType,
)


def render_growth_engine(db_path: str = "data/cdms_dev.db"):
    st.title("🚀 Creator Growth System (CGS)")
    st.caption("Motor de Experimentação Operacional, Diagnóstico de Funil e Ranking ICE")

    repo = SQLiteGrowthRepository(db_path)
    audit_uc = AuditFunnelOpportunityUseCase(repo)
    hypo_uc = ManageHypothesesUseCase(repo)
    prop_uc = PrepareCDMSProposalUseCase(growth_repository=repo)
    export_uc = ExportCycleReportUseCase(growth_repository=repo, cdms_repository=SQLiteRepository(Path(db_path)))

    tabs = st.tabs([
        "📊 Diagnóstico de Funil",
        "💡 Backlog & Ciclo de Vida",
        "⚙️ Configuração de Baseline",
        "📑 Relatório Executivo",
    ])

    # =========================================================================
    # ABA 1: Diagnóstico de Funil e Histórico Acumulado
    # =========================================================================
    with tabs[0]:
        st.subheader("Auditoria de Oportunidade de Receita")
        active_baseline = repo.get_active_baseline()
        if not active_baseline:
            st.warning("⚠️ Cadastre primeiro uma linha de base na aba 'Configuração de Baseline'.")
        else:
            is_lead_funnel = active_baseline.conversion_type == ConversionType.LEAD
            
            funnel_badge = "Funil de 2 Passos (LEAD)" if is_lead_funnel else "Venda Direta (DIRECT_SALE)"
            st.info(
                f"Configuração Ativa: **{funnel_badge}** | "
                f"Ticket Médio: **R$ {active_baseline.ticket_price:,.2f}** | "
                f"CTR Meta: **{active_baseline.expected_ctr_pct}%**"
            )

            col1, col2, col3 = st.columns(3)
            source_cycle = col1.date_input("Segunda-feira de Referência", value=date.today() - timedelta(days=date.today().weekday() + 7))
            impressions = col2.number_input("Impressões Totais", min_value=0, value=10000, step=500)
            clicks = col3.number_input("Cliques Registados", min_value=0, value=300, step=50)

            leads = None
            if is_lead_funnel:
                col_lead, col_conv = st.columns(2)
                leads = col_lead.number_input("Leads Captados (Opt-in)", min_value=0, value=60, step=5)
                conversions = col_conv.number_input("Vendas Concluídas (a partir dos Leads)", min_value=0, value=6, step=1)
            else:
                conversions = st.number_input("Conversões / Vendas Concluídas", min_value=0, value=15, step=5)

            if st.button("Executar Diagnóstico Financeiro", type="primary"):
                try:
                    if source_cycle.weekday() != 0:
                        raise ValueError("O ciclo deve começar numa segunda-feira.")
                    audit = audit_uc.execute(
                        source_cycle_id=source_cycle.isoformat(),
                        impressions=impressions,
                        clicks=clicks,
                        conversions=conversions,
                        leads=leads,
                    )
                    st.success(audit.diagnosis_summary)

                    if is_lead_funnel:
                        m1, m2, m3, m4 = st.columns(4)
                        m1.metric("Gargalo Crítico", audit.primary_bottleneck.value)
                        m2.metric("Perda Intenção (CTR)", f"R$ {audit.intention_opportunity_reais:,.2f}")
                        m3.metric("Perda Captura Lead", f"R$ {(audit.leads_opportunity_reais or Decimal('0.00')):,.2f}")
                        m4.metric("Perda Fechamento Venda", f"R$ {(audit.closing_opportunity_reais or Decimal('0.00')):,.2f}")
                    else:
                        m1, m2, m3 = st.columns(3)
                        m1.metric("Gargalo Crítico", audit.primary_bottleneck.value)
                        m2.metric("Oportunidade Intenção", f"R$ {audit.intention_opportunity_reais:,.2f}")
                        m3.metric("Oportunidade Conversão", f"R$ {audit.conversion_opportunity_reais:,.2f}")

                    st.info(f"💰 Oportunidade Estimada Total Destravável: **R$ {audit.total_opportunity_reais:,.2f}**")
                except Exception as e:
                    st.error(f"Erro ao executar auditoria: {e}")

        st.divider()
        st.subheader("📈 Histórico Acumulado de Oportunidade Desperdiçada")
        
        audit_history = audit_uc.get_audit_history(limit=20)
        if not audit_history:
            st.info("Nenhuma auditoria registrada no histórico até o momento.")
        else:
            total_historico = sum(a.total_opportunity_reais for a in audit_history)
            media_desperdicio = total_historico / Decimal(str(len(audit_history)))

            col_h1, col_h2, col_h3 = st.columns(3)
            col_h1.metric("Ciclos Auditados", len(audit_history))
            col_h2.metric("Desperdício Total Registrado", f"R$ {total_historico:,.2f}")
            col_h3.metric("Média de Desperdício / Ciclo", f"R$ {media_desperdicio:,.2f}")

            if len(audit_history) >= 2:
                ultimo = audit_history[0].total_opportunity_reais
                penultimo = audit_history[1].total_opportunity_reais
                delta_reais = ultimo - penultimo
                if delta_reais <= Decimal("0"):
                    st.success(
                        f"🎉 **ROI de Governança Positivo:** Redução de **R$ {abs(delta_reais):,.2f}** em oportunidade desperdiçada "
                        f"do ciclo `{audit_history[1].source_cycle_id}` para `{audit_history[0].source_cycle_id}`!"
                    )
                else:
                    st.warning(
                        f"⚠️ Aumento de **R$ {delta_reais:,.2f}** em oportunidade desperdiçada no ciclo "
                        f"`{audit_history[0].source_cycle_id}` em relação ao anterior."
                    )

            chart_data = []
            for a in reversed(audit_history):
                chart_data.append({
                    "Ciclo": a.source_cycle_id,
                    "Perda em Intenção (R$)": float(a.intention_opportunity_reais),
                    "Perda em Conversão (R$)": float(a.conversion_opportunity_reais),
                })
            
            st.bar_chart(
                data=chart_data,
                x="Ciclo",
                y=["Perda em Intenção (R$)", "Perda em Conversão (R$)"],
                stack=True,
            )

            table_rows = []
            for a in audit_history:
                table_rows.append({
                    "Ciclo": a.source_cycle_id,
                    "Gargalo Dominante": a.primary_bottleneck.value,
                    "Perda Intenção": f"R$ {a.intention_opportunity_reais:,.2f}",
                    "Perda Conversão": f"R$ {a.conversion_opportunity_reais:,.2f}",
                    "Oportunidade Total": f"R$ {a.total_opportunity_reais:,.2f}",
                    "Resumo Diagnóstico": a.diagnosis_summary,
                })
            st.dataframe(table_rows, width="stretch", hide_index=True)

    # =========================================================================
    # ABA 2: Backlog de Hipóteses e Ciclo de Vida
    # =========================================================================
    with tabs[1]:
        st.subheader("Nova Hipótese Operacional (Janela de 7 Dias)")
        with st.form("new_hypothesis_form"):
            action = st.text_input("Ação Prática", placeholder="Ex: Adicionar CTA verbal direto nos primeiros 5s")
            col_var, col_met, col_unit, col_dir = st.columns(4)
            var_type = col_var.selectbox("Variável Única", [v.value for v in VariableType])
            metric_key = col_met.text_input("Chave da Métrica", value="ctr_pct")
            metric_unit = col_unit.text_input("Unidade", value="%")
            direction = col_dir.selectbox("Direção", [d.value for d in MetricDirection])

            c_base, c_target, c_floor = st.columns(3)
            base_val = c_base.number_input("Referência Atual", value=3.0, step=0.1)
            target_val = c_target.number_input("Meta de Sucesso", value=4.5, step=0.1)
            floor_val = c_floor.number_input("Piso/Teto Invalidação", value=2.5, step=0.1)

            c_imp, c_conf, c_ease = st.columns(3)
            impact = c_imp.slider("Impacto (1-10)", 1, 10, 7)
            conf = c_conf.slider("Confiança (1-10)", 1, 10, 7)
            ease = c_ease.slider("Facilidade (1-10)", 1, 10, 8)

            submitted = st.form_submit_button("Adicionar ao Backlog")
            if submitted:
                try:
                    new_h = hypo_uc.create_hypothesis(
                        action_description=action,
                        tested_variable=VariableType(var_type),
                        target_metric_key=metric_key,
                        target_metric_unit=metric_unit,
                        metric_direction=MetricDirection(direction),
                        baseline_reference_value=Decimal(str(base_val)),
                        success_metric_target=Decimal(str(target_val)),
                        invalidation_floor=Decimal(str(floor_val)),
                        expected_impact_description=f"Destravar {metric_key}",
                        impact_score=impact,
                        confidence_score=conf,
                        ease_score=ease,
                    )
                    st.success(f"Hipótese #{new_h.id} cadastrada com ICE Score de {new_h.ice_score}!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar hipótese: {e}")

        st.divider()

        target_cycle = st.date_input(
            "Ciclo alvo da proposta CDMS",
            value=date.today() - timedelta(days=date.today().weekday()),
            key="proposal_cycle",
        )
        sub_pend, sub_act, sub_hist = st.tabs(["⏳ Pendentes (Ranking ICE)", "🔬 Em Teste (ACTIVE)", "📜 Histórico"])

        with sub_pend:
            st.subheader("Backlog Pendente Priorizado")
            backlog = hypo_uc.get_ranked_backlog()
            if not backlog:
                st.info("Nenhuma hipótese pendente no backlog.")
            else:
                for h in backlog:
                    with st.expander(f"⭐ ICE: {h.ice_score} | [{h.tested_variable.value}] {h.action_description}"):
                        st.write(f"**Meta:** {h.target_metric_key} para {h.success_metric_target}{h.target_metric_unit} (Piso: {h.invalidation_floor}{h.target_metric_unit})")
                        if h.target_cycle_id:
                            st.info(f"Proposta preparada para `{h.target_cycle_id}`. Conclua o ritual no CDMS para ativá-la.")
                        st.write(f"**Parâmetros ICE:** Impacto: {h.impact_score} | Confiança: {h.confidence_score} | Facilidade: {h.ease_score}")

                        c_act, c_disc = st.columns([3, 1])
                        if c_act.button(f"Preparar para Ritual CDMS #{h.id}", key=f"btn_prop_{h.id}"):
                            try:
                                proposal = prop_uc.execute(
                                    hypothesis_id=h.id,
                                    target_cycle_start=target_cycle,
                                )
                                st.success(
                                    f"Proposta #{h.id} preparada para o ciclo `{proposal.target_cycle_id}`. "
                                    "Selecione-a no CDMS e conclua o ritual para iniciar o teste."
                                )
                                st.code(proposal.formal_hypothesis, language="markdown")
                                st.rerun()
                            except ConflictingActiveVariableError as var_err:
                                st.error(f"🛑 Trava de Governança Acionada:\n\n{var_err}")
                            except Exception as e:
                                st.error(f"Erro ao processar ativação: {e}")

                        if c_disc.button("Descartar", key=f"btn_disc_pend_{h.id}"):
                            hypo_uc.discard_hypothesis(h.id)
                            st.warning(f"Hipótese #{h.id} descartada.")
                            st.rerun()

        with sub_act:
            st.subheader("Hipóteses Atualmente em Teste Operacional")
            active_hypotheses = hypo_uc.list_by_status(HypothesisStatus.ACTIVE)
            if not active_hypotheses:
                st.info("Nenhuma hipótese em execução ativa no momento.")
            else:
                for h in active_hypotheses:
                    with st.expander(f"🔵 #{h.id} - [{h.tested_variable.value}] {h.action_description}", expanded=True):
                        decision_badge = f"Decisão CDMS #{h.promoted_decision_id}" if h.promoted_decision_id else "Decisão CDMS não vinculada"
                        st.caption(f"🔗 **Vínculo Operacional:** `{decision_badge}` | **Ciclo:** `{h.target_cycle_id or 'Não definido'}`")
                        st.write(f"**Meta Esperada:** {h.target_metric_key} ≥ {h.success_metric_target}{h.target_metric_unit}")
                        st.write(f"**Piso de Invalidação:** {h.invalidation_floor}{h.target_metric_unit}")

                        if h.promoted_decision_id:
                            st.caption("O resultado deste teste será auditado no próximo ritual CDMS.")
                        col_comp, col_disc = st.columns(2)
                        if col_comp.button("Concluir Teste (COMPLETED)", key=f"btn_comp_{h.id}", type="primary"):
                            hypo_uc.complete_hypothesis(h.id)
                            st.success(f"Hipótese #{h.id} concluída com sucesso!")
                            st.rerun()

                        if col_disc.button("Invalidar / Descartar (DISCARDED)", key=f"btn_disc_act_{h.id}"):
                            hypo_uc.discard_hypothesis(h.id)
                            st.warning(f"Hipótese #{h.id} marcada como descartada.")
                            st.rerun()

        with sub_hist:
            st.subheader("Histórico de Conclusão e Descarte")
            completed = hypo_uc.list_by_status(HypothesisStatus.COMPLETED)
            discarded = hypo_uc.list_by_status(HypothesisStatus.DISCARDED)

            st.markdown(f"**Concluídas ({len(completed)})**")
            for h in completed:
                dec_ref = f" (Decisão CDMS #{h.promoted_decision_id})" if h.promoted_decision_id else ""
                st.caption(f"✅ #{h.id} [{h.tested_variable.value}] {h.action_description}{dec_ref} — ICE: {h.ice_score}")

            st.markdown(f"**Descartadas ({len(discarded)})**")
            for h in discarded:
                dec_ref = f" (Decisão CDMS #{h.promoted_decision_id})" if h.promoted_decision_id else ""
                st.caption(f"❌ #{h.id} [{h.tested_variable.value}] {h.action_description}{dec_ref} — ICE: {h.ice_score}")

    # =========================================================================
    # ABA 3: Configuração de Baseline
    # =========================================================================
    with tabs[2]:
        st.subheader("Definição da Linha de Base Comercial")

        active_bl = repo.get_active_baseline()
        init_ticket = float(active_bl.ticket_price) if active_bl else 150.00
        init_ctr = float(active_bl.expected_ctr_pct) if active_bl else 4.00
        init_conv = float(active_bl.expected_conversion_rate_pct) if active_bl else 8.00
        init_lead_sale = float(active_bl.lead_to_sale_rate_pct) if (active_bl and active_bl.lead_to_sale_rate_pct) else 10.00

        conversion_types = [ct.value for ct in ConversionType]
        init_type_idx = 0
        if active_bl and active_bl.conversion_type.value in conversion_types:
            init_type_idx = conversion_types.index(active_bl.conversion_type.value)

        selected_type = st.selectbox(
            "Tipo de Conversão Comercial",
            conversion_types,
            index=init_type_idx,
            help="DIRECT_SALE para vendas diretas no checkout; LEAD para funis de opt-in com fechamento posterior.",
        )

        with st.form("baseline_form"):
            t_price = st.number_input(
                "Ticket Médio do Produto Final (R$)",
                min_value=1.0,
                value=init_ticket,
                step=10.0,
                format="%.2f",
            )
            e_ctr = st.number_input(
                "CTR Esperado no Tráfego (%)",
                min_value=0.1,
                max_value=100.0,
                value=init_ctr,
                step=0.5,
                format="%.2f",
            )

            if selected_type == ConversionType.LEAD.value:
                e_conv = st.number_input(
                    "Taxa Esperada de Captura de Leads / Cliques (%)",
                    min_value=0.1,
                    max_value=100.0,
                    value=init_conv,
                    step=0.5,
                    format="%.2f",
                    help="Percentual de cliques que se transformam em leads cadastrados.",
                )
                e_lead_sale = st.number_input(
                    "Taxa Esperada de Fechamento Lead → Venda (%)",
                    min_value=0.1,
                    max_value=100.0,
                    value=init_lead_sale,
                    step=0.5,
                    format="%.2f",
                    help="Percentual de leads qualificados que compram o produto.",
                )
            else:
                e_conv = st.number_input(
                    "Taxa de Conversão Esperada Venda Direta / Cliques (%)",
                    min_value=0.1,
                    max_value=100.0,
                    value=init_conv,
                    step=0.5,
                    format="%.2f",
                    help="Percentual de cliques que concluem a compra direta.",
                )
                e_lead_sale = None

            if st.form_submit_button("Salvar Baseline Ativa"):
                try:
                    repo.save_baseline(
                        FunnelBaseline(
                            ticket_price=Decimal(str(t_price)),
                            expected_ctr_pct=Decimal(str(e_ctr)),
                            expected_conversion_rate_pct=Decimal(str(e_conv)),
                            conversion_type=ConversionType(selected_type),
                            lead_to_sale_rate_pct=Decimal(str(e_lead_sale)) if e_lead_sale is not None else None,
                        )
                    )
                    st.success("Nova baseline ativa gravada com sucesso!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar baseline: {e}")

    # =========================================================================
    # ABA 4: Relatório Executivo Consolidado
    # =========================================================================
    with tabs[3]:
        st.subheader("📑 Exportador de Relatório Executivo de Ciclo")
        st.caption("Consolidação formal de auditoria de funil, governança de causalidade e decisões em Markdown.")

        all_audits = repo.list_funnel_audits(limit=50)
        available_cycles = [a.source_cycle_id for a in all_audits]
        today_iso = (date.today() - timedelta(days=date.today().weekday())).isoformat()
        if today_iso not in available_cycles:
            available_cycles.insert(0, today_iso)

        selected_cycle = st.selectbox(
            "Ciclo Alvo do Relatório",
            options=available_cycles,
            index=0,
            help="Selecione o ciclo semanal para compilar o relatório executivo.",
        )

        report = export_uc.execute(cycle_id=selected_cycle)

        col_rep1, col_rep2 = st.columns([3, 1])
        col_rep1.info(
            f"Relatório gerado para o ciclo **`{selected_cycle}`** contendo "
            f"**{report.hypotheses_count}** experimento(s) associado(s)."
        )
        col_rep2.download_button(
            label="⬇️ Baixar Relatório (.md)",
            data=report.markdown_content,
            file_name=f"relatorio_ciclo_{selected_cycle}.md",
            mime="text/markdown",
            type="primary",
            width="stretch",
        )

        with st.expander("👁️ Pré-visualização do Relatório Markdown", expanded=True):
            st.markdown(report.markdown_content)