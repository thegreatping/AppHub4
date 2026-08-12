"""DDL setup for Rent Forecasting 2.0 — run ONCE."""
import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

# 1. Add FLAG_ARCHIVED to FORECAST_FORECASTS (check first)
cur = conn.execute("""
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA='dbo' AND TABLE_NAME='FORECAST_FORECASTS' AND COLUMN_NAME='FLAG_ARCHIVED'
""")
if cur.fetchone()[0] == 0:
    conn.execute("ALTER TABLE dbo.FORECAST_FORECASTS ADD FLAG_ARCHIVED BIT NOT NULL DEFAULT 0")
    print("FLAG_ARCHIVED added to FORECAST_FORECASTS")
else:
    print("FLAG_ARCHIVED already exists — skipped")

# 2. Insert Rent Forecasting 2.0 into APP_LIST (let identity assign ID)
cur = conn.execute("SELECT App_ID FROM dbo.APP_LIST WHERE App_Name = 'Rent Forecasting 2.0'")
row = cur.fetchone()
if row is None:
    cur = conn.execute("""
        INSERT INTO dbo.APP_LIST (App_Name, App_Level, App_Security_Level, Flag_Active)
        OUTPUT INSERTED.App_ID
        VALUES ('Rent Forecasting 2.0', 1, 50, 1)
    """)
    new_id = cur.fetchone()[0]
    print(f"Rent Forecasting 2.0 inserted into APP_LIST — App_ID={new_id}")
else:
    new_id = row[0]
    print(f"Rent Forecasting 2.0 already exists in APP_LIST — App_ID={new_id}")

conn.commit()
conn.close()
print("\nDDL setup complete.")
