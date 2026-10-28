"""Catálogo e calibrações iniciais das quatro métricas canônicas."""
from cdms.domain.entities.metric import MetricDefinition, MetricCalibration

CANONICAL_DEFINITIONS = [
    MetricDefinition("reach", "Alcance Semanal", "usuários", "Total de contas únicas alcançadas no canal principal"),
    MetricDefinition("avg_retention_pct", "Retenção Média", "%", "Média ponderada do tempo assistido relativo à duração"),
    MetricDefinition("ctr_pct", "Taxa de Cliques (CTR)", "%", "(Cliques Registrados / Impressões Totais) * 100"),
    MetricDefinition("conversions", "Conversões", "un", "Contagem total de eventos de fundo de funil (leads/vendas)"),
]

DEFAULT_CALIBRATIONS = {
    "reach": MetricCalibration("reach", 1000.0, 5000.0),
    "avg_retention_pct": MetricCalibration("avg_retention_pct", 30.0, 60.0),
    "ctr_pct": MetricCalibration("ctr_pct", 2.0, 5.0),
    "conversions": MetricCalibration("conversions", 10.0, 30.0),
}

