from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
import bcrypt
from fastapi import HTTPException, status
from backend.core.config import settings

"""
JWT token creation and verification.
Password hashing with bcrypt directly (no passlib).
"""
def hash_password(password: str) -> str:
    """Hash a plain password using bcrypt."""
    # bcrypt requires bytes, so we encode the password
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed_bytes = bcrypt.hashpw(password_bytes, salt)
    # Return as string for database storage
    return hashed_bytes.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a bcrypt hash."""
    plain_bytes = plain_password.encode('utf-8')
    hashed_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(plain_bytes, hashed_bytes)


def create_access_token(data: dict) -> str:
    """
    Create a JWT access token.
    data should contain at least {"sub": user_id, "email": user_email}
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.jwt_expiry_minutes
    )
    to_encode.update({"exp": expire})
    return jwt.encode(
        to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm
    )


def decode_access_token(token: str) -> dict:
    """
    Decode and verify a JWT token.
    Raises HTTPException if token is invalid or expired.
    """
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )