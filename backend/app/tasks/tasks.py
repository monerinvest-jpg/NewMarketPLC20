"""
Background tasks: auto order status progression.
"""
import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.models import DeliveryInfo, Order, OrderStatus
from app.tasks.celery_app import celery_app


async def _auto_mark_delivered_async():
    from app.services.settings_service import get_setting
    async with AsyncSessionLocal() as db:
        days_str = await get_setting(db, "order_auto_delivered_days")
        days = int(days_str)
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        result = await db.execute(
            select(Order)
            .join(Order.delivery_info)
            .where(
                Order.status == OrderStatus.shipped,
                DeliveryInfo.shipped_at <= cutoff,
            )
        )
        orders = result.scalars().all()
        for order in orders:
            order.status = OrderStatus.delivered
            if order.delivery_info:
                order.delivery_info.delivered_at = datetime.now(timezone.utc)

        await db.commit()
        return len(orders)


async def _auto_complete_orders_async():
    from app.services.settings_service import get_setting
    from app.services.referral_service import process_buyer_referral_reward, process_seller_referral_reward
    from app.services.payout_service import payout_sellers_for_order

    async with AsyncSessionLocal() as db:
        days_str = await get_setting(db, "order_auto_complete_days")
        days = int(days_str)
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        result = await db.execute(
            select(Order)
            .join(Order.delivery_info)
            .where(
                Order.status == OrderStatus.delivered,
                DeliveryInfo.delivered_at <= cutoff,
            )
        )
        orders = result.scalars().all()
        for order in orders:
            order.status = OrderStatus.completed

            # Credit every seller represented in this order their own share —
            # an order can span multiple shops, each with its own commission.
            await payout_sellers_for_order(order, db)

            await process_buyer_referral_reward(order, db)
            from app.services.loyalty_service import award_cashback_for_order
            await award_cashback_for_order(order, db)
            await process_seller_referral_reward(order, db)

        await db.commit()
        return len(orders)


@celery_app.task(name="app.tasks.tasks.auto_mark_delivered")
def auto_mark_delivered():
    """Mark shipped orders as delivered after configured number of days."""
    return asyncio.get_event_loop().run_until_complete(_auto_mark_delivered_async())


@celery_app.task(name="app.tasks.tasks.auto_complete_orders")
def auto_complete_orders():
    """Auto-complete delivered orders after configured number of days."""
    return asyncio.get_event_loop().run_until_complete(_auto_complete_orders_async())


# ─── Item 4: seller subscription auto-renewal ────────────────────────────────────

async def _process_subscription_renewals_async():
    """
    Renew or expire seller subscriptions whose period has ended. For paid plans
    with auto_renew, attempt to charge the seller's balance for another month;
    on insufficient funds, downgrade to the default (free) plan.
    """
    from datetime import datetime, timezone, timedelta
    from decimal import Decimal
    from sqlalchemy import select
    from app.models.models import (
        SellerSubscription, SellerPlan, SubscriptionStatus, Shop, User,
        Transaction, TransactionType, BalanceTransaction, BalanceTransactionType,
    )
    from app.services.subscription_service import get_default_plan

    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        subs = (await db.execute(
            select(SellerSubscription).where(
                SellerSubscription.status.in_([SubscriptionStatus.active, SubscriptionStatus.trial]),
                SellerSubscription.current_period_end.is_not(None),
                SellerSubscription.current_period_end <= now,
            )
        )).scalars().all()

        for sub in subs:
            plan = (await db.execute(select(SellerPlan).where(SellerPlan.id == sub.plan_id))).scalar_one_or_none()
            if not plan or plan.monthly_price <= 0:
                # Free plan: just clear the expiry
                sub.status = SubscriptionStatus.active
                sub.current_period_end = None
                continue

            shop = (await db.execute(select(Shop).where(Shop.id == sub.shop_id))).scalar_one_or_none()
            owner = (await db.execute(select(User).where(User.id == shop.owner_id))).scalar_one_or_none() if shop else None

            if sub.auto_renew and owner and owner.balance >= plan.monthly_price:
                owner.balance -= plan.monthly_price
                db.add(Transaction(
                    user_id=owner.id, type=TransactionType.payout, amount=-plan.monthly_price,
                    description=f"Автопродление подписки «{plan.name}»", balance_after=owner.balance,
                ))
                db.add(BalanceTransaction(
                    user_id=owner.id, change=-plan.monthly_price, type=BalanceTransactionType.debit,
                    reference_type="subscription_renewal", reference_id=sub.id,
                    description=f"Автопродление «{plan.name}»", balance_after=owner.balance,
                ))
                sub.status = SubscriptionStatus.active
                sub.current_period_end = now + timedelta(days=30)
            else:
                # Can't renew: downgrade to default plan
                default_plan = await get_default_plan(db)
                if default_plan:
                    sub.plan_id = default_plan.id
                sub.status = SubscriptionStatus.expired
                sub.current_period_end = None
        await db.commit()


@celery_app.task(name="app.tasks.tasks.process_subscription_renewals")
def process_subscription_renewals():
    """Charge or expire due seller subscriptions."""
    return asyncio.get_event_loop().run_until_complete(_process_subscription_renewals_async())


# ─── Item 7: product subscription notifications (back-in-stock / price-drop) ─────

async def _notify_product_subscriptions_async():
    from sqlalchemy import select
    from app.models.models import ProductSubscription, Product, NotificationType
    from app.services.notification_service import notify

    async with AsyncSessionLocal() as db:
        subs = (await db.execute(
            select(ProductSubscription).where(ProductSubscription.is_notified == False)  # noqa: E712
        )).scalars().all()
        for sub in subs:
            product = (await db.execute(select(Product).where(Product.id == sub.product_id))).scalar_one_or_none()
            if not product:
                continue
            triggered = False
            if sub.kind == "back_in_stock" and product.quantity > 0:
                triggered = True
                title = "Товар снова в наличии"
            elif sub.kind == "price_drop" and sub.target_price and product.price <= sub.target_price:
                triggered = True
                title = "Цена снизилась"
            if triggered:
                await notify(
                    db, sub.user_id, NotificationType.system,
                    title=title, body=product.title,
                    link=f"/products/{product.slug or product.id}", send_email=True,
                )
                sub.is_notified = True
        await db.commit()


@celery_app.task(name="app.tasks.tasks.notify_product_subscriptions")
def notify_product_subscriptions():
    """Notify buyers about back-in-stock / price-drop events."""
    return asyncio.get_event_loop().run_until_complete(_notify_product_subscriptions_async())


# ─── Item 7: abandoned cart reminders ────────────────────────────────────────────

async def _remind_abandoned_carts_async():
    from datetime import datetime, timezone, timedelta
    from sqlalchemy import select, func
    from app.models.models import CartItem, NotificationType
    from app.services.notification_service import notify

    cutoff = datetime.now(timezone.utc) - timedelta(days=1)
    async with AsyncSessionLocal() as db:
        # Users with cart items older than a day, grouped by user
        rows = (await db.execute(
            select(CartItem.user_id, func.count(CartItem.id))
            .where(CartItem.created_at <= cutoff)
            .group_by(CartItem.user_id)
        )).all()
        for user_id, count in rows:
            await notify(
                db, user_id, NotificationType.system,
                title="Вы забыли товары в корзине",
                body=f"В вашей корзине {count} тов. — оформите заказ, пока они в наличии",
                link="/cart", send_email=True,
            )
        await db.commit()


@celery_app.task(name="app.tasks.tasks.remind_abandoned_carts")
def remind_abandoned_carts():
    """Remind buyers about abandoned carts."""
    return asyncio.get_event_loop().run_until_complete(_remind_abandoned_carts_async())


async def _rebuild_recommendations_async():
    from app.services import recommendation_service

    async with AsyncSessionLocal() as db:
        pairs = await recommendation_service.rebuild_co_purchase(db)
        await db.commit()
        return {"pairs": pairs}


@celery_app.task(name="app.tasks.tasks.rebuild_recommendations")
def rebuild_recommendations():
    """Rebuild the materialized "bought together" co-purchase signal."""
    return asyncio.get_event_loop().run_until_complete(_rebuild_recommendations_async())


async def _settle_promotions_async():
    from app.services import promotion_service

    async with AsyncSessionLocal() as db:
        results = await promotion_service.settle_all(db)
        await db.commit()
        return {"results": results}


@celery_app.task(name="app.tasks.tasks.settle_promotions")
def settle_promotions():
    """Daily auction settlement: charge winners, demote outbid promotions."""
    return asyncio.get_event_loop().run_until_complete(_settle_promotions_async())


async def _support_sla_sweep_async():
    from app.services import support_service

    async with AsyncSessionLocal() as db:
        result = await support_service.sla_sweep(db)
        await db.commit()
        return result


@celery_app.task(name="app.tasks.tasks.support_sla_sweep")
def support_sla_sweep():
    """Escalate overdue support tickets and auto-assign unowned ones."""
    return asyncio.get_event_loop().run_until_complete(_support_sla_sweep_async())


async def _loyalty_decay_async():
    from app.services import loyalty_tier_service

    async with AsyncSessionLocal() as db:
        result = await loyalty_tier_service.decay_sweep(db)
        await db.commit()
        return result


@celery_app.task(name="app.tasks.tasks.loyalty_decay")
def loyalty_decay():
    """Downgrade loyalty tiers for buyers inactive beyond their retention window."""
    return asyncio.get_event_loop().run_until_complete(_loyalty_decay_async())
