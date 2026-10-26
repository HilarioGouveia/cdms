from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

class HypothesisOutcome(str, Enum):
    ACHIEVED = "ACHIEVED"          # Meta atingida
    PARTIAL = "PARTIAL"            # Meta parcialmente atingida
    NOT_ACHIEVED = "NOT_ACHIEVED"  # Meta não atingida
    INCONCLUSIVE = "INCONCLUSIVE"  # Inconclusivo / Fatores externos

@dataclass
class Learning:
    id: Optional[int]
    target_decision_id: int
    target_decision_summary: str
    outcome: HypothesisOutcome
    evidence_notes: str
    recorded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))