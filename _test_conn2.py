"""Test with azure.identity directly vs az CLI token."""
import sys, struct
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env

env = load_env()
server = env.get("FABRIC_DB_APP_SUPPORT")
dbname = env.get("FABRIC_DB_APP_SUPPORT_DBNAME")

def try_connect(token, label):
    import pyodbc
    token_bytes = token.encode("utf-16-le")
    ts = struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)
    cs = (f"DRIVER={{ODBC Driver 18 for SQL Server}};SERVER={server};"
          f"DATABASE={dbname};Encrypt=yes;Connection Timeout=60;")
    try:
        cn = pyodbc.connect(cs, attrs_before={1256: ts}, timeout=30)
        r = cn.execute("SELECT TOP 1 PROPERTY_KEY FROM dbo.PROPERTY_0").fetchone()
        print(f"[{label}] SUCCESS — first key: {r[0]}")
        cn.close()
        return True
    except Exception as e:
        print(f"[{label}] FAILED: {str(e)[:200]}")
        return False

# Try 1: AzureCliCredential
print("--- Test 1: azure.identity AzureCliCredential ---")
try:
    from azure.identity import AzureCliCredential
    cred = AzureCliCredential()
    tok = cred.get_token("https://database.windows.net/.default")
    print(f"  AzureCliCredential token length: {len(tok.token)}, expires: {tok.expires_on}")
    import base64, json as _j
    payload = tok.token.split(".")[1]
    payload += "=" * (4 - len(payload) % 4)
    claims = _j.loads(base64.b64decode(payload))
    print(f"  aud={claims.get('aud')}, upn={claims.get('upn')}, scp={claims.get('scp')}")
    try_connect(tok.token, "AzureCliCredential")
except Exception as e:
    print(f"  Error: {e}")
