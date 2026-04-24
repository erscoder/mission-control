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
BREAKDOWN_FILE = Path("/tmp/sentinel_v2_flow_breakdown.json")
AGENT_MESSAGES_FILE = Path("/tmp/sentinel_v2_agent_messages.json")
DRAFTS_FILE = Path("/tmp/sentinel_v2_drafts.json")
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


def read_drafts() -> dict:
    """Read drafts list from file. Each draft has rich metadata + lifecycle status.

    If the drafts file does not exist yet, synthesize one from the legacy approval
    state so older Sentinel runs still populate the dashboard's draft queue.
    """
    default = {"drafts": [], "updated_at": ""}
    if DRAFTS_FILE.exists():
        try:
            with open(DRAFTS_FILE) as f:
                data = json.load(f)
                if isinstance(data, dict) and isinstance(data.get("drafts"), list):
                    return {**default, **data}
        except (IOError, json.JSONDecodeError):
            pass

    # Fallback: synthesize drafts from legacy approval state
    legacy = read_approval_state()
    drafts: list[dict] = []

    def _normalize(item: dict, default_status: str) -> dict:
        if not isinstance(item, dict) or not item.get("title"):
            return {}
        cycle = item.get("cycle", 0)
        status = item.get("status") or default_status
        # Map legacy status values to new lifecycle
        status = {
            "approve": "approved",
            "reject": "rejected",
        }.get(status, status)
        return {
            "id": item.get("id") or f"legacy_c{cycle}_{abs(hash(item.get('title',''))) % 10_000}",
            "cycle": cycle,
            "title": item.get("title", ""),
            "tagline": item.get("tagline")
            or (item.get("solution", "")[:80] if item.get("solution") else ""),
            "description": item.get("description")
            or item.get("problem", "")
            or "",
            "problem": item.get("problem", ""),
            "solution": item.get("solution", ""),
            "tech_fit": float(item.get("tech_fit", 0.0) or 0.0),
            "complexity": int(item.get("complexity", 0) or 0),
            "estimated_hours": item.get("estimated_hours"),
            "tags": item.get("tags", []) or [],
            "status": status,
            "created_at": item.get("created_at", ""),
            "updated_at": item.get("resolved_at") or item.get("updated_at", ""),
            "build_progress": float(item.get("build_progress", 0.0) or 0.0),
            "queue_position": item.get("queue_position"),
            "revision_notes": item.get("revision_notes"),
            "deployment_url": item.get("deployment_url"),
        }

    pending_raw = legacy.get("pending")
    if isinstance(pending_raw, dict) and pending_raw.get("title"):
        d = _normalize(pending_raw, "pending")
        if d:
            drafts.append(d)
    elif isinstance(pending_raw, list):
        for item in pending_raw:
            d = _normalize(item, "pending")
            if d:
                drafts.append(d)

    for item in legacy.get("approved", []) or []:
        d = _normalize(item, "approved")
        if d:
            drafts.append(d)
    for item in legacy.get("rejected", []) or []:
        d = _normalize(item, "rejected")
        if d:
            drafts.append(d)

    return {"drafts": drafts, "updated_at": ""}


def write_drafts(data: dict) -> bool:
    try:
        with open(DRAFTS_FILE, "w") as f:
            json.dump(data, f, indent=2)
        return True
    except (IOError, OSError):
        return False


def update_draft_status(draft_id: str, new_status: str, revision_notes: str | None = None) -> bool:
    """Update a single draft's status by id. Returns True on success."""
    data = read_drafts()
    drafts = data.get("drafts", [])
    found = False
    now = datetime.now().isoformat()
    for d in drafts:
        if d.get("id") == draft_id:
            d["status"] = new_status
            d["updated_at"] = now
            if revision_notes:
                d["revision_notes"] = revision_notes
            found = True
            break
    if not found:
        return False
    data["drafts"] = drafts
    data["updated_at"] = now
    return write_drafts(data)


def compute_build_queue(drafts: list[dict]) -> list[dict]:
    """Derive a build queue view from drafts. Drafts with status 'pending' (just surfaced)
    now appear at the head of the pipeline as a 'draft' stage; rejected items stay out."""
    ACTIVE = {"pending", "approved", "queued", "building", "review", "testing", "built", "deployed", "failed"}
    queue = [d for d in drafts if d.get("status") in ACTIVE]
    order = {
        "pending": 0,
        "building": 1,
        "review": 1,
        "testing": 1,
        "queued": 2,
        "approved": 2,
        "built": 3,
        "deployed": 4,
        "failed": 5,
    }
    queue.sort(key=lambda d: (order.get(d.get("status", ""), 99), d.get("queue_position") or 0, d.get("created_at") or ""))
    return queue


def read_flow_breakdown() -> dict:
    """Read granular flow breakdown from file."""
    default = {
        "cycle": 0,
        "phase": "idle",
        "sub_phase": None,
        "status": "idle",
        "progress": 0.0,
        "current_task": None,
        "next_task": None,
        "completed_tasks": [],
        "pending_tasks": [],
        "blockers": [],
        "metrics": {},
        "opportunity_title": None,
        "match_score": 0.0,
        "deployed": False,
        "updated_at": "",
    }
    if not BREAKDOWN_FILE.exists():
        return default
    try:
        with open(BREAKDOWN_FILE) as f:
            data = json.load(f)
            return {**default, **data}
    except (IOError, json.JSONDecodeError):
        return default


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
    last_breakdown = ""
    last_drafts = ""

    while True:
        try:
            flow_state = read_flow_state()
            approval_state = read_approval_state()
            log_content, log_name = get_latest_log()
            agent_messages = get_agent_messages()
            breakdown = read_flow_breakdown()
            drafts_data = read_drafts()
            build_queue = compute_build_queue(drafts_data.get("drafts", []))

            current_state = json.dumps(flow_state)
            current_approval = json.dumps(approval_state)
            current_messages = json.dumps(agent_messages)
            current_breakdown = json.dumps(breakdown)
            current_drafts = json.dumps({"drafts": drafts_data.get("drafts", []), "build_queue": build_queue})

            if current_state != last_state:
                socketio.emit("state_update", flow_state, namespace="/dashboard")
                last_state = current_state

            if current_approval != last_approval:
                socketio.emit("approval_update", approval_state, namespace="/dashboard")
                last_approval = current_approval

            if current_messages != last_agent_messages:
                socketio.emit("agent_messages", agent_messages, namespace="/dashboard")
                last_agent_messages = current_messages

            if current_breakdown != last_breakdown:
                socketio.emit("flow_breakdown_update", breakdown, namespace="/dashboard")
                last_breakdown = current_breakdown

            if current_drafts != last_drafts:
                socketio.emit(
                    "drafts_update",
                    {"drafts": drafts_data.get("drafts", []), "build_queue": build_queue},
                    namespace="/dashboard",
                )
                last_drafts = current_drafts

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

        socketio.sleep(1)  # Poll every 1 second


# ── SocketIO events ───────────────────────────────────────────────────────────

@socketio.on("connect", namespace="/dashboard")
def handle_connect(auth=None):
    """Client connected - validate auth token, send current state."""
    token = request.args.get("token")
    if not token and isinstance(auth, dict):
        token = auth.get("token")
    if token != SOCKET_AUTH_TOKEN:
        log.warning("Unauthorized socket connection attempt from %s", request.sid)
        return False  # Reject connection
    print(f"Client connected: {request.sid}")
    emit("connected", {"message": "Connected to Sentinel Dashboard"}, namespace="/dashboard")

    # Send current state immediately
    emit("state_update", read_flow_state(), namespace="/dashboard")
    emit("approval_update", read_approval_state(), namespace="/dashboard")
    emit("flow_breakdown_update", read_flow_breakdown(), namespace="/dashboard")
    emit("agent_messages", get_agent_messages(), namespace="/dashboard")
    _drafts = read_drafts()
    emit(
        "drafts_update",
        {"drafts": _drafts.get("drafts", []), "build_queue": compute_build_queue(_drafts.get("drafts", []))},
        namespace="/dashboard",
    )


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


@socketio.on("approve_draft", namespace="/dashboard")
def handle_approve_draft(data):
    """Approve a single draft by id. Sets status to 'queued' so the flow picks it up."""
    draft_id = (data or {}).get("id", "")
    if not draft_id:
        emit("action_response", {"success": False, "action": "approve_draft", "error": "missing id"}, namespace="/dashboard")
        return
    ok = update_draft_status(draft_id, "queued")
    emit("action_response", {"success": ok, "action": "approve_draft", "id": draft_id}, namespace="/dashboard")


@socketio.on("reject_draft", namespace="/dashboard")
def handle_reject_draft(data):
    """Reject a single draft by id. Optional revision notes move it to 'pending' with notes."""
    payload = data or {}
    draft_id = payload.get("id", "")
    revision = bool(payload.get("revision", False))
    notes = payload.get("notes", "")
    if not draft_id:
        emit("action_response", {"success": False, "action": "reject_draft", "error": "missing id"}, namespace="/dashboard")
        return
    if revision:
        ok = update_draft_status(draft_id, "pending", revision_notes=notes)
        action = "revise_draft"
    else:
        ok = update_draft_status(draft_id, "rejected")
        action = "reject_draft"
    emit("action_response", {"success": ok, "action": action, "id": draft_id}, namespace="/dashboard")


@socketio.on("approve_deploy", namespace="/dashboard")
def handle_approve_deploy(data):
    """Second approval gate: after a draft is built, human approves deployment."""
    draft_id = (data or {}).get("id", "")
    if not draft_id:
        emit("action_response", {"success": False, "action": "approve_deploy", "error": "missing id"}, namespace="/dashboard")
        return
    ok = update_draft_status(draft_id, "deployed")
    emit("action_response", {"success": ok, "action": "approve_deploy", "id": draft_id}, namespace="/dashboard")


@socketio.on("reject_deploy", namespace="/dashboard")
def handle_reject_deploy(data):
    """Second approval gate: reject deployment of a built draft. Marks it as failed."""
    draft_id = (data or {}).get("id", "")
    if not draft_id:
        emit("action_response", {"success": False, "action": "reject_deploy", "error": "missing id"}, namespace="/dashboard")
        return
    ok = update_draft_status(draft_id, "failed")
    emit("action_response", {"success": ok, "action": "reject_deploy", "id": draft_id}, namespace="/dashboard")


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


@app.route("/api/flow_breakdown")
def api_flow_breakdown():
    return jsonify(read_flow_breakdown())


@app.route("/api/agent_messages")
def api_agent_messages():
    return jsonify(get_agent_messages())


@app.route("/api/drafts")
def api_drafts():
    data = read_drafts()
    drafts = data.get("drafts", [])
    return jsonify({
        "drafts": drafts,
        "build_queue": compute_build_queue(drafts),
        "updated_at": data.get("updated_at", ""),
    })


@app.route("/api/drafts/action", methods=["POST"])
def api_drafts_action():
    payload = request.get_json(silent=True) or {}
    draft_id = payload.get("id", "")
    action = payload.get("action", "")
    notes = payload.get("notes", "")
    valid = {"approve", "reject", "revise", "approve_deploy", "reject_deploy"}
    if not draft_id or action not in valid:
        return jsonify({"success": False, "error": "invalid payload"}), 400
    if action == "approve":
        ok = update_draft_status(draft_id, "queued")
    elif action == "revise":
        ok = update_draft_status(draft_id, "pending", revision_notes=notes)
    elif action == "approve_deploy":
        ok = update_draft_status(draft_id, "deployed")
    elif action == "reject_deploy":
        ok = update_draft_status(draft_id, "failed")
    else:
        ok = update_draft_status(draft_id, "rejected")
    return jsonify({"success": ok, "action": action, "id": draft_id})


# ── Main ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("🚀 Sentinel Dashboard → http://localhost:5173 (WebSocket enabled)")
    print("   Namespace: /dashboard")
    
    # Start background state poller
    poller_thread = threading.Thread(target=state_poller, daemon=True)
    poller_thread.start()
    
    # Run with SocketIO (WebSocket support)
    socketio.run(app, host="0.0.0.0", port=5173, debug=False, allow_unsafe_werkzeug=True)
