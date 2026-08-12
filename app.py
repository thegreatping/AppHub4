"""Peak AppHub 4.0 - Flask Shell"""
import os
from flask import Flask, redirect, url_for, session, request
from config import Config
from auth import auth_bp, login_required
from routes import main_bp
from maintenance import maintenance_bp
from edm import edm_bp
from pdm import pdm_bp
from cultivate import cultivate_bp
from fasttrack import fasttrack_bp
from mentor_cert import mentor_cert_bp
from mindset import mindset_bp
from new_hire import newhire_bp
from peak_link import peak_link_bp
from rent_forecast import rfs_bp
from rent_forecast2 import rfs2_bp
from market_benchmark import mrb_bp
from milestones import milestones_bp
from promotion_transfer import paf_bp
from rush_check import rush_check_bp
from sam_ad_spend import sam_ad_spend_bp
from usage_log import log_request

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Register blueprints
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(main_bp)
    app.register_blueprint(maintenance_bp)
    app.register_blueprint(edm_bp)
    app.register_blueprint(pdm_bp)
    app.register_blueprint(cultivate_bp)
    app.register_blueprint(fasttrack_bp)
    app.register_blueprint(mentor_cert_bp)
    app.register_blueprint(mindset_bp)
    app.register_blueprint(newhire_bp)
    app.register_blueprint(peak_link_bp)
    app.register_blueprint(rfs_bp)
    app.register_blueprint(rfs2_bp)
    app.register_blueprint(mrb_bp)
    app.register_blueprint(milestones_bp)
    app.register_blueprint(paf_bp)
    app.register_blueprint(rush_check_bp)
    app.register_blueprint(sam_ad_spend_bp)

    # ── Usage logging (fire-and-forget, never blocks response) ──────────────────
    _SKIP_PREFIXES = ("/static/", "/auth/", "/api/", "/favicon")

    @app.after_request
    def _log_usage(response):
        try:
            path = request.path
            # Skip static assets, auth flows, and raw API calls
            if any(path.startswith(p) for p in _SKIP_PREFIXES):
                return response
            # Only log authenticated sessions
            user = session.get("user")
            if not user:
                return response
            # Infer module_id from first path segment (e.g. /pdm/ → "pdm")
            parts = path.strip("/").split("/")
            module_id = parts[0] if parts and parts[0] else "dashboard"
            log_request(
                user_email=user.get("email", ""),
                user_name=user.get("name", ""),
                module_id=module_id,
                route=path,
                method=request.method,
                status_code=response.status_code,
            )
        except Exception:
            pass  # logging must never break the response
        return response

    return app


app = create_app()

if __name__ == "__main__":
    import os
    app.run(debug=True, port=5000,
            extra_files=[],
            reloader_type='stat',
            exclude_patterns=[os.path.join('..', '*')])
