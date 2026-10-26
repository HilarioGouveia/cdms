from typing import List, Optional
from datetime import date
from cdms.application.ports.repository import RepositoryPort
from cdms.domain.entities.weekly_ritual import WeeklyRitualRecord
from cdms.domain.entities.decision import Decision

class GetHistoryUseCase:
    """Recupera histórico de rituais e decisões pendentes elegíveis."""

    def __init__(self, repo: RepositoryPort):
        self.repo = repo

    def execute_list(self, limit: int = 20) -> List[WeeklyRitualRecord]:
        return self.repo.list_rituals(limit=limit)

    def execute_get_by_cycle(self, cycle_id: str) -> Optional[WeeklyRitualRecord]:
        return self.repo.get_ritual_by_cycle(cycle_id)

    def execute_get_pending_decision(self, before_week_start: date, evaluation_as_of: date) -> Optional[Decision]:
        return self.repo.get_pending_decision(before_week_start=before_week_start, evaluation_as_of=evaluation_as_of)