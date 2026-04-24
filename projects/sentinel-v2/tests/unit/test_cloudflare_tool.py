"""Tests for cloudflare_tool.py — Cloudflare API v4 wrapper (httpx mocked)."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from sentinel_v2.tools.cloudflare_tool import (
    CloudflareDnsCnameTool,
    CloudflarePagesAddCustomDomainTool,
    CloudflarePagesCreateTool,
    CloudflarePagesSetEnvTool,
    _resolve_zone_id,
)


@pytest.fixture(autouse=True)
def _cf_creds(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "cf_test_123")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acct_ABC")


def _ok_response(result: dict | list, status: int = 200):
    mock = MagicMock()
    mock.status_code = status
    mock.json.return_value = {"success": True, "result": result}
    mock.raise_for_status.return_value = None
    return mock


def _not_found_response():
    mock = MagicMock()
    mock.status_code = 404
    mock.json.return_value = {"success": False, "errors": []}
    mock.raise_for_status.side_effect = Exception("404")
    return mock


# ── _resolve_zone_id ─────────────────────────────────────────────────────────


def test_resolve_zone_id_returns_first():
    response = _ok_response([{"id": "zone_abc", "name": "erslabs.net"}])
    with patch("sentinel_v2.tools.cloudflare_tool.httpx.get", return_value=response):
        zone_id = _resolve_zone_id("erslabs.net")
    assert zone_id == "zone_abc"


def test_resolve_zone_id_raises_on_empty():
    response = _ok_response([])
    with patch("sentinel_v2.tools.cloudflare_tool.httpx.get", return_value=response):
        with pytest.raises(RuntimeError, match="not found"):
            _resolve_zone_id("missing.net")


# ── CloudflarePagesCreateTool ────────────────────────────────────────────────


def test_pages_create_reuses_existing():
    existing = _ok_response({"name": "myapp", "subdomain": "myapp.pages.dev"})
    with patch("sentinel_v2.tools.cloudflare_tool.httpx.get", return_value=existing):
        result = CloudflarePagesCreateTool()._run(project_name="myapp")
    data = json.loads(result)
    assert data["reused"] is True
    assert data["subdomain"] == "myapp.pages.dev"


def test_pages_create_creates_new():
    get_response = _not_found_response()
    post_response = _ok_response({"name": "newapp", "subdomain": "newapp.pages.dev"}, status=201)
    with patch("sentinel_v2.tools.cloudflare_tool.httpx.get", return_value=get_response), \
         patch("sentinel_v2.tools.cloudflare_tool.httpx.post", return_value=post_response):
        result = CloudflarePagesCreateTool()._run(project_name="newapp")
    data = json.loads(result)
    assert data["reused"] is False
    assert data["project_name"] == "newapp"


# ── CloudflareDnsCnameTool ───────────────────────────────────────────────────


def test_dns_cname_rejects_dots_in_subdomain():
    result = CloudflareDnsCnameTool()._run(
        subdomain="my.app", target="target.pages.dev"
    )
    assert "must not contain dots" in result


def test_dns_cname_creates_new():
    zone_response = _ok_response([{"id": "zone_abc", "name": "erslabs.net"}])
    list_response = _ok_response([])  # no existing
    create_response = _ok_response({
        "id": "rec_123",
        "name": "myapp.erslabs.net",
        "content": "myapp.pages.dev",
    }, status=201)

    def fake_get(url, **_):
        if "zones/zone_abc/dns_records" in url:
            return list_response
        return zone_response

    with patch("sentinel_v2.tools.cloudflare_tool.httpx.get", side_effect=fake_get), \
         patch("sentinel_v2.tools.cloudflare_tool.httpx.post", return_value=create_response):
        result = CloudflareDnsCnameTool()._run(subdomain="myapp", target="myapp.pages.dev")

    data = json.loads(result)
    assert data["record_id"] == "rec_123"
    assert data["name"] == "myapp.erslabs.net"


def test_dns_cname_updates_existing():
    zone_response = _ok_response([{"id": "zone_abc", "name": "erslabs.net"}])
    existing = _ok_response([{
        "id": "rec_existing",
        "name": "myapp.erslabs.net",
        "content": "old.pages.dev",
    }])
    updated = _ok_response({
        "id": "rec_existing",
        "name": "myapp.erslabs.net",
        "content": "myapp.pages.dev",
    })

    def fake_get(url, **_):
        if "zones/zone_abc/dns_records" in url:
            return existing
        return zone_response

    with patch("sentinel_v2.tools.cloudflare_tool.httpx.get", side_effect=fake_get), \
         patch("sentinel_v2.tools.cloudflare_tool.httpx.put", return_value=updated) as mock_put:
        result = CloudflareDnsCnameTool()._run(subdomain="myapp", target="myapp.pages.dev")

    data = json.loads(result)
    assert data["record_id"] == "rec_existing"
    mock_put.assert_called_once()


# ── CloudflarePagesAddCustomDomainTool ───────────────────────────────────────


def test_add_custom_domain_success():
    response = _ok_response({"name": "myapp.erslabs.net", "status": "pending"}, status=201)
    with patch("sentinel_v2.tools.cloudflare_tool.httpx.post", return_value=response):
        result = CloudflarePagesAddCustomDomainTool()._run(
            project_name="myapp", domain="myapp.erslabs.net"
        )
    data = json.loads(result)
    assert data["domain"] == "myapp.erslabs.net"


def test_add_custom_domain_already_attached_is_ok():
    mock = MagicMock()
    mock.status_code = 409
    mock.json.return_value = {}
    with patch("sentinel_v2.tools.cloudflare_tool.httpx.post", return_value=mock):
        result = CloudflarePagesAddCustomDomainTool()._run(
            project_name="myapp", domain="myapp.erslabs.net"
        )
    data = json.loads(result)
    assert data["status"] == "already_attached"


# ── CloudflarePagesSetEnvTool ────────────────────────────────────────────────


def test_pages_set_env_formats_payload():
    response = _ok_response({})
    with patch("sentinel_v2.tools.cloudflare_tool.httpx.patch", return_value=response) as mock_patch:
        result = CloudflarePagesSetEnvTool()._run(
            project_name="myapp",
            env_vars={"NEXT_PUBLIC_API_URL": "https://api.fly.dev"},
        )
    data = json.loads(result)
    assert data["updated"] == ["NEXT_PUBLIC_API_URL"]
    _, kwargs = mock_patch.call_args
    payload = kwargs["json"]
    assert payload["deployment_configs"]["production"]["env_vars"][
        "NEXT_PUBLIC_API_URL"
    ]["value"] == "https://api.fly.dev"


# ── Missing env vars ─────────────────────────────────────────────────────────


def test_missing_cf_token_raises(monkeypatch):
    monkeypatch.delenv("CLOUDFLARE_API_TOKEN", raising=False)
    from sentinel_v2.tools.cloudflare_tool import _auth_headers
    with pytest.raises(RuntimeError, match="CLOUDFLARE_API_TOKEN"):
        _auth_headers()


def test_missing_cf_account_raises(monkeypatch):
    monkeypatch.delenv("CLOUDFLARE_ACCOUNT_ID", raising=False)
    from sentinel_v2.tools.cloudflare_tool import _account_id
    with pytest.raises(RuntimeError, match="CLOUDFLARE_ACCOUNT_ID"):
        _account_id()
