from __future__ import annotations

from pathlib import Path

import yaml

from oura_mcp_server.admin.tenants_store import create_key, list_all, revoke_key

TENANTS_YAML = """
default_tenant: scaleflow
tenants:
  scaleflow:
    name: Scaleflow Internal
    api_keys:
      - key: sk-oura-kike-existente
        agent: claude-code
        user: kike
"""


def _escribir(tmp_path: Path) -> Path:
    p = tmp_path / "tenants.yaml"
    p.write_text(TENANTS_YAML)
    return p


def test_list_all_lee_las_keys_existentes_enmascaradas(tmp_path: Path) -> None:
    path = _escribir(tmp_path)
    entradas = list_all(path)
    assert len(entradas) == 1
    e = entradas[0]
    assert e.tenant_id == "scaleflow"
    assert e.user == "kike"
    assert e.agent == "claude-code"
    assert "sk-oura-kike-existente" not in e.key_masked
    assert e.key_masked.startswith("sk-oura-ki")


def test_create_key_la_agrega_y_devuelve_la_key_completa(tmp_path: Path) -> None:
    path = _escribir(tmp_path)
    key = create_key(path, "scaleflow", "Scaleflow Internal", agent="openclaw", user="amber")

    assert key.startswith("sk-oura-amber-")
    entradas = list_all(path)
    assert len(entradas) == 2
    nueva = next(e for e in entradas if e.user == "amber")
    assert nueva.agent == "openclaw"


def test_create_key_persiste_en_disco(tmp_path: Path) -> None:
    path = _escribir(tmp_path)
    create_key(path, "scaleflow", "Scaleflow Internal", agent="openclaw", user="amber")

    en_disco = yaml.safe_load(path.read_text())
    keys = en_disco["tenants"]["scaleflow"]["api_keys"]
    assert any(k["user"] == "amber" for k in keys)


def test_revoke_key_elimina_solo_la_indicada(tmp_path: Path) -> None:
    path = _escribir(tmp_path)
    create_key(path, "scaleflow", "Scaleflow Internal", agent="openclaw", user="amber")
    entradas = list_all(path)
    key_id_amber = next(e.key_id for e in entradas if e.user == "amber")

    resultado = revoke_key(path, key_id_amber)

    assert resultado is True
    restantes = list_all(path)
    assert len(restantes) == 1
    assert restantes[0].user == "kike"


def test_revoke_key_inexistente_devuelve_false(tmp_path: Path) -> None:
    path = _escribir(tmp_path)
    assert revoke_key(path, "no-existe-1234") is False


def test_list_all_sobre_archivo_inexistente_devuelve_vacio(tmp_path: Path) -> None:
    assert list_all(tmp_path / "no-existe.yaml") == []
