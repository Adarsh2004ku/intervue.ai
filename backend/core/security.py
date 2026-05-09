from datetime import datetime,timedelta,timezone
from jose import JWTError,jwt
from passlib.context import CryptContext
from fastapi import HTTPException,status
from backend.core.config import settings


"""
JWT token creation and verification
and password hashing with bcrypt
"""

pwd_context = CryptContext(schemes=["bcrypt"],deprecated = "auto")

def hash_password(password:str)->str:
    """Hash a plain password using bcrypt."""
    return pwd_context.hash(password)

def verify_password(plain_password:str,hashed_password:str)->bool:
    """
    verify a plain password against bcrypt hash
    """
    return pwd_context.verify(plain_password,hashed_password)

def create_access_token(data:dict)->str:
    """
    create JWT tokens data should contain at 
    least {"sub":user_id,"email":user_email}
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes = settings.jwt_expiry_minutes
    )
    to_encode.update({"exp":expire})
    return jwt.encode(
        to_encode,settings.jwt_secret,algorithm=settings.jwt_algorithm
    )

def decode_access_token(token:str)->dict:
    """
    Decode and verify a JWT token.
    Raises HTTPException if token is valid or expired
    """
    try:
        payload = jwt.decode(
            token,settings.jwt_secret,algorithms = [settings.jwt_algorithm]
        )
        return payload
    except JWTError:
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail = "Invalid or expired token",
            headers={"WWW-Authenticate":"Bearer"}
        )
