"""
Memory API  –  adds retrieval (semantic search) & simple health/debug endpoints.
Place in: server/routes/memory_api.py
"""

import os
from flask import Blueprint, request, jsonify

memory_bp = Blueprint("memory", __name__)

# Lazy initialization to support testing with different database configurations
_memory = None

def get_memory_store():
    """Lazy load MemoryStore to avoid connection at import time in tests."""
    global _memory
    if _memory is None:
        # Only initialize if we have a valid PostgreSQL URL (not SQLite for tests)
        db_url = os.environ.get("DATABASE_URL", "")
        if db_url.startswith("postgresql"):
            from server.models.memory_store import MemoryStore
            _memory = MemoryStore()
        else:
            # Return a mock/stub for testing environments
            return None
    return _memory


@memory_bp.route("/memory/add", methods=["POST"])
def add_memory():
    memory = get_memory_store()
    if memory is None:
        return jsonify({"error": "Memory service unavailable"}), 503
    
    data = request.get_json(force=True)
    if not data or "content" not in data:
        return jsonify({"error": "Missing content field"}), 400

    ok = memory.add_memory(
        data.get("session_id", "unknown"),
        data.get("user_id", "anonymous"),
        data["content"],
        data.get("source_type", "transcript"),
    )

    if ok:
        return jsonify({"status": "ok", "message": "Memory stored successfully."})
    return jsonify({"status": "error", "message": "Failed to store memory."}), 500


@memory_bp.route("/memory/search", methods=["GET", "POST"])
def search_memory():
    memory = get_memory_store()
    if memory is None:
        return jsonify({"error": "Memory service unavailable"}), 503
    
    if request.method == "GET":
        query = request.args.get("query")
        top_k = int(request.args.get("top_k", 5))
    else:
        data = request.get_json(force=True)
        query = data.get("query")
        top_k = int(data.get("top_k", 5))

    if not query:
        return jsonify({"error": "Missing query parameter"}), 400

    results = memory.search_memory(query, top_k)
    return jsonify({"query": query, "results": results}), 200


@memory_bp.route("/memory/latest", methods=["GET"])
def get_latest_memories():
    """
    Retrieve the most recent memory entries (for UI display of recent memories).
    Query parameter 'limit' controls number of items (default 5).
    """
    memory = get_memory_store()
    if memory is None:
        return jsonify({"error": "Memory service unavailable"}), 503
    
    try:
        limit = request.args.get('limit', 5, type=int)
        rows = memory.latest_memories(limit)
        results = []
        for r in rows:  # each row: (id, user_id, content_snippet, created_at)
            results.append({
                "id": r[0],
                "user_id": r[1],
                "content_snippet": r[2],
                "created_at": r[3].isoformat() if r[3] else None
            })
        return jsonify({"success": True, "latest_memories": results}), 200
    except Exception as e:
        print("ERROR retrieving latest memories:", e)
        return jsonify({"error": "internal_error", "message": str(e), "request_id": None}), 500
        

@memory_bp.route("/memory/debug", methods=["GET"])
def debug_memory():
    """Return a few recent rows for quick inspection."""
    memory = get_memory_store()
    if memory is None:
        return jsonify({"error": "Memory service unavailable"}), 503
    
    try:
        rows = memory.search_memory("", top_k=10)
        return jsonify({"latest": rows}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500