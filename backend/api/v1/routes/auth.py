from fastapi import APIRouter,HTTPException,status,Depends
from pydantic import BaseModel,EmailStr
from backend.core.security import hash_password,verify_password,create_access_token,decode_access_token
from backend.db.session import supabase
from backend.core.logging import get_logger

logger = get_logger("auth")
router = APIRouter()


"""
Authentication routes:
- POST /signup — Register new user
- POST /login — Login and get JWT token
- GET /me — Get current user profile
"""


class SignupRequest(BaseModel):
    email : EmailStr
    password : str
    full_name : str = ""

class LoginRequest(BaseModel):
    email : EmailStr
    password : str

class TokenResposne(BaseModel):
    access_token : str
    token_type : str = "bearer"
    user_id : str
    email : str

class UserResponse(BaseModel):
    id : str
    email : str
    full_name : str | None
    plan : str
    difficulty_profile : str

async def get_current_user(token : str = Depends(lambda : None)) -> dict:
    """
    Dependency that extracts and verifies JWT from Authorization header.
    """

    if token is None:
        raise HTTPException(status_code= 401,detail="Not authenticated")
    return decode_access_token(token)

@router.post("/signup",response_model = TokenResposne)
async def signup(req : SignupRequest):
    "Register new user"
    existing = supabase.table("users").select("id").eq("email",req.email).execute()
    if existing.data:
        raise HTTPException(status_code=400,detail="Email already registered")
    
    # create user 
    hashed = hash_password(req.password)
    result = supabase.table("users").insert({
        "email" :req.email,
        "hashed_password":hashed,
        "full_name" : req.full_name,
    }).execute()

    if not result.data:
        raise HTTPException(status_code=500,detail="Failed to create user")
    
    user = result.data[0]
    token = create_access_token({"sub":user["id"],"email":user["email"]})

    logger.info("user_signed_up",email = req.email)
    return TokenResposne(
        access_token=token,
        user_id= user["id"],
        email=user["email"],
    )


@router.post("/login",response_model = TokenResposne)
async def login(req:LoginRequest):
    """ Login and recive a JWT token"""
    result = supabase.table("users").select("*").eq("email",req.email).execute()

    if not result.data:
        raise HTTPException(status_code=401,detail= "Invalid Email or password")
    
    user = result.data[0]

    if not verify_password(req.password.user.get("hashed_password","")):
        raise HTTPException(status_code=401,detail= "Invalid Email or password")
    
    token = create_access_token({"sub": user["id"],"email":user["email"]})

    logger.info("user_logged_in",email = req.email)
    return TokenResposne(
        access_token= token,
        user_id= user["id"],
        email = user["email"]
    )


@router.get("/me", response_model=UserResponse)
async def get_me(authorization: str = ""):
    """Get current user profile."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")

    token = authorization.replace("Bearer ", "")
    payload = decode_access_token(token)

    result = supabase.table("users").select("*").eq("id", payload["sub"]).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="User not found")

    user = result.data[0]
    return UserResponse(
        id=user["id"],
        email=user["email"],
        full_name=user.get("full_name"),
        plan=user.get("plan", "free"),
        difficulty_profile=user.get("difficulty_profile", "beginner"),
    )