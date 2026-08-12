import sys, re
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection

env = load_env()
conn = SafeConnection(env, "WH_STAGING", None, direct=True)

cur = conn.execute("""
    SELECT m.definition, o.name
    FROM sys.sql_modules m
    JOIN sys.objects o ON m.object_id = o.object_id
    WHERE m.definition LIKE '%PROPERTY_0%'
    AND o.type IN ('P','FN','IF','TF','V','TR')
    ORDER BY o.name
""")
rows = cur.fetchall()

all_cols = set()
for definition, name in rows:
    if not definition or 'UPDATE' not in definition.upper():
        continue
    # More flexible: find all UPDATE statements, then look for SET blocks
    # Handle both "UPDATE dbo.PROPERTY_0" and "UPDATE p SET" with FROM PROPERTY_0
    
    # Method 1: Direct UPDATE dbo.PROPERTY_0 SET
    for m in re.finditer(r'UPDATE\s+(?:\[?dbo\]?\.)?\[?PROPERTY_0\]?\s+SET\s+(.*?)(?:\bWHERE\b|\bFROM\b|\bGO\b|$)', definition, re.IGNORECASE | re.DOTALL):
        cols = re.findall(r'\b([A-Z_][A-Z_0-9]+)\b\s*=', m.group(1))
        for c in cols:
            if c.upper() not in ('NULL','CASE','WHEN','THEN','ELSE','END','AND','OR','NOT','SELECT','FROM','SET','IS','GETDATE','ISNULL','COALESCE','CAST','CONVERT','LEFT','RIGHT','UPPER','LOWER','TRIM','LEN','REPLACE','DATEADD','DATEDIFF','CONCAT','STUFF','IIF','CHARINDEX','SUBSTRING'):
                all_cols.add(c.upper())
    
    # Method 2: UPDATE alias SET ... FROM PROPERTY_0
    for m in re.finditer(r'UPDATE\s+(\w+)\s+SET\s+(.*?)\bFROM\b.*?PROPERTY_0', definition, re.IGNORECASE | re.DOTALL):
        cols = re.findall(r'\b([A-Z_][A-Z_0-9]+)\b\s*=', m.group(2))
        for c in cols:
            if c.upper() not in ('NULL','CASE','WHEN','THEN','ELSE','END','AND','OR','NOT','SELECT','FROM','SET','IS','GETDATE','ISNULL','COALESCE','CAST','CONVERT','LEFT','RIGHT','UPPER','LOWER','TRIM','LEN','REPLACE','DATEADD','DATEDIFF','CONCAT','STUFF','IIF','CHARINDEX','SUBSTRING'):
                all_cols.add(c.upper())

# Also combine with the NB_PROPERTY_0_COMBO columns we already found
nb_cols = {
    'ACCOUNTANT','ACCOUNTING_MGR','AM_EMAIL','AM_EMP_CODE','AM_NAME',
    'BED_COUNT_CUSTOM','CONTROLLER','DATE_LAST_UPDATED',
    'EXEC_DIR_EMAIL','EXEC_DIR_EMP_CODE','EXEC_DIR_NAME',
    'LEGACY_ENTRATA_ID','LEGACY_SUBPROPERTY_ID_ENTRATA',
    'LIST_MANAGED','LIST_STATUS','LIST_TRANSITIONTYPE','LIST_TYPE',
    'LM_EMAIL','LM_EMP_CODE','LM_NAME',
    'MAINT_SUPV_EMAIL','MAINT_SUPV_EMP_CODE','MAINT_SUPV_NAME',
    'PM_EMAIL','PM_EMP_CODE','PM_NAME',
    'PROPERTY_LIST_CODE','RAM_NAME',
    'RESIDENT_DIR_EMAIL','RESIDENT_DIR_EMP_CODE','RESIDENT_DIR_NAME',
    'RMLS_NAME','RM_NAME','RVP_NAME','SOURCE_SYSTEM',
}

all_cols.update(nb_cols)

print(f"TOTAL SYSTEM-UPDATED COLUMNS: {len(all_cols)}")
print("=" * 60)
for c in sorted(all_cols):
    print(f"  {c}")

conn.close()
