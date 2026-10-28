"""Adaptador de infraestrutura para leitura e normalização de relatórios de plataformas."""
from dataclasses import dataclass
from typing import Optional
import io
import pandas as pd


@dataclass(frozen=True)
class ParsedMetricsDTO:
    reach: Optional[float] = None
    retention_pct: Optional[float] = None
    ctr_pct: Optional[float] = None
    conversions: Optional[float] = None


class PlatformMetricsParser:
    """Extrai as 4 métricas canónicas do CDMS a partir de relatórios CSV ou XLSX."""

    @staticmethod
    def parse_file(file_bytes: bytes, filename: str) -> ParsedMetricsDTO:
        name_lower = filename.lower()
        bio = io.BytesIO(file_bytes)

        if name_lower.endswith(".csv"):
            try:
                df = pd.read_csv(bio, sep=",")
            except Exception:
                bio.seek(0)
                df = pd.read_csv(bio, sep=";")
        elif name_lower.endswith((".xlsx", ".xls")):
            df = pd.read_excel(bio)
        else:
            raise ValueError("Formato de ficheiro inválido. Envie um ficheiro .csv ou .xlsx.")

        # Normalizar nomes de colunas
        df.columns = [str(col).strip().lower().replace(" ", "_") for col in df.columns]

        reach_val = None
        retention_val = None
        ctr_val = None
        conv_val = None

        # 1. Mapeamento de Alcance / Reach / Impressões
        for col in ["reach", "alcance", "impressions", "impressoes", "views", "visualizacoes"]:
            if col in df.columns:
                reach_val = float(pd.to_numeric(df[col], errors="coerce").fillna(0).sum())
                break

        # 2. Mapeamento de Retenção Média (%)
        for col in ["retention_pct", "retencao", "avg_retention", "duracao_media_pct", "retention"]:
            if col in df.columns:
                val = float(pd.to_numeric(df[col], errors="coerce").fillna(0).mean())
                retention_val = val * 100 if val <= 1.0 and val > 0 else val
                break

        # 3. Mapeamento de CTR (%)
        for col in ["ctr", "ctr_pct", "taxa_cliques", "click_through_rate"]:
            if col in df.columns:
                val = float(pd.to_numeric(df[col], errors="coerce").fillna(0).mean())
                ctr_val = val * 100 if val <= 1.0 and val > 0 else val
                break

        # 4. Mapeamento de Conversões (unidades)
        for col in ["conversions", "conversoes", "vendas", "leads", "compras"]:
            if col in df.columns:
                conv_val = float(pd.to_numeric(df[col], errors="coerce").fillna(0).sum())
                break

        return ParsedMetricsDTO(
            reach=reach_val,
            retention_pct=retention_val,
            ctr_pct=ctr_val,
            conversions=conv_val
        )