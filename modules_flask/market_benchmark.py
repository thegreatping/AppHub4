"""Market Benchmark module - launches the external Market Benchmark app."""
from flask import Blueprint, redirect, render_template, session
from auth import login_required
from modules import get_visible_modules

market_benchmark_bp = Blueprint("market_benchmark", __name__)

MARKET_BENCHMARK_URL = (
    "https://apps.powerapps.com/play/e/default-ea0cd29c-45e6-4ad1-94ff-2e9f36fb84b5"
    "/a/42b46f69-3eec-4dd9-bf23-63f04444dbb4"
    "?tenantId=ea0cd29c-45e6-4ad1-94ff-2e9f36fb84b5"
)


@market_benchmark_bp.route("/market-benchmark")
@login_required
def index():
    """Render the Market Benchmark launcher."""
    return render_template(
        "modules/market_benchmark.html",
        url=MARKET_BENCHMARK_URL,
        modules=get_visible_modules(is_admin=session.get("is_dev_mode", False)),
        active_module="market_benchmark",
        user=session.get("user", {}),
        is_dev_mode=session.get("is_dev_mode", False),
    )
