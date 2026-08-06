"""El TokenStore no debe dejar conexiones SQLite abiertas.

`with sqlite3.connect(...) as conn` gestiona la transaccion, NO cierra el
descriptor. Con una operacion por llamada a tool, las conexiones se acumulan
durante toda la vida del proceso.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from oura_mcp_server.auth.token_store import TokenStore
from oura_mcp_server.models import OAuthTokens


def test_todas_las_operaciones_cierran_su_conexion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tras cada operacion la conexion queda cerrada de verdad, no solo commiteada."""
    abiertas: list[sqlite3.Connection] = []
    real_connect = TokenStore._connect

    def espia(self: TokenStore) -> sqlite3.Connection:
        conn = real_connect(self)
        abiertas.append(conn)
        return conn

    monkeypatch.setattr(TokenStore, "_connect", espia)

    store = TokenStore(tmp_path / "tokens.sqlite3")  # _init_db
    store.save("kike", OAuthTokens(access_token="a", refresh_token="r"))
    store.get("kike")
    store.list_user_ids()
    store.delete("kike")

    assert len(abiertas) == 5, "cada operacion abre exactamente una conexion"
    for i, conn in enumerate(abiertas):
        # Una conexion cerrada lanza ProgrammingError; una abierta devolveria 1.
        with pytest.raises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")
            pytest.fail(f"la conexion #{i} sigue abierta")
