"""Contrato da porta de persistência para o Creator Growth System (CGS)."""

from abc import ABC, abstractmethod
from typing import List, Optional

from cgs.domain.entities.funnel import FunnelBaseline, FunnelOpportunityAudit
from cgs.domain.entities.hypothesis import GrowthHypothesis, HypothesisStatus


class GrowthRepositoryPort(ABC):
    """Porta dirigida (Driven Port) para operações de persistência do CGS."""

    @abstractmethod
    def save_funnel_audit(self, audit: FunnelOpportunityAudit) -> FunnelOpportunityAudit:
        """Persiste um diagnóstico de oportunidade de funil associado a um ciclo de origem."""
        pass

    @abstractmethod
    def get_funnel_audit(self, source_cycle_id: str) -> Optional[FunnelOpportunityAudit]:
        """Recupera a auditoria de funil pelo identificador do ciclo de origem."""
        pass

    @abstractmethod
    def save_baseline(self, baseline: FunnelBaseline) -> FunnelBaseline:
        """Persiste uma nova linha de base do funil, marcando-a como ativa."""
        pass

    @abstractmethod
    def get_active_baseline(self) -> Optional[FunnelBaseline]:
        """Obtém a linha de base ativa de referência do funil."""
        pass

    @abstractmethod
    def save_hypothesis(self, hypothesis: GrowthHypothesis) -> GrowthHypothesis:
        """Cria ou atualiza uma hipótese operacional no repositório."""
        pass

    @abstractmethod
    def get_hypothesis_by_id(self, hypothesis_id: int) -> Optional[GrowthHypothesis]:
        """Recupera uma hipótese pelo seu identificador primário."""
        pass

    @abstractmethod
    def list_hypotheses(
        self,
        status: Optional[HypothesisStatus] = None,
        limit: int = 50,
    ) -> List[GrowthHypothesis]:
        """Lista hipóteses com ordenação estável por ICE score decrescente, data e ID."""
        pass

    @abstractmethod
    def update_hypothesis_status(
        self,
        hypothesis_id: int,
        status: HypothesisStatus,
        target_cycle_id: Optional[str] = None,
        promoted_decision_id: Optional[int] = None,
    ) -> GrowthHypothesis:
        """Atualiza atipicamente o status e os vínculos operacionais de uma hipótese."""
        pass