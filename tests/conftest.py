"""Fixtures globais e configuração de ambiente de testes."""

import os
import tempfile
from typing import Generator
import pytest

from cgs.adapters.notifications.mock_notification_service import (
    MockNotificationService,
)
from cgs.adapters.persistence.sqlite_growth_repo import SQLiteGrowthRepository


@pytest.fixture
def mock_notifier() -> MockNotificationService:
    """Fixture para mock do serviço de e-mail/notificações."""
    service = MockNotificationService()
    yield service
    service.clear()


@pytest.fixture
def failing_notifier() -> MockNotificationService:
    """Fixture de mock configurado para simular falhas de rede e indisponibilidade."""
    return MockNotificationService(always_fail=True)


@pytest.fixture
def network_timeout_notifier() -> MockNotificationService:
    """Fixture configurada para levantar NetworkSimulationError."""
    return MockNotificationService(raise_on_network_error=True)


@pytest.fixture
def temp_growth_repo() -> Generator[SQLiteGrowthRepository, None, None]:
    """Repositório SQLite isolado em diretório temporário compatível com Windows."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    repo = SQLiteGrowthRepository(path)

    try:
        yield repo
    finally:
        os.remove(path)
