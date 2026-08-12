"""Create dbo.APPHUB_USAGE_LOG in DB_APP_SUPPORT."""
import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

# Check if table already exists
cur = conn.execute("""
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = 'APPHUB_USAGE_LOG'
""")
exists = cur.fetchone()[0] > 0

if exists:
    print("Table dbo.APPHUB_USAGE_LOG already exists — nothing to do.")
else:
    conn.execute("""
        CREATE TABLE dbo.APPHUB_USAGE_LOG (
            log_id      INT            IDENTITY(1,1) NOT NULL,
            logged_at   DATETIME2      NOT NULL DEFAULT GETUTCDATE(),
            user_email  NVARCHAR(255)  NULL,
            user_name   NVARCHAR(255)  NULL,
            module_id   NVARCHAR(100)  NULL,
            route       NVARCHAR(500)  NULL,
            http_method NVARCHAR(10)   NULL,
            status_code INT            NULL,
            CONSTRAINT PK_APPHUB_USAGE_LOG PRIMARY KEY (log_id)
        )
    """)
    print("OK — dbo.APPHUB_USAGE_LOG created.")

# Verify
cur = conn.execute("""
    SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, COLUMN_DEFAULT
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = 'APPHUB_USAGE_LOG'
    ORDER BY ORDINAL_POSITION
""")
print("\nColumns:")
for r in cur.fetchall():
    default = f"  DEFAULT {r[3]}" if r[3] else ""
    length  = f"({r[2]})" if r[2] else ""
    print(f"  {r[0]:20s}  {r[1]}{length}{default}")
