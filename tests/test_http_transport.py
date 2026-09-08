from __future__ import annotations

from pathlib import Path

from starlette.testclient import TestClient

from oura_mcp_server.config import Settings
from oura_mcp_server.transports.http import build_http_server


def test_build_http_server_monta_las_rutas_admin_junto_a_las_de_auth(tmp_path: Path) -> None:
    settings = Settings(
        token_db_path=tmp_path / "t.sqlite3",
        oura_state_secret="secreto-de-test",
        admin_password="pw-de-test",
    )
    mcp = build_http_server(settings)
    client = TestClient(mcp.http_app())

    assert client.get("/health").status_code == 200
    assert client.get("/auth/login").status_code == 200
    assert client.get("/admin/login").status_code == 200
