"""Test direct connection to DB_APP_SUPPORT using the same path as Flask."""
import sys, json, time, struct
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, _get_fabric_token, _TOKEN_CACHE_PATH

env = load_env()
print("Env keys:", [k for k in env if 'APP_SUPPORT' in k or 'FABRIC' in k])

# Test 1: Check what token is returned
print("\n--- Token check ---")
token = _get_fabric_token(env)
print(f"Token (first 30): {token[:30]}...")
print(f"Token length: {len(token)}")

# Test 2: Try connecting
print("\n--- Connection test ---")
import pyodbc
server = env.get("FABRIC_DB_APP_SUPPORT")
dbname = env.get("FABRIC_DB_APP_SUPPORT_DBNAME")
print(f"Server: {server}")
print(f"DB: {dbname}")

token_bytes = token.encode("utf-16-le")
ts = struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)
cs = (f"DRIVER={{ODBC Driver 18 for SQL Server}};SERVER={server};"
      f"DATABASE={dbname};Encrypt=yes;Connection Timeout=60;")
try:
    cn = pyodbc.connect(cs, attrs_before={1256: ts}, timeout=30)
    result = cn.execute("SELECT TOP 1 PROPERTY_KEY FROM dbo.PROPERTY_0").fetchone()
    print(f"SUCCESS! First property_key: {result[0]}")
    cn.close()
except Exception as e:
    print(f"FAILED: {e}")
