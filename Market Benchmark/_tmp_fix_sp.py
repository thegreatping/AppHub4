import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

sql = """
ALTER PROCEDURE [dbo].[MS_Comp_Assignment_Projector_SP]
AS
/*
============================================================================
MS_Comp_Assignment_Projector_SP
============================================================================
PURPOSE:
    Runs on Wednesday morning (Central time).
    Clones the most recently completed week's (RELATIVE_WEEK = -1) comp
    assignments into the current week (RELATIVE_WEEK = 0) by swapping the
    DATE_KEY.

Changes (2026-07-24):
    - Removed BEGIN TRY/CATCH (Fabric silent rollback issue).
============================================================================
*/
BEGIN

    SET NOCOUNT ON;

    -- Day-of-week guard: Wednesday only (Central time)
    IF DATENAME(WEEKDAY, SYSDATETIMEOFFSET() AT TIME ZONE 'Central Standard Time') <> 'Wednesday'
    BEGIN
        PRINT 'MS_Comp_Assignment_Projector_SP: skipped (not Wednesday Central)';
        RETURN;
    END;

    -- STEP 1: Resolve date keys
    DECLARE @LastWeekDateKey INT;
    DECLARE @ThisWeekDateKey INT;

    SELECT @LastWeekDateKey = DATE_KEY FROM [dbo].[WEEKS] WHERE RELATIVE_WEEK = -1;
    SELECT @ThisWeekDateKey = DATE_KEY FROM [dbo].[WEEKS] WHERE RELATIVE_WEEK = 0;

    IF @LastWeekDateKey IS NULL OR @ThisWeekDateKey IS NULL
    BEGIN
        RAISERROR('Could not determine last or current week DATE_KEY from WEEKS table.', 16, 1);
        RETURN;
    END;

    -- STEP 2: Idempotency DELETE
    DELETE FROM [dbo].[COMP_ASSIGNMENTS]
    WHERE DATE_KEY = @ThisWeekDateKey
      AND PARENT_COMP_KEY IN (
            SELECT PARENT_COMP_KEY
            FROM   [dbo].[COMP_ASSIGNMENTS]
            WHERE  DATE_KEY = @LastWeekDateKey
      );

    -- STEP 3: INSERT cloned rows with this week's DATE_KEY
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

END;
"""

conn.execute(sql)
conn.commit()
print("SP altered successfully — BEGIN TRY/CATCH removed.")
