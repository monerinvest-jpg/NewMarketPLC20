"""
Celery application and background task definitions.
"""
from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "marketplace",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Moscow",
    enable_utc=True,
    beat_schedule={
        # Every hour: auto-mark shipped orders as delivered after N days
        "auto-delivered": {
            "task": "app.tasks.tasks.auto_mark_delivered",
            "schedule": crontab(minute=0, hour="*"),
        },
        # Every hour: auto-complete delivered orders after N days
        "auto-complete": {
            "task": "app.tasks.tasks.auto_complete_orders",
            "schedule": crontab(minute=30, hour="*"),
        },
        # Daily: charge/expire seller subscriptions due for renewal
        "renew-subscriptions": {
            "task": "app.tasks.tasks.process_subscription_renewals",
            "schedule": crontab(minute=0, hour=3),
        },
        # Every 15 min: notify buyers when subscribed products are back in stock
        # or have dropped below their target price
        "notify-product-subscriptions": {
            "task": "app.tasks.tasks.notify_product_subscriptions",
            "schedule": crontab(minute="*/15"),
        },
        # Daily: remind buyers about abandoned carts
        "abandoned-cart": {
            "task": "app.tasks.tasks.remind_abandoned_carts",
            "schedule": crontab(minute=0, hour=12),
        },
        # Nightly: rebuild the "bought together" co-purchase recommendations
        "rebuild-recommendations": {
            "task": "app.tasks.tasks.rebuild_recommendations",
            "schedule": crontab(minute=0, hour=4),
        },
        # Hourly: rebuild the MeiliSearch products index (no-op without Meili)
        "rebuild-search-index": {
            "task": "app.tasks.tasks.rebuild_search_index",
            "schedule": crontab(minute=45),
        },
        # Nightly: settle the promotion auction (charge winners, demote outbid)
        "settle-promotions": {
            "task": "app.tasks.tasks.settle_promotions",
            "schedule": crontab(minute=30, hour=0),
        },
        # Hourly: support SLA sweep — escalate overdue tickets, auto-assign
        "support-sla-sweep": {
            "task": "app.tasks.tasks.support_sla_sweep",
            "schedule": crontab(minute=15),
        },
        # Daily: loyalty tier decay for inactive buyers
        "loyalty-decay": {
            "task": "app.tasks.tasks.loyalty_decay",
            "schedule": crontab(minute=0, hour=3),
        },
    },
)
