from typing import List
from cdms.domain.entities.metric import MetricSnapshot
from cdms.domain.entities.scenario import Scenario
from cdms.domain.services.scenario_classifier import ScenarioClassifier

class DiagnoseScenarioUseCase:
    """Coordena a entrada de snapshots e executa o diagnóstico heurístico via ScenarioClassifier."""

    def __init__(self, classifier: ScenarioClassifier):
        self.classifier = classifier

    def execute(self, snapshots: List[MetricSnapshot]) -> Scenario:
        return self.classifier.classify(snapshots)