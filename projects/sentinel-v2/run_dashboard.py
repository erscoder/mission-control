#!/usr/bin/env python3
"""Start Sentinel V2 dashboard (WebSocket + state poller)."""
import eventlet  # must monkey-patch before importing anything else
eventlet.monkey_patch()

import os  # noqa: E402
import sys  # noqa: E402

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dashboard.app import app, socketio, state_poller  # noqa: E402

if __name__ == "__main__":
    print("Sentinel Dashboard -> http://localhost:5173 (WebSocket enabled)")
    print("Namespace: /dashboard")

    # Use eventlet-compatible green thread, not stdlib threading.Thread
    socketio.start_background_task(state_poller)

    socketio.run(
        app,
        host="0.0.0.0",
        port=5173,
        debug=False,
        allow_unsafe_werkzeug=True,
    )
