"""Testes unitários para validar fixtures de mock de rede, e-mail e notificações."""

import pytest
from cgs.adapters.notifications.mock_notification_service import (
    NetworkSimulationError,
)
from cgs.application.ports.notification_service import (
    NotificationChannel,
    NotificationMessage,
    NotificationPriority,
)


def test_mock_notifier_successful_delivery(mock_notifier):
    """Verifica envio bem-sucedido e rastreamento em outbox."""
    msg = NotificationMessage(
        subject="🚀 Alerta de Governança: Hipótese Ativada",
        body="A hipótese #12 foi promovida para o ciclo 2026-11-02.",
        recipient="creator@growth.com",
        channel=NotificationChannel.EMAIL,
        priority=NotificationPriority.HIGH,
    )

    result = mock_notifier.send_notification(msg)

    assert result.success is True
    assert result.message_id is not None
    assert mock_notifier.total_sent == 1
    assert len(mock_notifier.find_by_recipient("creator@growth.com")) == 1


def test_mock_notifier_broadcast(mock_notifier):
    """Verifica envio em lote de relatório para múltiplos canais e destinatários."""
    markdown_report = "# Relatório Semanal\n\n- Oportunidade recuperada: R$ 3.400,00"
    recipients = ["lead1@growth.com", "lead2@growth.com"]
    channels = [NotificationChannel.EMAIL, NotificationChannel.SLACK]

    results = mock_notifier.broadcast_report(
        report_markdown=markdown_report,
        recipients=recipients,
        channels=channels,
    )

    assert len(results) == 4
    assert all(r.success for r in results)
    assert len(mock_notifier.find_by_channel(NotificationChannel.SLACK)) == 2
    assert len(mock_notifier.find_by_channel(NotificationChannel.EMAIL)) == 2


def test_failing_notifier_fixture(failing_notifier):
    """Valida resiliência e captura de resposta sem levantar exceção quando o gateway falha."""
    msg = NotificationMessage(
        subject="Alerta Teste",
        body="Corpo do alerta",
        recipient="ops@growth.com",
    )

    result = failing_notifier.send_notification(msg)

    assert result.success is False
    assert "Simulated forced failure" in result.error_message
    assert failing_notifier.total_sent == 0


def test_network_timeout_notifier_fixture(network_timeout_notifier):
    """Valida o lançamento de erro simulado de timeout/rede."""
    msg = NotificationMessage(
        subject="Tentativa com Timeout",
        body="Corpo do teste",
        recipient="ops@growth.com",
    )

    with pytest.raises(NetworkSimulationError, match="Falha de conexão com gateway"):
        network_timeout_notifier.send_notification(msg)