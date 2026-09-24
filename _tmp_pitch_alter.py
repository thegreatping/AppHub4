"""Add missing columns to THE_PITCH for the native rebuild."""
import sys
sys.path.insert(0, ".")
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

alterations = [
    "ALTER TABLE dbo.THE_PITCH ADD PITCH_TITLE     varchar(255)  NULL",
    "ALTER TABLE dbo.THE_PITCH ADD PITCH_CATEGORY  varchar(100)  NULL",
    "ALTER TABLE dbo.THE_PITCH ADD PITCH_STATUS    varchar(50)   NULL DEFAULT 'Submitted'",
    "ALTER TABLE dbo.THE_PITCH ADD REVIEW_COMMENTS varchar(2500) NULL",
    "ALTER TABLE dbo.THE_PITCH ADD REVIEWED_BY     varchar(255)  NULL",
    "ALTER TABLE dbo.THE_PITCH ADD DATE_MODIFIED   int           NULL",
    "ALTER TABLE dbo.THE_PITCH ADD MODIFIED_BY     varchar(255)  NULL",
]

for sql in alterations:
    conn.execute(sql)
    col = sql.split("ADD ")[1].split(" ")[0]
    print(f"  Added: {col}")

print("\nAlterations complete.")

# Confirm
cols = conn.fetchall("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='THE_PITCH' ORDER BY ORDINAL_POSITION")
print("\nFinal column list:")
for c in cols: print(f"  {c[0]}")
