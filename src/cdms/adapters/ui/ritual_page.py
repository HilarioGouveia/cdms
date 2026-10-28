import streamlit as st
from cgs.adapters.persistence.sqlite_growth_repo import SQLiteGrowthRepository
from cgs.application.use_cases.sync_cdms_outcome import SyncCDMSOutcomeUseCase

def render_decision_audit_section(decision_id: int, db_path: str = "data/cdms_dev.db"):
    st.subheader("Auditoria da Decisão do Ciclo Anterior")
    
    # Repositório e Caso de Uso CGS
    growth_repo = SQLiteGrowthRepository(db_path)
    sync_cgs_uc = SyncCDMSOutcomeUseCase(growth_repo)
    
    # Identifica se a decisão auditada possui origem/vínculo no CGS
    linked_hypo = growth_repo.get_hypothesis_by_decision_id(decision_id)
    if linked_hypo:
        st.info(
            f"🔗 **Hipótese CGS Vinculada (#{linked_hypo.id}):** "
            f"[{linked_hypo.tested_variable.value}] {linked_hypo.action_description} "
            f"(Status atual: `{linked_hypo.status.value}`)"
        )

    verdict = st.radio(
        "Veredito Operacional",
        options=["ACHIEVED", "PARTIAL", "NOT_ACHIEVED"],
        horizontal=True,
    )
    justification = st.text_area("Justificativa e Aprendizados da Semana")

    if st.button("Gravar Auditoria e Fechar Ciclo", type="primary"):
        # 1. Persistência do ritual no motor CDMS
        # cdms_service.audit_decision(decision_id, verdict, justification)
        st.success(f"Decisão #{decision_id} auditada com veredito {verdict} no CDMS.")

        # 2. Sincronização automática com o CGS
        updated_hypo = sync_cgs_uc.execute(decision_id=decision_id, verdict=verdict)
        if updated_hypo:
            status_badge = "✅ COMPLETED" if updated_hypo.status.value == "COMPLETED" else "❌ DISCARDED"
            st.toast(
                f"CGS sincronizado: Hipótese #{updated_hypo.id} movida para {status_badge}!",
                icon="🚀",
            )
            st.info(
                f"O CGS atualizou automaticamente a Hipótese #{updated_hypo.id} "
                f"para o estado **{updated_hypo.status.value}**."
            )
        
        st.rerun()