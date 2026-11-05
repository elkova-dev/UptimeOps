from fastapi.testclient import TestClient
from uptimeops.api import app


def test_health_and_url_validation() -> None:
    client = TestClient(app)
    assert client.get('/api/health').json()['status'] == 'ok'
    assert client.post('/api/monitors', json={'name':'Example','url':'file:///etc/passwd'}).status_code == 422


def test_missing_monitor() -> None:
    client = TestClient(app)
    assert client.get('/api/monitors/9999999/checks').status_code == 404
