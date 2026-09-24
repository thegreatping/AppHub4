"""Full schema for Pitch Workflow tables."""
import sys
sys.path.insert(0, ".")
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

for tbl in ["THE_PITCH", "WorkflowAssignment", "WorkflowEvent"]:
    print(f"\n=== {tbl} columns ===")
    rows = conn.fetchall(f"""
        SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, IS_NULLABLE
        FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='{tbl}' ORDER BY ORDINAL_POSITION
    """)
    for r in rows:
        print(f"  {r[0]:40s} {r[1]:20s} len={r[2]}  null={r[3]}")
    cnt = conn.fetchall(f"SELECT COUNT(*) FROM dbo.[{tbl}]")[0][0]
    print(f"  --> {cnt} rows")

print("\n=== Sample THE_PITCH rows ===")
rows = conn.fetchall("SELECT TOP 5 * FROM dbo.THE_PITCH ORDER BY 1 DESC")
cols = [r[0] for r in conn.fetchall("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='THE_PITCH' ORDER BY ORDINAL_POSITION")]
for row in rows:
    for i, v in enumerate(row):
        if v is not None and str(v).strip():
            print(f"  {cols[i]}: {v}")
    print()

print("\n=== Distinct PITCH_STATUS ===")
for r in conn.fetchall("SELECT DISTINCT PITCH_STATUS, COUNT(*) cnt FROM dbo.THE_PITCH GROUP BY PITCH_STATUS ORDER BY 1"):
    print(f"  {r[0]}: {r[1]}")

print("\n=== Distinct PITCH_CATEGORY ===")
for r in conn.fetchall("SELECT DISTINCT PITCH_CATEGORY FROM dbo.THE_PITCH WHERE PITCH_CATEGORY IS NOT NULL ORDER BY 1"):
    print(f"  {r[0]}")

print("\n=== Sample WorkflowEvent ===")
rows = conn.fetchall("SELECT TOP 5 * FROM dbo.WorkflowEvent ORDER BY 1 DESC")
cols2 = [r[0] for r in conn.fetchall("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='WorkflowEvent' ORDER BY ORDINAL_POSITION")]
for row in rows:
    for i, v in enumerate(row):
        print(f"  {cols2[i]}: {v}")
    print()
