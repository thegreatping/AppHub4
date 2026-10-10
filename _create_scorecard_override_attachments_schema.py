"""Create DB_APP_SUPPORT.dbo.SCORECARD_OVERRIDE_ATTACHMENTS -- stores override
screenshot evidence as VARBINARY(MAX) (beta #50 / Item #64 part 4).

Mirrors the existing in-app attachment pattern (PeakLink DOCUMENT_1/2/3, vendor
DOC_* columns). Uses the app's proven SafeConnection to DB_APP_SUPPORT.
Run once:  py -u _create_scorecard_override_attachments_schema.py
"""
from helpers import load_env, SafeConnection

DDL = """
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'SCORECARD_OVERRIDE_ATTACHMENTS' AND schema_id = SCHEMA_ID('dbo'))
CREATE TABLE dbo.SCORECARD_OVERRIDE_ATTACHMENTS (
    ATTACHMENT_ID INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    PROPERTY_KEY  INT NOT NULL,
    MEASURE_KEY   VARCHAR(40) NOT NULL,
    AY            INT NULL,
    QUARTER       VARCHAR(10) NULL,
    CONTENT_TYPE  VARCHAR(100) NOT NULL,
    FILE_NAME     NVARCHAR(260) NULL,
    FILE_SIZE     INT NULL,
    IMAGE_BYTES   VARBINARY(MAX) NOT NULL,
    UPLOADED_BY   NVARCHAR(200) NULL,
    UPLOADED_AT   DATETIME2 NOT NULL CONSTRAINT DF_SC_OVR_ATT_UPLOADED_AT DEFAULT SYSUTCDATETIME()
);
"""

INDEX_DDL = """
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_SC_OVR_ATT_PROP_MEASURE')
CREATE INDEX IX_SC_OVR_ATT_PROP_MEASURE
    ON dbo.SCORECARD_OVERRIDE_ATTACHMENTS (PROPERTY_KEY, MEASURE_KEY, AY, QUARTER);
"""

env = load_env()
conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
try:
    conn.execute(DDL)
    conn.commit()
    conn.execute(INDEX_DDL)
    conn.commit()
    cols = conn.fetchall(
        "SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS "
        "WHERE TABLE_NAME = 'SCORECARD_OVERRIDE_ATTACHMENTS' ORDER BY ORDINAL_POSITION")
    print("SCORECARD_OVERRIDE_ATTACHMENTS columns:")
    for c in cols:
        print(f"  {c[0]} ({c[1]})")
    print(f"\nTotal columns: {len(cols)}")
finally:
    conn.close()
