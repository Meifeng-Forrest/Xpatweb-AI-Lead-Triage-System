import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.database import get_pool
from app.repositories.users import UserRepository
from app.schemas import AuthLoginRequest, AuthTokenResponse, AuthUserRead
from app.services.auth import (
    CurrentUser,
    create_access_token,
    get_current_user,
    login_log_summary,
    permissions_for_roles,
    verify_password,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
logger = logging.getLogger("lead_triage.api.auth")


def to_auth_user_read(user: CurrentUser) -> AuthUserRead:
    return AuthUserRead(
        user_id=user.user_id,
        email=user.email,
        display_name=user.display_name,
        roles=list(user.roles),
        permissions=list(user.permissions),
    )


@router.post("/login", response_model=AuthTokenResponse)
async def login(
    payload: AuthLoginRequest,
    request: Request,
    pool=Depends(get_pool),
) -> AuthTokenResponse:
    settings = request.app.state.settings
    logger.info("[api/auth/login] enter %s", login_log_summary(str(payload.email)))
    repo = UserRepository(pool)
    user = await repo.get_by_email(str(payload.email))
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        logger.info("[api/auth/login] fail %s", {**login_log_summary(str(payload.email)), "reason": "invalid_credentials"})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    token = create_access_token(user, settings)
    logger.info(
        "[api/auth/login] success %s",
        {
            **login_log_summary(user.email),
            "user_id": user.user_id,
            "role_count": len(user.roles),
        },
    )
    return AuthTokenResponse(
        access_token=token,
        expires_in_seconds=settings.auth_token_ttl_minutes * 60,
        user=AuthUserRead(
            user_id=user.user_id,
            email=user.email,
            display_name=user.display_name,
            roles=list(user.roles),
            permissions=list(permissions_for_roles(user.roles)),
        ),
    )


@router.get("/me", response_model=AuthUserRead)
async def me(current_user: CurrentUser = Depends(get_current_user)) -> AuthUserRead:
    logger.info("[api/auth/me] success %s", {"user_id": current_user.user_id})
    return to_auth_user_read(current_user)
