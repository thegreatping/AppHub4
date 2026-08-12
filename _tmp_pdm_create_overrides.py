"""Create PDM_FIELD_OVERRIDES table in DB_APP_SUPPORT for override tracking."""
import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import SafeConnection, load_env

env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

# Check if table exists
cur = conn.execute("SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'PDM_FIELD_OVERRIDES'")
if cur.fetchone()[0] == 0:
    print("Creating PDM_FIELD_OVERRIDES table...")
    conn.execute("""
        CREATE TABLE dbo.PDM_FIELD_OVERRIDES (
            PROPERTY_KEY INT NOT NULL,
            FIELD_NAME VARCHAR(100) NOT NULL,
            OVERRIDE_VALUE VARCHAR(500) NULL,
            CREATED_BY VARCHAR(255) NULL,
            CREATED_DATE DATETIME DEFAULT GETDATE(),
            PRIMARY KEY (PROPERTY_KEY, FIELD_NAME)
        )
    """)
    print("Done.")
else:
    print("Table already exists.")

conn.close()
