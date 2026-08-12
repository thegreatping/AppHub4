"""Quick DB auth test - checks if we can connect to DB_APP_SUPPORT directly."""
import sys, os
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection

print("Loading env...")
env = load_env()
print(f"  FABRIC_DB_APP_SUPPORT = {env.get('FABRIC_DB_APP_SUPPORT', 'NOT SET')}")
print(f"  FABRIC_DB_APP_SUPPORT_DBNAME = {env.get('FABRIC_DB_APP_SUPPORT_DBNAME', 'NOT SET')}")
print()
print("Attempting direct connection to DB_APP_SUPPORT...")
try:
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    result = conn.execute("SELECT TOP 1 App_ID, App_Name FROM dbo.APP_LIST").fetchone()
    print(f"SUCCESS! First row: {result}")
    conn.close()
except Exception as e:
    print(f"FAILED: {e}")
    import traceback
    traceback.print_exc()
