"""
FastAPI dependencies for authentication and authorization.
"""
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import verify_token
from app.models.models import User, UserRole

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract and validate the current user from the Bearer token."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = verify_token(credentials.credentials, token_type="access")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive")

    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    return current_user


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """
    Like get_current_user but returns None instead of raising when there's no
    valid token. For endpoints that work anonymously but personalize when the
    user is logged in (e.g. recording browsing history).
    """
    if not credentials:
        return None
    user_id = verify_token(credentials.credentials, token_type="access")
    if not user_id:
        return None
    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        return None
    return user


async def get_current_seller(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in (UserRole.seller, UserRole.superadmin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Seller access required")
    return current_user


async def get_current_moderator_or_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in (UserRole.moderator, UserRole.superadmin) and not current_user.is_staff:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Staff access required")
    return current_user


async def get_current_superadmin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.superadmin and not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Superadmin access required")
    return current_user


async def get_current_support_staff(current_user: User = Depends(get_current_user)) -> User:
    """Support agents, moderators and superadmins (anyone who can handle tickets)."""
    from app.services.rbac_service import has_permission
    if current_user.role in (UserRole.support, UserRole.moderator, UserRole.superadmin) \
            or current_user.is_superuser or has_permission(current_user, "support.handle"):
        return current_user
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Support staff access required")
