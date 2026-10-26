"""
Camada de Aplicação do CDMS.

Orquestra os fluxos de casos de uso (Use Cases) e define os contratos
de portas abstratas (Ports) orientados à Clean Architecture.
"""

from cdms.application.ports.repository import RepositoryPort
from cdms.application.use_cases.run_weekly_ritual import RunWeeklyRitualUseCase
from cdms.application.use_cases.diagnose_scenario import DiagnoseScenarioUseCase
from cdms.application.use_cases.calibrate_metrics import CalibrateMetricsUseCase
from cdms.application.use_cases.get_history import GetHistoryUseCase
from cdms.application.use_cases.export_ritual import ExportRitualUseCase

__all__ = [
    "RepositoryPort",
    "RunWeeklyRitualUseCase",
    "DiagnoseScenarioUseCase",
    "CalibrateMetricsUseCase",
    "GetHistoryUseCase",
    "ExportRitualUseCase",
]