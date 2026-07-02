"""
Celery application and background task definitions.
"""
import json
from datetime import datetime, timezone as dt_timezone

from celery import Celery, Task
from celery.schedules import crontab

from app.core.config import settings

DLQ_KEY = "celery:dlq"
DLQ_MAX = 1000


class ReliableTask(Task):
    """
    Base class for every task: transient failures (SMTP down, payment gateway
    timeout, S3 hiccup) retry automatically with exponential backoff instead of
    silently losing the job. Tasks that exhaust all retries land in a Redis
    dead-letter list (celery:dlq) for manual inspection/replay.
    """
    autoretry_for = (Exception,)
    retry_backoff = True          # 1s, 2s, 4s, ... between attempts
    retry_backoff_max = 600       # cap the delay at 10 minutes
    retry_jitter = True
    retry_kwargs = {"max_retries": 5}

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        # Called only when retries are exhausted (or the error isn't retryable).
        try:
            import redis  # ships with the celery[redis] stack
            r = redis.Redis.from_url(settings.REDIS_URL)
            r.lpush(DLQ_KEY, json.dumps({
                "task": self.name,
                "task_id": task_id,
                "args": repr(args),
                "kwargs": repr(kwargs),
                "error": repr(exc),
                "failed_at": datetime.now(dt_timezone.utc).isoformat(),
            }, ensure_ascii=False))
            r.ltrim(DLQ_KEY, 0, DLQ_MAX - 1)
        except Exception:
            pass  # the DLQ must never mask the original failure
        super().on_failure(exc, task_id, args, kwargs, einfo)


celery_app = Celery(
    "marketplace",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.tasks"],
    task_cls=ReliableTask,
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
