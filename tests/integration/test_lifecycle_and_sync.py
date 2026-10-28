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


@pytest.mark.parametrize("outcome, expected_status", [
    ("ACHIEVED", "COMPLETED"), ("PARTIAL", "COMPLETED"),
    ("NOT_ACHIEVED", "DISCARDED"), ("INCONCLUSIVE", "ACTIVE"),
])
def test_prepare_proposal_and_bidirectional_cdms_sync(temp_repo, outcome, expected_status):
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
    )
    assert proposal.target_cycle_id == "2026-10-26"
    assert "\n" in proposal.formal_hypothesis
    assert "\\n" not in proposal.formal_hypothesis
    assert temp_repo.get_hypothesis_by_id(h.id).status == HypothesisStatus.PENDING

    # A decisão canônica é criada apenas ao fechar o ritual, na mesma transação do vínculo.
    from pathlib import Path
    from cdms.config.container import Container
    from cdms.adapters.ui.components.metric_inputs import CANONICAL_DEFINITIONS, DEFAULT_CALIBRATIONS
    from cdms.domain.entities.metric import MetricSnapshot
    from cdms.domain.entities.learning import HypothesisOutcome
    cdms = Container(db_path=Path(temp_repo._db_path))
    snapshots = [MetricSnapshot(d, DEFAULT_CALIBRATIONS[d.key], 20.0) for d in CANONICAL_DEFINITIONS]
    record = cdms.run_weekly_ritual_use_case.execute(
        week_start=date(2026, 10, 26), snapshots=snapshots,
        decision_summary=h.action_description, decision_hypothesis=h.expected_impact_description,
        decision_success_criterion="Fechamento >= 14%", decision_evaluation_due_date=date(2026, 11, 2),
        source_hypothesis_id=h.id,
    )
    reloaded_hypo = temp_repo.get_hypothesis_by_id(h.id)
    assert reloaded_hypo.status == HypothesisStatus.ACTIVE
    assert reloaded_hypo.promoted_decision_id == record.decision.id
    assert cdms.repository.get_ritual_by_cycle("2026-10-26").decision.source_hypothesis_id == h.id

    cdms.run_weekly_ritual_use_case.execute(
        week_start=date(2026, 11, 2), snapshots=snapshots,
        decision_summary="Próximo teste", decision_hypothesis="Novo ângulo aumenta alcance",
        decision_success_criterion="Alcance >= 1500", decision_evaluation_due_date=date(2026, 11, 9),
        target_decision_id=record.decision.id, learning_outcome=HypothesisOutcome(outcome),
        learning_evidence_notes="Fechamento observado de 15%", evaluation_as_of=date(2026, 11, 2),
    )
    assert temp_repo.get_hypothesis_by_id(h.id).status == HypothesisStatus(expected_status)


def test_failed_ritual_rolls_back_hypothesis_activation(temp_repo):
    import sqlite3
    from pathlib import Path
    from cdms.config.container import Container
    from cdms.adapters.ui.components.metric_inputs import CANONICAL_DEFINITIONS, DEFAULT_CALIBRATIONS
    from cdms.domain.entities.metric import MetricSnapshot

    cdms = Container(db_path=Path(temp_repo._db_path))
    h = ManageHypothesesUseCase(temp_repo).create_hypothesis(
        action_description="Testar CTA", tested_variable=VariableType.CTA,
        target_metric_key="ctr_pct", target_metric_unit="%",
        metric_direction=MetricDirection.HIGHER_IS_BETTER,
        baseline_reference_value=Decimal("3"), success_metric_target=Decimal("5"),
        invalidation_floor=Decimal("2"), expected_impact_description="Aumentar cliques",
        impact_score=8, confidence_score=8, ease_score=8,
    )
    PrepareCDMSProposalUseCase(temp_repo).execute(h.id, date(2026, 10, 26))
    with temp_repo._get_connection() as conn:
        conn.execute("""CREATE TRIGGER reject_snapshot BEFORE INSERT ON metric_snapshots
                        BEGIN SELECT RAISE(ABORT, 'simulated persistence failure'); END""")
    snapshots = [MetricSnapshot(d, DEFAULT_CALIBRATIONS[d.key], 20.0) for d in CANONICAL_DEFINITIONS]
    with pytest.raises(sqlite3.IntegrityError, match="simulated persistence failure"):
        cdms.run_weekly_ritual_use_case.execute(
            week_start=date(2026, 10, 26), snapshots=snapshots,
            decision_summary="Testar CTA", decision_hypothesis="Aumentar cliques",
            decision_success_criterion="CTR >= 5%", decision_evaluation_due_date=date(2026, 11, 2),
            source_hypothesis_id=h.id,
        )
    assert cdms.repository.get_ritual_by_cycle("2026-10-26") is None
    pending = temp_repo.get_hypothesis_by_id(h.id)
    assert pending.status == HypothesisStatus.PENDING
    assert pending.promoted_decision_id is None
    with temp_repo._get_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == 0


def test_proposal_requires_monday_and_preserves_canonical_decisions_schema(temp_repo):
    from pathlib import Path
    from cdms.adapters.persistence.sqlite_repo import SQLiteRepository
    cdms = SQLiteRepository(Path(temp_repo._db_path))
    with pytest.raises(ValueError, match="segunda-feira"):
        PrepareCDMSProposalUseCase(temp_repo).execute(1, date(2026, 10, 28))
    with temp_repo._get_connection() as conn:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(decisions)")}
        assert {"ritual_id", "summary", "success_criterion", "cgs_hypothesis_id"} <= columns
        assert conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == 0


def test_existing_cdms_database_is_upgraded_without_losing_rituals(tmp_path):
    from cdms.adapters.persistence.sqlite_repo import SQLiteRepository
    from cdms.config.container import Container
    from cdms.adapters.ui.components.metric_inputs import CANONICAL_DEFINITIONS, DEFAULT_CALIBRATIONS
    from cdms.domain.entities.metric import MetricSnapshot
    db_path = tmp_path / "existing.db"
    container = Container(db_path=db_path)
    record = container.run_weekly_ritual_use_case.execute(
        week_start=date(2026, 10, 26),
        snapshots=[MetricSnapshot(d, DEFAULT_CALIBRATIONS[d.key], 20.0) for d in CANONICAL_DEFINITIONS],
        decision_summary="Decisão existente", decision_hypothesis="Hipótese existente",
        decision_success_criterion="CTR >= 5%", decision_evaluation_due_date=date(2026, 11, 2),
    )
    with container.repository._connection() as conn:
        conn.execute("ALTER TABLE decisions DROP COLUMN cgs_hypothesis_id")
        conn.commit()
    migrated = SQLiteRepository(db_path)
    loaded = migrated.get_ritual_by_cycle(record.cycle_id)
    assert loaded.decision.summary == "Decisão existente"
    assert loaded.decision.source_hypothesis_id is None
    assert SQLiteRepository(db_path).get_ritual_by_cycle(record.cycle_id).id == record.id


def test_variable_conflict_at_commit_does_not_leave_partial_ritual(temp_repo):
    from pathlib import Path
    from cdms.config.container import Container
    from cdms.adapters.ui.components.metric_inputs import CANONICAL_DEFINITIONS, DEFAULT_CALIBRATIONS
    from cdms.domain.entities.metric import MetricSnapshot
    cdms = Container(db_path=Path(temp_repo._db_path))
    manager = ManageHypothesesUseCase(temp_repo)
    kwargs = dict(
        action_description="Testar CTA", tested_variable=VariableType.CTA,
        target_metric_key="ctr_pct", target_metric_unit="%", metric_direction=MetricDirection.HIGHER_IS_BETTER,
        baseline_reference_value=Decimal("3"), success_metric_target=Decimal("5"),
        invalidation_floor=Decimal("2"), expected_impact_description="Aumentar cliques",
        impact_score=8, confidence_score=8, ease_score=8,
    )
    candidate = manager.create_hypothesis(**kwargs)
    competitor = manager.create_hypothesis(**kwargs)
    PrepareCDMSProposalUseCase(temp_repo).execute(candidate.id, date(2026, 10, 26))
    manager.activate_hypothesis(competitor.id, target_cycle_id="2026-10-26")
    with pytest.raises(ValueError, match="hipótese ativa"):
        cdms.run_weekly_ritual_use_case.execute(
            week_start=date(2026, 10, 26),
            snapshots=[MetricSnapshot(d, DEFAULT_CALIBRATIONS[d.key], 20.0) for d in CANONICAL_DEFINITIONS],
            decision_summary="Testar CTA", decision_hypothesis="Aumentar cliques",
            decision_success_criterion="CTR >= 5%", decision_evaluation_due_date=date(2026, 11, 2),
            source_hypothesis_id=candidate.id,
        )
    assert not cdms.repository.list_rituals()
    assert temp_repo.get_hypothesis_by_id(candidate.id).status == HypothesisStatus.PENDING
    assert temp_repo.get_hypothesis_by_id(competitor.id).status == HypothesisStatus.ACTIVE
