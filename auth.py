"""Entra ID (Azure AD) authentication."""
import os
import msal
from functools import wraps
from flask import Blueprint, redirect, url_for, session, request, current_app

auth_bp = Blueprint("auth", __name__)

_DEV_BYPASS = os.environ.get("DEV_BYPASS", "").lower() == "true"
_DEV_USER = {"email": "dev@peakmade.com", "name": "Dev User", "security_level": 100}


def _build_msal_app(cache=None):
    """Create MSAL confidential client."""
    return msal.ConfidentialClientApplication(
        current_app.config["AZURE_CLIENT_ID"],
        authority=current_app.config["AZURE_AUTHORITY"],
        client_credential=current_app.config["AZURE_CLIENT_SECRET"],
        token_cache=cache,
    )


def login_required(f):
    """Decorator to require authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if _DEV_BYPASS:
            if not session.get("user"):
                session["user"] = _DEV_USER
                session["is_developer"] = True
                session["security_level"] = 100
                # All known App_IDs from APP_ID_MAP — keep in sync with modules.py
                session["user_modules"] = [{"id": i} for i in [
                    1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 14, 15, 16, 17,
                    18, 19, 20, 21, 22, 24, 25, 26, 27, 35
                ]]
            return f(*args, **kwargs)
        if not session.get("user"):
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated_function


def _redirect_uri():
    """Build redirect URI from the current request host (works locally and on Azure)."""
    configured = current_app.config.get("AZURE_REDIRECT_URI", "")
    if configured and not configured.startswith("http://localhost"):
        return configured
    proto = request.headers.get("X-Forwarded-Proto", request.scheme)
    return f"{proto}://{request.host}/auth/callback"


@auth_bp.route("/login")
def login():
    """Initiate Entra ID login flow."""
    app_msal = _build_msal_app()
    auth_url = app_msal.get_authorization_request_url(
        scopes=current_app.config["AZURE_SCOPE"],
        redirect_uri=_redirect_uri(),
    )
    return redirect(auth_url)


@auth_bp.route("/callback")
def callback():
    """Handle Entra ID callback after login."""
    if request.args.get("error"):
        return f"Auth error: {request.args.get('error_description')}", 403

    code = request.args.get("code")
    if not code:
        return redirect(url_for("auth.login"))

    app_msal = _build_msal_app()
    result = app_msal.acquire_token_by_authorization_code(
        code,
        scopes=current_app.config["AZURE_SCOPE"],
        redirect_uri=_redirect_uri(),
    )

    if "error" in result:
        return f"Token error: {result.get('error_description')}", 403

    # Store user info in session
    id_claims = result.get("id_token_claims", {})
    session["user"] = {
        "name": id_claims.get("name", "Unknown"),
        "email": id_claims.get("preferred_username", ""),
        "oid": id_claims.get("oid", ""),
    }
    session["is_dev_mode"] = False

    return redirect(url_for("main.index"))


@auth_bp.route("/logout")
def logout():
    """Clear session and redirect to Entra ID logout."""
    session.clear()
    authority = current_app.config["AZURE_AUTHORITY"]
    return redirect(
        f"{authority}/oauth2/v2.0/logout"
        f"?post_logout_redirect_uri={url_for('auth.login', _external=True)}"
    )
