from __future__ import annotations
from flask import Blueprint, request, jsonify, abort
from models.organization import Team, TeamMembership, TeamRole
from models import db

teams_bp = Blueprint("teams", __name__, url_prefix="/teams")

@teams_bp.post("/")
def create_team():
    body = request.get_json(force=True)
    name = body.get("name"); owner_id = body.get("owner_id")
    if not name or not owner_id:
        abort(400, "name and owner_id required")
    t = Team(name=name, owner_id=owner_id)
    db.session.add(t); db.session.commit()
    m = TeamMembership(team_id=t.id, user_id=owner_id, role=TeamRole.TEAM_LEAD)
    db.session.add(m); db.session.commit()
    return jsonify({"id": t.id, "name": t.name})

@teams_bp.post("/<int:team_id>/invite")
def invite(team_id: int):
    body = request.get_json(force=True)
    user_id = body.get("user_id"); role = body.get("role","member")
    if not user_id:
        abort(400, "user_id required")
    team_role = TeamRole.MEMBER if role == "member" else TeamRole.ADMIN
    m = TeamMembership(team_id=team_id, user_id=user_id, role=team_role)
    db.session.add(m); db.session.commit()
    return jsonify({"team_id": team_id, "user_id": user_id, "role": role})

@teams_bp.get("/<int:team_id>/members")
def members(team_id: int):
    ms = TeamMembership.query.filter_by(team_id=team_id).all()
    return jsonify([{"user_id": m.user_id, "role": m.role.value} for m in ms])