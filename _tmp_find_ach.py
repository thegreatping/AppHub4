"""Search for ACH-related SharePoint lists and DB tables."""
from dotenv import load_dotenv; load_dotenv()
from app import create_app
from helpers import load_env, SafeConnection

app = create_app()
with app.app_context():
    from graph_client import _headers
    import requests

    # 1. Search all accessible SharePoint sites
    r = requests.get(
        "https://graph.microsoft.com/v1.0/sites?search=peak",
        headers=_headers()
    )
    sites = r.json().get("value", [])
    print(f"Found {len(sites)} SP sites matching 'peak':")
    for s in sites:
        print(f"  {s.get('webUrl')}  ({s.get('id')})")

    # 2. Check each site's lists for ACH
    keywords = ["ach", "bank", "transfer", "wire", "direct deposit"]
    print("\n--- ACH-related lists across all sites ---")
    for s in sites:
        sid = s.get("id")
        r2 = requests.get(f"https://graph.microsoft.com/v1.0/sites/{sid}/lists", headers=_headers())
        for lst in r2.json().get("value", []):
            nm = lst.get("displayName", "").lower()
            if any(k in nm for k in keywords):
                print(f"  Site: {s.get('webUrl')}")
                print(f"  List: {lst.get('displayName')}  GUID: {lst.get('id')}")

# 3. Check DB for ACH tables
print("\n--- DB_APP_SUPPORT tables with ACH/Bank/Transfer ---")
conn = SafeConnection(load_env(), "DB_APP_SUPPORT", None, direct=True)
rows = conn.fetchall(
    "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE='BASE TABLE' ORDER BY TABLE_NAME"
)
for (t,) in rows:
    if any(k in t.upper() for k in ["ACH", "BANK", "TRANSFER", "WIRE"]):
        print(f"  {t}")
