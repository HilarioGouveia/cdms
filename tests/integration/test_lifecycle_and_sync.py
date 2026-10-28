"""Testes de Integração e Domínio: Ciclo de Vida, Trava Causal e Sincronização CDMS."""

import gc
import os
import tempfile
import time
import pytest


from datetime import date
from decimal import Decimal


from cgs.adapters.persistence.sqlite_growth_repo import SQLiteGrowthRepository
from cgs.application.use_cases.audit_funnel_opportunity import AuditFunnelOpportunityUseCase
from cgs.application.use_cases.manage_hypotheses import ManageHypothesesUseCase
from cgs.application.use_cases.prepare_cdms_proposal import PrepareCDMSProposalUseCase
from cgs.application.use_cases.sync_cdms_outcome import CDMSDecisionVerdict, SyncCDMSOutcomeUseCase
from cgs.domain.entities.funnel import ConversionType, FunnelBaseline, FunnelStage
from cgs.domain.entities.hypothesis import (
    ConflictingActiveVariableError,
    HypothesisStatus,
    MetricDirection,
    VariableType,
)


@pytest.fixture
def temp_repo():
    """Gera um repositório isolado em banco temporário, liberando conexões no Windows."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    repo = SQLiteGrowthRepository(path)
    
    yield repo

    # Teardown seguro para evitar WinError 32 no Windows
    del repo
    gc.collect()

    for _ in range(5):
        try:
            if os.path.exists(path):
                os.remove(path)
            break
        except PermissionError:
            time.sleep(0.05)
            gc.collect()


def test_hypothesis_state_machine_and_transitions(temp_repo):
    """Garante que as transições ricas de estado respeitam o ciclo PENDING -> ACTIVE -> COMPLETED/DISCARDED."""
    hypo_uc = ManageHypothesesUseCase(temp_repo)

    # 1. Criação no estado PENDING
    h = hypo_uc.create_hypothesis(
        action_description="Inserir CTA claro aos 5s",
        tested_variable=VariableType.CTA,
        target_metric_key="ctr_pct",
        target_metric_unit="%",
        metric_direction=MetricDirection.HIGHER_IS_BETTER,
        baseline_reference_value=Decimal("2.5"),
        success_metric_target=Decimal("4.0"),
        invalidation_floor=Decimal("1.8"),
        expected_impact_description="Aumentar intenção",
        impact_score=8,
        confidence_score=7,
        ease_score=9,
    )
    assert h.id is not None
    assert h.status == HypothesisStatus.PENDING

    # 2. Ativação segura
    activated = hypo_uc.activate_hypothesis(h.id, target_cycle_id="2026-10-26", promoted_decision_id=101)
    assert activated.status == HypothesisStatus.ACTIVE
    assert activated.target_cycle_id == "2026-10-26"
    assert activated.promoted_decision_id == 101

    # 3. Conclusão do teste
    completed = hypo_uc.complete_hypothesis(h.id)
    assert completed.status == HypothesisStatus.COMPLETED

    # 4. Violação de máquina de estados: não pode reativar uma hipótese concluída
    with pytest.raises(ValueError, match="Apenas hipóteses PENDING podem ser ativadas"):
        completed.activate(target_cycle_id="2026-11-02")


def test_unique_variable_rule_governance_lock(temp_repo):
    """Impede que duas hipóteses testem a mesma variável única concorrentemente no mesmo ciclo."""
    hypo_uc = ManageHypothesesUseCase(temp_repo)

    # Criação de duas hipóteses isoladas para LANDING_PAGE
    h1 = hypo_uc.create_hypothesis(
        action_description="Refatorar hero section da landing page",
        tested_variable=VariableType.LANDING_PAGE,
        target_metric_key="lead_capture_pct",
        target_metric_unit="%",
        metric_direction=MetricDirection.HIGHER_IS_BETTER,
        baseline_reference_value=Decimal("15.0"),
        success_metric_target=Decimal("25.0"),
        invalidation_floor=Decimal("12.0"),
        expected_impact_description="Reduzir bounce rate",
        impact_score=8,
        confidence_score=8,
        ease_score=6,
    )
    h2 = hypo_uc.create_hypothesis(
        action_description="Reduzir campos do formulário para 2 inputs",
        tested_variable=VariableType.LANDING_PAGE,
        target_metric_key="lead_capture_pct",
        target_metric_unit="%",
        metric_direction=MetricDirection.HIGHER_IS_BETTER,
        baseline_reference_value=Decimal("15.0"),
        success_metric_target=Decimal("28.0"),
        invalidation_floor=Decimal("14.0"),
        expected_impact_description="Aumentar submissões",
        impact_score=9,
        confidence_score=7,
        ease_score=9,
    )

    cycle_target = "2026-10-26"

    # Ativa a primeira com sucesso
    hypo_uc.activate_hypothesis(h1.id, target_cycle_id=cycle_target)

    # A segunda tentativa no mesmo ciclo com a mesma variável DEVE ser bloqueada
    with pytest.raises(ConflictingActiveVariableError) as exc_info:
        hypo_uc.activate_hypothesis(h2.id, target_cycle_id=cycle_target)

    assert exc_info.value.variable == VariableType.LANDING_PAGE
    assert exc_info.value.active_hypothesis_id == h1.id


def test_lead_funnel_two_step_audit_and_history(temp_repo):
    """Valida o diagnóstico de 2 passos (opt-in e fechamento comercial) e o histórico consolidado."""
    # Linha de base para funil LEAD
    baseline = FunnelBaseline(
        ticket_price=Decimal("197.00"),
        expected_ctr_pct=Decimal("4.00"),
        expected_conversion_rate_pct=Decimal("20.00"),  # Taxa cliques -> leads
        conversion_type=ConversionType.LEAD,
        lead_to_sale_rate_pct=Decimal("10.00"),         # Taxa leads -> vendas
    )
    temp_repo.save_baseline(baseline)

    audit_uc = AuditFunnelOpportunityUseCase(temp_repo)

    # Ciclo 1: Gargalo na captura de leads
    # 10.000 imp, 400 cliques (CTR 4.0% em linha), mas apenas 40 leads (10% vs 20% meta) e 4 vendas
    audit_c1 = audit_uc.execute(
        source_cycle_id="2026-W43",
        impressions=10000,
        clicks=400,
        leads=40,
        conversions=4,
    )
    assert audit_c1.primary_bottleneck == FunnelStage.LEAD_CAPTURE
    assert audit_c1.leads_opportunity_reais is not None
    assert audit_c1.leads_opportunity_reais > Decimal("0")
    assert audit_c1.total_opportunity_reais > Decimal("0")

    # Ciclo 2: Otimização bem-sucedida (redução de desperdício)
    # 10.000 imp, 400 cliques, 80 leads (20% exato) e 8 vendas (10% exato)
    audit_c2 = audit_uc.execute(
        source_cycle_id="2026-W44",
        impressions=10000,
        clicks=400,
        leads=80,
        conversions=8,
    )
    assert audit_c2.primary_bottleneck == FunnelStage.NONE
    assert audit_c2.total_opportunity_reais == Decimal("0.00")

    # Auditoria de histórico ordenado
    history = audit_uc.get_audit_history(limit=10)
    assert len(history) == 2
    assert history[0].source_cycle_id == "2026-W44"
    assert history[1].source_cycle_id == "2026-W43"


def test_prepare_proposal_and_bidirectional_cdms_sync(temp_repo):
    """Valida a injeção do ID da decisão CDMS e o fechamento do loop com sincronização de veredito."""
    hypo_uc = ManageHypothesesUseCase(temp_repo)
    prop_uc = PrepareCDMSProposalUseCase(growth_repository=temp_repo)
    sync_uc = SyncCDMSOutcomeUseCase(temp_repo)

    # 1. Cria hipótese
    h = hypo_uc.create_hypothesis(
        action_description="Oferta com bônus de onboarding",
        tested_variable=VariableType.OFFER,
        target_metric_key="lead_to_sale_pct",
        target_metric_unit="%",
        metric_direction=MetricDirection.HIGHER_IS_BETTER,
        baseline_reference_value=Decimal("8.0"),
        success_metric_target=Decimal("14.0"),
        invalidation_floor=Decimal("6.0"),
        expected_impact_description="Aumentar fechamento",
        impact_score=9,
        confidence_score=7,
        ease_score=8,
    )

    # 2. Prepara proposta para ritual do CDMS
    proposal = prop_uc.execute(
        hypothesis_id=h.id,
        target_cycle_start=date(2026, 10, 26),
        auto_activate=True,
    )
    assert proposal.promoted_decision_id is not None
    assert proposal.promoted_decision_id > 0

    # Verifica se o CGS vinculou o promoted_decision_id e ativou a hipótese
    reloaded_hypo = temp_repo.get_hypothesis_by_id(h.id)
    assert reloaded_hypo.status == HypothesisStatus.ACTIVE
    assert reloaded_hypo.promoted_decision_id == proposal.promoted_decision_id

    # 3. Simula auditoria do ritual CDMS: Decisão atinge o objetivo (ACHIEVED)
    updated_hypo = sync_uc.execute(
        decision_id=proposal.promoted_decision_id,
        verdict=CDMSDecisionVerdict.ACHIEVED.value,
    )
    assert updated_hypo is not None
    assert updated_hypo.status == HypothesisStatus.COMPLETED

    # 4. Confirmação na persistência
    persisted_hypo = temp_repo.get_hypothesis_by_id(h.id)
    assert persisted_hypo.status == HypothesisStatus.COMPLETED