import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.database import get_pool
from app.logging import summarize_email
from app.repositories.users import RoutingRuleRepository, UserRecord, UserRepository
from app.schemas import (
    UserCreateRequest,
    UserPasswordResetRequest,
    UserRead,
    UserRoutingCategoriesUpdateRequest,
    UserUpdateRequest,
)
from app.services.auth import CurrentUser, ROLE_PERMISSIONS, password_hash, permissions_for_roles, require_permission
from app.services.routing import ROUTING_CATEGORIES

router = APIRouter(prefix="/api/v1/users", tags=["users"])
logger = logging.getLogger("lead_triage.api.users")


def to_user_read(user: UserRecord, routing_categories: list[str] | None = None) -> UserRead:
    return UserRead(
        user_id=user.user_id,
        email=user.email,
        display_name=user.display_name,
        roles=list(user.roles),
        permissions=list(permissions_for_roles(user.roles)),
        routing_categories=routing_categories or [],
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


def validate_roles(roles: list[str]) -> tuple[str, ...]:
    normalized = tuple(sorted(set(role.strip() for role in roles if role.strip())))
    invalid = [role for role in normalized if role not in ROLE_PERMISSIONS]
    if invalid:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Unknown role: {invalid[0]}")
    if not normalized:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="At least one role is required")
    if len(normalized) != 1:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Exactly one role is required")
    return normalized


def validate_routing_categories(categories: list[str]) -> tuple[str, ...]:
    normalized = tuple(sorted(set(category.strip() for category in categories if category.strip())))
    invalid = [category for category in normalized if category not in ROUTING_CATEGORIES]
    if invalid:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Unknown routing category: {invalid[0]}")
    return normalized


async def ensure_not_removing_last_superadmin(
    repo: UserRepository,
    target: UserRecord,
    *,
    next_roles: tuple[str, ...] | None = None,
    next_is_active: bool | None = None,
) -> None:
    roles = next_roles if next_roles is not None else target.roles
    is_active = next_is_active if next_is_active is not None else target.is_active
    if target.is_active and "superadmin" in target.roles and (not is_active or "superadmin" not in roles):
        active_superadmin_count = await repo.count_active_superadmins()
        if active_superadmin_count <= 1:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="At least one active superadmin is required")


@router.get("", response_model=list[UserRead])
async def list_users(
    pool=Depends(get_pool),
    current_user: CurrentUser = Depends(require_permission("user.manage")),
) -> list[UserRead]:
    logger.info("[api/users/list] enter %s", {"actor": current_user.user_id})
    users = await UserRepository(pool).list_users()
    routing_repo = RoutingRuleRepository(pool)
    logger.info("[api/users/list] success %s", {"actor": current_user.user_id, "count": len(users)})
    return [to_user_read(user, await routing_repo.list_categories_for_user(user.user_id)) for user in users]


@router.get("/roles", response_model=list[str])
async def list_roles(
    current_user: CurrentUser = Depends(require_permission("user.manage")),
) -> list[str]:
    roles = sorted(ROLE_PERMISSIONS)
    logger.info("[api/users/roles] success %s", {"actor": current_user.user_id, "count": len(roles)})
    return roles


@router.post("", response_model=UserRead, status_code=201)
async def create_user(
    payload: UserCreateRequest,
    pool=Depends(get_pool),
    current_user: CurrentUser = Depends(require_permission("user.manage")),
) -> UserRead:
    roles = validate_roles(payload.roles)
    logger.info(
        "[api/users/create] enter %s",
        {
            "actor": current_user.user_id,
            "email": summarize_email(str(payload.email)),
            "role_count": len(roles),
            "is_active": payload.is_active,
        },
    )
    repo = UserRepository(pool)
    if await repo.get_by_email(str(payload.email)):
        logger.info("[api/users/create] conflict %s", {"actor": current_user.user_id, "email": summarize_email(str(payload.email))})
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User email already exists")

    user = await repo.create_user(
        email=str(payload.email),
        display_name=payload.display_name.strip(),
        password_hash=password_hash(payload.password),
        roles=roles,
        is_active=payload.is_active,
    )
    await repo.append_user_audit_event(
        target_user_id=user.user_id,
        event_type="user.created",
        actor=current_user.user_id,
        metadata={"role_count": len(roles), "is_active": payload.is_active},
    )
    logger.info("[api/users/create] success %s", {"actor": current_user.user_id, "target_user_id": user.user_id})
    routing_categories = await RoutingRuleRepository(pool).list_categories_for_user(user.user_id)
    return to_user_read(user, routing_categories)


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: str,
    payload: UserUpdateRequest,
    pool=Depends(get_pool),
    current_user: CurrentUser = Depends(require_permission("user.manage")),
) -> UserRead:
    repo = UserRepository(pool)
    target = await repo.get_by_id(user_id)
    if target is None:
        logger.info("[api/users/update] not_found %s", {"actor": current_user.user_id, "target_user_id": user_id})
        raise HTTPException(status_code=404, detail="User not found")

    next_roles = validate_roles(payload.roles) if payload.roles is not None else None
    await ensure_not_removing_last_superadmin(
        repo,
        target,
        next_roles=next_roles,
        next_is_active=payload.is_active,
    )
    logger.info(
        "[api/users/update] enter %s",
        {
            "actor": current_user.user_id,
            "target_user_id": user_id,
            "display_name_changed": payload.display_name is not None,
            "roles_changed": next_roles is not None,
            "is_active": payload.is_active,
        },
    )
    updated = await repo.update_user(
        user_id,
        display_name=payload.display_name.strip() if payload.display_name is not None else None,
        roles=next_roles,
        is_active=payload.is_active,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="User not found")

    await repo.append_user_audit_event(
        target_user_id=user_id,
        event_type="user.updated",
        actor=current_user.user_id,
        metadata={
            "display_name_changed": payload.display_name is not None,
            "roles_changed": next_roles is not None,
            "is_active_changed": payload.is_active is not None,
            "role_count": len(updated.roles),
        },
    )
    logger.info("[api/users/update] success %s", {"actor": current_user.user_id, "target_user_id": user_id})
    routing_categories = await RoutingRuleRepository(pool).list_categories_for_user(updated.user_id)
    return to_user_read(updated, routing_categories)


@router.post("/{user_id}/password", response_model=UserRead)
async def reset_user_password(
    user_id: str,
    payload: UserPasswordResetRequest,
    pool=Depends(get_pool),
    current_user: CurrentUser = Depends(require_permission("user.manage")),
) -> UserRead:
    logger.info("[api/users/password] enter %s", {"actor": current_user.user_id, "target_user_id": user_id})
    repo = UserRepository(pool)
    updated = await repo.update_password(user_id, password_hash(payload.password))
    if updated is None:
        logger.info("[api/users/password] not_found %s", {"actor": current_user.user_id, "target_user_id": user_id})
        raise HTTPException(status_code=404, detail="User not found")

    await repo.append_user_audit_event(
        target_user_id=user_id,
        event_type="user.password_reset",
        actor=current_user.user_id,
        metadata={"password_replaced": True},
    )
    logger.info("[api/users/password] success %s", {"actor": current_user.user_id, "target_user_id": user_id})
    routing_categories = await RoutingRuleRepository(pool).list_categories_for_user(updated.user_id)
    return to_user_read(updated, routing_categories)


@router.put("/{user_id}/routing-categories", response_model=UserRead)
async def update_user_routing_categories(
    user_id: str,
    payload: UserRoutingCategoriesUpdateRequest,
    pool=Depends(get_pool),
    current_user: CurrentUser = Depends(require_permission("routing.config")),
) -> UserRead:
    categories = validate_routing_categories(payload.categories)
    logger.info(
        "[api/users/routing-categories] enter %s",
        {"actor": current_user.user_id, "target_user_id": user_id, "category_count": len(categories)},
    )
    user_repo = UserRepository(pool)
    target = await user_repo.get_by_id(user_id)
    if target is None:
        logger.info("[api/users/routing-categories] not_found %s", {"actor": current_user.user_id, "target_user_id": user_id})
        raise HTTPException(status_code=404, detail="User not found")

    routing_repo = RoutingRuleRepository(pool)
    try:
        updated_categories = await routing_repo.set_categories_for_user(user_id, categories)
    except ValueError as exc:
        logger.info(
            "[api/users/routing-categories] invalid_user %s",
            {"actor": current_user.user_id, "target_user_id": user_id, "reason": str(exc)},
        )
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    await user_repo.append_user_audit_event(
        target_user_id=user_id,
        event_type="user.routing_categories.updated",
        actor=current_user.user_id,
        metadata={"category_count": len(updated_categories)},
    )
    logger.info(
        "[api/users/routing-categories] success %s",
        {"actor": current_user.user_id, "target_user_id": user_id, "category_count": len(updated_categories)},
    )
    return to_user_read(target, updated_categories)
