"""App settings. Everything overridable from the workspace .env / environment."""

import os

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACE_DIR = os.path.dirname(APP_DIR)


class Config:
    # Identity in AppHub comes from the signed-in session (see views._current_email),
    # not Easy Auth. Kept only so the legacy /dev/view-as route stays disabled (404).
    AUTH_MODE = os.environ.get("LMS_AUTH_MODE", "easyauth")

    # Admins are sourced from AppHub's APP_ADMINS table (App_ID 38) + developers at
    # request time; this env fallback is unused in the AppHub integration.
    ADMIN_EMAILS = {e.strip().lower() for e in os.environ.get("LMS_ADMIN_EMAILS", "").split(",") if e.strip()}

    # The warehouse is read once and then served from memory (and a disk copy that
    # survives restarts); the source only changes on the manual extract cadence.
    CACHE_TTL_MINUTES = int(os.environ.get("LMS_CACHE_TTL_MINUTES", "240"))
    CACHE_FILE = os.environ.get("LMS_CACHE_FILE", os.path.join(APP_DIR, "_pa_cache", "snapshot.pkl"))

    SECRET_KEY = os.environ.get("LMS_SECRET_KEY", "dev-only-not-secret")
