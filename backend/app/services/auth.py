import base64
import hashlib
import hmac
import json
import logging
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import Settings, get_settings
from app.database import get_pool
from app.logging import summarize_email
from app.repositories.users import UserRecord, UserRepository

try:
    import bcrypt
except ImportError:  # pragma: no cover - Docker requirements include bcrypt; local fallback avoids blocking tests.
    bcrypt = None


logger = logging.getLogger("lead_triage.auth")
bearer_scheme = HTTPBearer(auto_error=False)

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "superadmin": {
        "lead.view",
        "lead.draft.edit",
        "lead.approve",
        "lead.reject",
        "lead.reject.confirm",
        "routing.config",
        "user.manage",
    },
    "approver": {"lead.view", "lead.approve"},
    "agent": {"lead.view", "lead.draft.edit", "lead.reject"},
    "quality_lead": {"lead.view", "lead.reject.confirm"},
    "reviewer": {"lead.view"},
}


@dataclass(frozen=True)
class CurrentUser:
    user_id: str
    email: str
    display_name: str
    roles: tuple[str, ...]
    permissions: tuple[str, ...]
    is_auth_disabled: bool = False


def permissions_for_roles(roles: tuple[str, ...]) -> tuple[str, ...]:
    permissions: set[str] = set()
    for role in roles:
        permissions.update(ROLE_PERMISSIONS.get(role, set()))
    return tuple(sorted(permissions))


def password_hash(password: str) -> str:
    if bcrypt is not None:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    # 本地测试环境可能没有 bcrypt；这里用带 scheme 的 PBKDF2 兜底，避免认证模块无法导入。
    # Docker 运行时 requirements 会安装 bcrypt，真实部署不会走这个分支。
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 180_000)
    return "pbkdf2_sha256$180000$%s$%s" % (
        base64.urlsafe_b64encode(salt).decode("ascii"),
        base64.urlsafe_b64encode(digest).decode("ascii"),
    )


def verify_password(password: str, stored_hash: str) -> bool:
    if stored_hash.startswith("pbkdf2_sha256$"):
        try:
            _scheme, iterations, salt_b64, digest_b64 = stored_hash.split("$", 3)
            expected = base64.urlsafe_b64decode(digest_b64.encode("ascii"))
            actual = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                base64.urlsafe_b64decode(salt_b64.encode("ascii")),
                int(iterations),
            )
            return hmac.compare_digest(actual, expected)
        except (ValueError, TypeError):
            return False
    if bcrypt is None:
        return False
    return bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8"))


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


def create_access_token(user: UserRecord, settings: Settings) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": user.user_id,
        "email": user.email,
        "roles": list(user.roles),
        "permissions": list(permissions_for_roles(user.roles)),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.auth_token_ttl_minutes)).timestamp()),
    }
    header = {"alg": "HS256", "typ": "JWT"}
    signing_input = ".".join(
        [
            _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8")),
            _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")),
        ]
    )
    signature = hmac.new(
        settings.auth_jwt_secret.encode("utf-8"),
        signing_input.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{signing_input}.{_b64url_encode(signature)}"


def decode_access_token(token: str, settings: Settings) -> dict[str, Any]:
    try:
        header_b64, payload_b64, signature_b64 = token.split(".", 2)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    signing_input = f"{header_b64}.{payload_b64}"
    expected = hmac.new(
        settings.auth_jwt_secret.encode("utf-8"),
        signing_input.encode("ascii"),
        hashlib.sha256,
    ).digest()
    actual = _b64url_decode(signature_b64)
    if not hmac.compare_digest(actual, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    exp = payload.get("exp")
    if not isinstance(exp, int) or exp < int(datetime.now(UTC).timestamp()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    return payload


def user_to_current(user: UserRecord) -> CurrentUser:
    return CurrentUser(
        user_id=user.user_id,
        email=user.email,
        display_name=user.display_name,
        roles=user.roles,
        permissions=permissions_for_roles(user.roles),
    )


def disabled_auth_user() -> CurrentUser:
    return CurrentUser(
        user_id="dev-user",
        email="dev@example.com",
        display_name="Dev User",
        roles=("superadmin",),
        permissions=permissions_for_roles(("superadmin",)),
        is_auth_disabled=True,
    )


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> CurrentUser:
    settings: Settings = getattr(request.app.state, "settings", get_settings())
    if not settings.auth_enabled:
        return disabled_auth_user()

    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    payload = decode_access_token(credentials.credentials, settings)
    user_id = payload.get("sub")
    if not isinstance(user_id, str):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    repo = UserRepository(get_pool(request))
    user = await repo.get_by_id(user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")
    return user_to_current(user)


def require_permission(permission: str):
    async def dependency(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if permission not in current_user.permissions:
            logger.info(
                "[auth/permission] denied %s",
                {"user_id": current_user.user_id, "permission": permission},
            )
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
        return current_user

    return dependency


async def seed_default_users(pool, settings: Settings) -> None:
    repo = UserRepository(pool)
    seed_users = [
        ("admin@example.com", "Admin", ("superadmin",)),
        ("melissa@example.com", "Melissa", ("agent",)),
        ("marisa@example.com", "Marisa", ("quality_lead",)),
        ("jerry@example.com", "Jerry", ("approver",)),
        ("willem@example.com", "Willem Pretorius", ("reviewer",)),
    ]
    logger.info("[auth/seed] enter %s", {"count": len(seed_users), "auth_enabled": settings.auth_enabled})
    created = 0
    for email, display_name, roles in seed_users:
        existing = await repo.get_by_email(email)
        if existing is not None:
            continue
        await repo.create_user(
            email=email,
            display_name=display_name,
            password_hash=password_hash(settings.auth_seed_password),
            roles=roles,
        )
        created += 1
    logger.info("[auth/seed] success %s", {"created": created, "count": len(seed_users)})


def login_log_summary(email: str) -> dict[str, str | None]:
    return {"email": summarize_email(email)}
