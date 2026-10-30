from datetime import date
from decimal import Decimal
from types import SimpleNamespace as NS

import pytest

from cdms.application.use_cases.generate_cycle_story import GenerateCycleStoryUseCase, StoryAudience, safe_markdown
from cdms.domain.entities.learning import Learning, HypothesisOutcome
from cgs.domain.entities.funnel import FunnelOpportunityAudit, FunnelStage

CYCLE = "2026-11-02"


def fixtures(outcome=None, stage=FunnelStage.INTENTION, amount="1234.56"):
    decision = NS(id=42, cycle_id=CYCLE, summary="Ação interna CONFIDENCIAL",
                  hypothesis="Hipótese interna", success_criterion="CTR ≥ 4%",
                  evaluation_due_date=date(2026, 11, 9), owner="Pessoa privada")
    previous = Learning(9, 10, "Decisão anterior", HypothesisOutcome.ACHIEVED, "NOTA DO CICLO ANTERIOR")
    ritual = NS(cycle_id=CYCLE, decision=decision, learning=previous,
                rules_version="2.3.1", scenario=NS(type=NS(value="PRE_DROP")))
    learning = Learning(11, 42, decision.summary, outcome, "NOTA INTERNA") if outcome else None
    audit = FunnelOpportunityAudit(CYCLE, stage, Decimal(amount), Decimal("0"), Decimal(amount), "Resumo")
    calls = []
    def get_learning(decision_id):
        calls.append(decision_id)
        return learning
    core = NS(get_ritual_by_cycle=lambda cycle: ritual, get_learning_by_decision_id=get_learning)
    growth = NS(get_funnel_audit=lambda cycle: audit)
    return core, growth, ritual, learning, calls


@pytest.mark.parametrize("audience", list(StoryAudience))
def test_missing_data_never_becomes_a_success(audience):
    core = NS(get_ritual_by_cycle=lambda cycle: None)
    growth = NS(get_funnel_audit=lambda cycle: None)
    story = GenerateCycleStoryUseCase(core, growth).execute(CYCLE, audience)
    assert "Não há diagnóstico" in story.blocks[0].text
    assert "Não há decisão" in story.blocks[1].text
    assert "Sem resultado auditado" in story.blocks[2].text
    assert all(block.sources for block in story.blocks)
    assert "variante vencedora" not in story.markdown


def test_pending_uses_current_decision_query_not_learning_of_previous_cycle():
    core, growth, ritual, _, calls = fixtures()
    story = GenerateCycleStoryUseCase(core, growth).execute(CYCLE)
    assert calls == [42]
    assert "Aguardando avaliação" in story.blocks[2].text
    assert "NOTA DO CICLO ANTERIOR" not in story.markdown
    assert "R$ 1.234,56" in story.blocks[0].text
    assert "Critério de sucesso: CTR ≥ 4%" in story.blocks[1].text
    assert "execução na plataforma" in story.blocks[1].text


@pytest.mark.parametrize("outcome", list(HypothesisOutcome))
def test_all_audited_outcomes_are_described_as_recorded_not_causal_proof(outcome):
    core, growth, _, _, _ = fixtures(outcome)
    story = GenerateCycleStoryUseCase(core, growth).execute(CYCLE, StoryAudience.OPERATOR)
    assert "NOTA INTERNA" in story.blocks[2].text
    assert "não comprova" in story.blocks[2].text
    assert "Pessoa privada" in story.blocks[1].text
    assert "decisão #42" in story.blocks[2].sources[0]
    assert "incremento de" not in story.markdown


def test_communication_is_allowlisted_and_demo_export_is_labeled():
    core, growth, _, _, _ = fixtures(HypothesisOutcome.ACHIEVED)
    story = GenerateCycleStoryUseCase(core, growth).execute(CYCLE, StoryAudience.COMMUNICATION, simulated=True)
    for secret in ("CONFIDENCIAL", "Hipótese interna", "CTR ≥ 4%", "Pessoa privada", "NOTA INTERNA", "1.234", "R$"):
        assert secret not in story.markdown
    assert "DADOS SIMULADOS" in story.markdown
    assert "Meta atingida" in story.blocks[2].text
    assert "Fontes:" in story.markdown


def test_zero_opportunity_is_preserved_and_distinct_from_missing():
    core, growth, _, _, _ = fixtures(stage=FunnelStage.NONE, amount="0")
    story = GenerateCycleStoryUseCase(core, growth).execute(CYCLE)
    assert "R$ 0,00" in story.blocks[0].text
    assert "nenhum gargalo crítico" in story.blocks[0].text


@pytest.mark.parametrize("cycle", ["2026-11-03", "2026-11-2", "invalid"])
def test_invalid_cycles_are_rejected(cycle):
    with pytest.raises(ValueError):
        GenerateCycleStoryUseCase(NS(), NS()).execute(cycle)


def test_invalid_audience_and_mismatched_evidence_are_rejected():
    core, growth, ritual, learning, _ = fixtures(HypothesisOutcome.ACHIEVED)
    with pytest.raises(ValueError):
        GenerateCycleStoryUseCase(core, growth).execute(CYCLE, "unknown")
    learning.target_decision_id = 99
    with pytest.raises(ValueError, match="Aprendizado"):
        GenerateCycleStoryUseCase(core, growth).execute(CYCLE)
    ritual.cycle_id = "2026-10-26"
    with pytest.raises(ValueError, match="Decisão"):
        GenerateCycleStoryUseCase(core, growth).execute(CYCLE)


def test_recorded_content_cannot_inject_html_or_markdown_in_preview_or_export():
    core, growth, ritual, _, _ = fixtures()
    ritual.decision.summary = "<script>alert(1)</script> ![image](https://example.com)"
    story = GenerateCycleStoryUseCase(core, growth).execute(CYCLE)
    assert "<script>" not in story.markdown
    assert "![image](" not in story.markdown
    assert safe_markdown(ritual.decision.summary) in story.markdown


def test_real_demo_links_and_read_only_generation(tmp_path):
    from dataclasses import replace
    import hashlib
    from uuid import uuid4
    from cdms.application.demo_data import create_demo_bundle
    from cdms.config.settings import settings
    from cdms.adapters.persistence.sqlite_repo import SQLiteRepository
    from cgs.adapters.persistence.sqlite_growth_repo import SQLiteGrowthRepository
    config = replace(settings, DATA_DIR=tmp_path, DB_PATH=tmp_path / "local.db")
    bundle = create_demo_bundle(config, uuid4().hex, date(2026, 11, 9), "Tour guiado")
    before = hashlib.sha256(bundle.db_path.read_bytes()).hexdigest()
    core, growth = SQLiteRepository(bundle.db_path), SQLiteGrowthRepository(str(bundle.db_path))
    use_case = GenerateCycleStoryUseCase(core, growth)
    for ritual in core.list_rituals(limit=100):
        story = use_case.execute(ritual.cycle_id)
        learning = core.get_learning_by_decision_id(ritual.decision.id)
        assert ("Aguardando avaliação" in story.blocks[2].text) == (learning is None)
        if learning:
            assert str(learning.id) in story.blocks[2].sources[0]
    assert hashlib.sha256(bundle.db_path.read_bytes()).hexdigest() == before
