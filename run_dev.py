"""Development runner - bypasses Entra ID auth for local testing."""
import os
os.environ.setdefault("FLASK_SECRET_KEY", "dev-local-testing-key")

from app import app
from flask import session


@app.before_request
def dev_auto_login():
    """Auto-login as dev user and resolve security context."""
    from modules import APP_ID_MAP
    all_modules = [
        {"id": app_id, "name": name, "access": "developer"}
        for app_id, name in APP_ID_MAP.items()
    ]
    if not session.get("user") or "is_developer" not in session:
        session["user"] = {
            "name": "Craig Pell",
            "email": "cpell@peakmade.com",
            "oid": "dev-mode",
        }
        session["is_developer"] = True
        session["is_dev_mode"] = False  # Start with dev mode OFF
    # Always keep user_modules in sync with current APP_ID_MAP so new modules appear immediately
    session["user_modules"] = all_modules


if __name__ == "__main__":
    print("\n  🏠 Peak AppHub 4.0 - Development Mode")
    print("  → http://localhost:5001\n")
    app.run(debug=True, port=5001)
