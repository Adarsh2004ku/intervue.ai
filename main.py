"""Vercel FastAPI entrypoint.

The application lives in backend.main; this root module lets Vercel's
FastAPI preset detect the ASGI app without changing the local backend layout.
"""

from backend.main import app
