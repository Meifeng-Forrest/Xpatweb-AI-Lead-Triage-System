import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.users import to_user_read
from app.database import get_pool
from app.repositories.users import RoutingRuleRepository
from app.schemas import RoutingRuleRead
from app.services.auth import CurrentUser, require_permission
from app.services.routing import ROUTING_CATEGORIES

router = APIRouter(prefix="/api/v1/routing", tags=["routing"])
logger = logging.getLogger("lead_triage.api.routing")


def _validate_category(category: str) -> str:
    if category not in ROUTING_CATEGORIES:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown routing category")
    return category


@router.get("/rules", response_model=list[RoutingRuleRead])
async def list_routing_rules(
    pool=Depends(get_pool),
    current_user: CurrentUser = Depends(require_permission("routing.config")),
) -> list[RoutingRuleRead]:
    logger.info("[api/routing/rules/list] enter %s", {"actor": current_user.user_id})
    repo = RoutingRuleRepository(pool)
    rules: list[RoutingRuleRead] = []
    for category in ROUTING_CATEGORIES:
        configured_user_ids = await repo.list_configured_user_ids(category)
        recipients = await repo.list_recipients(category)
        rules.append(
            RoutingRuleRead(
                category=category,
                recipients=[to_user_read(user, await repo.list_categories_for_user(user.user_id)) for user in recipients],
                fallback_to_superadmin=len(configured_user_ids) == 0,
            )
        )
    logger.info("[api/routing/rules/list] success %s", {"actor": current_user.user_id, "category_count": len(rules)})
    return rules


@router.put("/rules/{category}", response_model=RoutingRuleRead, deprecated=True)
async def update_routing_rule(
    category: str,
    current_user: CurrentUser = Depends(require_permission("routing.config")),
) -> RoutingRuleRead:
    category = _validate_category(category)
    logger.info(
        "[api/routing/rules/update] gone %s",
        {"actor": current_user.user_id, "category": category, "reason": "per_user_write_required"},
    )
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Per-category routing writes are deprecated. Use PUT /api/v1/users/{user_id}/routing-categories.",
    )
