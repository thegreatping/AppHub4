from dotenv import load_dotenv; load_dotenv()
from app import create_app
import json

SITE_ID = "peakcampus.sharepoint.com,86d5fb45-1c0c-4986-b31c-a044e171bcc7,f65502be-a283-4eae-a759-a23b23603fbb"
LIST_ID = "fcdb3412-0198-4fae-a7ef-37143f40caaa"

app = create_app()
with app.app_context():
    from graph_client import list_items, get_list_columns
    cols = get_list_columns(SITE_ID, LIST_ID)
    print("=== COLUMNS ===")
    for c in cols:
        if not c.get("hidden") and not c.get("readOnly"):
            print(f"  {c['name']:<40s} -> {c['displayName']}")
    print()
    rows = list_items(SITE_ID, LIST_ID)
    print(f"=== {len(rows)} ROWS ===")
    if rows:
        print(json.dumps(rows[0], indent=2, default=str))
