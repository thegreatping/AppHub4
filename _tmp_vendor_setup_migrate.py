"""Create dbo.VENDOR_SETUP_REQUEST in DB_APP_SUPPORT."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import load_env, SafeConnection

env  = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)

# Check if table already exists
if conn.scalar("SELECT OBJECT_ID('dbo.VENDOR_SETUP_REQUEST','U')") is not None:
    print("Table dbo.VENDOR_SETUP_REQUEST already exists — nothing to do.")
    sys.exit(0)

ddl = """
CREATE TABLE dbo.VENDOR_SETUP_REQUEST (
    ID                   INT IDENTITY(1,1) PRIMARY KEY,
    VENDOR_NAME          NVARCHAR(255)  NOT NULL,
    VENDOR_DBA           NVARCHAR(255)  NULL,
    VENDOR_TYPE          NVARCHAR(100)  NULL,
    BUSINESS_TYPE        NVARCHAR(100)  NULL,
    EIN                  NVARCHAR(50)   NULL,
    PRIMARY_CONTACT      NVARCHAR(255)  NULL,
    CONTACT_PHONE        NVARCHAR(50)   NULL,
    CONTACT_EMAIL        NVARCHAR(255)  NULL,
    ADDRESS_1            NVARCHAR(255)  NULL,
    ADDRESS_2            NVARCHAR(255)  NULL,
    CITY                 NVARCHAR(100)  NULL,
    STATE                NVARCHAR(50)   NULL,
    ZIP                  NVARCHAR(20)   NULL,
    PROPERTY_NAME        NVARCHAR(255)  NULL,
    PAYMENT_METHOD       NVARCHAR(50)   NULL,
    BANK_NAME            NVARCHAR(255)  NULL,
    BANK_ACCOUNT_TYPE    NVARCHAR(50)   NULL,
    BANK_ROUTING         NVARCHAR(50)   NULL,
    BANK_ACCOUNT         NVARCHAR(100)  NULL,
    NOTES                NVARCHAR(MAX)  NULL,
    DOC_W9               VARBINARY(MAX) NULL,
    DOC_W9_NAME          NVARCHAR(255)  NULL,
    DOC_INSURANCE        VARBINARY(MAX) NULL,
    DOC_INSURANCE_NAME   NVARCHAR(255)  NULL,
    DOC_OTHER            VARBINARY(MAX) NULL,
    DOC_OTHER_NAME       NVARCHAR(255)  NULL,
    STATUS               NVARCHAR(50)   NOT NULL DEFAULT 'Pending',
    SUBMITTED_BY         NVARCHAR(255)  NULL,
    SUBMITTED_BY_EMAIL   NVARCHAR(255)  NULL,
    DATE_SUBMITTED       DATETIME2      NOT NULL DEFAULT GETDATE(),
    DATE_MODIFIED        DATETIME2      NULL,
    MODIFIED_BY          NVARCHAR(255)  NULL,
    REVIEW_NOTES         NVARCHAR(MAX)  NULL,
    REVIEWED_BY          NVARCHAR(255)  NULL
)
"""
conn.execute(ddl)
print("dbo.VENDOR_SETUP_REQUEST created successfully.")
