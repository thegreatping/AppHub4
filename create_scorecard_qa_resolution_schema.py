"""Create shared, auditable "What we did" storage for Scorecard QA.

By default this is a dry run. Pass --apply to create the two DB_APP_SUPPORT
SQL Database tables. Existing per-tester QA state is not altered.
"""
import argparse

from helpers import load_env, SafeConnection

DDL = """
IF OBJECT_ID('dbo.SCORECARD_QA_RESOLUTION', 'U') IS NULL
EXEC('
    CREATE TABLE dbo.SCORECARD_QA_RESOLUTION (
        SCENARIO_KEY varchar(50) NOT NULL,
        WHAT_WE_DID varchar(max) NULL,
        UPDATED_BY varchar(200) NOT NULL,
        UPDATED_AT datetime2 NOT NULL,
        CONSTRAINT PK_SCORECARD_QA_RESOLUTION PRIMARY KEY (SCENARIO_KEY)
    )
');

IF OBJECT_ID('dbo.SCORECARD_QA_RESOLUTION_AUDIT', 'U') IS NULL
EXEC('
    CREATE TABLE dbo.SCORECARD_QA_RESOLUTION_AUDIT (
        AUDIT_ID bigint IDENTITY(1,1) NOT NULL,
        SCENARIO_KEY varchar(50) NOT NULL,
        OLD_WHAT_WE_DID varchar(max) NULL,
        NEW_WHAT_WE_DID varchar(max) NULL,
        CHANGED_BY varchar(200) NOT NULL,
        CHANGED_AT datetime2 NOT NULL,
        CONSTRAINT PK_SCORECARD_QA_RESOLUTION_AUDIT PRIMARY KEY (AUDIT_ID)
    )
');
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Apply the idempotent DDL to DB_APP_SUPPORT")
    args = parser.parse_args()
    if not args.apply:
        print("Dry run only. This will create:")
        print("  dbo.SCORECARD_QA_RESOLUTION (one shared current resolution per scenario)")
        print("  dbo.SCORECARD_QA_RESOLUTION_AUDIT (append-only old/new history)")
        print("No database changes made. Pass --apply when authorized.")
        return

    conn = SafeConnection(load_env(), "DB_APP_SUPPORT", None, direct=True)
    try:
        conn.execute(DDL)
        conn.commit()
        for table in ("SCORECARD_QA_RESOLUTION", "SCORECARD_QA_RESOLUTION_AUDIT"):
            exists = conn.fetchall(
                "SELECT OBJECT_ID(?, 'U')", (f"dbo.{table}",))
            if not exists or not exists[0][0]:
                raise RuntimeError(f"dbo.{table} was not created")
            count = conn.fetchall(f"SELECT COUNT(*) FROM dbo.{table}")[0][0]
            print(f"  verified dbo.{table}: {count} rows")
        print("Created/verified SCORECARD_QA_RESOLUTION and SCORECARD_QA_RESOLUTION_AUDIT.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
