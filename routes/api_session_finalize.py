"""
File: /routes/api_session_finalize.py
Purpose: Safely finalize an active transcription session once recording stops.
Author: GPT-5 CTO Assistant for Chinyemba Malowa (Crown+ Fix Pack – Oct 2025)
---------------------------------------------------------------------------
This endpoint marks a Session as 'completed', calculates core metrics
(total segments, avg confidence, total duration), commits them,
and invalidates cached analytics/dashboard data.
---------------------------------------------------------------------------
"""

from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from flask import current_app as app
from models import db
from services.cache import cache
from datetime import datetime
from sqlalchemy import func
from models import Session, Segment
from models.metrics import SessionMetric
import logging
logger = logging.getLogger(__name__)

api_session_finalize_bp = Blueprint("api_session_finalize", __name__, url_prefix="/api/sessions")


@api_session_finalize_bp.route("/<external_id>/complete", methods=["POST"])
@login_required
def finalize_session(external_id: str):
    """
    🎯 Finalize a transcription session and update analytics visibility.
    Expected payload: { "force": bool (optional) }
    """
    try:
        logger.info(f"🔹 Finalizing session: {external_id}")
        session_obj: Session | None = (
            db.session.query(Session)
            .filter_by(external_id=external_id)
            .first()
        )

        if not session_obj:
            return jsonify({"error": "Session not found"}), 404

        # Skip if already finalized unless force=True
        request_data = request.get_json() or {}
        if session_obj.status == "completed" and not request_data.get("force", False):
            return jsonify({"message": "Session already finalized"}), 200

        # --- Aggregate segment metrics -------------------------------------
        segments = db.session.query(Segment).filter_by(session_id=session_obj.id, kind="final").all()
        total_segments = len(segments)
        avg_conf = float(sum([s.avg_confidence or 0 for s in segments]) / total_segments) if total_segments else 0.0
        total_dur = float(sum([(s.end_ms or 0) - (s.start_ms or 0) for s in segments]) / 1000.0)

        # --- Update session fields ----------------------------------------
        session_obj.status = "completed"
        session_obj.completed_at = datetime.utcnow()
        session_obj.total_segments = total_segments
        session_obj.average_confidence = round(avg_conf, 4)
        session_obj.total_duration = total_dur

        db.session.add(session_obj)

        # --- Optional: Update or create SessionMetric row -----------------
        metric = db.session.query(SessionMetric).filter_by(session_id=session_obj.id).first()
        if not metric:
            metric = SessionMetric(session_id=session_obj.id)
        # SessionMetric has different field names, use available fields
        metric.total_chunks = total_segments
        # Other metrics can be calculated from chunk data later
        db.session.add(metric)

        # --- Commit -------------------------------------------------------
        db.session.commit()
        logger.info(f"✅ Session {external_id} finalized successfully.")

        # --- Cache invalidation -------------------------------------------
        try:
            cache.delete_prefix("analytics")  # assuming cache supports prefix deletion
            logger.info("🧹 Analytics cache invalidated.")
        except Exception as ce:
            logger.warning(f"Cache clear failed: {ce}")
        
        # 🚀 CROWN+ Event Sequencing: Trigger post-transcription pipeline
        pipeline_task_id = None
        try:
            from services.post_transcription_orchestrator import PostTranscriptionOrchestrator
            orchestrator = PostTranscriptionOrchestrator()
            logger.info(f"[API] 🎬 Starting post-transcription pipeline for: {external_id}")
            
            # Submit to background task manager (non-blocking)
            # Events will stream back via WebSocket as each stage completes
            pipeline_task_id = orchestrator.process_session_async(external_id)
            
            logger.info(f"[API] ✅ Pipeline submitted to background (task_id={pipeline_task_id})")
                
        except Exception as pipeline_error:
            # Graceful degradation - log error but don't fail the response
            logger.error(f"[API] ❌ Post-transcription pipeline failed for {external_id}: {pipeline_error}", exc_info=True)

        return jsonify({
            "message": "Session finalized successfully",
            "session_id": session_obj.id,
            "external_id": external_id,
            "total_segments": total_segments,
            "average_confidence": avg_conf,
            "total_duration": total_dur,
            "pipeline_task_id": pipeline_task_id
        }), 200

    except Exception as e:
        logger.error(f"❌ Finalization failed for {external_id}: {e}", exc_info=True)
        db.session.rollback()
        return jsonify({"error": "Internal server error"}), 500