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


def _key_id_de_entrada(key_entry: object) -> str | None:
    """key_id de una entrada de api_keys, o None si la entrada esta malformada."""
    if not isinstance(key_entry, dict):
        return None
    key = key_entry.get("key")
    if not isinstance(key, str) or not key:
        return None
    return _key_id(key)


def _mask(key: str) -> str:
    if len(key) <= 14:
        return key
    return f"{key[:10]}…{key[-4:]}"


def _load_raw(path: Path) -> dict:
    if not path.exists():
        return {"default_tenant": "scaleflow", "tenants": {}}
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        return {"default_tenant": "scaleflow", "tenants": {}}
    # `tenants:` sin nada debajo parsea como None (no como clave ausente), asi
    # que setdefault no alcanza. Cualquier forma que no sea un mapping se
    # normaliza a {} para que el panel siga abriendo y muestre la pagina vacia
    # en vez de un 500.
    if not isinstance(data.get("tenants"), dict):
        data["tenants"] = {}
    return data


def _save_raw(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)


def list_all(path: Path) -> list[KeyEntry]:
    data = _load_raw(path)
    entradas: list[KeyEntry] = []
    # Lectura tolerante: tenants.yaml tambien se edita a mano por SSH, y una
    # entrada mal escrita no debe tumbar la pagina entera (que es justo donde
    # el admin va a mirar para diagnosticarla). Se salta lo roto, no se repara.
    for tenant_id, tenant_data in data["tenants"].items():
        if not isinstance(tenant_data, dict):
            continue
        tenant_name = tenant_data.get("name", tenant_id)
        for key_entry in tenant_data.get("api_keys") or []:
            if not isinstance(key_entry, dict):
                continue
            key = key_entry.get("key")
            if not isinstance(key, str) or not key:
                continue
            entradas.append(
                KeyEntry(
                    tenant_id=str(tenant_id),
                    tenant_name=str(tenant_name),
                    key_id=_key_id(key),
                    key_masked=_mask(key),
                    agent=str(key_entry.get("agent") or ""),
                    user=str(key_entry.get("user") or ""),
                )
            )
    return entradas


def create_key(path: Path, tenant_id: str, tenant_name: str, agent: str, user: str) -> str:
    """Crea una key nueva y la persiste. Devuelve la key completa (una sola vez)."""
    with _write_lock:
        data = _load_raw(path)
        tenants = data["tenants"]
        tenant = tenants.get(tenant_id)
        if not isinstance(tenant, dict):
            tenant = {"name": tenant_name, "api_keys": []}
            tenants[tenant_id] = tenant
        tenant.setdefault("name", tenant_name)
        # `api_keys:` vacio parsea como None: setdefault lo dejaria en None.
        if not isinstance(tenant.get("api_keys"), list):
            tenant["api_keys"] = []

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
        for tenant_data in data["tenants"].values():
            if not isinstance(tenant_data, dict):
                continue
            api_keys = tenant_data.get("api_keys") or []
            # Una entrada que no se puede interpretar se conserva tal cual:
            # revocar no debe borrar lo que no entendemos.
            restantes = [k for k in api_keys if _key_id_de_entrada(k) != key_id]
            if len(restantes) != len(api_keys):
                encontrada = True
            tenant_data["api_keys"] = restantes
        if encontrada:
            _save_raw(path, data)
    return encontrada
