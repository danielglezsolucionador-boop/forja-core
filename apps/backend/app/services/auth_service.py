from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings
from app.core.security import create_access_token, hash_password, verify_password


@dataclass(frozen=True)
class LocalUser:
    username: str
    password_hash: str
    scopes: list[str]


class AuthService:
    def __init__(self) -> None:
        self._admin = LocalUser(
            username=settings.admin_username,
            password_hash=hash_password(settings.admin_password, salt=b"forja-local-salt"),
            scopes=["admin", "factory:read", "factory:approve"],
        )

    def authenticate(self, username: str, password: str) -> LocalUser | None:
        if username != self._admin.username:
            return None
        if not verify_password(password, self._admin.password_hash):
            return None
        return self._admin

    def token_for(self, user: LocalUser) -> str:
        return create_access_token(user.username, user.scopes)


auth_service = AuthService()
