"""Application configuration."""
import os


APP_VERSION = "4.0.1"


class Config:
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "dev-key-change-in-production")
    SESSION_TYPE = "filesystem"

    # Entra ID (Azure AD) settings
    AZURE_CLIENT_ID = os.environ.get("AZURE_CLIENT_ID", "")
    AZURE_CLIENT_SECRET = os.environ.get("AZURE_CLIENT_SECRET", "")
    AZURE_TENANT_ID = os.environ.get("AZURE_TENANT_ID", "")
    AZURE_AUTHORITY = f"https://login.microsoftonline.com/{os.environ.get('AZURE_TENANT_ID', 'common')}"
    AZURE_REDIRECT_URI = os.environ.get("AZURE_REDIRECT_URI", "http://localhost:5000/auth/callback")
    AZURE_SCOPE = ["User.Read"]

    # Graph API — FabricPipelineApp service principal (Sites.ReadWrite.All)
    # Used for SharePoint list access (Peak Link and any future SP-backed modules).
    # These are separate from the Entra ID user-auth credentials above.
    GRAPH_TENANT_ID     = os.environ.get("GRAPH_TENANT_ID",     "")
    GRAPH_CLIENT_ID     = os.environ.get("GRAPH_CLIENT_ID",     "")
    GRAPH_CLIENT_SECRET = os.environ.get("GRAPH_CLIENT_SECRET", "")

    # Power Apps base URL (for linking back to legacy modules)
    POWERAPPS_APP_URL = os.environ.get("POWERAPPS_APP_URL", "")
