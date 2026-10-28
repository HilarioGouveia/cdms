import streamlit as st
from typing import List, Dict
from cdms.domain.entities.metric import (
    MetricDefinition,
    MetricCalibration,
    MetricSnapshot,
)

from cdms.domain.services.canonical_metrics import CANONICAL_DEFINITIONS, DEFAULT_CALIBRATIONS


def render_calibration_editor(active_calibrations: List[MetricCalibration]) -> Dict[str, MetricCalibration]:
    """Exibe e permite ajustar os limites saudáveis nominais das 4 métricas."""
    calib_map = {c.metric_key: c for c in active_calibrations}
    updated = {}

    st.markdown("#### ⚙️ Calibração de Faixas Saudáveis de Referência")
    cols = st.columns(4)

    for i, m_def in enumerate(CANONICAL_DEFINITIONS):
        current_cal = calib_map.get(m_def.key, DEFAULT_CALIBRATIONS[m_def.key])
        with cols[i]:
            st.caption(f"**{m_def.name}** ({m_def.unit})")
            min_val = st.number_input(
                "Mín. Saudável",
                value=float(current_cal.healthy_min),
                min_value=0.0,
                step=1.0 if m_def.key in {"reach", "conversions"} else 0.5,
                key=f"cal_min_{m_def.key}",
            )
            max_val = st.number_input(
                "Máx. Saudável",
                value=float(current_cal.healthy_max),
                min_value=min_val,
                step=1.0 if m_def.key in {"reach", "conversions"} else 0.5,
                key=f"cal_max_{m_def.key}",
            )
            updated[m_def.key] = MetricCalibration(m_def.key, min_val, max_val)

    return updated


def render_metric_snapshots_form(calibrations: Dict[str, MetricCalibration]) -> List[MetricSnapshot]:
    """Renderiza a entrada de dados do ciclo com suporte a indisponibilidade e motivos."""
    snapshots = []
    cols = st.columns(4)

    for i, m_def in enumerate(CANONICAL_DEFINITIONS):
        cal = calibrations.get(m_def.key, DEFAULT_CALIBRATIONS[m_def.key])
        with cols[i]:
            st.markdown(f"**{m_def.name}**")
            st.caption(f"Faixa saudável: {cal.healthy_min:g} a {cal.healthy_max:g} {m_def.unit}")

            is_avail = st.checkbox("Métrica disponível", value=True, key=f"avail_{m_def.key}")

            if is_avail:
                is_int = m_def.key in {"reach", "conversions"}
                mid_val = cal.healthy_min + (cal.healthy_max - cal.healthy_min) / 2

                if is_int:
                    raw_val = st.number_input(
                        f"Valor ({m_def.unit})",
                        value=int(round(mid_val)),
                        min_value=0,
                        step=1,
                        format="%d",
                        key=f"val_{m_def.key}",
                    )
                else:
                    raw_val = st.number_input(
                        f"Valor ({m_def.unit})",
                        value=float(mid_val),
                        min_value=0.0,
                        step=0.1,
                        format="%.2f",
                        key=f"val_{m_def.key}",
                    )

                snapshots.append(
                    MetricSnapshot(
                        definition=m_def,
                        calibration=cal,
                        observed_value=float(raw_val),
                        is_available=True,
                    )
                )
            else:
                reason = st.selectbox(
                    "Motivo de indisponibilidade",
                    options=["ZERO_IMPRESSIONS", "NO_EXPOSURE", "TRACKING_ERROR", "OUTRO"],
                    key=f"reason_{m_def.key}",
                )
                custom_reason = reason
                if reason == "OUTRO":
                    custom_reason = (
                        st.text_input("Especifique o motivo", key=f"custom_reason_{m_def.key}")
                        or "INDISPONIVEL"
                    )

                snapshots.append(
                    MetricSnapshot(
                        definition=m_def,
                        calibration=cal,
                        observed_value=None,
                        is_available=False,
                        unavailability_reason=custom_reason,
                    )
                )

    return snapshots