"""Multi-tenant / multi-user resolution from a YAML config.

Mirrors the pattern of the Scaleflow memory MCP: each API key maps to an
identity. For Oura, the relevant identity is the *person* (`user`), since each
member connects their own ring. Tokens OAuth se guardan por `user`.

Formato de `config/tenants.yaml`:

    default_tenant: "scaleflow"
    tenants:
      scaleflow:
        name: "Scaleflow Internal"
        api_keys:
          - key: "sk-sf-kike-xxxx"
            agent: "claude-code"
            user: "kike"             # <- clave de almacenamiento de tokens Oura
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass
from pathlib import Path

import yaml

from oura_mcp_server.config import get_settings


@dataclass
class TenantInfo:
    tenant_id: str
    name: str
    agent: str = ""
    user: str = ""

    @property
    def oura_user_id(self) -> str:
        """Clave estable para guardar/leer tokens Oura de esta identidad."""
        return self.user or self.tenant_id


_key_lookup: dict[str, TenantInfo] | None = None
_default_tenant: TenantInfo | None = None


def _get_path() -> Path:
    return Path(get_settings().tenants_config_path)


def _load() -> None:
    global _key_lookup, _default_tenant

    default_id = get_settings().default_tenant_id
    path = _get_path()
    if not path.exists():
        _default_tenant = TenantInfo(tenant_id=default_id, name="Default")
        _key_lookup = {}
        return

    with open(path) as f:
        data = yaml.safe_load(f) or {}

    _key_lookup = {}
    tenants = data.get("tenants", {})
    default_id = data.get("default_tenant", default_id)

    for tenant_id, tenant_data in tenants.items():
        name = tenant_data.get("name", tenant_id)
        for key_entry in tenant_data.get("api_keys", []):
            _key_lookup[key_entry["key"]] = TenantInfo(
                tenant_id=tenant_id,
                name=name,
                agent=key_entry.get("agent", ""),
                user=key_entry.get("user", ""),
            )
        if tenant_id == default_id:
            _default_tenant = TenantInfo(tenant_id=tenant_id, name=name)

    if _default_tenant is None:
        _default_tenant = TenantInfo(tenant_id=default_id, name=default_id)


def reload() -> None:
    global _key_lookup, _default_tenant
    _key_lookup = None
    _default_tenant = None
    _load()


def resolve_tenant(api_key: str) -> TenantInfo | None:
    if _key_lookup is None:
        _load()
    assert _key_lookup is not None
    return _key_lookup.get(api_key)


def get_default_tenant() -> TenantInfo:
    if _default_tenant is None:
        _load()
    assert _default_tenant is not None
    return _default_tenant


def generate_api_key(prefix: str) -> str:
    return f"sk-{prefix}-{secrets.token_hex(10)}"
