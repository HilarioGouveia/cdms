"""Porta dirigida (Driven Port) para serviços de notificação e mensageria externa."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class NotificationChannel(str, Enum):
    EMAIL = "EMAIL"
    SLACK = "SLACK"
    DISCORD = "DISCORD"
    WEBHOOK = "WEBHOOK"


class NotificationPriority(str, Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class NotificationMessage:
    """Mensagem normalizada independente do meio de transporte."""
    subject: str
    body: str
    recipient: str
    channel: NotificationChannel = NotificationChannel.EMAIL
    priority: NotificationPriority = NotificationPriority.NORMAL
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class NotificationDeliveryResult:
    """Resultado da tentativa de despacho da notificação."""
    success: bool
    channel: NotificationChannel
    message_id: Optional[str] = None
    error_message: Optional[str] = None
    sent_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class NotificationServicePort(ABC):
    """Interface abstrata para envio de alertas de governança e relatórios de ciclo."""

    @abstractmethod
    def send_notification(self, message: NotificationMessage) -> NotificationDeliveryResult:
        """Envia uma notificação síncrona/transacional."""
        pass

    @abstractmethod
    def broadcast_report(
        self,
        report_markdown: str,
        recipients: List[str],
        channels: Optional[List[NotificationChannel]] = None,
    ) -> List[NotificationDeliveryResult]:
        """Dispara relatório semanal consolidado para múltiplos destinatários."""
        pass