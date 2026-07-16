"""Session-based login: Google OAuth (restricted to ALLOWED_EMAIL) plus a
username/password fallback. Replaces the raw HTTP Basic Auth popup with a
real, styled /login page.
"""

from __future__ import annotations

import secrets

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from src.config import Settings, load_settings
from web.ratelimit import rate_limit
from web.templating import templates

router = APIRouter()

_ERROR_MESSAGES = {
    "invalid": "Invalid username or password.",
    "not_allowed": "That Google account isn't authorized for this site.",
    "oauth_failed": "Google sign-in failed. Try again or use the password below.",
}


class NotAuthenticated(Exception):
    """Raised by require_auth when the request has no valid login session."""


def build_oauth(settings: Settings) -> OAuth:
    oauth = OAuth()
    if settings.google_client_id and settings.google_client_secret:
        oauth.register(
            name="google",
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email profile"},
        )
    return oauth


oauth = build_oauth(load_settings())


def require_auth(request: Request) -> None:
    if not request.session.get("authenticated"):
        raise NotAuthenticated()


def is_authenticated(request: Request) -> bool:
    """Same check as require_auth, but for places that render differently
    for logged-in vs anonymous visitors instead of hard-blocking (e.g. the
    public showcase, or an owner-only button on an otherwise-public page)."""
    return bool(request.session.get("authenticated"))


def _valid_password_login(settings: Settings, username: str, password: str) -> bool:
    if not settings.site_username or not settings.site_password:
        return False
    return secrets.compare_digest(username, settings.site_username) and secrets.compare_digest(
        password, settings.site_password
    )


def _allowed_emails(settings: Settings) -> set[str]:
    if not settings.allowed_email:
        return set()
    return {email.strip().lower() for email in settings.allowed_email.split(",") if email.strip()}


@router.get("/login")
def login_page(request: Request):
    settings = load_settings()
    error = request.query_params.get("error")
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "google_enabled": bool(settings.google_client_id and settings.google_client_secret),
            "error_message": _ERROR_MESSAGES.get(error),
        },
    )


@router.post("/login", dependencies=[Depends(rate_limit(10, 300, "login"))])
def login_submit(request: Request, username: str = Form(...), password: str = Form(...)):
    settings = load_settings()
    if _valid_password_login(settings, username, password):
        request.session["authenticated"] = True
        return RedirectResponse(url="/ask", status_code=303)
    return RedirectResponse(url="/login?error=invalid", status_code=303)


@router.get("/auth/google")
async def google_login(request: Request):
    settings = load_settings()
    if not (settings.google_client_id and settings.google_client_secret):
        return RedirectResponse(url="/login", status_code=303)
    redirect_uri = str(request.url_for("google_callback"))
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/auth/google/callback")
async def google_callback(request: Request):
    settings = load_settings()
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception:
        return RedirectResponse(url="/login?error=oauth_failed", status_code=303)

    email = ((token.get("userinfo") or {}).get("email") or "").strip().lower()
    if not email or email not in _allowed_emails(settings):
        return RedirectResponse(url="/login?error=not_allowed", status_code=303)

    request.session["authenticated"] = True
    request.session["email"] = email
    return RedirectResponse(url="/ask", status_code=303)


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)
