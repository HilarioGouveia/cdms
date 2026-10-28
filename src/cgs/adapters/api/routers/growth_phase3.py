"""Endpoints REST da Fase 3 do CGS: Bandits Dinâmicos e Circuit Breakers."""

from decimal import Decimal
from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from cdms.adapters.api.dependencies import get_current_tenant
from cdms.domain.entities.tenant import TenantContext
from cgs.adapters.persistence.sqlite_cgs_fase3_repo import SQLiteCGSPhase3Repository
from cgs.application.use_cases.optimize_variant_allocation import OptimizeVariantAllocationUseCase
from cgs.domain.entities.bandit_policy import VariantArm

router = APIRouter(prefix="/growth-v3", tags=["CGS Fase 3: Auto-Scale & Disjuntores"])


class ArmPayload(BaseModel):
    arm_id: str
    variable_name: str
    total_impressions: int
    total_conversions: int


class OptimizationRequest(BaseModel):
    hypothesis_id: int
    cycle_id: str
    arms: List[ArmPayload]
    current_cpa_reais: float
    max_allowed_cpa_reais: Optional[float] = None
    current_spend_reais: float
    max_budget_reais: float


class OptimizationResponse(BaseModel):
    hypothesis_id: int
    cycle_id: str
    action_taken: str
    is_tripped: bool
    is_converged: bool
    weights: Dict[str, float]


@router.post("/optimize-traffic", response_model=OptimizationResponse)
def optimize_traffic(
    payload: OptimizationRequest,
    tenant: TenantContext = Depends(get_current_tenant),
):
    """Executa o ciclo contínuo de avaliação de disjuntor e alocação dinâmica por Thompson Sampling."""
    repo = SQLiteCGSPhase3Repository()
    uc = OptimizeVariantAllocationUseCase(repo)

    arms_domain = [
        VariantArm(
            arm_id=a.arm_id,
            variable_name=a.variable_name,
            total_impressions=a.total_impressions,
            total_conversions=a.total_conversions,
        )
        for a in payload.arms
    ]

    try:
        res = uc.execute(
            hypothesis_id=payload.hypothesis_id,
            cycle_id=payload.cycle_id,
            arms=arms_domain,
            current_cpa_reais=Decimal(str(payload.current_cpa_reais)),
            max_allowed_cpa_reais=Decimal(str(payload.max_allowed_cpa_reais)) if payload.max_allowed_cpa_reais else None,
            current_spend_reais=Decimal(str(payload.current_spend_reais)),
            max_budget_reais=Decimal(str(payload.max_budget_reais)),
        )

        weights = (
            {k: float(v) for k, v in res.bandit_decision.arm_weights.items()}
            if res.bandit_decision
            else {a.arm_id: (100.0 if i == 0 else 0.0) for i, a in enumerate(arms_domain)}
        )

        return OptimizationResponse(
            hypothesis_id=payload.hypothesis_id,
            cycle_id=payload.cycle_id,
            action_taken=res.action_taken,
            is_tripped=res.circuit_breaker.is_tripped,
            is_converged=res.bandit_decision.is_converged if res.bandit_decision else False,
            weights=weights,
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))