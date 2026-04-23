"""
Sentinel V2 Dashboard — Flask + SocketIO backend with WebSocket bi-directional communication.

Provides:
- /                   → dashboard UI
- SocketIO events:
  - connect/ disconnect
  - subscribe_state → dashboard receives state updates
  - state_update     → app pushes state updates
  - approve          → client approves proposal
  - reject           → client rejects proposal

Endpoints:
- /api/state          → current flow state
- /api/approval       → current approval state
- /api/approval/action → approve/reject/revision action
- /api/log            → tail latest log
"""
from __future__ import annotations

import json
import logging

log = logging.getLogger("sentinel_v2.dashboard")
import threading
from pathlib import Path
from flask import Flask, jsonify, request
from flask_socketio import SocketIO, emit
from datetime import datetime

log = logging.getLogger("sentinel_v2.dashboard")

# ── Flask + SocketIO app ──────────────────────────────────────────────────────

app = Flask(__name__, static_folder="static")
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="eventlet",
    logger=False,
    engineio_logger=False,
)

BASE_DIR = Path(__file__).parent.parent
LOGS_DIR = BASE_DIR / "logs"
APPROVAL_FILE = Path("/tmp/sentinel_v2_approval.json")
STATE_FILE = Path("/tmp/sentinel_v2_state.json")
SOCKET_AUTH_TOKEN = "sentinel-v2-dashboard-secret"

# ── State reader ──────────────────────────────────────────────────────────────


def read_approval_state() -> dict:
    """Read current approval state."""
    if not APPROVAL_FILE.exists():
        return {"status": "no_cycle", "pending": {}, "approved": [], "rejected": []}
    try:
        with open(APPROVAL_FILE) as f:
            return json.load(f)
    except (IOError, json.JSONDecodeError):
        return {"status": "error", "pending": {}, "approved": [], "rejected": []}


def get_agent_messages() -> list:
    """Get all agent messages from dashboard state."""
    msg_file = Path("/tmp/sentinel_v2_agent_messages.json")
    if not msg_file.exists():
        return []
    try:
        with open(msg_file) as f:
            return json.load(f)
    except (IOError, json.JSONDecodeError):
        return []


def read_flow_state() -> dict:
    """Read current flow state from file."""
    if not STATE_FILE.exists():
        return {"cycle": 0, "phase": "idle", "opportunity": None, "build_output": None, "match_score": 0.0}
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (IOError, json.JSONDecodeError):
        return {"cycle": 0, "phase": "idle", "opportunity": None, "build_output": None, "match_score": 0.0}


def get_latest_log() -> tuple[str, str]:
    """Return (log_content, log_filename) of most recent log."""
    if not LOGS_DIR.exists():
        return "", ""
    log_files = sorted(LOGS_DIR.glob("sentinel-*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not log_files:
        return "", ""
    log_path = log_files[0]
    try:
        content = log_path.read_text()
        lines = content.split("\n")
        tail = lines[-200:] if len(lines) > 200 else lines
        return "\n".join(tail), log_path.name
    except (IOError, OSError):
        return "", log_path.name


def write_approval_action(action: str, revision_notes: str | None = None) -> bool:
    """Write an approval/rejection/revision action. Returns True on success."""
    state = read_approval_state()
    now = datetime.now().isoformat()

    if action not in ("approve", "reject"):
        return False

    # Support both pending as list and pending as dict
    pending_raw = state.get("pending")
    pending_item = None

    if isinstance(pending_raw, dict):
        # A single dict item — treat null/missing status as pending
        item_status = pending_raw.get("status")
        if item_status is None or item_status == "pending":
            pending_item = pending_raw
    elif isinstance(pending_raw, list):
        for item in pending_raw:
            if item.get("status") == "pending":
                pending_item = item
                break

    if not pending_item:
        return False

    # Update the item
    pending_item["status"] = action
    pending_item["resolved_at"] = now
    if revision_notes:
        pending_item["revision_notes"] = revision_notes

    # Map action to the correct array key (approve→approved, reject→rejected)
    array_key = "approved" if action == "approve" else "rejected"

    # Clear pending, add to correct resolved array
    if isinstance(pending_raw, dict):
        state["pending"] = {}
    else:
        state["pending"] = [i for i in state.get("pending", []) if i.get("status") != "pending"]

    state.setdefault(array_key, []).append(pending_item)

    # Also update the action
    state["last_action"] = action
    state["last_action_at"] = now

    try:
        with open(APPROVAL_FILE, "w") as f:
            json.dump(state, f, indent=2)
        return True
    except (IOError, json.JSONDecodeError):
        return False


# ── Background state poller ────────────────────────────────────────────────────

def state_poller():
    """Background thread that polls state files and pushes updates via SocketIO."""
    last_state = ""
    last_approval = ""
    last_log = ""
    last_agent_messages = ""

    while True:
        try:
            flow_state = read_flow_state()
            approval_state = read_approval_state()
            log_content, log_name = get_latest_log()
            agent_messages = get_agent_messages()

            current_state = json.dumps(flow_state)
            current_approval = json.dumps(approval_state)
            current_messages = json.dumps(agent_messages)

            if current_state != last_state:
                socketio.emit("state_update", flow_state, namespace="/dashboard")
                last_state = current_state

            if current_approval != last_approval:
                socketio.emit("approval_update", approval_state, namespace="/dashboard")
                last_approval = current_approval

            if current_messages != last_agent_messages:
                socketio.emit("agent_messages", agent_messages, namespace="/dashboard")
                last_agent_messages = current_messages

            if log_content != last_log:
                socketio.emit("log_update", {"content": log_content, "name": log_name}, namespace="/dashboard")
                last_log = log_content

            # Heartbeat
            socketio.emit(
                "heartbeat",
                {"time": datetime.now().isoformat(), "cycle": flow_state.get("cycle", 0), "phase": flow_state.get("phase", "idle")},
                namespace="/dashboard",
            )

        except (IOError, json.JSONDecodeError) as e:
            socketio.emit("error", {"message": str(e)}, namespace="/dashboard")

        socketio.sleep(2)  # Poll every 2 seconds


# ── SocketIO events ───────────────────────────────────────────────────────────

@socketio.on("connect", namespace="/dashboard")
def handle_connect():
    """Client connected - validate auth token, send current state."""
    token = request.args.get("token") or (request.auth or {}).get("token")
    if token != SOCKET_AUTH_TOKEN:
        log.warning("Unauthorized socket connection attempt from %s", request.sid)
        return False  # Reject connection
    print(f"Client connected: {request.sid}")
    emit("connected", {"message": "Connected to Sentinel Dashboard"}, namespace="/dashboard")

    # Send current state immediately
    emit("state_update", read_flow_state(), namespace="/dashboard")
    emit("approval_update", read_approval_state(), namespace="/dashboard")


@socketio.on("disconnect", namespace="/dashboard")
def handle_disconnect():
    """Client disconnected."""
    print(f"Client disconnected: {request.sid}")


@socketio.on("approve", namespace="/dashboard")
def handle_approve():
    """Approve the current proposal."""
    success = write_approval_action("approve")
    emit("action_response", {"success": success, "action": "approve"}, namespace="/dashboard")


@socketio.on("reject", namespace="/dashboard")
def handle_reject(data):
    """Reject the current proposal (or request revision)."""
    revision = data.get("revision", False)
    notes = data.get("notes", "")
    
    # revision means approve to continue with feedback
    if revision:
        success = write_approval_action("approve", revision_notes=notes)
        action_name = "revision"
    else:
        success = write_approval_action("reject")
        action_name = "reject"
    
    emit("action_response", {"success": success, "action": action_name}, namespace="/dashboard")


# ── HTTP routes ──────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return "Sentinel V2 Dashboard - Use /api endpoints or connect via SocketIO"


@app.route("/api/state")
def api_state():
    return jsonify(read_flow_state())


@app.route("/api/approval")
def api_approval():
    return jsonify(read_approval_state())


@app.route("/api/approval/action", methods=["POST"])
def api_approval_action():
    """HTTP endpoint for approve/reject/revision actions."""
    data = request.get_json() or {}
    action = data.get("action", "")
    notes = data.get("notes", "")
    revision = data.get("revision", False)

    if action == "approve":
        success = write_approval_action("approve")
    elif action == "reject":
        success = write_approval_action("reject")
    elif action == "revision":
        success = write_approval_action("approve", revision_notes=notes)
    else:
        return jsonify({"success": False, "error": "invalid action"}), 400

    return jsonify({"success": success, "action": action})


@app.route("/api/log")
def api_log():
    content, name = get_latest_log()
    return jsonify({"content": content, "name": name})


# ── Main ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("🚀 Sentinel Dashboard → http://localhost:5173 (WebSocket enabled)")
    print("   Namespace: /dashboard")
    
    # Start background state poller
    poller_thread = threading.Thread(target=state_poller, daemon=True)
    poller_thread.start()
    
    # Run with SocketIO (WebSocket support)
    socketio.run(app, host="0.0.0.0", port=5173, debug=False, allow_unsafe_werkzeug=True)
