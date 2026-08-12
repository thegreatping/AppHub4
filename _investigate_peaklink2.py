"""Investigate PeakLink deeper - lookup tables, Power Apps flow, related tables."""
import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

print("=" * 70)
print("1. SUGGESTION_TYPE LOOKUP TABLE?")
print("=" * 70)
# Check for lookup tables
lookups = conn.fetchall("""
    SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_NAME LIKE '%SUGGESTION%' OR TABLE_NAME LIKE '%PEAK%LINK%'
       OR TABLE_NAME LIKE '%IDEA%'
    ORDER BY TABLE_NAME
""")
print(f"\nTables matching SUGGESTION/PEAKLINK/IDEA ({len(lookups)}):")
for t in lookups:
    print(f"  {t[0]}")

print("\n" + "=" * 70)
print("2. CHECK APP_DROPDOWN / DROPDOWN TABLES")
print("=" * 70)
# Power Apps often stores dropdowns in a generic table
dd_tables = conn.fetchall("""
    SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_NAME LIKE '%DROPDOWN%' OR TABLE_NAME LIKE '%LOOKUP%'
       OR TABLE_NAME LIKE '%TYPE%'
    ORDER BY TABLE_NAME
""")
print(f"\nDropdown/Lookup tables ({len(dd_tables)}):")
for t in dd_tables:
    print(f"  {t[0]}")

# Check if there's a generic dropdown table with PeakLink entries
for tbl in dd_tables:
    try:
        sample = conn.fetchall(f"SELECT TOP 3 * FROM dbo.[{tbl[0]}]")
        if sample:
            cols = conn.fetchall(f"""
                SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME = '{tbl[0]}' ORDER BY ORDINAL_POSITION
            """)
            col_names = [c[0] for c in cols]
            # Check if any column has 'peak' or 'suggestion' or 'app' in values
            for s in sample:
                row_str = str(s).lower()
                if 'peak' in row_str or 'suggestion' in row_str or 'link' in row_str:
                    print(f"\n  → Found match in {tbl[0]}:")
                    print(f"    Columns: {col_names}")
                    # Get all rows related
                    all_rows = conn.fetchall(f"""
                        SELECT * FROM dbo.[{tbl[0]}]
                        WHERE CAST(({col_names[0]}) AS VARCHAR(MAX)) + ' ' + 
                              ISNULL(CAST(({col_names[1] if len(col_names) > 1 else col_names[0]}) AS VARCHAR(MAX)), '')
                              LIKE '%peak%' OR
                              CAST(({col_names[0]}) AS VARCHAR(MAX)) + ' ' +
                              ISNULL(CAST(({col_names[1] if len(col_names) > 1 else col_names[0]}) AS VARCHAR(MAX)), '')
                              LIKE '%suggestion%'
                    """)
                    for r in all_rows:
                        print(f"    {r}")
                    break
    except:
        pass

print("\n" + "=" * 70)
print("3. CHECK PROPERTY LOOKUP (PROPERTY_OR_LOCATION)")
print("=" * 70)
prop_tables = conn.fetchall("""
    SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_NAME LIKE '%PROPERTY%' OR TABLE_NAME LIKE '%LOCATION%'
    ORDER BY TABLE_NAME
""")
print(f"\nProperty/Location tables ({len(prop_tables)}):")
for t in prop_tables:
    print(f"  {t[0]}")

print("\n" + "=" * 70)
print("4. CHECK SPECIFIC DROPDOWN TABLE (APP_ID = 25)")
print("=" * 70)
# Many Power Apps use a central dropdown table keyed by App_ID
for tbl in dd_tables:
    try:
        cols = conn.fetchall(f"""
            SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = '{tbl[0]}' ORDER BY ORDINAL_POSITION
        """)
        col_names = [c[0] for c in cols]
        # Check if any column holds App_ID = 25
        for cn in col_names:
            if 'app' in cn.lower() or 'id' in cn.lower():
                try:
                    rows = conn.fetchall(f"""
                        SELECT * FROM dbo.[{tbl[0]}]
                        WHERE [{cn}] = 25
                    """)
                    if rows:
                        print(f"\n  → Found in {tbl[0]} where {cn}=25:")
                        print(f"    Columns: {col_names}")
                        for r in rows:
                            print(f"    {r}")
                except:
                    pass
    except:
        pass

print("\n" + "=" * 70)
print("5. ALL TABLES IN DB_APP_SUPPORT")
print("=" * 70)
all_tables = conn.fetchall("""
    SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_TYPE = 'BASE TABLE'
    ORDER BY TABLE_NAME
""")
print(f"\nAll tables ({len(all_tables)}):")
for t in all_tables:
    print(f"  {t[0]}")

conn.close()
