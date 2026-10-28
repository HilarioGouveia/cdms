"""Rotas REST para operações do Creator Growth System (CGS) multi-tenant."""

from datetime import date
from decimal import Decimal
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from cdms.adapters.api.dependencies import get_current_tenant
from cdms.domain.entities.tenant import TenantContext
from cgs.adapters.persistence.sqlite_growth_repo import SQLiteGrowthRepository
from cgs.application.use_cases.audit_funnel_opportunity import AuditFunnelOpportunityUseCase
from cgs.application.use_cases.manage_hypotheses import ManageHypothesesUseCase
from cgs.application.use_cases.prepare_cdms_proposal import PrepareCDMSProposalUseCase

router = APIRouter(prefix="/growth", tags=["Creator Growth System"])


class FunnelAuditRequest(BaseModel):
    source_cycle_id: str
    impressions: int
    clicks: int
    conversions: int
    leads: Optional[int] = None


class FunnelAuditResponse(BaseModel):
    source_cycle_id: str
    primary_bottleneck: str
    intention_opportunity_reais: float
    conversion_opportunity_reais: float
    total_opportunity_reais: float
    diagnosis_summary: str


@router.post("/audit-funnel", response_model=FunnelAuditResponse)
def audit_funnel(
    payload: FunnelAuditRequest,
    tenant: TenantContext = Depends(get_current_tenant),
):
    """Executa diagnóstico financeiro de funil no contexto do Workspace."""
    repo = SQLiteGrowthRepository("data/cdms_dev.db")
    uc = AuditFunnelOpportunityUseCase(repo)

    try:
        audit = uc.execute(
            source_cycle_id=payload.source_cycle_id,
            impressions=payload.impressions,
            clicks=payload.clicks,
            conversions=payload.conversions,
            leads=payload.leads,
        )
        return FunnelAuditResponse(
            source_cycle_id=audit.source_cycle_id,
            primary_bottleneck=audit.primary_bottleneck.value,
            intention_opportunity_reais=float(audit.intention_opportunity_reais),
            conversion_opportunity_reais=float(audit.conversion_opportunity_reais),
            total_opportunity_reais=float(audit.total_opportunity_reais),
            diagnosis_summary=audit.diagnosis_summary,
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))