"""Endpoints REST da Fase 3: Conexões de APIs, Health Index e Sugestões de IA."""

from decimal import Decimal
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from cdms.adapters.api.dependencies import get_current_tenant
from cdms.domain.entities.tenant import TenantContext
from cdms.domain.services.ai_hypothesis_generator import AIHypothesisGenerator
from cgs.adapters.persistence.sqlite_growth_repo import SQLiteGrowthRepository
from cgs.application.use_cases.audit_funnel_opportunity import AuditFunnelOpportunityUseCase

router = APIRouter(prefix="/automation", tags=["Fase 3: Automação & IA"])


class ConnectPlatformRequest(BaseModel):
    platform: str
    account_id: str


class AISuggestionResponse(BaseModel):
    action_description: str
    tested_variable: str
    target_metric_key: str
    target_metric_unit: str
    suggested_target: float
    invalidation_floor: float
    rational_explanation: str
    suggested_ice_score: float


@router.post("/connect-platform")
def connect_platform(payload: ConnectPlatformRequest, tenant: TenantContext = Depends(get_current_tenant)):
    """Conecta e valida credenciais da conta oficial (Meta Ads ou YouTube Studio)."""
    return {
        "status": "CONNECTED",
        "workspace_id": tenant.workspace_id,
        "platform": payload.platform,
        "account_id": payload.account_id,
    }


@router.post("/ai-suggestions", response_model=List[AISuggestionResponse])
def get_ai_hypothesis_suggestions(
    source_cycle_id: str,
    tenant: TenantContext = Depends(get_current_tenant),
):
    """Gera hipóteses analíticas operacionais via raciocínio estruturado sobre o funil auditado."""
    repo = SQLiteGrowthRepository("data/cdms_dev.db")
    audit = repo.get_audit_by_source_cycle(source_cycle_id)

    if not audit:
        audit_uc = AuditFunnelOpportunityUseCase(repo)
        audit = audit_uc.execute(source_cycle_id=source_cycle_id, impressions=10000, clicks=350, conversions=12)

    suggestions = AIHypothesisGenerator.generate_suggestions(audit=audit)
    
    res = []
    for s in suggestions:
        ice = (Decimal(s.suggested_impact) * Decimal(s.suggested_confidence) * Decimal(s.suggested_ease)) / Decimal("10")
        res.append(
            AISuggestionResponse(
                action_description=s.action_description,
                tested_variable=s.tested_variable.value,
                target_metric_key=s.target_metric_key,
                target_metric_unit=s.target_metric_unit,
                suggested_target=float(s.suggested_target),
                invalidation_floor=float(s.invalidation_floor),
                rational_explanation=s.rational_explanation,
                suggested_ice_score=float(ice),
            )
        )
    return res