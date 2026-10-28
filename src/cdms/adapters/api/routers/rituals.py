"""Rituais e calibrações isolados pelo workspace autenticado."""
from datetime import date, datetime
from typing import Literal
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field
from cdms.adapters.api.dependencies import get_workspace_repositories, require_writer, WorkspaceRepositories
from cdms.adapters.api.routers.growth import InputModel
from cdms.application.use_cases.run_weekly_ritual import RunWeeklyRitualUseCase, CycleAlreadyClosedError
from cdms.config.settings import settings
from cdms.domain.entities.learning import HypothesisOutcome
from cdms.domain.entities.metric import MetricCalibration, MetricSnapshot
from cdms.domain.services.scenario_classifier import ScenarioClassifier
from cdms.domain.services.canonical_metrics import CANONICAL_DEFINITIONS, DEFAULT_CALIBRATIONS

router = APIRouter(prefix="/rituals", tags=["Rituais"])
MetricKey = Literal["reach", "avg_retention_pct", "ctr_pct", "conversions"]


class MetricInput(InputModel):
    key: MetricKey
    observed_value: float | None = None
    is_available: bool = True
    unavailability_reason: str | None = None


class CalibrationInput(InputModel):
    metric_key: MetricKey
    healthy_min: float = Field(ge=0)
    healthy_max: float = Field(ge=0)


class RitualInput(InputModel):
    week_start: date
    snapshots: list[MetricInput] = Field(min_length=4, max_length=4)
    decision_summary: str = Field(min_length=1, max_length=1000)
    decision_hypothesis: str = Field(min_length=1, max_length=2000)
    decision_success_criterion: str = Field(min_length=1, max_length=2000)
    decision_evaluation_due_date: date
    decision_owner: str = Field(default="Creator", min_length=1, max_length=200)
    source_hypothesis_id: int | None = Field(default=None, gt=0)
    target_decision_id: int | None = Field(default=None, gt=0)
    learning_outcome: HypothesisOutcome | None = None
    learning_evidence_notes: str | None = Field(default=None, max_length=5000)


@router.get("/calibrations")
def get_calibrations(store: WorkspaceRepositories = Depends(get_workspace_repositories)):
    return store.core.get_active_calibrations()


@router.put("/calibrations", dependencies=[Depends(require_writer)])
def save_calibration(payload: CalibrationInput, store: WorkspaceRepositories = Depends(get_workspace_repositories)):
    calibration = MetricCalibration(**payload.model_dump())
    store.core.save_metric_calibration(calibration)
    return calibration


@router.post("", dependencies=[Depends(require_writer)])
def save_ritual(payload: RitualInput, store: WorkspaceRepositories = Depends(get_workspace_repositories)):
    if payload.week_start.weekday() != 0:
        raise ValueError("O ciclo deve começar numa segunda-feira.")
    if len({s.key for s in payload.snapshots}) != 4:
        raise ValueError("Informe cada uma das quatro métricas exatamente uma vez.")
    if payload.source_hypothesis_id is not None:
        store.hypothesis(payload.source_hypothesis_id)
    if payload.decision_evaluation_due_date < payload.week_start:
        raise ValueError("O prazo de avaliação não pode anteceder o início do ciclo.")
    calibrations = {c.metric_key: c for c in store.core.get_active_calibrations()}
    definitions = {d.key: d for d in CANONICAL_DEFINITIONS}
    snapshots = [MetricSnapshot(
        definition=definitions[s.key], calibration=calibrations.get(s.key, DEFAULT_CALIBRATIONS[s.key]),
        observed_value=s.observed_value, is_available=s.is_available,
        unavailability_reason=s.unavailability_reason,
    ) for s in payload.snapshots]
    values = payload.model_dump(exclude={"snapshots"})
    # Usa enums/datas tipados em vez das representações JSON.
    values["learning_outcome"] = payload.learning_outcome
    try:
        return RunWeeklyRitualUseCase(store.core, ScenarioClassifier()).execute(
            snapshots=snapshots, evaluation_as_of=datetime.now(ZoneInfo(settings.TIMEZONE_NAME)).date(), **values,
        )
    except CycleAlreadyClosedError as exc:
        raise HTTPException(409, str(exc))


@router.get("")
def list_rituals(store: WorkspaceRepositories = Depends(get_workspace_repositories)):
    return store.core.list_rituals(limit=100)


@router.get("/{cycle_id}")
def get_ritual(cycle_id: date, store: WorkspaceRepositories = Depends(get_workspace_repositories)):
    record = store.core.get_ritual_by_cycle(cycle_id.isoformat())
    if record is None:
        raise HTTPException(404, "Ritual não encontrado neste workspace.")
    return record
