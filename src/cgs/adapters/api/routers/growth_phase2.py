"""Endpoints REST da Fase 2 do CGS: Orçamento de Testes e Significância Bayesiana."""

from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from cdms.adapters.api.dependencies import get_current_tenant
from cdms.domain.entities.tenant import TenantContext
from cgs.adapters.persistence.sqlite_cgs_fase2_repo import SQLiteCGSPhase2Repository
from cgs.application.use_cases.allocate_experiment_budget import AllocateExperimentBudgetUseCase
from cgs.domain.entities.budget_allocation import ExperimentRiskTier
from cgs.domain.services.bayesian_analyzer import BayesianExperimentAnalyzer

router = APIRouter(prefix="/growth-v2", tags=["CGS Fase 2: Alocação Orçamentária e Significância"])


class BudgetAllocationRequest(BaseModel):
    hypothesis_id: int
    cycle_id: str
    amount_reais: float
    risk_tier: ExperimentRiskTier = ExperimentRiskTier.LOW
    max_cpa_target_reais: Optional[float] = None


class BudgetAllocationResponse(BaseModel):
    hypothesis_id: int
    cycle_id: str
    allocated_reais: float
    risk_tier: str
    burn_rate_pct: float


class BayesianEvaluationRequest(BaseModel):
    hypothesis_id: int
    control_conversions: int
    control_sample: int
    treatment_conversions: int
    treatment_sample: int
    sample_minimum: int = 100


class BayesianEvaluationResponse(BaseModel):
    hypothesis_id: int
    probability_to_beat_control: float
    lift_pct: float
    verdict: str
    sample_adequacy_ratio: float


@router.post("/allocate-budget", response_model=BudgetAllocationResponse)
def allocate_budget(
    payload: BudgetAllocationRequest,
    tenant: TenantContext = Depends(get_current_tenant),
):
    """Aloca teto orçamentário para o teste com trava de limite do ciclo."""
    repo = SQLiteCGSPhase2Repository()
    uc = AllocateExperimentBudgetUseCase(repo)

    try:
        alloc = uc.execute(
            hypothesis_id=payload.hypothesis_id,
            cycle_id=payload.cycle_id,
            amount_reais=Decimal(str(payload.amount_reais)),
            risk_tier=payload.risk_tier,
            max_cpa_target_reais=Decimal(str(payload.max_cpa_target_reais)) if payload.max_cpa_target_reais else None,
        )
        return BudgetAllocationResponse(
            hypothesis_id=alloc.hypothesis_id,
            cycle_id=alloc.cycle_id,
            allocated_reais=float(alloc.allocated_reais),
            risk_tier=alloc.risk_tier.value,
            burn_rate_pct=float(alloc.burn_rate_pct),
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/evaluate-statistical-significance", response_model=BayesianEvaluationResponse)
def evaluate_significance(
    payload: BayesianEvaluationRequest,
    tenant: TenantContext = Depends(get_current_tenant),
):
    """Calcula a significância Bayesiana, lift e regras de Early Stopping."""
    repo = SQLiteCGSPhase2Repository()
    try:
        eval_result = BayesianExperimentAnalyzer.evaluate(
            hypothesis_id=payload.hypothesis_id,
            control_conversions=payload.control_conversions,
            control_sample=payload.control_sample,
            treatment_conversions=payload.treatment_conversions,
            treatment_sample=payload.treatment_sample,
            sample_minimum=payload.sample_minimum,
        )
        repo.save_statistical_evaluation(eval_result)

        return BayesianEvaluationResponse(
            hypothesis_id=eval_result.hypothesis_id,
            probability_to_beat_control=float(eval_result.probability_to_beat_control),
            lift_pct=float(eval_result.lift_pct),
            verdict=eval_result.verdict.value,
            sample_adequacy_ratio=float(eval_result.sample_adequacy_ratio),
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))