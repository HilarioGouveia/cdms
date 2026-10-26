from typing import List, Dict, Set
from cdms.domain.entities.metric import MetricSnapshot, MetricStatus
from cdms.domain.entities.scenario import Scenario, ScenarioType, InconclusiveReason

class ScenarioClassifier:
    """
    Serviço de Domínio Puro para classificação heurística em cascata de precedência estrita.
    Avalia o espaço exaustivo das 81 combinações das 4 métricas canônicas conforme SDD v2.3.1.
    """
    
    CANONICAL_KEYS: Set[str] = {"reach", "avg_retention_pct", "ctr_pct", "conversions"}

    def classify(self, snapshots: List[MetricSnapshot]) -> Scenario:
        # 1. Etapa de Guarda: Validação de presença exata das 4 chaves sem duplicatas
        if not snapshots:
            return Scenario(
                type=ScenarioType.INCONCLUSIVE,
                description="Nenhuma métrica foi fornecida para classificação.",
                recommendation="Forneça as 4 métricas canônicas obrigatórias.",
                evidence_metric_keys=[],
                inconclusive_reason=InconclusiveReason.MISSING_DATA
            )

        provided_keys = [s.definition.key for s in snapshots]
        unique_keys = set(provided_keys)

        if len(provided_keys) != len(unique_keys):
            return Scenario(
                type=ScenarioType.INCONCLUSIVE,
                description="Métricas duplicadas detectadas no vetor de entrada.",
                recommendation="Envie exatamente uma observação por métrica canônica.",
                evidence_metric_keys=provided_keys,
                inconclusive_reason=InconclusiveReason.MISSING_DATA
            )

        if unique_keys != self.CANONICAL_KEYS:
            missing = self.CANONICAL_KEYS - unique_keys
            unexpected = unique_keys - self.CANONICAL_KEYS
            desc_parts = []
            if missing:
                desc_parts.append(f"Métricas faltantes: {sorted(list(missing))}")
            if unexpected:
                desc_parts.append(f"Métricas inesperadas: {sorted(list(unexpected))}")
            return Scenario(
                type=ScenarioType.INCONCLUSIVE,
                description="Vetor de métricas incompatível com o catálogo canônico. " + " | ".join(desc_parts),
                recommendation="Certifique-se de preencher as 4 métricas obrigatórias: reach, avg_retention_pct, ctr_pct, conversions.",
                evidence_metric_keys=provided_keys,
                inconclusive_reason=InconclusiveReason.MISSING_DATA
            )

        # 2. Etapa de Guarda: Verificação de disponibilidade
        unavailable_snapshots = [s for s in snapshots if not s.is_available]
        if unavailable_snapshots:
            unavail_details = [
                f"{s.definition.key} ({s.unavailability_reason or 'SEM_MOTIVO'})"
                for s in unavailable_snapshots
            ]
            return Scenario(
                type=ScenarioType.INCONCLUSIVE,
                description=f"Métricas canônicas indisponíveis no ciclo: {', '.join(unavail_details)}.",
                recommendation="Ciclo classificado como inconclusivo por ausência de dados operacionais válidos.",
                evidence_metric_keys=[s.definition.key for s in unavailable_snapshots],
                inconclusive_reason=InconclusiveReason.MISSING_DATA
            )

        # 3. Contagem dos estados operacionais (BELOW, HEALTHY, ABOVE)
        status_map: Dict[str, MetricStatus] = {s.definition.key: s.status() for s in snapshots}
        
        below_keys = [k for k, st in status_map.items() if st == MetricStatus.BELOW]
        above_keys = [k for k, st in status_map.items() if st == MetricStatus.ABOVE]
        healthy_keys = [k for k, st in status_map.items() if st == MetricStatus.HEALTHY]

        below_count = len(below_keys)
        above_count = len(above_keys)

        # 4. Cascata de Precedência Estrita (SDD v2.3.1)
        if below_count >= 2:
            return Scenario(
                type=ScenarioType.PRE_DROP,
                description=f"Risco de Queda Operacional: múltiplos indicadores abaixo da referência ({', '.join(sorted(below_keys))}).",
                recommendation="Ação Corretiva: Investigar os indicadores abaixo da referência e priorizar uma ação coerente com as evidências.",
                evidence_metric_keys=sorted(below_keys),
                inconclusive_reason=None
            )

        if below_count >= 1 and above_count >= 1:
            return Scenario(
                type=ScenarioType.ANOMALY,
                description=f"Assimetria Crítica detectada entre etapas do funil: abaixo ({', '.join(sorted(below_keys))}) vs acima ({', '.join(sorted(above_keys))}).",
                recommendation="Investigação: Examinar a assimetria entre os indicadores abaixo e acima das referências.",
                evidence_metric_keys=sorted(below_keys + above_keys),
                inconclusive_reason=None
            )

        if below_count == 0 and above_count >= 2:
            return Scenario(
                type=ScenarioType.SCALE,
                description=f"Alavancagem de Escala: indicadores superando as metas de referência ({', '.join(sorted(above_keys))}).",
                recommendation="Expansão Gradual: Avaliar expansão conforme objetivo, capacidade e indicadores envolvidos.",
                evidence_metric_keys=sorted(above_keys),
                inconclusive_reason=None
            )

        if below_count == 0 and above_count <= 1:
            evidences = above_keys if above_keys else healthy_keys
            return Scenario(
                type=ScenarioType.STABILITY,
                description="Equilíbrio Operacional: operação em conformidade nominal dentro das faixas saudáveis.",
                recommendation="Consistência e Testes A/B: Otimizações incrementais sem romper a cadência de publicação.",
                evidence_metric_keys=sorted(evidences),
                inconclusive_reason=None
            )

        return Scenario(
            type=ScenarioType.INCONCLUSIVE,
            description=f"Sinais Mistos: apenas um indicador em desvio ({', '.join(sorted(below_keys))}) com os demais em equilíbrio.",
            recommendation="Observação Diligente: Monitorar o indicador isolado sem alterar o rumo estratégico.",
            evidence_metric_keys=sorted(below_keys),
            inconclusive_reason=InconclusiveReason.MIXED_SIGNALS
        )