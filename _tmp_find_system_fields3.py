import sys, os, re
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection

env = load_env()

# Check SPs in WH_STAGING (Fabric warehouse) where the SPs likely live
try:
    conn2 = SafeConnection(env, "WH_STAGING", None, direct=True)
    cur = conn2.execute("""
        SELECT m.definition, o.name
        FROM sys.sql_modules m
        JOIN sys.objects o ON m.object_id = o.object_id
        WHERE m.definition LIKE '%PROPERTY_0%'
        AND o.type IN ('P','FN','IF','TF','V','TR')
        ORDER BY o.name
    """)
    rows = cur.fetchall()
    print(f"=== WH_STAGING SPs referencing PROPERTY_0: {len(rows)} ===\n")
    
    all_cols = set()
    for definition, name in rows:
        if not definition:
            continue
        segments = re.split(r'UPDATE\s+(?:\w+\.)*(?:\[?dbo\]?\.)?(?:\[?)?\s*PROPERTY_0', definition, flags=re.IGNORECASE)
        sp_cols = set()
        for seg in segments[1:]:
            set_match = re.search(r'SET\s+(.*?)(?:\bWHERE\b|\bFROM\b|;\s*\n|\bUPDATE\b|\bINSERT\b|\bDELETE\b|\bEXEC\b)', seg, re.IGNORECASE | re.DOTALL)
            if set_match:
                cols = re.findall(r'\b(?:p\.|t\.|src\.)?\[?([A-Z][A-Z_0-9]+)\]?\s*=', set_match.group(1), re.IGNORECASE)
                for c in cols:
                    cu = c.upper()
                    if cu not in ('NULL','CASE','WHEN','THEN','ELSE','END','AND','OR','NOT','SELECT','FROM','SET','IS','GETDATE','ISNULL','COALESCE','CAST','CONVERT','LEFT','RIGHT','UPPER','LOWER','TRIM','LEN','REPLACE'):
                        sp_cols.add(cu)
                        all_cols.add(cu)
        if sp_cols:
            print(f"  {name}:")
            for c in sorted(sp_cols):
                print(f"    -> {c}")
            print()
    
    print(f"\nTOTAL from WH_STAGING SPs: {len(all_cols)}")
    for c in sorted(all_cols):
        print(f"  {c}")
    conn2.close()
except Exception as e:
    print(f"WH_STAGING error: {e}")

# Also check the local SP .sql files
print("\n\n=== Local .sql SP files ===")
sp_dir = r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\APPHUB_4"
workspace = r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files"
local_cols = set()
for root, dirs, files in os.walk(workspace):
    dirs[:] = [d for d in dirs if d not in ('.venv', 'node_modules', '__pycache__', '.git')]
    for fname in files:
        if fname.endswith('.sql'):
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                if 'PROPERTY_0' in content.upper() and 'UPDATE' in content.upper():
                    segments = re.split(r'UPDATE\s+(?:\w+\.)*(?:\[?dbo\]?\.)?(?:\[?)?\s*PROPERTY_0', content, flags=re.IGNORECASE)
                    file_cols = set()
                    for seg in segments[1:]:
                        set_match = re.search(r'SET\s+(.*?)(?:\bWHERE\b|\bFROM\b|;\s*$|\bUPDATE\b|\bINSERT\b)', seg, re.IGNORECASE | re.DOTALL)
                        if set_match:
                            cols = re.findall(r'\[?([A-Z][A-Z_0-9]+)\]?\s*=', set_match.group(1), re.IGNORECASE)
                            for c in cols:
                                cu = c.upper()
                                if cu not in ('NULL','CASE','WHEN','THEN','ELSE','END','AND','OR','NOT','SELECT','FROM','SET'):
                                    file_cols.add(cu)
                                    local_cols.add(cu)
                    if file_cols:
                        rel = os.path.relpath(fpath, workspace)
                        print(f"  {rel}:")
                        for c in sorted(file_cols):
                            print(f"    -> {c}")
                        print()
            except:
                pass

if local_cols:
    print(f"\nTOTAL from local .sql files: {len(local_cols)}")
    for c in sorted(local_cols):
        print(f"  {c}")
