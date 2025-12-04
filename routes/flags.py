from __future__ import annotations
from typing import Optional
from flask import Blueprint, request, jsonify, abort, current_app
from flask_login import login_required, current_user
from services.feature_flags import flags
from models.core_models import FeatureFlag, FlagAuditLog
from models import db
import re

flags_bp = Blueprint("flags", __name__, url_prefix="/flags")

def is_admin_user():
    if not current_user.is_authenticated:
        return False
    return current_user.is_admin

def create_audit_log(flag_key: str, action: str, old_value: Optional[dict] = None, new_value: Optional[dict] = None):
    audit_log = FlagAuditLog(
        flag_key=flag_key,
        action=action,
        user_id=current_user.id if current_user.is_authenticated else "system",
        old_value=old_value,
        new_value=new_value,
        ip_address=request.remote_addr,
        user_agent=request.headers.get('User-Agent', '')[:255]
    )
    db.session.add(audit_log)
    return audit_log

def validate_flag_key(key: str) -> bool:
    if not key or len(key) > 80:
        return False
    if not re.match(r'^[a-zA-Z0-9_-]+$', key):
        return False
    return True

@flags_bp.get("/")
@login_required
def list_flags():
    try:
        flag_list = db.session.query(FeatureFlag).order_by(FeatureFlag.key).all()
        return jsonify({"flags": [f.to_dict() for f in flag_list], "success": True})
    except Exception as e:
        return jsonify({"error": str(e), "success": False}), 500

@flags_bp.post("/")
@login_required
def upsert_flag():
    if not is_admin_user():
        abort(403, "Admin access required")
    
    try:
        body = request.get_json(force=True)
        key = body.get("key", "").strip()
        enabled = bool(body.get("enabled", False))
        note = body.get("note", "").strip() if body.get("note") else None
        
        if not validate_flag_key(key):
            return jsonify({"error": "Invalid flag key. Use only alphanumeric, underscore, and hyphen characters.", "success": False}), 400
        
        if note and len(note) > 255:
            return jsonify({"error": "Note must be 255 characters or less.", "success": False}), 400
        
        flag = db.session.query(FeatureFlag).filter_by(key=key).first()
        
        if not flag:
            action = "create"
            old_value = None
            new_value = {"enabled": enabled, "note": note}
            flag = FeatureFlag(key=key, enabled=enabled, note=note)
            db.session.add(flag)
        else:
            action = "update"
            old_value = {"enabled": flag.enabled, "note": flag.note}
            new_value = {"enabled": enabled, "note": note}
            flag.enabled = enabled
            flag.note = note
        
        create_audit_log(key, action, old_value, new_value)
        db.session.commit()
        flags.invalidate_cache()
        
        # Broadcast via WebSocket if available
        try:
            from app import socketio
            socketio.emit('flag_updated', {
                'flag': flag.to_dict(),
                'action': action,
                'user_id': current_user.id
            }, namespace='/flags', broadcast=True)
        except Exception:
            pass  # Socket not available, continue
        
        return jsonify({"flag": flag.to_dict(), "success": True, "action": action})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e), "success": False}), 500

@flags_bp.patch("/<string:key>/toggle")
@login_required
def toggle_flag(key: str):
    if not is_admin_user():
        abort(403, "Admin access required")
    
    try:
        flag = db.session.query(FeatureFlag).filter_by(key=key).first()
        if not flag:
            return jsonify({"error": "Flag not found", "success": False}), 404
        
        old_value = {"enabled": flag.enabled, "note": flag.note}
        flag.enabled = not flag.enabled
        new_value = {"enabled": flag.enabled, "note": flag.note}
        
        create_audit_log(key, "toggle", old_value, new_value)
        db.session.commit()
        flags.invalidate_cache()
        
        # Broadcast via WebSocket if available
        try:
            from app import socketio
            socketio.emit('flag_updated', {
                'flag': flag.to_dict(),
                'action': 'toggle',
                'user_id': current_user.id
            }, namespace='/flags', broadcast=True)
        except Exception:
            pass
        
        return jsonify({"flag": flag.to_dict(), "success": True, "action": "toggle"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e), "success": False}), 500

@flags_bp.delete("/<string:key>")
@login_required
def delete_flag(key: str):
    if not is_admin_user():
        abort(403, "Admin access required")
    
    try:
        flag = db.session.query(FeatureFlag).filter_by(key=key).first()
        if not flag:
            return jsonify({"error": "Flag not found", "success": False}), 404
        
        old_value = {"enabled": flag.enabled, "note": flag.note}
        create_audit_log(key, "delete", old_value, None)
        
        db.session.delete(flag)
        db.session.commit()
        flags.invalidate_cache()
        
        # Broadcast via WebSocket if available
        try:
            from app import socketio
            socketio.emit('flag_deleted', {
                'key': key,
                'user_id': current_user.id
            }, namespace='/flags', broadcast=True)
        except Exception:
            pass
        
        return jsonify({"success": True, "deleted": key})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e), "success": False}), 500

@flags_bp.get("/<string:key>/history")
@login_required
def get_flag_history(key: str):
    try:
        audit_logs = db.session.query(FlagAuditLog).filter_by(flag_key=key).order_by(FlagAuditLog.created_at.desc()).limit(100).all()
        return jsonify({"history": [log.to_dict() for log in audit_logs], "success": True})
    except Exception as e:
        return jsonify({"error": str(e), "success": False}), 500
