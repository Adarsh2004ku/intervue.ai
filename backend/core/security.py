"""
JWT token creation and verification.
Password hashing with bcrypt directly (no passlib).
"""

from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
import bcrypt
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from backend.core.config import settings


def hash_password(password: str) -> str:
    """Hash a plain password using bcrypt."""
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed_bytes = bcrypt.hashpw(password_bytes, salt)
    return hashed_bytes.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a bcrypt hash."""
    if not hashed_password:
        return False # Prevents crash if database has no password
    
    try:
        plain_bytes = plain_password.encode('utf-8')
        hashed_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(plain_bytes, hashed_bytes)
    except Exception:
        # If the hash is malformed or wrong format, return False instead of crashing
        return False


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expiry_minutes)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


# --- NEW: FastAPI Security Scheme & Dependency ---
security_scheme = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security_scheme)) -> dict:
    """
    FastAPI dependency that extracts the JWT from the Authorization header,
    verifies it, and returns the user payload.
    Using this makes the 🔒 Authorize button work in Swagger UI!
    """
    token = credentials.credentials
    return decode_access_token(token)


def is_admin_user(user: dict) -> bool:
    """Return whether a decoded JWT payload belongs to an admin email."""
    email = str(user.get("email") or "").strip().lower()
    return bool(email and email in settings.admin_email_list)


async def get_admin_user(user: dict = Depends(get_current_user)) -> dict:
    """Require the current user to be configured as an admin."""
    if not is_admin_user(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user
