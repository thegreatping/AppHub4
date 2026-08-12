"""
Create MODULE_AUDIENCE table in DB_App_Support and populate it from the current
security model (APP_LIST security levels + APP_ADMINS + EMPLOYEE_F title groups).

Resolution order:
1. individual grants (exact email)
2. title_group grants (exact match)
3. title_prefix grants (starts-with match)
4. baseline (no match → minimal access + alert)
"""
import sys
sys.path.insert(0, r"C:\Users\cpell\OneDrive - PeakMade Real Estate\VS_Code_Files\Help Ticket Triage\bi-triage-agent\scripts")
from helpers import load_env, SafeConnection, setup_logger

env = load_env()
log = setup_logger("security_migration")

dbas = SafeConnection(env, "DB_APP_SUPPORT", log, direct=True)
stg = SafeConnection(env, "WH_STAGING", log)

# ============================================================
# STEP 1: Create MODULE_AUDIENCE table
# ============================================================
print("=" * 60)
print("STEP 1: Creating MODULE_AUDIENCE table")
print("=" * 60)

dbas.execute("""
IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'MODULE_AUDIENCE')
BEGIN
    CREATE TABLE dbo.MODULE_AUDIENCE (
        ID INT IDENTITY(1,1) PRIMARY KEY,
        MODULE_ID INT NOT NULL,          -- FK to APP_LIST.App_ID; 0 = global/all modules
        GRANT_TYPE VARCHAR(20) NOT NULL,  -- 'title_group', 'title_prefix', 'individual', 'developer'
        GRANT_VALUE VARCHAR(200) NOT NULL,-- title group name, prefix, or email
        ACCESS_LEVEL VARCHAR(10) NOT NULL,-- 'user', 'admin', 'developer'
        DATE_CREATED DATETIME DEFAULT GETDATE(),
        CREATED_BY VARCHAR(100) DEFAULT 'migration_script'
    );
    PRINT 'Table MODULE_AUDIENCE created.';
END
ELSE
    PRINT 'Table MODULE_AUDIENCE already exists.';
""")
print("  Done.")

# ============================================================
# STEP 2: Get current APP_LIST + security levels
# ============================================================
print("\n" + "=" * 60)
print("STEP 2: Reading current APP_LIST and EMPLOYEE_F title groups")
print("=" * 60)

app_list = dbas.fetchall("""
    SELECT App_ID, App_Name, App_Security_Level
    FROM dbo.APP_LIST
    WHERE Flag_Active = 1
    ORDER BY App_ID
""")
print(f"  Active modules: {len(app_list)}")

# Get distinct title groups with their security levels from EMPLOYEE_F
title_groups = stg.fetchall("""
    SELECT DISTINCT TITLE_GROUP, TITLE_GROUP_SECURITY_LEVEL
    FROM dbo.EMPLOYEE_F
    WHERE FLAG_ACTIVE = 1
      AND TITLE_GROUP IS NOT NULL
      AND TITLE_GROUP NOT IN ('--', '_UNASSIGNED', '')
    ORDER BY TITLE_GROUP
""")
print(f"  Active title groups: {len(title_groups)}")

# Get current APP_ADMINS
admins = dbas.fetchall("""
    SELECT APP_ID, ADMIN_EMAIL
    FROM dbo.APP_ADMINS
    ORDER BY APP_ID, ADMIN_EMAIL
""")
print(f"  Current admin assignments: {len(admins)}")

# ============================================================
# STEP 3: Clear existing data and populate
# ============================================================
print("\n" + "=" * 60)
print("STEP 3: Populating MODULE_AUDIENCE")
print("=" * 60)

# Clear any existing data
dbas.execute("DELETE FROM dbo.MODULE_AUDIENCE")
print("  Cleared existing rows.")

insert_count = 0

# --- 3a: Title group grants (exact match) ---
# For each module, grant access to title groups whose security level meets the threshold
for app in app_list:
    app_id, app_name, app_sec_level = app[0], app[1], app[2]
    for tg in title_groups:
        tg_name, tg_sec_level = tg[0], tg[1]
        if tg_sec_level is not None and tg_sec_level >= app_sec_level:
            dbas.execute("""
                INSERT INTO dbo.MODULE_AUDIENCE (MODULE_ID, GRANT_TYPE, GRANT_VALUE, ACCESS_LEVEL, CREATED_BY)
                VALUES (?, 'title_group', ?, 'user', 'migration_script')
            """, (app_id, tg_name))
            insert_count += 1

print(f"  Title group grants: {insert_count}")

# --- 3b: Title prefix grants ---
# Add broad prefix grants for the main clusters
prefixes = {
    'PROPERTY': [],      # Will be matched by title_group already, but prefix ensures future groups work
    'CORPORATE': [],
    'REGIONAL': [],
    'MARKETING': [],
    'UC ': [],           # UC ASSOCIATE, UC MANAGER
}

# Determine which modules each prefix should access
# Use the median security level for each prefix group
prefix_levels = {}
for tg in title_groups:
    tg_name, tg_sec_level = tg[0], tg[1] or 0
    for prefix in prefixes:
        if tg_name.startswith(prefix):
            if prefix not in prefix_levels:
                prefix_levels[prefix] = []
            prefix_levels[prefix].append(tg_sec_level)

# For each prefix, use the MINIMUM security level of its members as the threshold
prefix_min_level = {}
for prefix, levels in prefix_levels.items():
    if levels:
        prefix_min_level[prefix] = min(levels)

prefix_count = 0
for app in app_list:
    app_id, app_name, app_sec_level = app[0], app[1], app[2]
    for prefix, min_level in prefix_min_level.items():
        if min_level >= app_sec_level:
            dbas.execute("""
                INSERT INTO dbo.MODULE_AUDIENCE (MODULE_ID, GRANT_TYPE, GRANT_VALUE, ACCESS_LEVEL, CREATED_BY)
                VALUES (?, 'title_prefix', ?, 'user', 'migration_script')
            """, (app_id, prefix))
            prefix_count += 1

print(f"  Title prefix grants: {prefix_count}")

# --- 3c: Individual admin grants (from APP_ADMINS) ---
admin_count = 0
for admin in admins:
    app_id, email = admin[0], admin[1]
    if email:
        dbas.execute("""
            INSERT INTO dbo.MODULE_AUDIENCE (MODULE_ID, GRANT_TYPE, GRANT_VALUE, ACCESS_LEVEL, CREATED_BY)
            VALUES (?, 'individual', ?, 'admin', 'migration_script')
        """, (app_id, email.strip().lower()))
        admin_count += 1

print(f"  Individual admin grants: {admin_count}")

# --- 3d: Developer grants ---
developers = ['cpell@peakmade.com']
for dev_email in developers:
    dbas.execute("""
        INSERT INTO dbo.MODULE_AUDIENCE (MODULE_ID, GRANT_TYPE, GRANT_VALUE, ACCESS_LEVEL, CREATED_BY)
        VALUES (0, 'developer', ?, 'developer', 'migration_script')
    """, (dev_email,))

print(f"  Developer grants: {len(developers)}")

# --- 3e: Baseline modules (everyone gets these regardless of title group) ---
# Market Benchmark (level 30) and potentially others that should be universal
baseline_modules = [15]  # Market Benchmark - currently level 30, nearly everyone has it
for mod_id in baseline_modules:
    dbas.execute("""
        INSERT INTO dbo.MODULE_AUDIENCE (MODULE_ID, GRANT_TYPE, GRANT_VALUE, ACCESS_LEVEL, CREATED_BY)
        VALUES (?, 'title_prefix', '*', 'user', 'migration_script')
    """, (mod_id,))

print(f"  Baseline (universal) grants: {len(baseline_modules)}")

# ============================================================
# STEP 4: Summary
# ============================================================
print("\n" + "=" * 60)
print("STEP 4: Summary")
print("=" * 60)

total = dbas.fetchall("SELECT GRANT_TYPE, COUNT(*) FROM dbo.MODULE_AUDIENCE GROUP BY GRANT_TYPE ORDER BY GRANT_TYPE")
for r in total:
    print(f"  {r[0]:<15s}: {r[1]} rows")

grand_total = dbas.fetchall("SELECT COUNT(*) FROM dbo.MODULE_AUDIENCE")
print(f"\n  TOTAL: {grand_total[0][0]} rows")

# Quick sanity check: what does Craig Pell see?
print("\n" + "=" * 60)
print("SANITY CHECK: Craig Pell (CORPORATE DIRECTOR) access")
print("=" * 60)
craig_modules = dbas.fetchall("""
    SELECT DISTINCT ma.MODULE_ID, al.App_Name, ma.ACCESS_LEVEL
    FROM dbo.MODULE_AUDIENCE ma
    JOIN dbo.APP_LIST al ON al.App_ID = ma.MODULE_ID OR ma.MODULE_ID = 0
    WHERE al.Flag_Active = 1
      AND (
        (ma.GRANT_TYPE = 'title_group' AND ma.GRANT_VALUE = 'CORPORATE DIRECTOR')
        OR (ma.GRANT_TYPE = 'title_prefix' AND 'CORPORATE DIRECTOR' LIKE ma.GRANT_VALUE + '%')
        OR (ma.GRANT_TYPE IN ('individual','developer') AND ma.GRANT_VALUE = 'cpell@peakmade.com')
        OR (ma.GRANT_VALUE = '*')
      )
    ORDER BY al.App_Name
""")
for r in craig_modules:
    print(f"  {r[1]:<35s} | {r[2]}")

# Check a low-level user
print("\n" + "=" * 60)
print("SANITY CHECK: A Leasing Consultant access")
print("=" * 60)
lc_modules = dbas.fetchall("""
    SELECT DISTINCT ma.MODULE_ID, al.App_Name, ma.ACCESS_LEVEL
    FROM dbo.MODULE_AUDIENCE ma
    JOIN dbo.APP_LIST al ON al.App_ID = ma.MODULE_ID OR ma.MODULE_ID = 0
    WHERE al.Flag_Active = 1
      AND (
        (ma.GRANT_TYPE = 'title_group' AND ma.GRANT_VALUE = 'PROPERTY LEASING CONSULTANT')
        OR (ma.GRANT_TYPE = 'title_prefix' AND 'PROPERTY LEASING CONSULTANT' LIKE ma.GRANT_VALUE + '%')
        OR (ma.GRANT_VALUE = '*')
      )
    ORDER BY al.App_Name
""")
for r in lc_modules:
    print(f"  {r[1]:<35s} | {r[2]}")

dbas.close()
stg.close()
print("\nDone.")
