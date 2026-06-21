from __future__ import annotations

from datetime import datetime, timedelta, timezone

from pydantic import BaseModel, Field


class OAuthTokens(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    scope: str | None = None
    expires_in: int | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def expires_at(self) -> datetime | None:
        if self.expires_in is None:
            return None
        return self.created_at + timedelta(seconds=self.expires_in)

    def is_expired(self, skew_seconds: int = 60) -> bool:
        expires_at = self.expires_at()
        if expires_at is None:
            return False
        return datetime.now(timezone.utc) >= (expires_at - timedelta(seconds=skew_seconds))


class HealthSnapshot(BaseModel):
    user_id: str = ""
    profile: dict = Field(default_factory=dict)
    daily_sleep: dict = Field(default_factory=dict)
    daily_readiness: dict = Field(default_factory=dict)
    daily_activity: dict = Field(default_factory=dict)
