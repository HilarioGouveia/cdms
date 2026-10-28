"""Operações de funil e hipóteses no armazenamento do workspace autenticado."""
from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from cdms.adapters.api.dependencies import get_workspace_repositories, require_writer, WorkspaceRepositories
from cgs.application.use_cases.audit_funnel_opportunity import AuditFunnelOpportunityUseCase
from cgs.application.use_cases.manage_hypotheses import ManageHypothesesUseCase
from cgs.application.use_cases.prepare_cdms_proposal import PrepareCDMSProposalUseCase
from cgs.application.use_cases.export_cycle_report import ExportCycleReportUseCase
from cgs.domain.entities.funnel import ConversionType, FunnelBaseline
from cgs.domain.entities.hypothesis import VariableType, MetricDirection

router = APIRouter(prefix="/growth", tags=["Growth"])


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, str_strip_whitespace=True)


class BaselineRequest(InputModel):
    ticket_price: Decimal = Field(gt=0)
    expected_ctr_pct: Decimal = Field(gt=0, le=100)
    expected_conversion_rate_pct: Decimal = Field(gt=0, le=100)
    conversion_type: ConversionType = ConversionType.DIRECT_SALE
    lead_to_sale_rate_pct: Decimal | None = Field(default=None, gt=0, le=100)


class FunnelAuditRequest(InputModel):
    source_cycle_id: date
    impressions: int = Field(ge=0)
    clicks: int = Field(ge=0)
    conversions: int = Field(ge=0)
    leads: int | None = Field(default=None, ge=0)


class HypothesisRequest(InputModel):
    action_description: str = Field(min_length=1, max_length=1000)
    tested_variable: VariableType
    target_metric_key: str = Field(min_length=1, max_length=100)
    target_metric_unit: str = Field(min_length=1, max_length=30)
    metric_direction: MetricDirection
    baseline_reference_value: Decimal
    success_metric_target: Decimal
    invalidation_floor: Decimal
    expected_impact_description: str = Field(min_length=1, max_length=2000)
    impact_score: int = Field(ge=1, le=10)
    confidence_score: int = Field(ge=1, le=10)
    ease_score: int = Field(ge=1, le=10)
    source_cycle_id: date | None = None
    sample_exposure_minimum: int = Field(default=100, ge=0)
    window_days: int = Field(default=7, ge=1, le=90)


class ProposalRequest(InputModel):
    target_cycle_start: date


@router.get("/baseline")
def get_baseline(store: WorkspaceRepositories = Depends(get_workspace_repositories)):
    baseline = store.growth.get_active_baseline()
    if baseline is None:
        raise HTTPException(404, "Baseline não encontrada neste workspace.")
    return baseline


@router.put("/baseline", dependencies=[Depends(require_writer)])
def save_baseline(payload: BaselineRequest, store: WorkspaceRepositories = Depends(get_workspace_repositories)):
    return store.growth.save_baseline(FunnelBaseline(**payload.model_dump()))


@router.post("/audit-funnel", dependencies=[Depends(require_writer)])
def audit_funnel(payload: FunnelAuditRequest, store: WorkspaceRepositories = Depends(get_workspace_repositories)):
    if payload.source_cycle_id.weekday() != 0:
        raise ValueError("O ciclo deve começar numa segunda-feira.")
    values = payload.model_dump()
    values["source_cycle_id"] = payload.source_cycle_id.isoformat()
    return AuditFunnelOpportunityUseCase(store.growth).execute(**values)


@router.get("/audits")
def list_audits(store: WorkspaceRepositories = Depends(get_workspace_repositories)):
    return store.growth.list_funnel_audits(limit=100)


@router.get("/audits/{cycle_id}")
def get_audit(cycle_id: date, store: WorkspaceRepositories = Depends(get_workspace_repositories)):
    audit = store.growth.get_funnel_audit(cycle_id.isoformat())
    if audit is None:
        raise HTTPException(404, "Auditoria não encontrada neste workspace.")
    return audit


@router.post("/hypotheses", status_code=201, dependencies=[Depends(require_writer)])
def create_hypothesis(payload: HypothesisRequest, store: WorkspaceRepositories = Depends(get_workspace_repositories)):
    values = payload.model_dump()
    if payload.source_cycle_id:
        values["source_cycle_id"] = payload.source_cycle_id.isoformat()
    return ManageHypothesesUseCase(store.growth).create_hypothesis(**values)


@router.get("/hypotheses")
def list_hypotheses(store: WorkspaceRepositories = Depends(get_workspace_repositories)):
    return store.growth.list_hypotheses(limit=100)


@router.get("/hypotheses/{hypothesis_id}")
def get_hypothesis(hypothesis_id: int, store: WorkspaceRepositories = Depends(get_workspace_repositories)):
    return store.hypothesis(hypothesis_id)


@router.post("/hypotheses/{hypothesis_id}/proposal", dependencies=[Depends(require_writer)])
def prepare_proposal(hypothesis_id: int, payload: ProposalRequest, store: WorkspaceRepositories = Depends(get_workspace_repositories)):
    store.hypothesis(hypothesis_id)
    return PrepareCDMSProposalUseCase(store.growth).execute(hypothesis_id, payload.target_cycle_start)


@router.get("/reports/{cycle_id}")
def get_report(cycle_id: date, store: WorkspaceRepositories = Depends(get_workspace_repositories)):
    return ExportCycleReportUseCase(store.growth, store.core).execute(cycle_id.isoformat())
