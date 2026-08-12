"""Investigate the PEAKLINK module thoroughly."""
import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection

env = load_env()

print("=" * 70)
print("1. PEAKLINK TABLE SCHEMA")
print("=" * 70)
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

# Get columns
rows = conn.fetchall("""
    SELECT c.COLUMN_NAME, c.DATA_TYPE, c.CHARACTER_MAXIMUM_LENGTH,
           c.IS_NULLABLE, c.COLUMN_DEFAULT
    FROM INFORMATION_SCHEMA.COLUMNS c
    WHERE c.TABLE_NAME = 'PEAKLINK' AND c.TABLE_SCHEMA = 'dbo'
    ORDER BY c.ORDINAL_POSITION
""")
print(f"\nColumns ({len(rows)}):")
for r in rows:
    print(f"  {r[0]:30s} {r[1]:15s} len={r[2]!s:6s} null={r[3]:3s} default={r[4]}")

print("\n" + "=" * 70)
print("2. ROW COUNT + SAMPLE DATA")
print("=" * 70)
count = conn.fetchall("SELECT COUNT(*) FROM dbo.PEAKLINK")
print(f"\nTotal rows: {count[0][0]}")

sample = conn.fetchall("SELECT TOP 5 * FROM dbo.PEAKLINK ORDER BY 1 DESC")
if sample:
    # Get column names for display
    cols = [r[0] for r in rows]
    print(f"\nTop 5 rows (by first column desc):")
    print(f"  Columns: {cols}")
    for s in sample:
        print(f"  {s}")

print("\n" + "=" * 70)
print("3. INDEXES AND CONSTRAINTS")
print("=" * 70)
idx = conn.fetchall("""
    SELECT i.name, i.type_desc, i.is_unique, i.is_primary_key,
           STRING_AGG(c.name, ', ') WITHIN GROUP (ORDER BY ic.key_ordinal)
    FROM sys.indexes i
    JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
    JOIN sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id
    WHERE i.object_id = OBJECT_ID('dbo.PEAKLINK')
    GROUP BY i.name, i.type_desc, i.is_unique, i.is_primary_key
""")
for r in idx:
    print(f"  {r[0]:40s} type={r[1]:15s} unique={r[2]} pk={r[3]} cols=({r[4]})")

print("\n" + "=" * 70)
print("4. RELATED STORED PROCEDURES")
print("=" * 70)
sps = conn.fetchall("""
    SELECT DISTINCT o.name, o.type_desc
    FROM sys.sql_modules m
    JOIN sys.objects o ON m.object_id = o.object_id
    WHERE m.definition LIKE '%PEAKLINK%'
    ORDER BY o.name
""")
print(f"\nObjects referencing PEAKLINK ({len(sps)}):")
for s in sps:
    print(f"  {s[0]:40s} ({s[1]})")

print("\n" + "=" * 70)
print("5. TRIGGERS ON PEAKLINK TABLE")
print("=" * 70)
triggers = conn.fetchall("""
    SELECT t.name, t.type_desc, te.type_desc as event_type
    FROM sys.triggers t
    JOIN sys.trigger_events te ON t.object_id = te.object_id
    WHERE t.parent_id = OBJECT_ID('dbo.PEAKLINK')
""")
if triggers:
    for t in triggers:
        print(f"  {t[0]:30s} {t[1]:15s} event={t[2]}")
else:
    print("  (none)")

print("\n" + "=" * 70)
print("6. APP_LIST ENTRY FOR APP_ID 25")
print("=" * 70)
app_entry = conn.fetchall("""
    SELECT * FROM dbo.APP_LIST WHERE App_ID = 25
""")
if app_entry:
    app_cols = conn.fetchall("""
        SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = 'APP_LIST' ORDER BY ORDINAL_POSITION
    """)
    col_names = [c[0] for c in app_cols]
    for i, val in enumerate(app_entry[0]):
        print(f"  {col_names[i]:25s} = {val}")

print("\n" + "=" * 70)
print("7. DISTINCT STATUS/CATEGORY VALUES")
print("=" * 70)
# Try to find status-like columns
for col in [r[0] for r in rows]:
    if any(kw in col.upper() for kw in ['STATUS', 'TYPE', 'CATEGORY', 'FLAG', 'ACTIVE']):
        vals = conn.fetchall(f"SELECT DISTINCT [{col}], COUNT(*) FROM dbo.PEAKLINK GROUP BY [{col}] ORDER BY 2 DESC")
        print(f"\n  {col}:")
        for v in vals:
            print(f"    {v[0]!s:30s} count={v[1]}")

conn.close()
