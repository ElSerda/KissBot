#!/usr/bin/env python3
"""
KissBot Web Backend - FastAPI

Entry point pour le dashboard web.
Gère l'OAuth Twitch et expose l'API pour le frontend.
"""

import os
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from auth.router import router as auth_router
from api.router import router as api_router

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger(__name__)

# Config
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
BASE_DIR = Path(__file__).parent

# Rate Limiter
limiter = Limiter(key_func=get_remote_address)

# Templates Jinja2
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown events."""
    logger.info("🚀 KissBot Web Backend starting...")
    yield
    logger.info("👋 KissBot Web Backend shutting down...")


app = FastAPI(
    title="KissBot API",
    description="API pour le dashboard KissBot",
    version="1.0.0",
    lifespan=lifespan,
)

# Rate Limiter state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Static files (CSS, JS, images)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

# CORS (pour les appels API depuis le même domaine)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
app.include_router(api_router, prefix="/api", tags=["API"])


# ============================================================
# SECURITY HEADERS MIDDLEWARE
# ============================================================
@app.middleware("http")
async def security_headers(request: Request, call_next):
    """Ajoute les headers de sécurité à toutes les réponses."""
    response: Response = await call_next(request)
    
    # Anti-clickjacking
    response.headers["X-Frame-Options"] = "DENY"
    
    # Empêche le sniffing MIME
    response.headers["X-Content-Type-Options"] = "nosniff"
    
    # XSS Protection (legacy mais utile)
    response.headers["X-XSS-Protection"] = "1; mode=block"
    
    # Referrer Policy
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    
    # Permissions Policy (désactive les APIs sensibles)
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    
    # Content Security Policy (calibrée pour Alpine.js + Tailwind CDN)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' https://unpkg.com https://cdn.tailwindcss.com 'unsafe-inline'; "
        "style-src 'self' https://cdn.tailwindcss.com 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "connect-src 'self'; "
        "font-src 'self' https:; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "object-src 'none';"
    )
    
    return response


@app.get("/")
async def index(request: Request, code: str = None, state: str = None, error: str = None):
    """Landing page + OAuth callback handler."""
    from fastapi.responses import RedirectResponse
    
    # Si c'est un callback OAuth (code présent)
    if code and state:
        # Déléguer au handler OAuth
        from auth.router import handle_oauth_callback
        return await handle_oauth_callback(code=code, state=state, error=error)
    
    # Si erreur OAuth
    if error:
        logger.warning(f"OAuth error: {error}")
        return templates.TemplateResponse("index.html", {
            "request": request,
            "user": None,
            "error": error,
        })
    
    # Check if user is logged in
    session = request.cookies.get("session")
    if session:
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "user": _parse_session(session),
            "bot_active": True,  # TODO: Check real status
        })
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "user": None,
    })


@app.get("/dashboard")
async def dashboard(request: Request):
    """Dashboard page (requires login)."""
    session = request.cookies.get("session")
    if not session:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/")
    
    user = _parse_session(session)
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "bot_active": True,  # TODO: Check real status
    })


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


def _parse_session(session: str) -> dict:
    """Parse session cookie into user dict."""
    try:
        parts = session.split(":")
        return {
            "id": parts[0],
            "login": parts[1],
            "display_name": parts[2] if len(parts) > 2 else parts[1],
        }
    except (IndexError, ValueError):
        return {"id": "0", "login": "unknown", "display_name": "Unknown"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8080,
        reload=DEBUG
    )
