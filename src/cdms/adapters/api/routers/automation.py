"""Endpoints REST da Fase 3: Conexões de APIs, Health Index e Sugestões de IA."""

from datetime import date
from decimal import Decimal
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from cdms.adapters.api.routers.growth import InputModel as BaseModel

from cdms.adapters.api.dependencies import get_workspace_repositories, require_writer, WorkspaceRepositories
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
def connect_platform(payload: ConnectPlatformRequest, tenant: TenantContext = Depends(require_writer)):
    """Conecta e valida credenciais da conta oficial (Meta Ads ou YouTube Studio)."""
    raise HTTPException(501, "Conexões reais de plataformas serão implementadas na etapa de automação.")


@router.post("/ai-suggestions", response_model=List[AISuggestionResponse])
def get_ai_hypothesis_suggestions(
    source_cycle_id: date,
    store: WorkspaceRepositories = Depends(get_workspace_repositories),
    _writer: TenantContext = Depends(require_writer),
):
    """Gera hipóteses analíticas operacionais via raciocínio estruturado sobre o funil auditado."""
    audit = store.growth.get_funnel_audit(source_cycle_id.isoformat())
    if audit is None:
        raise HTTPException(404, "Auditoria não encontrada neste workspace.")

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