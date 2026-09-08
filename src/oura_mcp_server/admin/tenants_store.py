"""Lectura/escritura de config/tenants.yaml para el panel admin.

A diferencia de auth/tenants.py (que carga el YAML una vez a memoria para
resolver keys en cada request MCP), este modulo relee el archivo en cada
operacion: el admin puede editarlo a mano por SSH mientras el panel esta
abierto, y no queremos pisar esos cambios con una copia vieja en memoria.

Limitacion conocida: `yaml.safe_dump` reescribe el archivo completo, asi que
cualquier comentario manual en tenants.yaml se pierde en el siguiente guardado
desde este modulo.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from threading import Lock

import yaml

from oura_mcp_server.auth.tenants import generate_api_key

_write_lock = Lock()


@dataclass
class KeyEntry:
    tenant_id: str
    tenant_name: str
    key_id: str
    key_masked: str
    agent: str
    user: str


def _key_id(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]


def _mask(key: str) -> str:
    if len(key) <= 14:
        return key
    return f"{key[:10]}…{key[-4:]}"


def _load_raw(path: Path) -> dict:
    if not path.exists():
        return {"default_tenant": "scaleflow", "tenants": {}}
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    data.setdefault("tenants", {})
    return data


def _save_raw(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)


def list_all(path: Path) -> list[KeyEntry]:
    data = _load_raw(path)
    entradas: list[KeyEntry] = []
    for tenant_id, tenant_data in data.get("tenants", {}).items():
        tenant_name = tenant_data.get("name", tenant_id)
        for key_entry in tenant_data.get("api_keys", []):
            key = key_entry["key"]
            entradas.append(
                KeyEntry(
                    tenant_id=tenant_id,
                    tenant_name=tenant_name,
                    key_id=_key_id(key),
                    key_masked=_mask(key),
                    agent=key_entry.get("agent", ""),
                    user=key_entry.get("user", ""),
                )
            )
    return entradas


def create_key(path: Path, tenant_id: str, tenant_name: str, agent: str, user: str) -> str:
    """Crea una key nueva y la persiste. Devuelve la key completa (una sola vez)."""
    with _write_lock:
        data = _load_raw(path)
        tenants = data.setdefault("tenants", {})
        tenant = tenants.setdefault(tenant_id, {"name": tenant_name, "api_keys": []})
        tenant.setdefault("name", tenant_name)
        tenant.setdefault("api_keys", [])

        key = generate_api_key(f"oura-{user}" if user else f"oura-{tenant_id}")
        tenant["api_keys"].append({"key": key, "agent": agent, "user": user})

        data.setdefault("default_tenant", tenant_id)
        _save_raw(path, data)
    return key


def revoke_key(path: Path, key_id: str) -> bool:
    """Elimina la key cuyo hash coincide con key_id. True si encontro y borro alguna."""
    with _write_lock:
        data = _load_raw(path)
        encontrada = False
        for tenant_data in data.get("tenants", {}).values():
            api_keys = tenant_data.get("api_keys", [])
            restantes = [k for k in api_keys if _key_id(k["key"]) != key_id]
            if len(restantes) != len(api_keys):
                encontrada = True
            tenant_data["api_keys"] = restantes
        if encontrada:
            _save_raw(path, data)
    return encontrada
