"""Caso de uso: Sincronização do Veredito da Decisão CDMS no CGS."""

from enum import Enum
from typing import Optional

from cgs.application.ports.growth_repository import GrowthRepositoryPort
from cgs.domain.entities.hypothesis import GrowthHypothesis, HypothesisStatus


class CDMSDecisionVerdict(str, Enum):
    """Veredito emitido na auditoria do ritual semanal do CDMS."""
    ACHIEVED = "ACHIEVED"
    PARTIAL = "PARTIAL"
    NOT_ACHIEVED = "NOT_ACHIEVED"


class SyncCDMSOutcomeUseCase:
    """Sincroniza o desfecho auditado no CDMS com o ciclo de vida da hipótese CGS."""

    def __init__(self, repository: GrowthRepositoryPort):
        self._repository = repository

    def execute(
        self,
        decision_id: int,
        verdict: str,
    ) -> Optional[GrowthHypothesis]:
        """Atualiza a hipótese vinculada à decisão de acordo com o veredito emitido.

        Mapeamento:
        - ACHIEVED / PARTIAL -> COMPLETED
        - NOT_ACHIEVED -> DISCARDED
        """
        hypo = self._repository.get_hypothesis_by_decision_id(decision_id)
        if not hypo:
            return None

        # Se já estiver num estado terminal, preserva o estado
        if hypo.status in (HypothesisStatus.COMPLETED, HypothesisStatus.DISCARDED):
            return hypo

        verdict_upper = verdict.upper()
        if verdict_upper in (CDMSDecisionVerdict.ACHIEVED.value, CDMSDecisionVerdict.PARTIAL.value):
            hypo.complete()
        elif verdict_upper == CDMSDecisionVerdict.NOT_ACHIEVED.value:
            hypo.discard()
        else:
            return hypo

        return self._repository.update_hypothesis_status(
            hypothesis_id=hypo.id,
            status=hypo.status,
        )    