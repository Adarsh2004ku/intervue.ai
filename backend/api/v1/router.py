"""
Master API router that includes all sub-routers.
All routes are prefixed with /api/v1/
"""

from fastapi import APIRouter
from backend.api.v1.routes.auth import router as auth_router
from backend.api.v1.routes.resume import router as resume_router
from backend.api.v1.routes.interview import router as interview_router
from backend.api.v1.routes.report import router as report_router
from backend.api.v1.routes.admin import router as admin_router

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
api_router.include_router(resume_router, prefix="/resume", tags=["Resume"])
api_router.include_router(interview_router, prefix="/interview", tags=["Interview"])
api_router.include_router(report_router, prefix="/report", tags=["Report"])
api_router.include_router(admin_router, prefix="/admin", tags=["Admin"])