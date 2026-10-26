from dataclasses import dataclass, field
from datetime import datetime, date, timezone
from typing import List, Optional

from cdms.domain.entities.metric import MetricSnapshot
from cdms.domain.entities.scenario import Scenario
from cdms.domain.entities.decision import Decision
from cdms.domain.entities.learning import Learning

@dataclass
class WeeklyRitualRecord:
    id: Optional[int]
    cycle_id: str                 # Formato canônico: 'YYYY-MM-DD' (segunda-feira de referência)
    week_start: date
    snapshots: List[MetricSnapshot]
    scenario: Scenario
    decision: Decision
    learning: Optional[Learning] = None
    rules_version: str = "2.3.1"
    completed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))