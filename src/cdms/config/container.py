from typing import Optional
from pathlib import Path

from cdms.config.settings import settings, Settings
from cdms.application.ports.repository import RepositoryPort
from cdms.adapters.persistence.sqlite_repo import SQLiteRepository
from cdms.domain.services.scenario_classifier import ScenarioClassifier
from cdms.application.use_cases.calibrate_metrics import CalibrateMetricsUseCase
from cdms.application.use_cases.diagnose_scenario import DiagnoseScenarioUseCase
from cdms.application.use_cases.run_weekly_ritual import RunWeeklyRitualUseCase
from cdms.application.use_cases.get_history import GetHistoryUseCase
from cdms.application.use_cases.export_ritual import ExportRitualUseCase

class Container:
    def __init__(self, db_path: Optional[Path] = None, app_settings: Optional[Settings] = None):
        self.settings = app_settings or settings
        self.settings.ensure_directories()
        
        target_db = db_path or self.settings.DB_PATH
        
        self.repository: RepositoryPort = SQLiteRepository(db_path=target_db)
        self.classifier = ScenarioClassifier()
        
        self.calibrate_metrics_use_case = CalibrateMetricsUseCase(repo=self.repository)
        self.diagnose_scenario_use_case = DiagnoseScenarioUseCase(classifier=self.classifier)
        self.run_weekly_ritual_use_case = RunWeeklyRitualUseCase(
            repo=self.repository,
            classifier=self.classifier,
            settings=self.settings
        )
        self.get_history_use_case = GetHistoryUseCase(repo=self.repository)
        self.export_ritual_use_case = ExportRitualUseCase(repo=self.repository)

_container_instance: Optional[Container] = None

def get_container(db_path: Optional[Path] = None, force_recreate: bool = False) -> Container:
    global _container_instance
    if _container_instance is None or force_recreate or db_path is not None:
        _container_instance = Container(db_path=db_path)
    return _container_instance