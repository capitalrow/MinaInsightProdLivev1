"""
Usage Tracking Service for Mina - Phase 2 Cost Optimization

Tracks transcription API usage per user/session for:
- Cost monitoring and alerts
- Tier limit enforcement (Free: 5 hours/month)
- Usage analytics and reporting
"""
import logging
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from calendar import monthrange

from models import db
from models.core_models import TranscriptionUsage, UsageSummary, SubscriptionTier

logger = logging.getLogger(__name__)

WHISPER_COST_PER_MINUTE_USD = 0.006


def get_billing_period(user_id: str, subscription_start: Optional[datetime] = None) -> Tuple[datetime, datetime]:
    """
    Get the current billing period for a user.
    If subscription_start is provided, uses that as the anchor.
    Otherwise, uses the 1st of the current month.
    """
    now = datetime.utcnow()
    
    if subscription_start:
        day_of_month = min(subscription_start.day, 28)
        if now.day >= day_of_month:
            period_start = now.replace(day=day_of_month, hour=0, minute=0, second=0, microsecond=0)
            next_month = now.month + 1 if now.month < 12 else 1
            next_year = now.year if now.month < 12 else now.year + 1
            max_day = monthrange(next_year, next_month)[1]
            period_end = datetime(next_year, next_month, min(day_of_month, max_day), 0, 0, 0)
        else:
            prev_month = now.month - 1 if now.month > 1 else 12
            prev_year = now.year if now.month > 1 else now.year - 1
            max_day = monthrange(prev_year, prev_month)[1]
            period_start = datetime(prev_year, prev_month, min(day_of_month, max_day), 0, 0, 0)
            period_end = now.replace(day=day_of_month, hour=0, minute=0, second=0, microsecond=0)
    else:
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        next_month = now.month + 1 if now.month < 12 else 1
        next_year = now.year if now.month < 12 else now.year + 1
        period_end = datetime(next_year, next_month, 1, 0, 0, 0)
    
    return period_start, period_end


def estimate_audio_duration(audio_bytes: bytes, mime_type: Optional[str] = None) -> float:
    """
    Estimate audio duration from bytes.
    Uses heuristics based on typical compression ratios.
    
    Returns duration in seconds.
    """
    if not audio_bytes:
        return 0.0
    
    size_bytes = len(audio_bytes)
    mime = (mime_type or "").lower()
    
    if "webm" in mime or "opus" in mime:
        bytes_per_second = 6000
    elif "mp3" in mime or "mpeg" in mime:
        bytes_per_second = 16000
    elif "ogg" in mime:
        bytes_per_second = 8000
    elif "wav" in mime:
        bytes_per_second = 32000
    elif "flac" in mime:
        bytes_per_second = 50000
    else:
        bytes_per_second = 16000
    
    duration = size_bytes / bytes_per_second
    return max(0.1, duration)


def calculate_cost(duration_seconds: float) -> float:
    """Calculate cost in USD for audio duration."""
    duration_minutes = duration_seconds / 60.0
    return duration_minutes * WHISPER_COST_PER_MINUTE_USD


def track_transcription(
    user_id: str,
    audio_bytes: bytes,
    session_id: Optional[str] = None,
    transcription_type: str = 'final',
    model_used: str = 'whisper-1',
    api_latency_ms: Optional[int] = None,
    was_cached: bool = False,
    error_occurred: bool = False,
    error_message: Optional[str] = None,
    mime_type: Optional[str] = None,
    actual_duration: Optional[float] = None
) -> TranscriptionUsage:
    """
    Track a transcription API call.
    
    Args:
        user_id: User who made the request
        audio_bytes: Raw audio data
        session_id: Optional meeting session ID
        transcription_type: 'interim' or 'final'
        model_used: Whisper model name
        api_latency_ms: API response time in milliseconds
        was_cached: Whether result was served from cache
        error_occurred: Whether an error occurred
        error_message: Error details if any
        mime_type: Audio MIME type for duration estimation
        actual_duration: Actual audio duration if known
    
    Returns:
        TranscriptionUsage record
    """
    if actual_duration is not None:
        duration_seconds = actual_duration
    else:
        duration_seconds = estimate_audio_duration(audio_bytes, mime_type)
    
    cost_usd = 0.0 if was_cached or error_occurred else calculate_cost(duration_seconds)
    
    period_start, _ = get_billing_period(user_id)
    
    usage = TranscriptionUsage(
        user_id=user_id,
        session_id=session_id,
        audio_duration_seconds=duration_seconds,
        audio_size_bytes=len(audio_bytes) if audio_bytes else 0,
        model_used=model_used,
        api_latency_ms=api_latency_ms,
        cost_usd=cost_usd,
        transcription_type=transcription_type,
        was_cached=was_cached,
        error_occurred=error_occurred,
        error_message=error_message[:512] if error_message else None,
        billing_period_start=period_start
    )
    
    try:
        db.session.add(usage)
        db.session.commit()
        
        update_usage_summary(user_id, period_start)
        
        logger.debug(f"📊 Tracked usage: user={user_id}, duration={duration_seconds:.1f}s, cost=${cost_usd:.4f}")
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Failed to track usage: {e}")
    
    return usage


def update_usage_summary(user_id: str, period_start: datetime) -> Optional[UsageSummary]:
    """
    Update or create the usage summary for a billing period.
    """
    from services.subscription_service import get_user_tier
    
    try:
        tier = get_user_tier(user_id)
        tier_config = SubscriptionTier.get_tier_config(tier)
        hours_limit = tier_config.get('hours_per_month', 5)
        if hours_limit == -1:
            hours_limit = None
        
        period_end = period_start + timedelta(days=32)
        period_end = period_end.replace(day=1)
        
        summary = UsageSummary.query.filter_by(
            user_id=user_id,
            billing_period_start=period_start
        ).first()
        
        if not summary:
            summary = UsageSummary(
                user_id=user_id,
                billing_period_start=period_start,
                billing_period_end=period_end,
                tier=tier,
                hours_limit=hours_limit
            )
            db.session.add(summary)
        
        totals = db.session.query(
            db.func.sum(TranscriptionUsage.audio_duration_seconds).label('total_seconds'),
            db.func.sum(TranscriptionUsage.cost_usd).label('total_cost'),
            db.func.count(TranscriptionUsage.id).label('total_calls')
        ).filter(
            TranscriptionUsage.user_id == user_id,
            TranscriptionUsage.billing_period_start == period_start,
            TranscriptionUsage.was_cached == False,
            TranscriptionUsage.error_occurred == False
        ).first()
        
        summary.total_audio_seconds = totals.total_seconds or 0.0
        summary.total_api_calls = totals.total_calls or 0
        summary.total_cost_usd = totals.total_cost or 0.0
        summary.hours_used = summary.total_audio_seconds / 3600.0
        summary.tier = tier
        summary.hours_limit = hours_limit
        
        db.session.commit()
        
        return summary
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Failed to update usage summary: {e}")
        return None


def get_user_usage(user_id: str) -> Dict[str, Any]:
    """
    Get current usage for a user in the current billing period.
    """
    from services.subscription_service import get_user_tier
    
    period_start, period_end = get_billing_period(user_id)
    
    summary = UsageSummary.query.filter_by(
        user_id=user_id,
        billing_period_start=period_start
    ).first()
    
    tier = get_user_tier(user_id)
    tier_config = SubscriptionTier.get_tier_config(tier)
    hours_limit = tier_config.get('hours_per_month', 5)
    
    if summary:
        hours_used = summary.hours_used
        total_cost = summary.total_cost_usd
        api_calls = summary.total_api_calls
    else:
        hours_used = 0.0
        total_cost = 0.0
        api_calls = 0
    
    if hours_limit == -1:
        percent_used = 0.0
        hours_remaining = float('inf')
        limit_reached = False
    else:
        percent_used = (hours_used / hours_limit * 100) if hours_limit > 0 else 0
        hours_remaining = max(0, hours_limit - hours_used)
        limit_reached = hours_used >= hours_limit
    
    return {
        'user_id': user_id,
        'tier': tier,
        'tier_name': tier_config.get('name', 'Free'),
        'billing_period_start': period_start.isoformat(),
        'billing_period_end': period_end.isoformat(),
        'hours_used': round(hours_used, 2),
        'hours_limit': hours_limit if hours_limit != -1 else 'unlimited',
        'hours_remaining': round(hours_remaining, 2) if hours_remaining != float('inf') else 'unlimited',
        'percent_used': round(percent_used, 1),
        'limit_reached': limit_reached,
        'total_cost_usd': round(total_cost, 4),
        'api_calls': api_calls
    }


def check_usage_limit(user_id: str) -> Tuple[bool, Dict[str, Any]]:
    """
    Check if user has remaining usage quota.
    
    Returns:
        Tuple of (can_transcribe: bool, usage_info: dict)
    """
    usage = get_user_usage(user_id)
    
    if usage['hours_limit'] == 'unlimited':
        return True, usage
    
    can_transcribe = not usage['limit_reached']
    
    return can_transcribe, usage


def get_usage_alerts(user_id: str) -> list:
    """
    Get usage alerts for a user (80%, 90%, 100% thresholds).
    """
    usage = get_user_usage(user_id)
    alerts = []
    
    if usage['hours_limit'] == 'unlimited':
        return alerts
    
    percent = usage['percent_used']
    
    if percent >= 100:
        alerts.append({
            'level': 'error',
            'message': f"You've reached your {usage['hours_limit']} hour monthly limit. Upgrade to continue transcribing.",
            'percent': percent,
            'action': 'upgrade'
        })
    elif percent >= 90:
        alerts.append({
            'level': 'warning',
            'message': f"You've used {percent:.0f}% of your monthly transcription limit.",
            'percent': percent,
            'action': 'consider_upgrade'
        })
    elif percent >= 80:
        alerts.append({
            'level': 'info',
            'message': f"You've used {percent:.0f}% of your monthly transcription limit.",
            'percent': percent,
            'action': None
        })
    
    return alerts


def get_admin_usage_stats() -> Dict[str, Any]:
    """
    Get aggregate usage statistics for admin dashboard.
    """
    now = datetime.utcnow()
    period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    monthly_totals = db.session.query(
        db.func.sum(TranscriptionUsage.audio_duration_seconds).label('total_seconds'),
        db.func.sum(TranscriptionUsage.cost_usd).label('total_cost'),
        db.func.count(TranscriptionUsage.id).label('total_calls'),
        db.func.count(db.func.distinct(TranscriptionUsage.user_id)).label('unique_users')
    ).filter(
        TranscriptionUsage.billing_period_start == period_start,
        TranscriptionUsage.error_occurred == False
    ).first()
    
    daily_totals = db.session.query(
        db.func.sum(TranscriptionUsage.audio_duration_seconds).label('total_seconds'),
        db.func.sum(TranscriptionUsage.cost_usd).label('total_cost'),
        db.func.count(TranscriptionUsage.id).label('total_calls')
    ).filter(
        TranscriptionUsage.created_at >= today_start,
        TranscriptionUsage.error_occurred == False
    ).first()
    
    error_count = TranscriptionUsage.query.filter(
        TranscriptionUsage.billing_period_start == period_start,
        TranscriptionUsage.error_occurred == True
    ).count()
    
    avg_latency = db.session.query(
        db.func.avg(TranscriptionUsage.api_latency_ms)
    ).filter(
        TranscriptionUsage.billing_period_start == period_start,
        TranscriptionUsage.api_latency_ms.isnot(None)
    ).scalar()
    
    return {
        'period': 'current_month',
        'period_start': period_start.isoformat(),
        'monthly': {
            'total_hours': round((monthly_totals.total_seconds or 0) / 3600, 2),
            'total_cost_usd': round(monthly_totals.total_cost or 0, 2),
            'total_api_calls': monthly_totals.total_calls or 0,
            'unique_users': monthly_totals.unique_users or 0
        },
        'today': {
            'total_hours': round((daily_totals.total_seconds or 0) / 3600, 2),
            'total_cost_usd': round(daily_totals.total_cost or 0, 4),
            'total_api_calls': daily_totals.total_calls or 0
        },
        'errors': {
            'monthly_error_count': error_count
        },
        'performance': {
            'avg_latency_ms': round(avg_latency or 0, 0)
        }
    }
