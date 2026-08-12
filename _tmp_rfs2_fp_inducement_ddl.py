"""DDL: Create FORECAST_FP_INDUCEMENT table — run ONCE."""
import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection

env  = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

cur = conn.execute("""
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_SCHEMA='dbo' AND TABLE_NAME='FORECAST_FP_INDUCEMENT'
""")
if cur.fetchone()[0] == 0:
    conn.execute("""
        CREATE TABLE dbo.FORECAST_FP_INDUCEMENT (
            FP_INDUCEMENT_KEY  INT          NOT NULL IDENTITY(1,1) PRIMARY KEY,
            FORECAST_KEY       INT          NOT NULL,
            FLOORPLAN_KEY      INT          NOT NULL,
            PLANNED_USE        FLOAT        NOT NULL DEFAULT 0,
            CREATED_BY         NVARCHAR(200) NULL,
            DATE_CREATED       INT          NULL,
            DATE_MODIFIED      INT          NULL,
            CONSTRAINT UQ_FORECAST_FP UNIQUE (FORECAST_KEY, FLOORPLAN_KEY)
        )
    """)
    print("FORECAST_FP_INDUCEMENT table created.")
else:
    print("FORECAST_FP_INDUCEMENT already exists — skipped.")

conn.commit()
conn.close()
print("Done.")
