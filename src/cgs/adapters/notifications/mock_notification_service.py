"""Adaptador de teste e mock in-memory com recursos avançados de inspeção e simulação de rede."""

from datetime import datetime, timezone
import time
from typing import List, Optional, Callable
import uuid

from cgs.application.ports.notification_service import (
    NotificationChannel,
    NotificationDeliveryResult,
    NotificationMessage,
    NotificationPriority,
    NotificationServicePort,
)


class NetworkSimulationError(IOError):
    """Erro simulado de timeout, DNS ou handshake de rede."""
    pass


class MockNotificationService(NotificationServicePort):
    """Mock de infraestrutura para testes de mensageria externa com gravador de chamadas."""

    def __init__(
        self,
        simulate_network_latency_ms: int = 0,
        failure_rate: float = 0.0,
        always_fail: bool = False,
        raise_on_network_error: bool = False,
    ):
        self.simulate_network_latency_ms = simulate_network_latency_ms
        self.failure_rate = failure_rate
        self.always_fail = always_fail
        self.raise_on_network_error = raise_on_network_error
        
        # Histórico de envio inspecionável (Test Spy)
        self.outbox: List[NotificationMessage] = []
        self.delivery_history: List[NotificationDeliveryResult] = []
        self._interceptors: List[Callable[[NotificationMessage], None]] = []

    def register_interceptor(self, callback: Callable[[NotificationMessage], None]) -> None:
        """Permite plugar asserções ou mutações durante o envio."""
        self._interceptors.append(callback)

    def send_notification(self, message: NotificationMessage) -> NotificationDeliveryResult:
        for interceptor in self._interceptors:
            interceptor(message)

        if self.simulate_network_latency_ms > 0:
            time.sleep(self.simulate_network_latency_ms / 1000.0)

        if self.raise_on_network_error:
            raise NetworkSimulationError("Falha de conexão com gateway de notificação (Simulated Timeout)")

        if self.always_fail:
            res = NotificationDeliveryResult(
                success=False,
                channel=message.channel,
                error_message="Simulated forced failure in notification gateway",
            )
            self.delivery_history.append(res)
            return res

        # Registro com sucesso
        self.outbox.append(message)
        res = NotificationDeliveryResult(
            success=True,
            channel=message.channel,
            message_id=f"mock-{uuid.uuid4().hex[:8]}",
        )
        self.delivery_history.append(res)
        return res

    def broadcast_report(
        self,
        report_markdown: str,
        recipients: List[str],
        channels: Optional[List[NotificationChannel]] = None,
    ) -> List[NotificationDeliveryResult]:
        target_channels = channels or [NotificationChannel.EMAIL]
        results = []

        for recipient in recipients:
            for ch in target_channels:
                msg = NotificationMessage(
                    subject="📊 Relatório Consolidado de Ciclo - CGS / CDMS",
                    body=report_markdown,
                    recipient=recipient,
                    channel=ch,
                    priority=NotificationPriority.HIGH,
                )
                results.append(self.send_notification(msg))

        return results

    def clear(self) -> None:
        """Limpa registros e buffers entre testes."""
        self.outbox.clear()
        self.delivery_history.clear()
        self._interceptors.clear()

    @property
    def total_sent(self) -> int:
        return len(self.outbox)

    def find_by_recipient(self, recipient: str) -> List[NotificationMessage]:
        return [m for m in self.outbox if m.recipient == recipient]

    def find_by_channel(self, channel: NotificationChannel) -> List[NotificationMessage]:
        return [m for m in self.outbox if m.channel == channel]