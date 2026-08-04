"""
Databricks App boilerplate:
- Serves a small Flask API
- Reads/writes to Lakebase (Databricks-managed Postgres) via lakebase.py
- Provides a simple internal support tickets UI and API

Run locally:
    python app.py
Deploy as a Databricks App using app.yaml.
"""

import logging
import os
import uuid

from databricks.sdk import WorkspaceClient
from flask import Flask, jsonify, render_template, request

import lakebase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("support-app")

app = Flask(__name__)
_w = WorkspaceClient()



def ensure_tickets_table():
    """Create the `tickets` table in Lakebase if it doesn't exist."""
    lakebase.run_write(
        """
        CREATE TABLE IF NOT EXISTS tickets (
            ticket_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            status TEXT NOT NULL,
            created_by TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )


def ensure_ticket_messages_table():
    """Create the `ticket_messages` table in Lakebase if it doesn't exist."""
    lakebase.run_write(
        """
        CREATE TABLE IF NOT EXISTS ticket_messages (
            message_id TEXT PRIMARY KEY,
            ticket_id TEXT NOT NULL REFERENCES tickets(ticket_id) ON DELETE CASCADE,
            message_text TEXT NOT NULL,
            author TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )



def _current_user_email() -> str:
    """
    Resolve the current user's email so the watchlist can be personalized.

    Databricks Apps inject the logged-in user's identity via the
    X-Forwarded-Email header on every request. Fall back to the Databricks
    SDK's current_user API for local development where that header isn't set.
    """
    header_email = request.headers.get("X-Forwarded-Email")
    if header_email:
        return header_email
    return _w.current_user.me().user_name


@app.route("/healthz")
def healthz():
    return jsonify({"status": "ok"})


@app.errorhandler(Exception)
def handle_error(error):
    """Catch-all error handler to return JSON errors for API consistency."""
    logger.exception("Unhandled exception while processing request")
    return jsonify({"error": str(error)}), 500


@app.route("/")
def index():
    """Support tickets UI."""
    return render_template("index.html")




# --- Support tickets API ---
@app.route("/tickets", methods=["GET"])
def list_tickets():
    """Return all tickets ordered by newest first."""
    ensure_tickets_table()
    rows = lakebase.run_query(
        "SELECT ticket_id, title, status, created_by, created_at FROM tickets ORDER BY created_at DESC",
        None,
    )
    return jsonify(rows)


@app.route("/tickets", methods=["POST"])
def create_ticket():
    """Create a new support ticket."""
    ensure_tickets_table()
    ensure_ticket_messages_table()
    if request.is_json:
        title = (request.json.get("title") or "").strip()
        status = (request.json.get("status") or "open").strip()
    else:
        title = (request.form.get("title") or "").strip()
        status = (request.form.get("status") or "open").strip()

    if not title:
        return jsonify({"error": "Title is required"}), 400

    ticket_id = str(uuid.uuid4())
    created_by = _current_user_email()

    lakebase.run_write(
        "INSERT INTO tickets (ticket_id, title, status, created_by, created_at) VALUES (%s, %s, %s, %s, now())",
        (ticket_id, title, status, created_by),
    )

    return jsonify({"ticket_id": ticket_id, "title": title, "status": status, "created_by": created_by})


@app.route("/tickets/<ticket_id>", methods=["PATCH"])
def update_ticket_status(ticket_id: str):
    """Update the status of an existing ticket."""
    ensure_tickets_table()
    
    if request.is_json:
        new_status = (request.json.get("status") or "").strip()
    else:
        new_status = (request.form.get("status") or "").strip()
    
    if not new_status:
        return jsonify({"error": "Status is required"}), 400
    
    if new_status not in ["open", "in-progress", "resolved"]:
        return jsonify({"error": "Status must be one of: open, in-progress, resolved"}), 400
    
    # Verify ticket exists
    found = lakebase.run_query("SELECT ticket_id FROM tickets WHERE ticket_id = %s", (ticket_id,))
    if not found:
        return jsonify({"error": "Ticket not found"}), 404
    
    # Update the status
    lakebase.run_write(
        "UPDATE tickets SET status = %s WHERE ticket_id = %s",
        (new_status, ticket_id),
    )
    
    return jsonify({"ticket_id": ticket_id, "status": new_status})


@app.route("/tickets/<ticket_id>/messages", methods=["GET"])
def list_messages(ticket_id: str):
    """Return all messages for a ticket ordered by creation time."""
    ensure_ticket_messages_table()
    rows = lakebase.run_query(
        "SELECT message_id, ticket_id, message_text, author, created_at FROM ticket_messages WHERE ticket_id = %s ORDER BY created_at ASC",
        (ticket_id,),
    )
    return jsonify(rows)


@app.route("/tickets/<ticket_id>/messages", methods=["POST"])
def add_message(ticket_id: str):
    """Add a message to an existing ticket."""
    ensure_ticket_messages_table()
    ensure_tickets_table()

    if request.is_json:
        message_text = (request.json.get("message_text") or "").strip()
    else:
        message_text = (request.form.get("message_text") or "").strip()

    if not message_text:
        return jsonify({"error": "message_text is required"}), 400

    # verify ticket exists
    found = lakebase.run_query("SELECT ticket_id FROM tickets WHERE ticket_id = %s", (ticket_id,))
    if not found:
        return jsonify({"error": "ticket not found"}), 404

    message_id = str(uuid.uuid4())
    author = _current_user_email()

    lakebase.run_write(
        "INSERT INTO ticket_messages (message_id, ticket_id, message_text, author, created_at) VALUES (%s, %s, %s, %s, now())",
        (message_id, ticket_id, message_text, author),
    )

    return jsonify({"message_id": message_id, "ticket_id": ticket_id, "message_text": message_text, "author": author})




if __name__ == '__main__':
    host = os.getenv('FLASK_RUN_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_RUN_PORT', 8000))
    app.run(debug=True, host=host, port=port)
    print(f"Flask app running on http://{host}:{port}")
