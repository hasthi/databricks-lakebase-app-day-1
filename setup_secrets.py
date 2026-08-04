"""
One-time setup script: creates the Databricks secret scope and stores the
Lakebase connection URL. Run this locally (with the Databricks CLI configured)
or from a notebook - never commit secret values anywhere.

Usage:
    python setup_secrets.py
"""
from databricks.sdk import WorkspaceClient
from databricks.sdk.service import workspace
import getpass

w = WorkspaceClient()

# Create a scope for Lakebase and store the connection URL
w.secrets.create_scope(scope="database")
w.secrets.put_secret(
    scope="database",
    key="lakebase-url",
    string_value=getpass.getpass("Paste your Lakebase URL: ")
)

# Grant read ACL to workspace users for the database scope
w.secrets.put_acl(
    scope="database",
    principal="users",
    permission=workspace.AclPermission.READ,
)
