"""Check the modules.py entry for PeakLink and search for Power Automate flows."""
import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

print("=" * 70)
print("1. APP_LOCATION_LIST - CORPORATE + NON-PROPERTY LOCATIONS")
print("=" * 70)
corp_locs = conn.fetchall("""
    SELECT PROPERTY_KEY, PROPERTY_NAME, LOCATION_GROUP, FLAG_CORPORATE_LOCATION, FLAG_NON_PROPERTY
    FROM dbo.APP_LOCATION_LIST
    WHERE FLAG_CORPORATE_LOCATION = 1 OR FLAG_NON_PROPERTY = 1
    ORDER BY PROPERTY_NAME
""")
print(f"\nCorporate/Non-Property locations ({len(corp_locs)}):")
for r in corp_locs:
    print(f"  {r[0]:6d} {r[1]:35s} corp={r[3]} non_prop={r[4]}")

print("\n" + "=" * 70)
print("2. SUGGESTION_TYPE_ID VALUES — Any reference in other tables?")
print("=" * 70)
# Search all columns named *TYPE* or *SUGGESTION* across all tables
type_cols = conn.fetchall("""
    SELECT TABLE_NAME, COLUMN_NAME
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE COLUMN_NAME LIKE '%SUGGESTION%'
    ORDER BY TABLE_NAME
""")
print(f"\nColumns with 'SUGGESTION' in name ({len(type_cols)}):")
for t in type_cols:
    print(f"  {t[0]:30s}.{t[1]}")

print("\n" + "=" * 70)
print("3. CHECK IF PEAKLINK HAS EVER HAD DATA (max ID)")
print("=" * 70)
max_id = conn.fetchall("SELECT MAX(ID) FROM dbo.PEAKLINK")
print(f"  MAX(ID): {max_id[0][0]}")

print("\n" + "=" * 70)
print("4. COLUMN DETAILS FOR PEAKLINK - DATE_MODIFIED format")
print("=" * 70)
# DATE_MODIFIED is an INT - likely YYYYMMDD format
# EMPLOYEE_CODE is varchar(10) - standard PeakMade employee code
# SUGGESTION_TYPE_ID is INT - references something (maybe hardcoded in Power App)
# Up to 3 document attachments (varbinary max)
print("""
Based on schema analysis:
- ID: int, PK, no identity (manually generated, probably MAX(ID)+1)
- DATE_MODIFIED: int (likely YYYYMMDD format)
- DOCUMENT_1/2/3: varbinary(max) — file attachments stored as binary
- DOCUMENT_NAME_1/2/3: varchar(255) — original filenames
- EMPLOYEE_CODE: varchar(10) — submitter's employee code
- EMPLOYEE_NAME_FULL: varchar(255) — submitter's full name
- MODIFIED_BY: varchar(10) — last editor's employee code
- PROPERTY_OR_LOCATION: varchar(255) — text name of property/location
- PROPERTY_OR_LOCATION_ID: int — FK to APP_LOCATION_LIST.PROPERTY_KEY
- SUGGESTION_DETAILS: varchar(2048) — free text description of the idea
- SUGGESTION_TYPE: varchar(255) — text name of suggestion category
- SUGGESTION_TYPE_ID: int — numeric ID for the type (hardcoded categories?)
""")

print("\n" + "=" * 70)
print("5. CHECK MODULE_AUDIENCE GRANTS FOR APP_ID 25")
print("=" * 70)
grants = conn.fetchall("""
    SELECT GRANT_TYPE, GRANT_VALUE, ACCESS_LEVEL, COUNT(*) as cnt
    FROM dbo.MODULE_AUDIENCE
    WHERE MODULE_ID = 25
    GROUP BY GRANT_TYPE, GRANT_VALUE, ACCESS_LEVEL
    ORDER BY GRANT_TYPE, GRANT_VALUE
""")
print(f"\nAudience grants for PeakLink ({len(grants)}):")
for g in grants:
    print(f"  {g[0]:15s} {g[1]:35s} access={g[2]:10s} count={g[3]}")

conn.close()
