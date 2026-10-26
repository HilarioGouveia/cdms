from dataclasses import dataclass
from enum import Enum
from typing import Optional
import math

class MetricStatus(str, Enum):
    HEALTHY = "HEALTHY"
    BELOW = "BELOW"
    ABOVE = "ABOVE"

@dataclass(frozen=True)
class MetricDefinition:
    key: str
    name: str
    unit: str
    description: str

@dataclass(frozen=True)
class MetricCalibration:
    metric_key: str
    healthy_min: float
    healthy_max: float

    def __post_init__(self):
        for val, name in [(self.healthy_min, "healthy_min"), (self.healthy_max, "healthy_max")]:
            if isinstance(val, bool) or not isinstance(val, (int, float)):
                raise ValueError(f"{name} deve ser numérico.")
            if math.isnan(val) or math.isinf(val):
                raise ValueError(f"{name} não pode ser NaN ou Infinito.")
            if val < 0:
                raise ValueError(f"{name} deve ser um valor não-negativo.")
        if self.healthy_min > self.healthy_max:
            raise ValueError(f"healthy_min ({self.healthy_min}) não pode ser maior que healthy_max ({self.healthy_max}).")

@dataclass(frozen=True)
class MetricSnapshot:
    definition: MetricDefinition
    calibration: MetricCalibration
    observed_value: Optional[float]
    is_available: bool = True
    unavailability_reason: Optional[str] = None

    def __post_init__(self):
        if self.definition.key != self.calibration.metric_key:
            raise ValueError(f"Chave de definição '{self.definition.key}' incompatível com calibração '{self.calibration.metric_key}'.")
        if not self.is_available:
            if self.observed_value is not None or not self.unavailability_reason:
                raise ValueError("Métrica indisponível exige valor None e motivo.")
            return
        if self.unavailability_reason is not None:
            raise ValueError("Métrica disponível não pode conter motivo de indisponibilidade.")
        if isinstance(self.observed_value, bool) or not isinstance(self.observed_value, (int, float)):
            raise ValueError("Valor observado deve ser numérico.")
        if self.observed_value is None or math.isnan(self.observed_value) or math.isinf(self.observed_value):
            raise ValueError(f"Métrica disponível '{self.definition.key}' deve conter um valor numérico finito.")
        if self.observed_value < 0:
            raise ValueError(f"Valor observado de '{self.definition.key}' não pode ser negativo.")

        if self.definition.key in {"reach", "conversions"}:
            if not float(self.observed_value).is_integer():
                raise ValueError("Contagens devem ser inteiras.")

    def status(self) -> Optional[MetricStatus]:
        if not self.is_available or self.observed_value is None:
            return None
        if self.observed_value < self.calibration.healthy_min:
            return MetricStatus.BELOW
        elif self.observed_value > self.calibration.healthy_max:
            return MetricStatus.ABOVE
        return MetricStatus.HEALTHY

    def deviation_pct(self) -> Optional[float]:
        st = self.status()
        if st is None:
            return None
        if st == MetricStatus.HEALTHY:
            return 0.0
        if st == MetricStatus.BELOW:
            if self.calibration.healthy_min == 0:
                return None
            return round(((self.observed_value - self.calibration.healthy_min) / self.calibration.healthy_min) * 100, 2)
        else:
            if self.calibration.healthy_max == 0:
                return None
            return round(((self.observed_value - self.calibration.healthy_max) / self.calibration.healthy_max) * 100, 2)