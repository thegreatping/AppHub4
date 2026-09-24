from dotenv import load_dotenv; load_dotenv()
from helpers import load_env, SafeConnection

conn = SafeConnection(load_env(), "DB_APP_SUPPORT", None, direct=True)

for table in ["BankAccount", "BeneficiaryBankInstruction"]:
    print(f"\n=== {table} ===")
    try:
        cols = conn.fetchall(
            "SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, IS_NULLABLE "
            "FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME=? ORDER BY ORDINAL_POSITION",
            (table,)
        )
        for c in cols:
            print(f"  {c[0]:<40s} {c[1]}{f'({c[2]})' if c[2] else '':<15s} NULL={c[3]}")
        cnt = conn.fetchall(f"SELECT COUNT(*) FROM dbo.[{table}]")
        print(f"  >> {cnt[0][0]} rows")
    except Exception as e:
        print(f"  ERROR: {e}")
