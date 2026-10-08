"""Peak Academy LMS reporting — AppHub 4.0 integration.

Ported from the standalone Flask app delivered by Ryan Mahaffey (2026-10-07).
Instead of its own Flask app + Easy Auth, it runs as an AppHub blueprint:
identity comes from the AppHub session, data from AppHub's SafeConnection, and
every page renders inside AppHub's shell.html.
"""

from .config import Config
from .data import Store


def init_peak_academy(app):
    """Attach the Peak Academy blueprint, data store, and Jinja helpers to the AppHub app."""
    # Per-process in-memory snapshot of the 4 WH_PROD2 LMS tables (TTL + disk pickle).
    app.extensions["lms_store"] = Store(Config.CACHE_FILE, Config.CACHE_TTL_MINUTES)

    from . import views
    app.register_blueprint(views.bp)
    app.jinja_env.filters.update(views.FILTERS)
    # Globals, not context: macros imported with {% from ... import %} can't see context vars.
    from .metrics import PERIODS
    app.jinja_env.globals["periods"] = PERIODS
    return app
