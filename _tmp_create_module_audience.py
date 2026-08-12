import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'Help Ticket Triage', 'bi-triage-agent', 'scripts'))
from helpers import SafeConnection, load_env

env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

# Check if table exists
rows = conn.fetchall("""
    SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES 
    WHERE TABLE_NAME = 'MODULE_AUDIENCE'
""")
if rows:
    print("MODULE_AUDIENCE already exists")
else:
    print("Creating MODULE_AUDIENCE table...")
    conn.execute("""
        CREATE TABLE dbo.MODULE_AUDIENCE (
            ID BIGINT IDENTITY NOT NULL,
            MODULE_ID INT NOT NULL,
            GRANT_TYPE VARCHAR(50) NOT NULL,
            GRANT_VALUE VARCHAR(200) NOT NULL,
            ACCESS_LEVEL VARCHAR(20) NOT NULL,
            CREATED_DATE DATETIME2(6) NULL
        )
    """)
    # Insert a wildcard grant so everyone can access all modules in dev
    conn.execute("""
        INSERT INTO dbo.MODULE_AUDIENCE (MODULE_ID, GRANT_TYPE, GRANT_VALUE, ACCESS_LEVEL)
        VALUES (0, 'title_group', '*', 'user')
    """)
    # Add developer access for Craig
    conn.execute("""
        INSERT INTO dbo.MODULE_AUDIENCE (MODULE_ID, GRANT_TYPE, GRANT_VALUE, ACCESS_LEVEL)
        VALUES (0, 'developer', 'cpell@peakmade.com', 'developer')
    """)
    print("Created and seeded MODULE_AUDIENCE")

conn.close()
