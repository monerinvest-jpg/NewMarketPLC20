"""
Re-export hub for ALL ORM models.

The former 124KB monolith is split by domain (users / shops / catalog /
learning / orders / platform, plus _base for shared imports). This module
keeps the historical import path working — `from app.models.models import X`
— and, importantly, importing it registers EVERY mapper on Base.metadata
(alembic migrations and create_all rely on that).
"""
from app.models._base import *  # noqa: F401,F403
from app.models._base import Enum, utcnow  # noqa: F401
from app.models.users import *  # noqa: F401,F403
from app.models.shops import *  # noqa: F401,F403
from app.models.catalog import *  # noqa: F401,F403
from app.models.learning import *  # noqa: F401,F403
from app.models.orders import *  # noqa: F401,F403
from app.models.platform import *  # noqa: F401,F403
