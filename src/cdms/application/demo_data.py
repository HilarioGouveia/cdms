"""Pacotes simulados determinísticos, gerados apenas em bancos de demonstração novos."""
from collections import Counter
from dataclasses import dataclass, replace
from datetime import date, timedelta
from decimal import Decimal
from itertools import product
import json
from pathlib import Path
from uuid import UUID, uuid4

from cdms.config.container import Container
from cdms.domain.entities.learning import HypothesisOutcome
from cdms.domain.entities.metric import MetricSnapshot
from cdms.domain.services.canonical_metrics import CANONICAL_DEFINITIONS, DEFAULT_CALIBRATIONS
from cdms.domain.services.scenario_classifier import ScenarioClassifier
from cgs.adapters.persistence.sqlite_growth_repo import SQLiteGrowthRepository
from cgs.application.use_cases.audit_funnel_opportunity import AuditFunnelOpportunityUseCase
from cgs.application.use_cases.manage_hypotheses import ManageHypothesesUseCase
from cgs.application.use_cases.prepare_cdms_proposal import PrepareCDMSProposalUseCase
from cgs.domain.entities.funnel import ConversionType, FunnelBaseline
from cgs.domain.entities.hypothesis import HypothesisStatus, MetricDirection, VariableType


VERSION = "2.0"
PACKAGES = ("Tour guiado", "Cobertura completa")
PATTERNS = (
    "HHHH", "BBBB", "BAHH", "AAAA", "BHHH", "HUHH",
    "UUUU", "BBBB", "AAAA", "AAAA", "AAAA", "AAAA",
)
TITLES = (
    "Estabilidade operacional", "Risco de queda", "Assimetria do funil",
    "Escala com referências superadas", "Indicador isolado em desvio",
    "Falha de rastreamento da retenção", "Sem exposição no ciclo",
    "Recuperação após queda", "Escala sustentada 1", "Escala sustentada 2",
    "Escala sustentada 3", "Escala sustentada 4 e recalibração",
)


def snapshots_for(pattern):
    snapshots = []
    for definition, status in zip(CANONICAL_DEFINITIONS, pattern, strict=True):
        calibration = DEFAULT_CALIBRATIONS[definition.key]
        values = {"B": calibration.healthy_min / 2,
                  "H": (calibration.healthy_min + calibration.healthy_max) / 2,
                  "A": calibration.healthy_max * 1.5}
        reason = "NO_EXPOSURE" if pattern == "UUUU" else "TRACKING_ERROR"
        snapshots.append(MetricSnapshot(
            definition=definition, calibration=calibration,
            observed_value=None if status == "U" else values[status],
            is_available=status != "U", unavailability_reason=reason if status == "U" else None,
        ))
    return snapshots


def scenario_catalog():
    classifier = ScenarioClassifier()
    patterns = ["".join(items) for items in product("BHA", repeat=4)]
    patterns += ["H" * index + "U" + "H" * (3 - index) for index in range(4)]
    return [{"code": pattern, "scenario": classifier.classify(snapshots_for(pattern)),
             "snapshots": snapshots_for(pattern)} for pattern in patterns]


def tour_preview(anchor):
    if anchor.weekday() != 0:
        raise ValueError("A referência da demonstração deve ser uma segunda-feira.")
    classifier = ScenarioClassifier()
    return [{"cycle": (anchor - timedelta(weeks=12 - index)).isoformat(),
             "title": TITLES[index], "pattern": pattern,
             "scenario": classifier.classify(snapshots_for(pattern)).type.value,
             "funnel": "LEAD" if index % 2 else "DIRECT_SALE"}
            for index, pattern in enumerate(PATTERNS)]


@dataclass(frozen=True)
class DemoBundle:
    db_path: Path
    manifest: dict


def demo_settings(base_settings, db_path):
    return replace(base_settings, DB_PATH=Path(db_path), DATA_DIR=Path(db_path).parent)


def new_demo_path(base_settings, session_id):
    """Only server-generated UUIDs may identify demo directories; no user paths."""
    session = UUID(str(session_id)).hex
    root = (base_settings.DATA_DIR / "demo").resolve()
    folder = root / session
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{uuid4().hex}.db"
    if not target.resolve().is_relative_to(root):
        raise ValueError("Destino de demonstração inválido.")
    return target


def create_demo_bundle(base_settings, session_id, anchor, package):
    if package not in PACKAGES:
        raise ValueError("Pacote de demonstração desconhecido.")
    rows = tour_preview(anchor)
    target = new_demo_path(base_settings, session_id)
    staging = target.with_suffix(".building.db")
    core = Container(app_settings=demo_settings(base_settings, staging))
    growth = SQLiteGrowthRepository(str(staging))
    manage = ManageHypothesesUseCase(growth)
    prepare = PrepareCDMSProposalUseCase(growth_repository=growth)
    audit_case = AuditFunnelOpportunityUseCase(growth)
    from cgs.adapters.persistence.sqlite_cgs_fase2_repo import SQLiteCGSPhase2Repository
    from cgs.domain.entities.budget_allocation import BudgetAllocation,ExperimentRiskTier
    from cgs.domain.services.bayesian_analyzer import BayesianExperimentAnalyzer
    from cdms.adapters.persistence.sqlite_ingestion_repo import SQLiteIngestionRepository
    from cdms.application.demo_ingestion import demo_payload,finish_demo_job
    finance=SQLiteCGSPhase2Repository(staging)
    ingestion=SQLiteIngestionRepository(staging)
    connection=ingestion.save_connection(account_id='act_000000001',encrypted_credentials='SIMULATED_NO_CREDENTIALS',
        api_version='SIMULATED',conversion_action_type='SIMULATED_PURCHASE',timezone_name='America/Sao_Paulo',
        currency='BRL',created_by='demo',automatic_sync=False)
    ab_cases=[(20,1000,50,1000,100),(50,1000,15,600,1000),(1,20,2,20,100)]
    for calibration in DEFAULT_CALIBRATIONS.values():
        core.calibrate_metrics_use_case.execute_save(calibration)
    outcomes = list(HypothesisOutcome)
    variables = list(VariableType)

    def make_hypothesis(action, index, source=None):
        return manage.create_hypothesis(
            action_description=action, tested_variable=variables[index % len(variables)],
            target_metric_key="ctr_pct", target_metric_unit="%",
            metric_direction=MetricDirection.HIGHER_IS_BETTER,
            baseline_reference_value=Decimal("3"), success_metric_target=Decimal("4.5"),
            invalidation_floor=Decimal("2.5"), expected_impact_description="[SIMULADO] Uma variável isolada aumenta a intenção do público.",
            impact_score=4 + index % 6, confidence_score=7, ease_score=8, source_cycle_id=source,
        )

    for index, row in enumerate(rows):
        cycle = date.fromisoformat(row["cycle"])
        snapshots = snapshots_for(row["pattern"])
        is_lead = row["funnel"] == "LEAD"
        baseline = FunnelBaseline(
            ticket_price=Decimal("150"), expected_ctr_pct=Decimal("4"),
            expected_conversion_rate_pct=Decimal("20") if is_lead else Decimal("5") if index == 10 else Decimal("8"),
            conversion_type=ConversionType(row["funnel"]),
            lead_to_sale_rate_pct=Decimal("25") if is_lead else None,
        )
        growth.save_baseline(baseline)
        impressions = 0 if row["pattern"] == "UUUU" else 10000
        ctr = snapshots[2].observed_value or 0
        clicks = int(impressions * ctr / 100)
        conversions = int(snapshots[3].observed_value or 0)
        lead_ratio = 0.1 if index == 9 else 0.2 if index % 4 == 3 else 0.4
        leads = max(conversions, int(clicks * lead_ratio)) if is_lead else None
        row["inputs"] = {"impressions": impressions, "clicks": clicks, "conversions": conversions, "leads": leads}
        row["baseline"] = {"ticket": str(baseline.ticket_price), "ctr": str(baseline.expected_ctr_pct),
                           "conversion": str(baseline.expected_conversion_rate_pct),
                           "lead_to_sale": str(baseline.lead_to_sale_rate_pct) if is_lead else None}
        audit = audit_case.execute(source_cycle_id=row["cycle"], impressions=impressions,
                                   clicks=clicks, conversions=conversions, leads=leads)
        row["bottleneck"] = audit.primary_bottleneck.value
        row["opportunity"] = str(audit.total_opportunity_reais)
        hypothesis = make_hypothesis(f"[SIMULADO] {row['title']}: testar {variables[index % 5].value}", index,
                                     rows[max(0, index - 1)]["cycle"])
        prepare.execute(hypothesis_id=hypothesis.id, target_cycle_start=cycle)
        row['hypothesis_id']=hypothesis.id
        finance.set_cycle_limit(row['cycle'],200000,'demo')
        amount=10000+index*1000
        finance.save_budget_allocation(BudgetAllocation(hypothesis.id,row['cycle'],amount,
            risk_tier=list(ExperimentRiskTier)[index%3]),actor='demo')
        finance.record_spend(hypothesis.id,row['cycle'],amount+5000 if index%3==1 else amount//2,'demo')
        evaluation=BayesianExperimentAnalyzer.evaluate(hypothesis.id,*ab_cases[index%3],cycle_id=row['cycle'],
            event_definition='[SIMULADO] Clique único por exposição no grupo do teste')
        finance.save_statistical_evaluation(evaluation,'demo')
        row['ab_verdict']=evaluation.verdict.value
        job,_=ingestion.enqueue(connection['id'],row['cycle'],'demo')
        finish_demo_job(ingestion,job,demo_payload(row['cycle'],snapshots))
        ingestion.record_ritual_source(job['id'],row['cycle'],'demo')
        pending = core.repository.get_pending_decision(before_week_start=cycle, evaluation_as_of=anchor)
        outcome = outcomes[(index - 1) % len(outcomes)] if pending else None
        core.run_weekly_ritual_use_case.execute(
            week_start=cycle, snapshots=snapshots, decision_summary=hypothesis.action_description,
            decision_hypothesis=hypothesis.expected_impact_description,
            decision_success_criterion="CTR ≥ 4,5%; limite de invalidação 2,5%.",
            decision_evaluation_due_date=cycle + timedelta(days=7), decision_owner="Apresentador Demo",
            target_decision_id=pending.id if pending else None, learning_outcome=outcome,
            learning_evidence_notes=f"[SIMULADO] Evidência do tour para {outcome.value}." if outcome else None,
            evaluation_as_of=anchor, source_hypothesis_id=hypothesis.id,
        )
    for index, variable in enumerate(variables):
        hypothesis = make_hypothesis(f"[SIMULADO] Próximo teste de {variable.value}", index, rows[-1]["cycle"])
        if index < 3:
            prepare.execute(hypothesis_id=hypothesis.id, target_cycle_start=anchor + timedelta(weeks=index // 2))
        if index==0:
            sandbox_hypothesis=hypothesis.id
            finance.set_cycle_limit(anchor.isoformat(),100000,'demo')
            finance.save_budget_allocation(BudgetAllocation(hypothesis.id,anchor.isoformat(),30000),actor='demo')
            finance.record_spend(hypothesis.id,anchor.isoformat(),12000,'demo')
            finance.save_statistical_evaluation(BayesianExperimentAnalyzer.evaluate(hypothesis.id,*ab_cases[2],cycle_id=anchor.isoformat(),
                event_definition='[SIMULADO] Clique único por exposição no grupo do teste'),'demo')
    # Three states in an open cycle allow the complete review/import workflow.
    job,_=ingestion.enqueue(connection['id'],anchor.isoformat(),'demo')
    finish_demo_job(ingestion,job,demo_payload(anchor.isoformat()))
    extra_connections=[]
    for account in ('act_000000002','act_000000003'):
        extra_connections.append(ingestion.save_connection(account_id=account,encrypted_credentials='SIMULATED_NO_CREDENTIALS',
            api_version='SIMULATED',conversion_action_type='SIMULATED_PURCHASE',timezone_name='America/Sao_Paulo',
            currency='BRL',created_by='demo',automatic_sync=False))
    failed,_=ingestion.enqueue(extra_connections[1]['id'],anchor.isoformat(),'demo')
    ingestion.fail(ingestion.claim(failed['id']),'SIMULATED_PERMISSION_ERROR')
    ingestion.enqueue(extra_connections[0]['id'],anchor.isoformat(),'demo')
    discarded = make_hypothesis("[SIMULADO] Ideia descartada antes do teste", 9, rows[-1]["cycle"])
    manage.discard_hypothesis(discarded.id)
    hypotheses = growth.list_hypotheses(limit=100)
    manifest = {"version": VERSION, "package": package, "anchor": anchor.isoformat(), "cycles": rows,
                "sandbox_cycle":anchor.isoformat(),"sandbox_hypothesis":sandbox_hypothesis,
                "catalog_examples": 85 if package == "Cobertura completa" else 0,
                "counts": {"rituals": len(core.repository.list_rituals(limit=100)),
                           "audits": len(growth.list_funnel_audits(limit=100)), "hypotheses": len(hypotheses),
                           "statuses": dict(Counter(item.status.value for item in hypotheses)),
                           "budgets":13,"ab_evaluations":13,"simulated_jobs":15,"simulated_connections":3}}
    # Publish only after every use case succeeds. A restore creates a new file;
    # no real or previous demo database is overwritten or deleted.
    staging.rename(target)
    target.with_suffix(".json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return DemoBundle(target, manifest)
