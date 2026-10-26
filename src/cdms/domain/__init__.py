"""
Camada de Domínio Puro (Domain Layer) do CDMS.

Contém as entidades puras de negócio, regras invariantes e serviços de domínio,
completamente desacoplados de frameworks e infraestrutura externa.
"""

from cdms.domain.entities.metric import (
    MetricStatus,
    MetricDefinition,
    MetricCalibration,
    MetricSnapshot,
)
from cdms.domain.entities.scenario import (
    ScenarioType,
    InconclusiveReason,
    Scenario,
)
from cdms.domain.entities.decision import Decision
from cdms.domain.entities.learning import (
    HypothesisOutcome,
    Learning,
)
from cdms.domain.entities.weekly_ritual import WeeklyRitualRecord
from cdms.domain.services.scenario_classifier import ScenarioClassifier

__all__ = [
    "MetricStatus",
    "MetricDefinition",
    "MetricCalibration",
    "MetricSnapshot",
    "ScenarioType",
    "InconclusiveReason",
    "Scenario",
    "Decision",
    "HypothesisOutcome",
    "Learning",
    "WeeklyRitualRecord",
    "ScenarioClassifier",
]