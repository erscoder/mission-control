"""Cloudflare tools for CrewAI agents.

Wrap Cloudflare API v4 calls (Pages + DNS) so the deploy agent can ship the
generated frontend to ``<slug>.pages.dev`` and point ``<slug>.erslabs.net`` at
it. Uses ``httpx`` with ``CLOUDFLARE_API_TOKEN`` + ``CLOUDFLARE_ACCOUNT_ID``.

Zone ID for ``erslabs.net`` is resolved on demand via the zones endpoint.
"""
from __future__ import annotations

import io
import json
import logging
import os
import tarfile
from pathlib import Path
from typing import Type

import httpx
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

log = logging.getLogger("sentinel_v2.tools.cloudflare")

CF_API = "https://api.cloudflare.com/client/v4"
ERSLABS_ROOT_DOMAIN = "erslabs.net"


def _auth_headers() -> dict[str, str]:
    token = os.environ.get("CLOUDFLARE_API_TOKEN")
    if not token:
        raise RuntimeError("CLOUDFLARE_API_TOKEN not set")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _account_id() -> str:
    acct = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    if not acct:
        raise RuntimeError("CLOUDFLARE_ACCOUNT_ID not set")
    return acct


def _resolve_zone_id(zone_name: str = ERSLABS_ROOT_DOMAIN) -> str:
    """Resolve the Cloudflare zone id for a given root domain."""
    resp = httpx.get(
        f"{CF_API}/zones",
        params={"name": zone_name},
        headers=_auth_headers(),
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if not data.get("success") or not data["result"]:
        raise RuntimeError(f"zone {zone_name!r} not found on this account")
    return data["result"][0]["id"]


# ── Pages: create project ────────────────────────────────────────────────────


class PagesCreateInput(BaseModel):
    project_name: str = Field(..., description="Lowercase, hyphen-only slug — becomes <project>.pages.dev")
    production_branch: str = Field(default="main", description="Git-style production branch label")


class CloudflarePagesCreateTool(BaseTool):
    name: str = "cloudflare_pages_create"
    description: str = (
        "Create (or reuse) a Cloudflare Pages project for Direct Upload deploys. "
        "Returns {project_name, subdomain} where subdomain is <name>.pages.dev."
    )
    args_schema: Type[BaseModel] = PagesCreateInput

    def _run(self, project_name: str, production_branch: str = "main") -> str:
        acct = _account_id()
        # Check if exists
        r = httpx.get(
            f"{CF_API}/accounts/{acct}/pages/projects/{project_name}",
            headers=_auth_headers(),
            timeout=30,
        )
        if r.status_code == 200 and r.json().get("success"):
            result = r.json()["result"]
            return json.dumps({
                "project_name": result["name"],
                "subdomain": result.get("subdomain"),
                "reused": True,
            })

        payload = {
            "name": project_name,
            "production_branch": production_branch,
        }
        r = httpx.post(
            f"{CF_API}/accounts/{acct}/pages/projects",
            headers=_auth_headers(),
            json=payload,
            timeout=30,
        )
        r.raise_for_status()
        result = r.json()["result"]
        return json.dumps({
            "project_name": result["name"],
            "subdomain": result.get("subdomain"),
            "reused": False,
        })


# ── Pages: deploy (Direct Upload) ────────────────────────────────────────────


class PagesDeployInput(BaseModel):
    project_name: str = Field(..., description="Pages project name")
    dist_dir: str = Field(..., description="Absolute path to the built static site (e.g. workspace/frontend/out)")


class CloudflarePagesDeployTool(BaseTool):
    name: str = "cloudflare_pages_deploy"
    description: str = (
        "Deploy a static site to an existing Pages project via Direct Upload. "
        "Uploads the directory as a tarball. Returns {deployment_id, url}."
    )
    args_schema: Type[BaseModel] = PagesDeployInput

    def _run(self, project_name: str, dist_dir: str) -> str:
        acct = _account_id()
        path = Path(dist_dir)
        if not path.is_dir():
            return f"error: dist_dir {dist_dir!r} not a directory"

        # Build tarball in-memory
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            tar.add(str(path), arcname=".")
        buf.seek(0)

        headers = {k: v for k, v in _auth_headers().items() if k != "Content-Type"}
        files = {"file": ("dist.tar.gz", buf, "application/gzip")}
        data = {"branch": "main"}
        r = httpx.post(
            f"{CF_API}/accounts/{acct}/pages/projects/{project_name}/deployments",
            headers=headers,
            files=files,
            data=data,
            timeout=300,
        )
        r.raise_for_status()
        result = r.json()["result"]
        return json.dumps({
            "deployment_id": result.get("id"),
            "url": result.get("url"),
        })


# ── Pages: env vars ──────────────────────────────────────────────────────────


class PagesSetEnvInput(BaseModel):
    project_name: str = Field(..., description="Pages project name")
    env_vars: dict[str, str] = Field(..., description="Dict of env vars to set on production")


class CloudflarePagesSetEnvTool(BaseTool):
    name: str = "cloudflare_pages_set_env"
    description: str = "Set production env vars on a Cloudflare Pages project (e.g. NEXT_PUBLIC_API_URL)."
    args_schema: Type[BaseModel] = PagesSetEnvInput

    def _run(self, project_name: str, env_vars: dict[str, str]) -> str:
        acct = _account_id()
        deploy_vars = {
            k: {"value": v, "type": "plain_text"}
            for k, v in env_vars.items()
        }
        payload = {
            "deployment_configs": {
                "production": {
                    "env_vars": deploy_vars,
                }
            }
        }
        r = httpx.patch(
            f"{CF_API}/accounts/{acct}/pages/projects/{project_name}",
            headers=_auth_headers(),
            json=payload,
            timeout=30,
        )
        r.raise_for_status()
        return json.dumps({"updated": list(env_vars.keys())})


# ── DNS: CNAME ───────────────────────────────────────────────────────────────


class DnsCnameInput(BaseModel):
    subdomain: str = Field(..., description="Label only (no dots), e.g. 'myapp' → myapp.erslabs.net")
    target: str = Field(..., description="CNAME target, e.g. myapp.pages.dev")
    proxied: bool = Field(default=True, description="Whether to proxy through Cloudflare")


class CloudflareDnsCnameTool(BaseTool):
    name: str = "cloudflare_dns_cname"
    description: str = (
        "Create a CNAME record on the erslabs.net zone. If a record for the same "
        "subdomain already exists, updates it. Returns {record_id, name, target}."
    )
    args_schema: Type[BaseModel] = DnsCnameInput

    def _run(self, subdomain: str, target: str, proxied: bool = True) -> str:
        if "." in subdomain:
            return f"error: subdomain {subdomain!r} must not contain dots"
        zone_id = _resolve_zone_id()
        fqdn = f"{subdomain}.{ERSLABS_ROOT_DOMAIN}"

        # Upsert
        existing = httpx.get(
            f"{CF_API}/zones/{zone_id}/dns_records",
            params={"name": fqdn, "type": "CNAME"},
            headers=_auth_headers(),
            timeout=30,
        ).json()

        payload = {
            "type": "CNAME",
            "name": fqdn,
            "content": target,
            "ttl": 1,  # auto
            "proxied": proxied,
        }
        if existing.get("success") and existing["result"]:
            record_id = existing["result"][0]["id"]
            r = httpx.put(
                f"{CF_API}/zones/{zone_id}/dns_records/{record_id}",
                headers=_auth_headers(),
                json=payload,
                timeout=30,
            )
        else:
            r = httpx.post(
                f"{CF_API}/zones/{zone_id}/dns_records",
                headers=_auth_headers(),
                json=payload,
                timeout=30,
            )
        r.raise_for_status()
        result = r.json()["result"]
        return json.dumps({
            "record_id": result["id"],
            "name": result["name"],
            "target": result["content"],
        })


# ── Pages: custom domain ─────────────────────────────────────────────────────


class PagesCustomDomainInput(BaseModel):
    project_name: str = Field(..., description="Pages project name")
    domain: str = Field(..., description="FQDN, e.g. myapp.erslabs.net")


class CloudflarePagesAddCustomDomainTool(BaseTool):
    name: str = "cloudflare_pages_add_custom_domain"
    description: str = "Attach a custom domain (e.g. myapp.erslabs.net) to a Cloudflare Pages project."
    args_schema: Type[BaseModel] = PagesCustomDomainInput

    def _run(self, project_name: str, domain: str) -> str:
        acct = _account_id()
        r = httpx.post(
            f"{CF_API}/accounts/{acct}/pages/projects/{project_name}/domains",
            headers=_auth_headers(),
            json={"name": domain},
            timeout=30,
        )
        # 409 (already attached) is fine
        if r.status_code in (200, 201):
            result = r.json().get("result", {})
            return json.dumps({"domain": result.get("name", domain), "status": result.get("status")})
        if r.status_code == 409:
            return json.dumps({"domain": domain, "status": "already_attached"})
        r.raise_for_status()
        return r.text
