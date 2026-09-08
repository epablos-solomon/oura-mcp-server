from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from threading import Lock

from oura_mcp_server.models import OAuthTokens


@dataclass
class TokenRecord:
    user_id: str
    tokens: OAuthTokens
    updated_at: str


class TokenStore:
    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self._lock = Lock()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS oauth_tokens (
                    user_id TEXT PRIMARY KEY,
                    tokens_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()

    def save(self, user_id: str, tokens: OAuthTokens) -> None:
        payload = tokens.model_dump(mode="json")
        with self._lock, closing(self._connect()) as conn:
            conn.execute(
                """INSERT INTO oauth_tokens (user_id, tokens_json, updated_at)
                   VALUES (?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(user_id) DO UPDATE SET
                       tokens_json = excluded.tokens_json,
                       updated_at = CURRENT_TIMESTAMP""",
                (user_id, json.dumps(payload)),
            )
            conn.commit()

    def get(self, user_id: str) -> OAuthTokens | None:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT tokens_json FROM oauth_tokens WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        if not row:
            return None
        return OAuthTokens.model_validate_json(row["tokens_json"])

    def delete(self, user_id: str) -> None:
        with self._lock, closing(self._connect()) as conn:
            conn.execute("DELETE FROM oauth_tokens WHERE user_id = ?", (user_id,))
            conn.commit()

    def list_user_ids(self) -> list[str]:
        with closing(self._connect()) as conn:
            rows = conn.execute("SELECT user_id FROM oauth_tokens ORDER BY user_id").fetchall()
        return [row[0] for row in rows]

    def list_with_metadata(self) -> list[TokenRecord]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT user_id, tokens_json, updated_at FROM oauth_tokens ORDER BY user_id"
            ).fetchall()
        return [
            TokenRecord(
                user_id=row["user_id"],
                tokens=OAuthTokens.model_validate_json(row["tokens_json"]),
                updated_at=row["updated_at"],
            )
            for row in rows
        ]
