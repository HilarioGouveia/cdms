from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import date

from cdms.domain.entities.weekly_ritual import WeeklyRitualRecord
from cdms.domain.entities.decision import Decision
from cdms.domain.entities.metric import MetricCalibration

class RepositoryPort(ABC):
    """
    Driven Port (Porta de Saída Conduzida) para persistência de dados.
    Define o contrato agnóstico de infraestrutura para armazenamento e
    recuperação de rituais semanais, decisões e calibrações de métricas
    conforme a especificação SDD v2.3.1.
    """

    @abstractmethod
    def save_ritual_atomic(self, ritual: WeeklyRitualRecord) -> WeeklyRitualRecord:
        """
        Persiste atomicamente o agregado WeeklyRitualRecord (snapshots,
        cenário, decisão e eventual aprendizado) em uma transação única.
        Aplica a política de idempotência estrita baseada em cycle_id.
        """
        pass

    @abstractmethod
    def get_ritual_by_cycle(self, cycle_id: str) -> Optional[WeeklyRitualRecord]:
        """
        Recupera o registro de ritual pelo identificador unívoco de ciclo
        (formato canônico YYYY-MM-DD da segunda-feira de referência).
        Retorna None se o ciclo ainda não tiver sido concluído.
        """
        pass

    @abstractmethod
    def get_pending_decision(self, before_week_start: date, evaluation_as_of: date) -> Optional[Decision]:
        """
        Recupera a decisão mais recente anterior a before_week_start que ainda
        não possui Learning registrado e cujo prazo de avaliação (evaluation_due_date)
        já foi atingido na data de referência evaluation_as_of.
        Retorna None caso não exista decisão pendente elegível.
        """
        pass

    @abstractmethod
    def list_rituals(self, limit: int = 20) -> List[WeeklyRitualRecord]:
        """
        Lista o histórico de rituais concluídos em ordem cronológica decrescente.
        """
        pass

    @abstractmethod
    def save_metric_calibration(self, calibration: MetricCalibration) -> None:
        """
        Salva ou atualiza os limites de referência saudável (healthy_min, healthy_max)
        para uma métrica do catálogo no contexto operacional ativo.
        """
        pass

    @abstractmethod
    def get_active_calibrations(self) -> List[MetricCalibration]:
        """
        Recupera a lista de calibrações de métricas atualmente vigentes.
        """
        pass