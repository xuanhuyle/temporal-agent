import sqlite3
from collections.abc import Iterator
from datetime import datetime, timezone

import pytest

from tasklane.config import Settings, load_settings
from tasklane.db import connect, migrate
from tasklane.providers import PayGateProvider
from vendor.paygate_sdk import PayGateClient, SandboxBackend

# Keep password hashing cheap in tests; production uses the configured cost.
TEST_PBKDF2_ITERATIONS = 1_000


@pytest.fixture
def settings() -> Settings:
    return load_settings(pbkdf2_iterations=TEST_PBKDF2_ITERATIONS, database_path=":memory:")


@pytest.fixture
def conn(settings: Settings) -> Iterator[sqlite3.Connection]:
    connection = connect(settings.database_path)
    migrate(connection)
    yield connection
    connection.close()


@pytest.fixture
def now() -> datetime:
    return datetime(2026, 1, 5, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def sandbox(now: datetime) -> SandboxBackend:
    return SandboxBackend(now=int(now.timestamp()))


@pytest.fixture
def provider(sandbox: SandboxBackend) -> PayGateProvider:
    return PayGateProvider(PayGateClient("sk_test_sandbox", backend=sandbox))
