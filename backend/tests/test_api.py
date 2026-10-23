from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app(Settings(docs_enabled=True))) as test_client:
        yield test_client


def test_health_contract(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "dota-hub-api"}
    assert response.headers["content-type"] == "application/json"
    assert response.headers["cache-control"] == "no-store"


def test_missing_endpoint(client: TestClient) -> None:
    response = client.get("/api/v1/matches/123/analysis")
    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "NOT_FOUND", "message": "Ресурс не найден", "details": []}
    }


def test_method_not_allowed(client: TestClient) -> None:
    response = client.post("/api/v1/health")
    assert response.status_code == 405
    assert response.json()["error"]["code"] == "METHOD_NOT_ALLOWED"
    assert "GET" in response.headers["allow"]


def test_internal_error_does_not_expose_details() -> None:
    application = create_app()

    @application.get("/test-error")
    async def fail() -> None:
        raise RuntimeError("private-diagnostic-marker")

    with TestClient(application, raise_server_exceptions=False) as client:
        response = client.get("/test-error")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "private-diagnostic-marker" not in response.text


def test_validation_error_does_not_echo_input() -> None:
    application = create_app()

    @application.get("/test-validation")
    async def validate(count: int) -> dict[str, int]:
        return {"count": count}

    with TestClient(application) as client:
        response = client.get("/test-validation", params={"count": "private-input-marker"})
    assert response.status_code == 422
    assert response.json()["error"]["details"] == [
        {"field": "query.count", "message": "Некорректное значение"}
    ]
    assert "private-input-marker" not in response.text


def test_settings_can_disable_documentation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOTA_DOCS_ENABLED", "false")
    with TestClient(create_app()) as client:
        assert client.get("/docs").status_code == 404
        assert client.get("/openapi.json").status_code == 404
        assert client.get("/api/v1/health").status_code == 200


def test_no_cross_origin_access_is_enabled(client: TestClient) -> None:
    response = client.get("/api/v1/health", headers={"Origin": "https://example.org"})
    assert "access-control-allow-origin" not in response.headers
