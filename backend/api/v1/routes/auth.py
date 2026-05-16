"""
Authentication routes:
- POST /signup — Register new user
- POST /login — Login with email/password and get JWT token
- POST /supabase-session — Exchange Supabase access token for app JWT (used by frontend OAuth)
- GET /google — Get Google OAuth authorization URL
- GET /callback — Handle OAuth callback from Google (server-side flow)
- GET /me — Get current user profile
"""

from fastapi import APIRouter, HTTPException, status, Depends, Request, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr
from urllib.parse import urlencode
from backend.core.security import create_access_token, get_current_user
from backend.core.config import settings
from backend.db.session import get_supabase_client, supabase
from backend.core.logging import get_logger

logger = get_logger("auth")
router = APIRouter()
_oauth_supabase = None


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str = ""


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class SupabaseSessionRequest(BaseModel):
    access_token: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _get_oauth_supabase():
    """Return the OAuth client that stores the PKCE verifier between redirects."""
    global _oauth_supabase
    if _oauth_supabase is None:
        _oauth_supabase = get_supabase_client()
    return _oauth_supabase


def _profile_supabase():
    """Return a fresh service-role client for backend-owned profile reads/writes."""
    return get_supabase_client()


def _upsert_user(auth_user, full_name: str = "", db_client=None):
    """Create or update the local users table row from a Supabase auth user."""
    email = auth_user.email or ""
    metadata = auth_user.user_metadata or {}
    name = full_name or metadata.get("full_name") or metadata.get("name") or ""
    profile_client = db_client or _profile_supabase()

    profile_client.table("users").upsert({
        "id": auth_user.id,
        "email": email,
        "hashed_password": "",
        "full_name": name,
        # Uncomment once you add an avatar_url column to the users table:
        # "avatar_url": metadata.get("avatar_url") or metadata.get("picture") or "",
    }).execute()


def _is_duplicate_signup_error(error: Exception) -> bool:
    """Detect Supabase duplicate-user errors across client/library versions."""
    message = str(error).lower()
    duplicate_markers = (
        "already registered",
        "already been registered",
        "already exists",
        "duplicate",
        "unique constraint",
    )
    return any(marker in message for marker in duplicate_markers)


# ---------------------------------------------------------------------------
# Email / Password
# ---------------------------------------------------------------------------

@router.post("/signup", response_model=TokenResponse)
async def signup(req: SignupRequest):
    """Register a new user through Supabase Auth and mirror the profile."""
    try:
        auth_client = get_supabase_client()
        profile_client = _profile_supabase()
        auth_response = auth_client.auth.admin.create_user({
            "email": req.email,
            "password": req.password,
            "email_confirm": True,
            "user_metadata": {
                "full_name": req.full_name,
            },
        })

        if not auth_response.user:
            raise HTTPException(status_code=500, detail="Failed to create Supabase auth user")

        auth_user = auth_response.user

        try:
            result = profile_client.table("users").upsert({
                "id": auth_user.id,
                "email": auth_user.email or req.email,
                "hashed_password": "",
                "full_name": req.full_name,
            }).execute()

            if not result.data:
                logger.error("signup_profile_upsert_failed", email=req.email)
        except Exception as profile_error:
            logger.error(
                "signup_profile_upsert_exception",
                email=req.email,
                error=str(profile_error),
            )

        token = create_access_token({"sub": auth_user.id, "email": auth_user.email or req.email})

        logger.info("user_signed_up", email=req.email)
        return TokenResponse(
            access_token=token,
            user_id=auth_user.id,
            email=auth_user.email or req.email,
        )
    except HTTPException:
        raise
    except Exception as e:
        if _is_duplicate_signup_error(e):
            logger.info("signup_duplicate_email", email=req.email)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            )

        logger.error("signup_exception", error=str(e))
        raise HTTPException(status_code=500, detail="Unable to create account right now")


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    """Login with Supabase Auth and receive an app JWT token."""
    try:
        auth_client = get_supabase_client()
        profile_client = _profile_supabase()
        auth_response = auth_client.auth.sign_in_with_password({
            "email": req.email,
            "password": req.password,
        })

        if not auth_response.user:
            raise HTTPException(status_code=401, detail="Invalid email or password")

        auth_user = auth_response.user
        try:
            profile = profile_client.table("users").select("*").eq("id", auth_user.id).execute()
            if not profile.data:
                profile_client.table("users").upsert({
                    "id": auth_user.id,
                    "email": auth_user.email or req.email,
                    "hashed_password": "",
                    "full_name": (auth_user.user_metadata or {}).get("full_name", ""),
                }).execute()
        except Exception as profile_error:
            logger.error(
                "login_profile_sync_failed",
                user_id=auth_user.id,
                error=str(profile_error),
            )

        token = create_access_token({"sub": auth_user.id, "email": auth_user.email or req.email})

        logger.info("user_logged_in", email=req.email)
        return TokenResponse(
            access_token=token,
            user_id=auth_user.id,
            email=auth_user.email or req.email,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("login_exception", error=str(e))
        raise HTTPException(status_code=401, detail="Invalid email or password")


# ---------------------------------------------------------------------------
# Supabase session exchange  (used by FRONTEND-driven Google OAuth)
# ---------------------------------------------------------------------------

@router.post("/supabase-session", response_model=TokenResponse)
async def login_with_supabase_session(req: SupabaseSessionRequest):
    """Exchange a Supabase Auth access token for this API's JWT.

    This is the primary endpoint for **frontend-driven** OAuth flows:
      1. Frontend calls `supabase.auth.signInWithOAuth({ provider: 'google' })`
      2. After redirect back, the frontend has a Supabase access_token
      3. Frontend sends that token here → receives the app JWT
    """
    try:
        auth_client = get_supabase_client()
        user_response = auth_client.auth.get_user(req.access_token)
        auth_user = user_response.user if user_response else None

        if not auth_user:
            raise HTTPException(status_code=401, detail="Invalid Supabase session")

        _upsert_user(auth_user)

        email = auth_user.email or ""
        token = create_access_token({"sub": auth_user.id, "email": email})

        logger.info("user_supabase_session_login", email=email)
        return TokenResponse(
            access_token=token,
            user_id=auth_user.id,
            email=email,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("supabase_session_login_exception", error=str(e))
        raise HTTPException(status_code=401, detail="Invalid Supabase session")


# ---------------------------------------------------------------------------
# Google OAuth  (SERVER-SIDE redirect flow)
# ---------------------------------------------------------------------------

@router.get("/google")
async def google_oauth(request: Request):
    """Get the Google OAuth authorization URL.

    **Server-side flow:**  Frontend navigates to this endpoint (or uses the
    returned URL to redirect).  After the user authenticates with Google,
    Supabase redirects to ``/auth/callback`` which exchanges the code and
    redirects the user back to the frontend with the app JWT.

    **Frontend-driven flow (simpler for SPAs):**
    Use the Supabase JS client on the frontend instead::

        const { data, error } = await supabase.auth.signInWithOAuth({
            provider: 'google',
            options: { redirectTo: window.location.origin + '/auth/callback' }
        });

    Then send the resulting ``access_token`` to ``POST /supabase-session``.
    """
    callback_url = str(request.url_for("oauth_callback"))

    try:
        oauth_client = _get_oauth_supabase()
        response = oauth_client.auth.sign_in_with_oauth({
            "provider": "google",
            "options": {
                "redirect_to": callback_url,
            },
        })
        return {"url": response.url}
    except Exception as e:
        logger.error("google_oauth_url_error", error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to generate Google OAuth URL",
        )


@router.get("/callback")
async def oauth_callback(
    code: str = Query(None),
    error: str = Query(None),
    error_description: str = Query(None),
):
    """Handle the OAuth callback from Google (via Supabase).

    Supabase redirects here with ``?code=<auth_code>`` after a successful
    Google sign-in.  This endpoint:

    1. Exchanges the code for a Supabase session
    2. Upserts the user into the local ``users`` table
    3. Creates an app JWT
    4. Redirects to the frontend with ``access_token``, ``user_id``, and
       ``email`` as query parameters

    **Important — Supabase dashboard setup:**
    Add your callback URL (e.g. ``https://api.yourdomain.com/auth/callback``)
    to **Authentication → URL Configuration → Redirect URLs** in the
    Supabase dashboard.
    """
    if error:
        logger.warning("oauth_error", error=error, description=error_description)
        return RedirectResponse(
            url=f"{settings.frontend_url}/login?error=oauth_failed"
        )

    if not code:
        return RedirectResponse(
            url=f"{settings.frontend_url}/login?error=missing_code"
        )

    try:
        # Exchange the authorization code for a Supabase session.
        # NOTE: If you run multiple workers, PKCE state may not be shared.
        # In that case prefer the frontend-driven flow (POST /supabase-session).
        oauth_client = _get_oauth_supabase()
        auth_response = oauth_client.auth.exchange_code_for_session({"auth_code": code})

        # Handle different supabase-py response shapes
        auth_user = getattr(auth_response, "user", None)
        if auth_user is None:
            session = getattr(auth_response, "session", None)
            if session:
                auth_user = getattr(session, "user", None)

        if not auth_user:
            return RedirectResponse(
                url=f"{settings.frontend_url}/login?error=auth_failed"
            )

        _upsert_user(auth_user)

        email = auth_user.email or ""
        token = create_access_token({"sub": auth_user.id, "email": email})

        logger.info("google_oauth_success", email=email)

        params = urlencode({
            "access_token": token,
            "user_id": auth_user.id,
            "email": email,
        })
        return RedirectResponse(
            url=f"{settings.frontend_url}/auth/callback?{params}"
        )
    except Exception as e:
        logger.error("google_oauth_callback_error", error=str(e))
        return RedirectResponse(
            url=f"{settings.frontend_url}/login?error=oauth_failed"
        )


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

@router.get("/me")
async def get_me(user: dict = Depends(get_current_user)):
    """Get current user profile."""
    profile_client = _profile_supabase()
    result = profile_client.table("users").select("*").eq("id", user["sub"]).execute()
    if not result.data:
        email = user.get("email", "")
        created = profile_client.table("users").upsert({
            "id": user["sub"],
            "email": email,
            "hashed_password": "",
            "full_name": "",
        }).execute()

        if not created.data:
            raise HTTPException(status_code=404, detail="User not found")

        result = created

    u = result.data[0]
    return {
        "id": u["id"],
        "email": u["email"],
        "full_name": u.get("full_name"),
        "plan": u.get("plan", "free"),
        "difficulty_profile": u.get("difficulty_profile", "beginner"),
    }
