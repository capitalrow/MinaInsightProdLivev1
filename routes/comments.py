from __future__ import annotations
from flask import Blueprint, request, jsonify, abort
from models.core_models import Comment
from models import db

comments_bp = Blueprint("comments", __name__, url_prefix="/comments")

@comments_bp.post("/")
def add_comment():
    b = request.get_json(force=True)
    session_id = b.get("session_id"); user_id = b.get("user_id"); text = b.get("text")
    ts = b.get("timestamp_ms")  # position in media
    if not all([session_id, user_id, text]):
        abort(400, "session_id, user_id, text required")
    c = Comment(session_id=session_id, user_id=user_id, text=text, timestamp_ms=ts)
    db.session.add(c); db.session.commit()
    return jsonify({"id": c.id})

@comments_bp.get("/by-session/<int:session_id>")
def list_comments(session_id: int):
    cs = Comment.query.filter_by(session_id=session_id).order_by(Comment.created_at.asc()).all()
    return jsonify([c.to_dict() for c in cs])