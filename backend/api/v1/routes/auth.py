"""
Authentication routes:
- POST /signup — Register new user
- POST /login — Login and get JWT token
- GET /me — Get current user profile
"""

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, EmailStr
from backend.core.security import hash_password, verify_password, create_access_token, decode_access_token, get_current_user
from backend.db.session import supabase
from backend.core.logging import get_logger

logger = get_logger("auth")
router = APIRouter()


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str = ""


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str


@router.post("/signup", response_model=TokenResponse)
async def signup(req: SignupRequest):
    """Register a new user."""
    try:
        # Check if user already exists
        existing = supabase.table("users").select("id").eq("email", req.email).execute()
        if existing.data:
            raise HTTPException(status_code=400, detail="Email already registered")

        hashed = hash_password(req.password)
        
        # Insert user
        result = supabase.table("users").insert({
            "email": req.email,
            "hashed_password": hashed,
            "full_name": req.full_name,
        }).execute()

        if not result.data:
            logger.error("signup_insert_failed", email=req.email, error=result.error)
            raise HTTPException(status_code=500, detail="Failed to create user in database")

        user = result.data[0]
        token = create_access_token({"sub": user["id"], "email": user["email"]})

        logger.info("user_signed_up", email=req.email)
        return TokenResponse(
            access_token=token,
            user_id=user["id"],
            email=user["email"],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("signup_exception", error=str(e))
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    """Login and receive a JWT token."""
    try:
        result = supabase.table("users").select("*").eq("email", req.email).execute()

        if not result.data:
            raise HTTPException(status_code=401, detail="Invalid email or password")

        user = result.data[0]

        # Verify password (won't crash now thanks to the security.py update)
        if not verify_password(req.password, user.get("hashed_password", "")):
            raise HTTPException(status_code=401, detail="Invalid email or password")

        token = create_access_token({"sub": user["id"], "email": user["email"]})

        logger.info("user_logged_in", email=req.email)
        return TokenResponse(
            access_token=token,
            user_id=user["id"],
            email=user["email"],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("login_exception", error=str(e))
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/me")
async def get_me(user: dict = Depends(get_current_user)):
    """Get current user profile."""
    result = supabase.table("users").select("*").eq("id", user["sub"]).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="User not found")
    
    u = result.data[0]
    return {
        "id": u["id"],
        "email": u["email"],
        "full_name": u.get("full_name"),
        "plan": u.get("plan", "free"),
        "difficulty_profile": u.get("difficulty_profile", "beginner"),
    }