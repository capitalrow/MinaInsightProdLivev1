"""
Analytics API Routes
REST API endpoints for analytics data, insights, and performance metrics.
"""

from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from models import db, Analytics, Meeting, Task, Participant, User
from services.analytics_service import analytics_service
from middleware.cache_decorator import cache_response
from utils.etag_helper import with_etag, compute_collection_etag
from datetime import datetime, timedelta, date
from sqlalchemy import func, desc, and_
from typing import Dict, List
import json


api_analytics_bp = Blueprint('api_analytics', __name__, url_prefix='/api/analytics')


@api_analytics_bp.route('/overview', methods=['GET'])
@with_etag
@cache_response(ttl=1800, prefix='analytics')  # 30 min cache
@login_required
def get_analytics_overview():
    """Get analytics overview for current workspace."""
    try:
        days = request.args.get('days', 30, type=int)
        
        # Get workspace analytics summary
        summary = analytics_service.get_workspace_analytics_summary(
            current_user.workspace_id, 
            days=days
        )
        
        return jsonify({
            'success': True,
            'overview': summary['summary'],
            'period_days': days
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@api_analytics_bp.route('/meetings/<int:meeting_id>', methods=['GET'])
@cache_response(ttl=3600, prefix='analytics')  # 1 hour cache
@login_required
def get_meeting_analytics(meeting_id):
    """Get detailed analytics for a specific meeting."""
    try:
        # Verify meeting belongs to user's workspace
        meeting = db.session.query(Meeting).filter_by(
            id=meeting_id,
            workspace_id=current_user.workspace_id
        ).first()
        
        if not meeting:
            return jsonify({'success': False, 'message': 'Meeting not found'}), 404
        
        # Get analytics record
        analytics = db.session.query(Analytics).filter_by(meeting_id=meeting_id).first()
        
        if not analytics or not analytics.is_analysis_complete:
            return jsonify({
                'success': False, 
                'message': 'Analytics not available. Please process the meeting first.'
            }), 404
        
        return jsonify({
            'success': True,
            'analytics': analytics.to_dict(include_detailed_data=True),
            'meeting': meeting.to_dict()
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@api_analytics_bp.route('/dashboard', methods=['GET'])
@with_etag
@cache_response(ttl=600, prefix='analytics')  # 10 min cache
@login_required
def get_dashboard_analytics():
    """Get analytics data for dashboard widgets."""
    try:
        workspace_id = current_user.workspace_id
        days = request.args.get('days', 7, type=int)
        cutoff_date = datetime.now() - timedelta(days=days)
        
        # Get recent analytics with eager loading to prevent N+1
        from sqlalchemy.orm import joinedload
        
        recent_analytics = db.session.query(Analytics).join(Meeting).filter(
            Meeting.workspace_id == workspace_id,
            Meeting.created_at >= cutoff_date,
            Analytics.analysis_status == 'completed'
        ).options(
            joinedload(Analytics.meeting)
        ).order_by(desc(Analytics.created_at)).limit(10).all()
        
        # Calculate averages
        if recent_analytics:
            avg_effectiveness = sum(a.meeting_effectiveness_score or 0 for a in recent_analytics) / len(recent_analytics)
            avg_engagement = sum(a.overall_engagement_score or 0 for a in recent_analytics) / len(recent_analytics)
            avg_sentiment = sum(a.overall_sentiment_score or 0 for a in recent_analytics) / len(recent_analytics)
            avg_duration = sum(a.total_duration_minutes or 0 for a in recent_analytics) / len(recent_analytics)
        else:
            avg_effectiveness = avg_engagement = avg_sentiment = avg_duration = 0
        
        # Get productivity metrics
        total_tasks_created = sum(a.action_items_created or 0 for a in recent_analytics)
        total_decisions_made = sum(a.decisions_made_count or 0 for a in recent_analytics)
        
        # Meeting trends - Single query with GROUP BY to prevent N+1 (was 7-30 queries, now 1)
        from sqlalchemy import cast, Date
        
        trend_data = db.session.query(
            cast(Meeting.created_at, Date).label('date'),
            func.count(Meeting.id).label('meetings')
        ).filter(
            Meeting.workspace_id == workspace_id,
            Meeting.created_at >= cutoff_date
        ).group_by(
            cast(Meeting.created_at, Date)
        ).order_by(
            cast(Meeting.created_at, Date)
        ).all()
        
        # Create date map for O(1) lookup
        trend_map = {row.date: row.meetings for row in trend_data}
        
        # Build complete trend with zeros for missing days
        meeting_trend = []
        for i in range(days):
            day = (datetime.now() - timedelta(days=i)).date()
            meeting_trend.append({
                'date': day.strftime('%Y-%m-%d'),
                'meetings': trend_map.get(day, 0)
            })
        
        meeting_trend.reverse()
        
        return jsonify({
            'success': True,
            'dashboard': {
                'averages': {
                    'effectiveness': round(avg_effectiveness * 100, 1),
                    'engagement': round(avg_engagement * 100, 1),
                    'sentiment': round(avg_sentiment * 100, 1),
                    'duration_minutes': round(avg_duration, 1)
                },
                'productivity': {
                    'total_tasks_created': total_tasks_created,
                    'total_decisions_made': total_decisions_made,
                    'avg_tasks_per_meeting': round(total_tasks_created / len(recent_analytics), 1) if recent_analytics else 0,
                    'avg_decisions_per_meeting': round(total_decisions_made / len(recent_analytics), 1) if recent_analytics else 0
                },
                'trends': {
                    'meeting_frequency': meeting_trend
                },
                'recent_analytics': [a.to_dict() for a in recent_analytics[:5]],
                'period_days': days
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@api_analytics_bp.route('/engagement', methods=['GET'])
@cache_response(ttl=1800, prefix='analytics')  # 30 min cache
@login_required
def get_engagement_analytics():
    """Get participant engagement analytics."""
    try:
        workspace_id = current_user.workspace_id
        days = request.args.get('days', 30, type=int)
        cutoff_date = datetime.now() - timedelta(days=days)
        
        # Get engagement data from analytics
        analytics = db.session.query(Analytics).join(Meeting).filter(
            Meeting.workspace_id == workspace_id,
            Meeting.created_at >= cutoff_date,
            Analytics.analysis_status == 'completed',
            Analytics.overall_engagement_score.isnot(None)
        ).all()
        
        if not analytics:
            return jsonify({
                'success': True,
                'engagement': {
                    'average_score': 0,
                    'trend': [],
                    'distribution': {},
                    'top_participants': []
                }
            })
        
        # Calculate engagement metrics
        engagement_scores = [a.overall_engagement_score for a in analytics if a.overall_engagement_score is not None]
        avg_engagement = sum(engagement_scores) / len(engagement_scores) if engagement_scores else 0
        
        # Engagement distribution
        score_ranges = {
            'low': len([s for s in engagement_scores if s is not None and s < 0.4]),
            'medium': len([s for s in engagement_scores if s is not None and 0.4 <= s < 0.7]),
            'high': len([s for s in engagement_scores if s is not None and s >= 0.7])
        }
        
        # Get top participants by engagement
        top_participants = db.session.query(
            Participant.name,
            func.avg(Participant.engagement_score).label('avg_engagement'),
            func.count(Participant.id).label('meeting_count')
        ).join(Meeting).filter(
            Meeting.workspace_id == workspace_id,
            Meeting.created_at >= cutoff_date,
            Participant.engagement_score.isnot(None)
        ).group_by(Participant.name).order_by(
            desc('avg_engagement')
        ).limit(5).all()
        
        return jsonify({
            'success': True,
            'engagement': {
                'average_score': round(avg_engagement * 100, 1),
                'total_meetings': len(analytics),
                'distribution': score_ranges,
                'top_participants': [
                    {
                        'name': name,
                        'avg_engagement': round(float(avg_eng) * 100, 1),
                        'meeting_count': count
                    } for name, avg_eng, count in top_participants
                ]
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@api_analytics_bp.route('/productivity', methods=['GET'])
@login_required
def get_productivity_analytics():
    """Get productivity metrics and task analytics."""
    try:
        workspace_id = current_user.workspace_id
        days = request.args.get('days', 30, type=int)
        cutoff_date = datetime.now() - timedelta(days=days)
        
        # Get meetings from the period
        meetings = db.session.query(Meeting).filter(
            Meeting.workspace_id == workspace_id,
            Meeting.created_at >= cutoff_date
        ).all()
        
        meeting_ids = [m.id for m in meetings]
        
        # Task analytics
        total_tasks = db.session.query(Task).filter(Task.meeting_id.in_(meeting_ids)).count()
        completed_tasks = db.session.query(Task).filter(
            Task.meeting_id.in_(meeting_ids),
            Task.status == 'completed'
        ).count()
        
        # Tasks by priority
        task_priority_dist = db.session.query(
            Task.priority,
            func.count(Task.id).label('count')
        ).filter(Task.meeting_id.in_(meeting_ids)).group_by(Task.priority).all()
        
        priority_distribution = {priority: count for priority, count in task_priority_dist}
        
        # Average completion time for completed tasks
        completed_task_times = []
        for task in db.session.query(Task).filter(
            Task.meeting_id.in_(meeting_ids),
            Task.status == 'completed',
            Task.completed_at.isnot(None)
        ).all():
            if task.completed_at and task.created_at:
                completion_time = (task.completed_at - task.created_at).days
                completed_task_times.append(completion_time)
        
        avg_completion_days = sum(completed_task_times) / len(completed_task_times) if completed_task_times else 0
        
        # Decision making analytics
        decisions_made = db.session.query(
            func.sum(Analytics.decisions_made_count)
        ).join(Meeting).filter(
            Meeting.workspace_id == workspace_id,
            Meeting.created_at >= cutoff_date,
            Analytics.decisions_made_count.isnot(None)
        ).scalar() or 0
        
        # Meeting efficiency
        efficiency_scores = db.session.query(Analytics).join(Meeting).filter(
            Meeting.workspace_id == workspace_id,
            Meeting.created_at >= cutoff_date,
            Analytics.meeting_efficiency_score.isnot(None)
        ).all()
        
        avg_efficiency = sum(a.meeting_efficiency_score for a in efficiency_scores if a.meeting_efficiency_score is not None) / len(efficiency_scores) if efficiency_scores else 0
        
        return jsonify({
            'success': True,
            'productivity': {
                'tasks': {
                    'total_created': total_tasks,
                    'total_completed': completed_tasks,
                    'completion_rate': round((completed_tasks / total_tasks * 100), 1) if total_tasks > 0 else 0,
                    'avg_completion_days': round(avg_completion_days, 1),
                    'priority_distribution': priority_distribution
                },
                'decisions': {
                    'total_made': int(decisions_made),
                    'avg_per_meeting': round(decisions_made / len(meetings), 1) if meetings else 0
                },
                'efficiency': {
                    'average_score': round(avg_efficiency * 100, 1),
                    'meetings_analyzed': len(efficiency_scores)
                },
                'period_days': days,
                'total_meetings': len(meetings)
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@api_analytics_bp.route('/insights', methods=['GET'])
@login_required
def get_insights():
    """Get AI-generated insights and recommendations."""
    try:
        workspace_id = current_user.workspace_id
        days = request.args.get('days', 30, type=int)
        cutoff_date = datetime.now() - timedelta(days=days)
        
        # Get recent analytics with insights
        analytics_with_insights = db.session.query(Analytics).join(Meeting).filter(
            Meeting.workspace_id == workspace_id,
            Meeting.created_at >= cutoff_date,
            Analytics.analysis_status == 'completed',
            Analytics.insights_generated.isnot(None)
        ).order_by(desc(Analytics.created_at)).limit(10).all()
        
        # Collect all insights and recommendations
        all_insights = []
        all_recommendations = []
        
        for analytics in analytics_with_insights:
            if analytics.insights_generated:
                all_insights.extend(analytics.insights_generated)
            if analytics.recommendations:
                all_recommendations.extend(analytics.recommendations)
        
        # Get recent insights (last 5)
        recent_insights = all_insights[-5:] if all_insights else []
        recent_recommendations = all_recommendations[-5:] if all_recommendations else []
        
        return jsonify({
            'success': True,
            'insights': {
                'recent_insights': recent_insights,
                'recent_recommendations': recent_recommendations,
                'total_insights': len(all_insights),
                'total_recommendations': len(all_recommendations),
                'meetings_with_insights': len(analytics_with_insights)
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@api_analytics_bp.route('/sentiment', methods=['GET'])
@login_required
def get_sentiment_analytics():
    """Get sentiment analysis data."""
    try:
        workspace_id = current_user.workspace_id
        days = request.args.get('days', 30, type=int)
        cutoff_date = datetime.now() - timedelta(days=days)
        
        # Get sentiment data
        analytics = db.session.query(Analytics).join(Meeting).filter(
            Meeting.workspace_id == workspace_id,
            Meeting.created_at >= cutoff_date,
            Analytics.analysis_status == 'completed',
            Analytics.overall_sentiment_score.isnot(None)
        ).all()
        
        if not analytics:
            return jsonify({
                'success': True,
                'sentiment': {
                    'average_score': 0,
                    'trend': [],
                    'distribution': {},
                    'positive_meetings': 0,
                    'negative_meetings': 0
                }
            })
        
        sentiment_scores = [a.overall_sentiment_score for a in analytics if a.overall_sentiment_score is not None]
        avg_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0
        
        # Sentiment distribution
        positive_meetings = len([s for s in sentiment_scores if s is not None and s > 0.1])
        neutral_meetings = len([s for s in sentiment_scores if s is not None and -0.1 <= s <= 0.1])
        negative_meetings = len([s for s in sentiment_scores if s is not None and s < -0.1])
        
        # Sentiment trend over time
        sentiment_trend = []
        for analytics_record in sorted(analytics, key=lambda x: x.created_at):
            if analytics_record.overall_sentiment_score is not None:
                sentiment_trend.append({
                    'date': analytics_record.created_at.strftime('%Y-%m-%d'),
                    'score': round(analytics_record.overall_sentiment_score * 100, 1),
                    'meeting_title': analytics_record.meeting.title
                })
        
        return jsonify({
            'success': True,
            'sentiment': {
                'average_score': round(avg_sentiment * 100, 1),
                'distribution': {
                    'positive': positive_meetings,
                    'neutral': neutral_meetings,
                    'negative': negative_meetings
                },
                'trend': sentiment_trend,
                'total_meetings': len(analytics)
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@api_analytics_bp.route('/communication', methods=['GET'])
@login_required
def get_communication_analytics():
    """Get communication patterns and participation analytics."""
    try:
        workspace_id = current_user.workspace_id
        days = request.args.get('days', 30, type=int)
        cutoff_date = datetime.now() - timedelta(days=days)
        
        # Get meetings and participants
        meetings = db.session.query(Meeting).filter(
            Meeting.workspace_id == workspace_id,
            Meeting.created_at >= cutoff_date
        ).all()
        
        meeting_ids = [m.id for m in meetings]
        
        # Participation statistics
        participants = db.session.query(Participant).filter(
            Participant.meeting_id.in_(meeting_ids)
        ).all()
        
        # Calculate communication metrics
        total_talk_time = sum(p.talk_time_seconds or 0 for p in participants)
        total_words = sum(p.word_count or 0 for p in participants)
        total_questions = sum(p.question_count or 0 for p in participants)
        total_interruptions = sum(p.interruption_count or 0 for p in participants)
        
        # Most active participants
        participant_stats = {}
        for participant in participants:
            name = participant.name
            if name not in participant_stats:
                participant_stats[name] = {
                    'talk_time': 0,
                    'word_count': 0,
                    'question_count': 0,
                    'segment_count': 0,
                    'meeting_count': 0
                }
            
            participant_stats[name]['talk_time'] += participant.talk_time_seconds or 0
            participant_stats[name]['word_count'] += participant.word_count or 0
            participant_stats[name]['question_count'] += participant.question_count or 0
            participant_stats[name]['segment_count'] += 0  # segment_count not tracked in Participant model
            participant_stats[name]['meeting_count'] += 1
        
        # Sort by total talk time
        top_speakers = sorted(
            participant_stats.items(),
            key=lambda x: x[1]['talk_time'],
            reverse=True
        )[:5]
        
        # Calculate averages per meeting
        num_meetings = len(meetings) if meetings else 1
        
        return jsonify({
            'success': True,
            'communication': {
                'totals': {
                    'total_talk_time_hours': round(total_talk_time / 3600, 1),
                    'total_words': total_words,
                    'total_questions': total_questions,
                    'total_interruptions': total_interruptions
                },
                'averages': {
                    'avg_talk_time_per_meeting': round(total_talk_time / num_meetings / 60, 1),
                    'avg_words_per_meeting': round(total_words / num_meetings, 1),
                    'avg_questions_per_meeting': round(total_questions / num_meetings, 1),
                    'avg_participants_per_meeting': round(len(participants) / num_meetings, 1) if meetings else 0
                },
                'top_speakers': [
                    {
                        'name': name,
                        'talk_time_minutes': round(stats['talk_time'] / 60, 1),
                        'word_count': stats['word_count'],
                        'question_count': stats['question_count'],
                        'segment_count': stats['segment_count'],
                        'meeting_count': stats['meeting_count']
                    } for name, stats in top_speakers
                ],
                'period_days': days,
                'total_meetings': len(meetings)
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@api_analytics_bp.route('/meetings/<int:meeting_id>/topic-trends', methods=['GET'])
@cache_response(ttl=3600, prefix='analytics')
@login_required
def get_topic_trends(meeting_id):
    """Get topic trend analysis with timeline visualization data."""
    try:
        import asyncio
        
        # Verify meeting belongs to user's workspace
        meeting = db.session.query(Meeting).filter_by(
            id=meeting_id,
            workspace_id=current_user.workspace_id
        ).first()
        
        if not meeting:
            return jsonify({'success': False, 'message': 'Meeting not found'}), 404
        
        # Get topic trends using async service method
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            trends = loop.run_until_complete(
                analytics_service.get_topic_trends(meeting)
            )
        finally:
            loop.close()
        
        return jsonify({
            'success': True,
            'trends': trends
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@api_analytics_bp.route('/meetings/<int:meeting_id>/questions', methods=['GET'])
@cache_response(ttl=3600, prefix='analytics')
@login_required
def get_question_analytics(meeting_id):
    """Get question/answer tracking analytics for a meeting."""
    try:
        import asyncio
        
        # Verify meeting belongs to user's workspace
        meeting = db.session.query(Meeting).filter_by(
            id=meeting_id,
            workspace_id=current_user.workspace_id
        ).first()
        
        if not meeting:
            return jsonify({'success': False, 'message': 'Meeting not found'}), 404
        
        # Get Q&A analytics using async service method
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            qa_data = loop.run_until_complete(
                analytics_service.get_question_answer_analytics(meeting)
            )
        finally:
            loop.close()
        
        return jsonify({
            'success': True,
            'qa_analytics': qa_data
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@api_analytics_bp.route('/meetings/<int:meeting_id>/action-items-completion', methods=['GET'])
@cache_response(ttl=600, prefix='analytics')
@login_required
def get_action_items_completion(meeting_id):
    """Get action items completion rate and status breakdown."""
    try:
        # Verify meeting belongs to user's workspace
        meeting = db.session.query(Meeting).filter_by(
            id=meeting_id,
            workspace_id=current_user.workspace_id
        ).first()
        
        if not meeting:
            return jsonify({'success': False, 'message': 'Meeting not found'}), 404
        
        # Get all tasks for this meeting
        tasks = db.session.query(Task).filter_by(meeting_id=meeting_id).all()
        
        if not tasks:
            return jsonify({
                'success': True,
                'completion': {
                    'total': 0,
                    'completed': 0,
                    'in_progress': 0,
                    'todo': 0,
                    'completion_rate': 0,
                    'tasks': []
                }
            })
        
        # Calculate status breakdown
        status_counts = {
            'completed': 0,
            'in_progress': 0,
            'todo': 0
        }
        
        task_list = []
        for task in tasks:
            status = task.status or 'todo'
            status_counts[status] = status_counts.get(status, 0) + 1
            
            task_list.append({
                'id': task.id,
                'title': task.title,
                'status': status,
                'priority': task.priority,
                'assignee': task.assigned_to.username if task.assigned_to else None,
                'due_date': task.due_date.isoformat() if task.due_date else None,
                'created_at': task.created_at.isoformat() if task.created_at else None
            })
        
        completion_rate = (status_counts['completed'] / len(tasks)) * 100 if tasks else 0
        
        return jsonify({
            'success': True,
            'completion': {
                'total': len(tasks),
                'completed': status_counts['completed'],
                'in_progress': status_counts['in_progress'],
                'todo': status_counts['todo'],
                'completion_rate': round(completion_rate, 1),
                'tasks': task_list
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@api_analytics_bp.route('/export', methods=['GET'])
@login_required
def export_analytics():
    """Export analytics data for external analysis."""
    try:
        workspace_id = current_user.workspace_id
        days = request.args.get('days', 30, type=int)
        format_type = request.args.get('format', 'json')  # json or csv
        
        if format_type not in ['json', 'csv']:
            return jsonify({'success': False, 'message': 'Invalid format. Use json or csv'}), 400
        
        cutoff_date = datetime.now() - timedelta(days=days)
        
        # Get comprehensive analytics data
        analytics = db.session.query(Analytics).join(Meeting).filter(
            Meeting.workspace_id == workspace_id,
            Meeting.created_at >= cutoff_date,
            Analytics.analysis_status == 'completed'
        ).all()
        
        export_data = []
        for analytics_record in analytics:
            data = analytics_record.to_dict(include_detailed_data=True)
            data['meeting_info'] = analytics_record.meeting.to_dict()
            export_data.append(data)
        
        if format_type == 'json':
            return jsonify({
                'success': True,
                'data': export_data,
                'export_info': {
                    'workspace_id': workspace_id,
                    'period_days': days,
                    'exported_at': datetime.now().isoformat(),
                    'record_count': len(export_data)
                }
            })
        
        # CSV format would require additional processing
        # For now, return JSON with instructions
        return jsonify({
            'success': False,
            'message': 'CSV export not yet implemented. Use format=json for now.'
        }), 501
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@api_analytics_bp.route('/header', methods=['GET'])
@login_required
def get_analytics_header():
    """
    CROWN⁵+ ETag reconciliation endpoint.
    Returns lightweight header with ETag for cache validation.
    Supports If-None-Match for 304 Not Modified responses.
    """
    try:
        import hashlib
        
        workspace_id = current_user.workspace_id
        
        # Get latest analytics metadata for ETag computation
        latest_analytics = db.session.query(
            func.max(Analytics.updated_at),
            func.count(Analytics.id)
        ).join(Meeting).filter(
            Meeting.workspace_id == workspace_id,
            Analytics.analysis_status == 'completed'
        ).first()
        
        # Use deterministic fallback for empty data (fixed epoch, not now())
        last_updated = latest_analytics[0]
        count = latest_analytics[1] or 0
        
        # Use fixed epoch for empty workspaces to ensure stable ETag
        if last_updated is None:
            last_updated_str = '1970-01-01T00:00:00'
        else:
            last_updated_str = last_updated.isoformat()
        
        etag_source = f"{workspace_id}:{last_updated_str}:{count}"
        etag = hashlib.md5(etag_source.encode()).hexdigest()
        
        # Check If-None-Match header
        if_none_match = request.headers.get('If-None-Match', '').strip('"')
        if if_none_match == etag:
            return '', 304  # Not Modified
        
        response = jsonify({
            'success': True,
            'last_updated': last_updated_str,
            'analytics_count': count,
            'workspace_id': workspace_id
        })
        
        response.headers['ETag'] = f'"{etag}"'
        response.headers['Cache-Control'] = 'private, must-revalidate'
        
        return response
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@api_analytics_bp.route('/checksum', methods=['GET'])
@login_required
def get_analytics_checksum():
    """
    CROWN⁵+ Checksum validation endpoint.
    Returns lightweight checksum for idle sync drift detection.
    """
    try:
        import hashlib
        
        workspace_id = current_user.workspace_id
        days = request.args.get('days', 30, type=int)
        cutoff_date = datetime.now() - timedelta(days=days)
        
        # Get distinct meeting count (separate query to avoid join duplication)
        meeting_count = db.session.query(
            func.count(Meeting.id)
        ).filter(
            Meeting.workspace_id == workspace_id,
            Meeting.created_at >= cutoff_date
        ).scalar() or 0
        
        # Get task count for workspace meetings
        task_count = db.session.query(
            func.count(Task.id)
        ).join(Meeting, Task.meeting_id == Meeting.id).filter(
            Meeting.workspace_id == workspace_id,
            Meeting.created_at >= cutoff_date
        ).scalar() or 0
        
        # Get latest update timestamps
        last_meeting_update = db.session.query(
            func.max(Meeting.updated_at)
        ).filter(
            Meeting.workspace_id == workspace_id,
            Meeting.created_at >= cutoff_date
        ).scalar()
        
        last_task_update = db.session.query(
            func.max(Task.updated_at)
        ).join(Meeting, Task.meeting_id == Meeting.id).filter(
            Meeting.workspace_id == workspace_id,
            Meeting.created_at >= cutoff_date
        ).scalar()
        
        # Build checksum from key metrics (use empty string for None values)
        checksum_parts = [
            str(workspace_id),
            str(meeting_count),
            str(task_count),
            last_meeting_update.isoformat() if last_meeting_update else '',
            last_task_update.isoformat() if last_task_update else ''
        ]
        
        checksum_source = ':'.join(checksum_parts)
        checksum = hashlib.sha256(checksum_source.encode()).hexdigest()[:16]
        
        return jsonify({
            'success': True,
            'checksum': checksum,
            'timestamp': datetime.now().isoformat(),
            'period_days': days
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500