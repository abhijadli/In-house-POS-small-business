import logging
from sqlalchemy import select, func
from datetime import datetime
from app.db.session import SessionLocal
from app.models.cart import ProductCart
from app.services.cart import empty_cart_for_user

logger = logging.getLogger(__name__)


async def my_job():
    logger.info("Abandoned-cart cleanup job started")
    async with SessionLocal() as db:
        # Per user: earliest expires_at = 30 min after their first add.
        result = await db.execute(
            select(
                ProductCart.user_id,
                func.min(ProductCart.expires_at).label("expires_at"),
            ).group_by(ProductCart.user_id)
        )
        for entry in result.all():
            if entry.expires_at < datetime.utcnow():
                # One user's failure must not abort the whole run.
                try:
                    await empty_cart_for_user(db, entry.user_id)
                except Exception:
                    logger.exception(
                        "Failed to empty abandoned cart for user_id=%s", entry.user_id
                    )
    logger.info("Abandoned-cart cleanup job finished")
