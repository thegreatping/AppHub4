"""Smoke-test: insert + read + delete one row via fabric_db.get_connection."""
import sys, os
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection

# Simulate what usage_log._write_log does (using SafeConnection since fabric_db
# needs Fabric token auth — SafeConnection is what works locally)
env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

print("=== INSERT test row ===")
conn.execute("""
    INSERT INTO dbo.APPHUB_USAGE_LOG
        (user_email, user_name, module_id, route, http_method, status_code)
    VALUES (?, ?, ?, ?, ?, ?)
""", ("test@peakmade.com", "Test User", "maintenance", "/maintenance/", "GET", 200))

print("=== READ back ===")
cur = conn.execute("""
    SELECT TOP 1 log_id, logged_at, user_email, module_id, status_code
    FROM dbo.APPHUB_USAGE_LOG
    ORDER BY log_id DESC
""")
row = cur.fetchone()
print(f"  log_id={row[0]}  logged_at={row[1]}  email={row[2]}  module={row[3]}  status={row[4]}")

print("=== CLEANUP ===")
conn.execute("DELETE FROM dbo.APPHUB_USAGE_LOG WHERE log_id = ?", [row[0]])
print(f"  Deleted log_id={row[0]}")

print("\nAll good — APPHUB_USAGE_LOG is ready.")
