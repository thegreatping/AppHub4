"""Quick check if MODULE_AUDIENCE exists and has data."""
import sys, os
os.environ['PYTHONUNBUFFERED'] = '1'
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection, setup_logger

env = load_env()
log = setup_logger("chk_ma")
sys.stdout.write("Starting...\n")
sys.stdout.flush()
dbas = SafeConnection(env, "DB_APP_SUPPORT", log, direct=True)
sys.stdout.write("Connected.\n")
sys.stdout.flush()

# Check if table exists
rows = dbas.fetchall("""
    SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'MODULE_AUDIENCE'
""")
sys.stdout.write(f"Table exists: {len(rows) > 0}\n")
sys.stdout.flush()

if rows:
    count = dbas.fetchall("SELECT COUNT(*) FROM dbo.MODULE_AUDIENCE")
    sys.stdout.write(f"Row count: {count[0][0]}\n")
    sys.stdout.flush()
    
    if count[0][0] > 0:
        by_type = dbas.fetchall("SELECT GRANT_TYPE, COUNT(*) FROM dbo.MODULE_AUDIENCE GROUP BY GRANT_TYPE")
        for r in by_type:
            sys.stdout.write(f"  {r[0]}: {r[1]}\n")
            sys.stdout.flush()

dbas.close()
sys.stdout.write("Done.\n")
sys.stdout.flush()
