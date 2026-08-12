import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

# Run the projection logic directly (bypass Wednesday guard)
sql = """
DECLARE @LastWeekDateKey INT;
DECLARE @ThisWeekDateKey INT;

SELECT @LastWeekDateKey = DATE_KEY FROM [dbo].[WEEKS] WHERE RELATIVE_WEEK = -1;
SELECT @ThisWeekDateKey = DATE_KEY FROM [dbo].[WEEKS] WHERE RELATIVE_WEEK = 0;

-- Idempotency DELETE
DELETE FROM [dbo].[COMP_ASSIGNMENTS]
WHERE DATE_KEY = @ThisWeekDateKey
  AND PARENT_COMP_KEY IN (
        SELECT PARENT_COMP_KEY
        FROM   [dbo].[COMP_ASSIGNMENTS]
        WHERE  DATE_KEY = @LastWeekDateKey
  );

-- INSERT cloned rows
INSERT INTO [dbo].[COMP_ASSIGNMENTS]
(
    PARENT_COMP_KEY, DATE_KEY, COMP_PROPERTY_KEY, COMP_PROPERTY_NAME,
    COMPID, ENDCOMPDATE, FLAG_COMP, FLAG_PARENT, FLAG_PARENT_1,
    MARKET_KEY, MARKET_CITY, MARKET_CITY_STATE, MARKET_STATE,
    MARKETCOMPMAPID, MODIFIEDBY, MODIFIEDDATE,
    PARENT_PROPERTY_KEY, PARENT_PROPERTY_NAME, RANK_ORDER,
    STARTCOMPDATE, SUBJECTID
)
SELECT
    ca.PARENT_COMP_KEY, @ThisWeekDateKey, ca.COMP_PROPERTY_KEY, ca.COMP_PROPERTY_NAME,
    ca.COMPID, ca.ENDCOMPDATE, ca.FLAG_COMP, ca.FLAG_PARENT, ca.FLAG_PARENT_1,
    ca.MARKET_KEY, ca.MARKET_CITY, ca.MARKET_CITY_STATE, ca.MARKET_STATE,
    ca.MARKETCOMPMAPID, 'SYSTEM', ca.MODIFIEDDATE,
    ca.PARENT_PROPERTY_KEY, ca.PARENT_PROPERTY_NAME, ca.RANK_ORDER,
    ca.STARTCOMPDATE, ca.SUBJECTID
FROM [dbo].[COMP_ASSIGNMENTS] ca
WHERE ca.DATE_KEY = @LastWeekDateKey;
"""

conn.execute(sql)
conn.commit()

# Verify
r = conn.execute("SELECT COUNT(*) FROM dbo.COMP_ASSIGNMENTS WHERE DATE_KEY = (SELECT DATE_KEY FROM dbo.WEEKS WHERE RELATIVE_WEEK = 0)").fetchone()
print(f"COMP_ASSIGNMENTS rows for this week (20260726): {r[0]}")
r2 = conn.execute("SELECT COUNT(DISTINCT PARENT_PROPERTY_KEY) FROM dbo.COMP_ASSIGNMENTS WHERE DATE_KEY = (SELECT DATE_KEY FROM dbo.WEEKS WHERE RELATIVE_WEEK = 0)").fetchone()
print(f"Distinct parent properties: {r2[0]}")
