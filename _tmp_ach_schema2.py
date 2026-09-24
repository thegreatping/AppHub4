from dotenv import load_dotenv; load_dotenv()
from app import create_app

ACCOUNTING_SITE = "peakcampus.sharepoint.com,dc67b387-b858-4611-bac2-a08676571070,f65502be-a283-4eae-a759-a23b23603fbb"
PEOPLEOPS_SITE  = "peakcampus.sharepoint.com,86d5fb45-1c0c-4986-b31c-a044e171bcc7,f65502be-a283-4eae-a759-a23b23603fbb"

app = create_app()
with app.app_context():
    from graph_client import _headers
    import requests

    for label, sid in [("Accounting", ACCOUNTING_SITE), ("PeopleOps", PEOPLEOPS_SITE)]:
        r = requests.get(f"https://graph.microsoft.com/v1.0/sites/{sid}/lists", headers=_headers())
        lists = r.json().get("value", [])
        print(f"\n=== {label} ({len(lists)} lists) ===")
        for lst in lists:
            name = lst.get("displayName", "")
            if lst.get("list", {}).get("template") != "documentLibrary" or any(
                k in name.lower() for k in ["ach", "bank", "transfer", "payment", "vendor", "request", "form"]
            ):
                print(f"  [{lst.get('id','')[:8]}] {name}")
