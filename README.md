# Support Tickets + Lakebase Databricks App

A minimal Databricks App for internal support where users can create tickets and add messages.

This app:
- Stores operational data in **Lakebase** (Databricks-managed Postgres) using a single `LAKEBASE_URL` secret
- Exposes a small Flask API to create/list tickets and add/list messages

## Files

- `app.py` - Flask app: `/healthz`, `/tickets` (GET/POST), `/tickets/<id>/messages` (GET/POST)
- `lakebase.py` - Lakebase connection helper (single `LAKEBASE_URL`, psycopg2 + SQLAlchemy)
- `setup_secrets.py` - One-time script to create the secret scope and store the Lakebase URL
- `app.yaml` - Databricks App deployment config (command + env vars)
- `.env.example` - Local dev env var template (copy to `.env`, do not commit real values)

## Step-by-step setup

### 1. Create a Lakebase instance and a native-password role

Follow your Databricks workspace Lakebase UI to create an instance and a native-password role. Copy the
connection URL that looks like:

```
postgresql://<role>:<password>@<host>.database.cloud.databricks.com:5432/databricks_postgres?sslmode=require
```

### 2. Store your Lakebase secret

Run once from a Databricks notebook (or locally if you have the Databricks SDK configured):

```python
%sh python setup_secrets.py
```

This prompts (via `getpass`) for your **Lakebase connection URL** and stores it in the `database/lakebase-url` secret scope.

### Databricks App `app.yaml` example

When you create the Databricks App from a Git folder, Databricks reads `app.yaml` to configure the command and environment for the app. You only need to ensure the app has the Lakebase secret scope/key names (the app fetches the secret at runtime using the Databricks SDK):

```yaml
command:
	- "python"
	- "app.py"

env:
	- name: LAKEBASE_SECRET_SCOPE
		value: "database"
	- name: LAKEBASE_SECRET_KEY
		value: "lakebase-url"
```

No plaintext `LAKEBASE_URL` is required in `app.yaml` — the app resolves the secret at runtime from the specified scope/key.

### 3. Configure environment variables (local dev)

Copy `.env.example` to `.env` and paste your Lakebase URL as `LAKEBASE_URL` for local runs:

```bash
cp .env.example .env
```

For deployment, `app.yaml` pulls the lakebase secret reference automatically.

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Run locally

```bash
python app.py
```

### 6. Deploy as a Databricks App

Use the Databricks workspace UI to create a Git folder/repo and create an App pointing at that folder; Databricks reads `app.yaml` to configure the app's command and env for deployment.

## Endpoints

- `GET /healthz` - health check
- `GET /tickets` - list tickets
- `POST /tickets` - create a ticket (JSON `{ "title": "..." }`)
- `GET /tickets/<ticket_id>/messages` - list messages for a ticket
- `POST /tickets/<ticket_id>/messages` - add a message (JSON `{ "message_text": "..." }`)

## Enabling Change Data Feed (CDF) for Postgres tables

Lakebase supports **Change Data Feed (CDF)** to stream row-level changes into Unity Catalog Delta tables. To include a table in CDF, enable `REPLICA IDENTITY FULL` on it once (e.g. for `tickets` and `ticket_messages`):

```sql
ALTER TABLE tickets REPLICA IDENTITY FULL;
ALTER TABLE ticket_messages REPLICA IDENTITY FULL;
```

Then start CDF from the Lakebase UI and choose the destination Unity Catalog schema for the history tables.

## Notes

- Lakebase auth uses a single `LAKEBASE_URL` secret pointing at a native Postgres role with a static password — no token refresh logic needed in `lakebase.py`.
- For new tables, run `ALTER TABLE ... REPLICA IDENTITY FULL` once to include them in CDF.
