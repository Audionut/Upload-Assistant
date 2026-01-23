import json
import os
from typing import Any


def _auth_header() -> dict[str, str]:
    token = os.environ.get("UA_TOKEN") or os.environ.get("UA_TEST_BEARER_TOKEN")
    return {"Authorization": f"Bearer {token}"} if token else {}


def test_health(client: Any) -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    data: dict[str, Any] = r.get_json()
    assert data and data.get("success") is True
    assert data.get("status") == "healthy"


def test_csrf_token_with_bearer(client: Any) -> None:
    headers = _auth_header()
    r = client.get("/api/csrf_token", headers=headers)
    assert r.status_code == 200
    data: dict[str, Any] = r.get_json()
    assert isinstance(data, dict) and "csrf_token" in data


def test_2fa_status_with_bearer(client: Any) -> None:
    headers = _auth_header()
    r = client.get("/api/2fa/status", headers=headers)
    assert r.status_code == 200
    data: dict[str, Any] = r.get_json()
    assert isinstance(data, dict) and data.get("success") is True


def test_config_options_and_torrent_clients_with_bearer(client: Any) -> None:
    headers = _auth_header()
    r = client.get("/api/config_options", headers=headers)
    assert r.status_code == 200
    data = r.get_json()
    assert data.get("success") is True and isinstance(data.get("sections"), list)

    r2 = client.get("/api/torrent_clients", headers=headers)
    assert r2.status_code == 200
    d2: dict[str, Any] = r2.get_json()
    assert d2.get("success") is True and isinstance(d2.get("clients"), list)


def test_browse_roots_and_browse_with_bearer(client: Any) -> None:
    headers = _auth_header()
    r = client.get("/api/browse_roots", headers=headers)
    # No browse roots configured in test env: expect 400
    assert r.status_code == 400

    r2 = client.get("/api/browse?path=/", headers=headers)
    assert r2.status_code == 400


def test_config_update_and_remove_subsection_validation(client: Any) -> None:
    headers = _auth_header()
    # invalid payload (path must be a list)
    r = client.post("/api/config_update", headers={**headers, "Content-Type": "application/json"}, data=json.dumps({"path": "not-a-list", "value": "x"}))
    assert r.status_code == 400

    r2 = client.post("/api/config_remove_subsection", headers={**headers, "Content-Type": "application/json"}, data=json.dumps({"path": "not-a-list"}))
    assert r2.status_code == 400


def test_execute_requires_json(client: Any) -> None:
    headers = _auth_header()
    r = client.post("/api/execute", headers={**headers, "Content-Type": "application/json"}, data=json.dumps({}))
    # empty JSON returns 400 (no JSON data received)
    assert r.status_code == 400


def test_tokens_endpoint_requires_session(client: Any) -> None:
    headers = _auth_header()
    r = client.get("/api/tokens", headers=headers)
    assert r.status_code == 401
