import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

conn.execute("""
IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'MINDSET_AWARD_NOMINATION')
CREATE TABLE dbo.MINDSET_AWARD_NOMINATION (
    ID INT IDENTITY(1,1) PRIMARY KEY,
    NOMINEE_NAME NVARCHAR(200),
    NOMINEE_POSITION NVARCHAR(200),
    NOMINEE_PROPERTY NVARCHAR(200),
    MINDSET_VALUE NVARCHAR(100),
    NOMINATION_REASON NVARCHAR(MAX),
    NOMINATED_BY NVARCHAR(200),
    DATE_CREATED DATETIME DEFAULT GETDATE(),
    PROD_VERSION NVARCHAR(50)
)
""")
print("Table created (or already exists).")
