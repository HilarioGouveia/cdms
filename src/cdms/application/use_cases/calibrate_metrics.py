from typing import List
from cdms.application.ports.repository import RepositoryPort
from cdms.domain.entities.metric import MetricCalibration

class CalibrateMetricsUseCase:
    """Caso de uso para atualizar e recuperar calibrações vigentes de métricas."""
    
    def __init__(self, repo: RepositoryPort):
        self.repo = repo

    def execute_save(self, calibration: MetricCalibration) -> None:
        self.repo.save_metric_calibration(calibration)

    def execute_get_active(self) -> List[MetricCalibration]:
        return self.repo.get_active_calibrations()