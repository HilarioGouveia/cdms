"""Página Streamlit do Creator Growth System (CGS) - Gestão de Gargalos e Hipóteses."""

from datetime import date, timedelta
from decimal import Decimal
import streamlit as st

from cgs.adapters.persistence.sqlite_growth_repo import SQLiteGrowthRepository
from cgs.application.use_cases.audit_funnel_opportunity import AuditFunnelOpportunityUseCase
from cgs.application.use_cases.manage_hypotheses import ManageHypothesesUseCase
from cgs.application.use_cases.prepare_cdms_proposal import PrepareCDMSProposalUseCase
from cgs.domain.entities.funnel import ConversionType, FunnelBaseline
from cgs.domain.entities.hypothesis import MetricDirection, VariableType


def render_growth_engine(db_path: str = "data/cdms_dev.db"):
    st.title("🚀 Creator Growth System (CGS)")
    st.caption("Motor de Experimentação Operacional, Diagnóstico de Funil e Ranking ICE")

    repo = SQLiteGrowthRepository(db_path)
    audit_uc = AuditFunnelOpportunityUseCase(repo)
    hypo_uc = ManageHypothesesUseCase(repo)
    prop_uc = PrepareCDMSProposalUseCase(repo)

    tabs = st.tabs(["📊 Diagnóstico de Funil", "💡 Backlog & Ranking ICE", "⚙️ Configuração de Baseline"])

    # ABA 1: Diagnóstico de Funil
    with tabs[0]:
        st.subheader("Auditoria de Oportunidade de Receita")
        active_baseline = repo.get_active_baseline()
        if not active_baseline:
            st.warning("⚠️ Cadastre primeiro uma linha de base na aba 'Configuração de Baseline'.")
        else:
            col1, col2, col3, col4 = st.columns(4)
            source_cycle = col1.date_input("Segunda-feira de Referência", value=date.today() - timedelta(days=7))
            impressions = col2.number_input("Impressões Totais", min_value=0, value=10000, step=500)
            clicks = col3.number_input("Cliques Registados", min_value=0, value=300, step=50)
            conversions = col4.number_input("Conversões Concluídas", min_value=0, value=15, step=5)

            if st.button("Executar Diagnóstico Financeiro", type="primary"):
                try:
                    audit = audit_uc.execute(
                        source_cycle_id=source_cycle.isoformat(),
                        impressions=impressions,
                        clicks=clicks,
                        conversions=conversions,
                    )
                    st.success(audit.diagnosis_summary)
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Gargalo Crítico", audit.primary_bottleneck.value)
                    m2.metric("Oportunidade em Intenção", f"R$ {audit.intention_opportunity_reais:,.2f}")
                    m3.metric("Oportunidade em Conversão", f"R$ {audit.conversion_opportunity_reais:,.2f}")
                    st.info(f"💰 Oportunidade Estimada Total: **R$ {audit.total_opportunity_reais:,.2f}**")
                except Exception as e:
                    st.error(f"Erro ao executar auditoria: {e}")

    # ABA 2: Backlog de Hipóteses e Priorização ICE
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
                except Exception as e:
                    st.error(f"Erro ao salvar hipótese: {e}")

        st.divider()
        st.subheader("Backlog Priorizado por ICE")
        backlog = hypo_uc.get_ranked_backlog()
        if not backlog:
            st.info("Nenhuma hipótese pendente no backlog.")
        else:
            for h in backlog:
                with st.expander(f"⭐ ICE: {h.ice_score} | [{h.tested_variable.value}] {h.action_description}"):
                    st.write(f"**Meta:** {h.target_metric_key} para {h.success_metric_target}{h.target_metric_unit} (Piso: {h.invalidation_floor}{h.target_metric_unit})")
                    st.write(f"**Parâmetros ICE:** Impacto: {h.impact_score} | Confiança: {h.confidence_score} | Facilidade: {h.ease_score}")
                    if st.button(f"Preparar para Ritual CDMS #{h.id}", key=f"btn_prop_{h.id}"):
                        prop = prop_uc.execute(h.id, date.today())
                        st.success("Proposta gerada para o próximo ritual do CDMS!")
                        st.code(prop.formal_hypothesis, language="markdown")

    # ABA 3: Configuração de Baseline
    with tabs[2]:
        st.subheader("Definição da Linha de Base Comercial")
        with st.form("baseline_form"):
            t_price = st.number_input("Ticket Médio (R$)", min_value=1.0, value=120.0, step=10.0)
            e_ctr = st.number_input("CTR Esperado (%)", min_value=0.1, max_value=100.0, value=5.0, step=0.5)
            e_conv = st.number_input("Taxa de Conversão Esperada (%)", min_value=0.1, max_value=100.0, value=10.0, step=0.5)
            c_type = st.selectbox("Tipo de Conversão", [ct.value for ct in ConversionType])
            
            if st.form_submit_button("Salvar Baseline Ativa"):
                repo.save_baseline(
                    FunnelBaseline(
                        ticket_price=Decimal(str(t_price)),
                        expected_ctr_pct=Decimal(str(e_ctr)),
                        expected_conversion_rate_pct=Decimal(str(e_conv)),
                        conversion_type=ConversionType(c_type),
                    )
                )
                st.success("Nova baseline ativa gravada com sucesso!")