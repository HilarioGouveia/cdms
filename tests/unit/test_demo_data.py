from dataclasses import replace
from datetime import date
import hashlib
from uuid import uuid4

import pytest

from cdms.application.demo_data import create_demo_bundle, new_demo_path, scenario_catalog
from cdms.config.container import Container
from cdms.config.settings import settings
from cdms.adapters.persistence.sqlite_repo import SQLiteRepository
from cdms.domain.services.baseline_drift_detector import BaselineDriftDetector
from cgs.adapters.persistence.sqlite_growth_repo import SQLiteGrowthRepository


def test_catalog_covers_all_combinations_and_unavailable_metrics():
    examples = scenario_catalog()
    assert len(examples) == 85
    assert len({item["code"] for item in examples[:81]}) == 81
    assert all(snapshot.is_available for item in examples[:81] for snapshot in item["snapshots"])
    assert all(sum(not snapshot.is_available for snapshot in item["snapshots"]) == 1 for item in examples[81:])
    assert {item["scenario"].type.value for item in examples} == {
        "PRE_DROP", "ANOMALY", "SCALE", "STABILITY", "INCONCLUSIVE",
    }


def test_tour_has_real_links_all_outcomes_and_isolated_repeatable_generations(tmp_path):
    config = replace(settings, DATA_DIR=tmp_path, DB_PATH=tmp_path / "real.db")
    Container(app_settings=config)
    before = hashlib.sha256(config.DB_PATH.read_bytes()).hexdigest()
    session = uuid4().hex
    bundle = create_demo_bundle(config, session, date(2026, 11, 9), "Cobertura completa")
    core = SQLiteRepository(bundle.db_path)
    growth = SQLiteGrowthRepository(str(bundle.db_path))
    rituals = core.list_rituals(limit=100)
    hypotheses = growth.list_hypotheses(limit=100)
    assert len(rituals) == 12
    assert len(growth.list_funnel_audits()) == 12
    assert len(hypotheses) == 18
    assert {ritual.scenario.type.value for ritual in rituals} == {
        "PRE_DROP", "ANOMALY", "SCALE", "STABILITY", "INCONCLUSIVE",
    }
    assert {ritual.learning.outcome.value for ritual in rituals if ritual.learning} == {
        "ACHIEVED", "PARTIAL", "NOT_ACHIEVED", "INCONCLUSIVE",
    }
    for ritual in rituals:
        linked = growth.get_hypothesis_by_id(ritual.decision.source_hypothesis_id)
        assert linked.promoted_decision_id == ritual.decision.id
        assert linked.target_cycle_id == ritual.cycle_id
    assert len([ritual for ritual in rituals if ritual.learning]) == 11
    assert BaselineDriftDetector.audit_drift(rituals[:8], min_consecutive_cycles=4)
    assert {item.primary_bottleneck.value for item in growth.list_funnel_audits()} == {
        "NONE", "ATTENTION", "INTENTION", "CONVERSION", "LEAD_CAPTURE", "LEAD_CLOSING",
    }
    again = create_demo_bundle(config, session, date(2026, 11, 9), "Cobertura completa")
    assert again.db_path != bundle.db_path
    assert again.manifest == bundle.manifest
    assert again.db_path.exists() and bundle.db_path.exists()
    assert hashlib.sha256(config.DB_PATH.read_bytes()).hexdigest() == before
    assert not SQLiteRepository(config.DB_PATH).list_rituals()


def test_demo_rejects_arbitrary_paths_dates_and_packages(tmp_path):
    config = replace(settings, DATA_DIR=tmp_path, DB_PATH=tmp_path / "real.db")
    with pytest.raises(ValueError):
        new_demo_path(config, "../../real.db")
    with pytest.raises(ValueError):
        create_demo_bundle(config, uuid4().hex, date(2026, 11, 10), "Tour guiado")
    with pytest.raises(ValueError):
        create_demo_bundle(config, uuid4().hex, date(2026, 11, 9), "custom")


def test_demo_finance_and_offline_import_pipeline_without_credentials(tmp_path,monkeypatch):
    from cgs.adapters.persistence.sqlite_cgs_fase2_repo import SQLiteCGSPhase2Repository
    from cdms.adapters.persistence.sqlite_ingestion_repo import SQLiteIngestionRepository
    from cdms.application.demo_ingestion import DemoPlatformIngestion
    import requests
    def forbidden(*args,**kwargs):
        raise AssertionError('A demonstração não pode chamar serviços externos.')
    monkeypatch.setattr(requests,'get',forbidden)
    monkeypatch.setattr('cdms.adapters.tasks.ingestion_runtime.dispatch_job',forbidden)
    monkeypatch.delenv('CDMS_CREDENTIAL_KEY',raising=False)
    config=replace(settings,DATA_DIR=tmp_path,DB_PATH=tmp_path/'real.db')
    Container(app_settings=config)
    before=hashlib.sha256(config.DB_PATH.read_bytes()).hexdigest()
    bundle=create_demo_bundle(config,uuid4().hex,date(2026,11,9),'Tour guiado')
    finance=SQLiteCGSPhase2Repository(bundle.db_path)
    ingestion=SQLiteIngestionRepository(bundle.db_path)
    counts=bundle.manifest['counts']
    assert counts['budgets']==counts['ab_evaluations']==13
    assert counts['simulated_jobs']==len(ingestion.list_jobs())==15
    assert len(ingestion.list_connections())==3
    budgets=[b for cycle in [*(r['cycle'] for r in bundle.manifest['cycles']),bundle.manifest['sandbox_cycle']]
             for b in finance.list_budgets_by_cycle(cycle)]
    assert len(budgets)==13
    assert any(b.spent_amount_cents>b.allocated_amount_cents for b in budgets)
    verdicts={finance.get_evaluation_by_hypothesis(r['hypothesis_id'],r['cycle']).verdict.value
              for r in bundle.manifest['cycles']}
    assert verdicts=={'STATISTICALLY_SIGNIFICANT','EARLY_STOPPED_HIGH_LOSS','INCONCLUSIVE_INSUFFICIENT_SAMPLE'}
    cycle=bundle.manifest['sandbox_cycle']
    core=SQLiteRepository(bundle.db_path)
    assert core.get_ritual_by_cycle(cycle) is None
    jobs=[j for j in ingestion.list_jobs() if j['cycle_id']==cycle]
    assert {j['status'] for j in jobs}=={'SUCCESS','PENDING','FAILED'}
    service=DemoPlatformIngestion(bundle.db_path,tmp_path/'demo')
    success=next(j for j in jobs if j['status']=='SUCCESS')
    batch=service.prepare_ritual(success['id'],core)
    assert batch['simulated'] and batch['metrics']['avg_retention_pct'] is None
    pending=next(j for j in jobs if j['status']=='PENDING')
    assert service.complete_pending(pending['id'])['status']=='SUCCESS'
    failed=next(j for j in jobs if j['status']=='FAILED')
    assert service.enqueue(failed['connection_id'],cycle,retry_failed=True)[0]['status']=='SUCCESS'
    old=success['id']
    fresh,_=service.enqueue(success['connection_id'],cycle,force_refresh=True)
    assert fresh['id']!=old and ingestion.get_batch(old)['simulated']
    closed=next(j for j in ingestion.list_jobs() if j['cycle_id']!=cycle)
    with pytest.raises(ValueError):
        service.prepare_ritual(closed['id'],core)
    with pytest.raises(ValueError):
        DemoPlatformIngestion(config.DB_PATH,tmp_path/'demo')
    assert hashlib.sha256(config.DB_PATH.read_bytes()).hexdigest()==before
