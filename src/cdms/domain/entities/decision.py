from dataclasses import dataclass, field
from datetime import datetime, date, timezone
from typing import Optional

@dataclass
class Decision:
    id: Optional[int]
    cycle_id: str
    summary: str
    hypothesis: str
    success_criterion: str
    evaluation_due_date: date
    owner: str = "Creator"
    recorded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source_hypothesis_id: Optional[int] = None
