from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

class ScenarioType(str, Enum):
    PRE_DROP = "PRE_DROP"          # Risco de Queda: alerta operacional em indicadores líderes
    ANOMALY = "ANOMALY"            # Assimetria Crítica entre etapas do funil
    SCALE = "SCALE"                # Múltiplas métricas acima das faixas; sem inferência temporal
    STABILITY = "STABILITY"        # Equilíbrio Operacional nominal
    INCONCLUSIVE = "INCONCLUSIVE"  # Sem enquadramento conclusivo

class InconclusiveReason(str, Enum):
    MISSING_DATA = "MISSING_DATA"    # Faltam métricas obrigatórias ou métricas indisponíveis
    MIXED_SIGNALS = "MIXED_SIGNALS"  # Vetor completo com dispersão de sinais sem enquadramento

@dataclass
class Scenario:
    type: ScenarioType
    description: str
    recommendation: str
    evidence_metric_keys: List[str]
    inconclusive_reason: Optional[InconclusiveReason] = None