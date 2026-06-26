"""
Security utilities: JWT token creation/verification, password hashing.
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Union

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = settings.ALGORITHM


def create_access_token(subject: Union[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a signed JWT access token."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {"exp": expire, "sub": str(subject), "type": "access"}
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(subject: Union[str, Any]) -> str:
    """Create a signed JWT refresh token with longer expiry."""
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode = {"exp": expire, "sub": str(subject), "type": "refresh"}
    return jwt.encode(to_encode, settings.REFRESH_SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str, token_type: str = "access") -> Optional[str]:
    """
    Verify a JWT token and return the subject (user id).
    Returns None if the token is invalid or expired.
    Access and refresh tokens are signed with separate secrets.
    """
    key = settings.REFRESH_SECRET_KEY if token_type == "refresh" else settings.SECRET_KEY
    try:
        payload = jwt.decode(token, key, algorithms=[ALGORITHM])
        if payload.get("type") != token_type:
            return None
        subject: str = payload.get("sub")
        return subject
    except JWTError:
        return None


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)
