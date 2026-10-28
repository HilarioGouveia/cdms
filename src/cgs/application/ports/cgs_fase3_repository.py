"""Porta dirigida para persistência da Fase 3 do CGS (Bandits, Tráfego e Disjuntores)."""

from abc import ABC, abstractmethod
from typing import List, Optional
from cgs.domain.entities.bandit_policy import BanditOptimizationResult, CircuitBreakerStatus, VariantArm


class CGSPhase3RepositoryPort(ABC):
    @abstractmethod
    def save_bandit_decision(self, result: BanditOptimizationResult) -> None:
        pass

    @abstractmethod
    def get_latest_bandit_decision(self, hypothesis_id: int) -> Optional[BanditOptimizationResult]:
        pass

    @abstractmethod
    def record_circuit_breaker_event(self, status: CircuitBreakerStatus) -> None:
        pass

    @abstractmethod
    def get_active_circuit_breaker(self, hypothesis_id: int) -> Optional[CircuitBreakerStatus]:
        pass