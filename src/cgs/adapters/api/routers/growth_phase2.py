"""Orçamento por ciclo e avaliação Beta-Binomial com histórico."""
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field
from cdms.adapters.api.routers.growth import InputModel
from cdms.adapters.api.dependencies import get_workspace_repositories, require_writer, require_manager, WorkspaceRepositories
from cdms.domain.entities.tenant import TenantContext
from cgs.application.use_cases.experiment_finance import ExperimentFinance, money_cents
from cgs.domain.entities.budget_allocation import ExperimentRiskTier

router=APIRouter(prefix='/growth-v2',tags=['Experimentos: orçamento e avaliação A/B'])

class BudgetAllocationRequest(InputModel):
    hypothesis_id: int = Field(gt=0,strict=True)
    cycle_id: str
    amount_reais: Decimal
    risk_tier: ExperimentRiskTier = ExperimentRiskTier.LOW
    max_cpa_target_reais: Decimal | None = None

class BayesianEvaluationRequest(InputModel):
    hypothesis_id: int = Field(gt=0,strict=True)
    cycle_id: str
    control_conversions: int = Field(ge=0,strict=True)
    control_sample: int = Field(gt=0,strict=True)
    treatment_conversions: int = Field(ge=0,strict=True)
    treatment_sample: int = Field(gt=0,strict=True)
    sample_minimum: int = Field(default=100,gt=0,strict=True)
    event_definition: str = Field(default='Conversão binária por unidade exposta',min_length=1,max_length=500)

class AmountRequest(InputModel):
    amount_reais: Decimal

@router.post('/allocate-budget')
def allocate_budget(payload: BudgetAllocationRequest, store: WorkspaceRepositories=Depends(get_workspace_repositories),
                    tenant: TenantContext=Depends(require_writer)):
    store.hypothesis(payload.hypothesis_id)
    alloc=ExperimentFinance(store.phase2(),store.growth,actor=tenant.user_id).allocate(
        payload.hypothesis_id,payload.cycle_id,payload.amount_reais,payload.risk_tier,payload.max_cpa_target_reais)
    return dict(hypothesis_id=alloc.hypothesis_id,cycle_id=alloc.cycle_id,allocated_reais=alloc.allocated_reais,
                risk_tier=alloc.risk_tier,burn_rate_pct=alloc.burn_rate_pct,spent_reais=alloc.spent_reais)

@router.post('/evaluate-statistical-significance')
def evaluate_significance(payload: BayesianEvaluationRequest,store: WorkspaceRepositories=Depends(get_workspace_repositories),
                          tenant: TenantContext=Depends(require_writer)):
    store.hypothesis(payload.hypothesis_id)
    values=payload.model_dump()
    return ExperimentFinance(store.phase2(),store.growth,actor=tenant.user_id).evaluate(**values)

@router.get('/budgets/{hypothesis_id}')
def get_budget(hypothesis_id: int,cycle_id: str | None=None,store: WorkspaceRepositories=Depends(get_workspace_repositories)):
    store.hypothesis(hypothesis_id)
    result=store.phase2().get_budget_by_hypothesis(hypothesis_id,cycle_id)
    if result is None:
        raise HTTPException(404,'Orçamento não encontrado neste workspace.')
    return result

@router.get('/evaluations/{hypothesis_id}')
def get_evaluation(hypothesis_id: int,cycle_id: str | None=None,store: WorkspaceRepositories=Depends(get_workspace_repositories)):
    store.hypothesis(hypothesis_id)
    result=store.phase2().get_evaluation_by_hypothesis(hypothesis_id,cycle_id)
    if result is None:
        raise HTTPException(404,'Avaliação não encontrada neste workspace.')
    return result

@router.get('/evaluations/{hypothesis_id}/history')
def evaluation_history(hypothesis_id: int,cycle_id: str | None=None,store: WorkspaceRepositories=Depends(get_workspace_repositories)):
    store.hypothesis(hypothesis_id)
    return store.phase2().evaluation_history(hypothesis_id,cycle_id)

@router.get('/cycles/{cycle_id}/budget')
def cycle_budget(cycle_id: str,store: WorkspaceRepositories=Depends(get_workspace_repositories)):
    repo=store.phase2()
    return dict(limit_cents=repo.get_cycle_limit(cycle_id),allocations=repo.list_budgets_by_cycle(cycle_id),history=repo.budget_history(cycle_id))

@router.put('/cycles/{cycle_id}/limit',status_code=204)
def set_limit(cycle_id: str,payload: AmountRequest,store: WorkspaceRepositories=Depends(get_workspace_repositories),
              tenant: TenantContext=Depends(require_manager)):
    store.phase2().set_cycle_limit(cycle_id,money_cents(payload.amount_reais),tenant.user_id)

@router.put('/budgets/{hypothesis_id}/cycles/{cycle_id}/spend',status_code=204)
def record_spend(hypothesis_id: int,cycle_id: str,payload: AmountRequest,store: WorkspaceRepositories=Depends(get_workspace_repositories),
                 tenant: TenantContext=Depends(require_writer)):
    store.hypothesis(hypothesis_id)
    ExperimentFinance(store.phase2(),store.growth,actor=tenant.user_id).spend(hypothesis_id,cycle_id,payload.amount_reais)
