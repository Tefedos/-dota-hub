from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError
import pytest

from app.core.config import Settings
from app.main import create_app


def test_local_routes_absent_when_flag_off() -> None:
    with TestClient(create_app(Settings(local_alpha=False, database_url=None))) as client:
        assert client.post('/api/v1/local-alpha/matches/123/analyze').status_code == 404


def test_local_flag_rejects_remote_database() -> None:
    with pytest.raises(ValidationError, match='loopback PostgreSQL'):
        Settings(local_alpha=True, database_url=SecretStr('postgresql+asyncpg://user@db.example.net/hub'))


def test_local_routes_reject_remote_clients_and_origins() -> None:
    config = Settings(local_alpha=True, database_url=SecretStr('postgresql+asyncpg://user@127.0.0.1:1/hub'))
    with TestClient(create_app(config), base_url='http://127.0.0.1:8000', client=('203.0.113.4', 50000)) as remote:
        assert remote.post('/api/v1/local-alpha/matches/123/analyze').status_code == 404
    with TestClient(create_app(config), base_url='http://127.0.0.1:8000', client=('127.0.0.1', 50000)) as local:
        assert local.post('/api/v1/local-alpha/matches/123/analyze', headers={'Origin': 'https://other.example'}).status_code == 403
