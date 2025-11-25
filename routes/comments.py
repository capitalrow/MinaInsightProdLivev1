from __future__ import annotations
from flask import Blueprint, request, jsonify, abort
from models import Comment, db

comments_bp = Blueprint("comments", __name__, url_prefix="/comments")

@comments_bp.post("/")
def add_comment():
    b = request.get_json(force=True)
    segment_id = b.get("segment_id"); user_id = b.get("user_id"); text = b.get("text")
    if not all([segment_id, user_id, text]):
        abort(400, "segment_id, user_id, text required")
    c = Comment(segment_id=segment_id, user_id=user_id, text=text)
    db.session.add(c); db.session.commit()
    return jsonify({"id": c.id})

@comments_bp.get("/by-segment/<int:segment_id>")
def list_comments(segment_id: int):
    cs = Comment.query.filter_by(segment_id=segment_id).order_by(Comment.created_at.asc()).all()
    return jsonify([c.to_dict() for c in cs])