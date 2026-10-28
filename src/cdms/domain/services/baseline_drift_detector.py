"""Serviço de domínio puro para deteção de deriva de baseline (Recalibração Assistida)."""
from dataclasses import dataclass
from typing import List, Any


@dataclass(frozen=True)
class DriftAlert:
    metric_key: str
    metric_name: str
    consecutive_above_count: int
    current_p90: float
    suggested_new_p50: float
    message: str


class BaselineDriftDetector:
    """Verifica se alguma métrica canónica estabilizou acima de P90 por ciclos consecutivos."""

    @staticmethod
    def audit_drift(rituals: List[Any], min_consecutive_cycles: int = 4) -> List[DriftAlert]:
        if not rituals or len(rituals) < min_consecutive_cycles:
            return []

        # Ordena do ciclo mais recente para o mais antigo
        recent_rituals = sorted(rituals, key=lambda r: r.week_start, reverse=True)[:min_consecutive_cycles]

        alerts: List[DriftAlert] = []
        if not recent_rituals[0].snapshots:
            return alerts

        reference_snapshots = recent_rituals[0].snapshots

        for ref_snap in reference_snapshots:
            # Obtém a chave como string de forma resiliente (seja Enum ou str)
            raw_key = getattr(ref_snap.definition, "key", None)
            m_key_str = raw_key.value if hasattr(raw_key, "value") else str(raw_key)

            is_persistently_above = True
            observed_values: List[float] = []

            for r in recent_rituals:
                matching_snap = None
                for s in r.snapshots:
                    s_key = getattr(s.definition, "key", None)
                    s_key_str = s_key.value if hasattr(s_key, "value") else str(s_key)
                    if s_key_str == m_key_str:
                        matching_snap = s
                        break

                if not matching_snap or not getattr(matching_snap, "is_available", False):
                    is_persistently_above = False
                    break

                # Avalia o status (suporta tanto método status() quanto atributo state/status)
                current_status = None
                if hasattr(matching_snap, "status") and callable(matching_snap.status):
                    st_val = matching_snap.status()
                    current_status = st_val.value if hasattr(st_val, "value") else str(st_val)
                elif hasattr(matching_snap, "state"):
                    st_val = matching_snap.state
                    current_status = st_val.value if hasattr(st_val, "value") else str(st_val)

                if current_status != "ABOVE":
                    is_persistently_above = False
                    break

                obs_val = getattr(matching_snap, "observed_value", 0.0)
                observed_values.append(float(obs_val))

            if is_persistently_above and observed_values:
                avg_high = sum(observed_values) / len(observed_values)
                calib = getattr(ref_snap, "calibration", None)
                current_p90 = float(calib.p90_reference) if calib else 0.0
                name_str = getattr(ref_snap.definition, "name", m_key_str)

                alerts.append(
                    DriftAlert(
                        metric_key=m_key_str,
                        metric_name=name_str,
                        consecutive_above_count=min_consecutive_cycles,
                        current_p90=current_p90,
                        suggested_new_p50=round(avg_high, 2),
                        message=(
                            f"A métrica '{name_str}' permaneceu acima do teto P90 ({current_p90}) "
                            f"durante {min_consecutive_cycles} ciclos consecutivos."
                        )
                    )
                )

        return alerts