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


@api_analytics_bp.route('/kpi-comparison', methods=['GET'])
@login_required
def get_kpi_comparison():
    """
    Get KPI metrics with period-over-period comparison.
    Returns current period values and percentage change from previous period.
    """
    try:
        workspace_id = current_user.workspace_id
        days = request.args.get('days', 30, type=int)
        
        # Current period
        current_start = datetime.now() - timedelta(days=days)
        current_end = datetime.now()
        
        # Previous period (same length, immediately before)
        previous_start = current_start - timedelta(days=days)
        previous_end = current_start
        
        # Current period metrics
        current_meetings = db.session.query(Meeting).filter(
            Meeting.workspace_id == workspace_id,
            Meeting.created_at >= current_start,
            Meeting.created_at < current_end
        ).all()
        
        current_meeting_count = len(current_meetings)
        current_meeting_ids = [m.id for m in current_meetings]
        
        # Helper to calculate meeting duration from timestamps
        def get_meeting_duration(m):
            if m.actual_start and m.actual_end:
                return (m.actual_end - m.actual_start).total_seconds() / 60
            elif m.scheduled_start and m.scheduled_end:
                return (m.scheduled_end - m.scheduled_start).total_seconds() / 60
            return 0
        
        # Current tasks
        if current_meeting_ids:
            current_tasks = db.session.query(Task).filter(
                Task.meeting_id.in_(current_meeting_ids)
            ).count()
            current_completed = db.session.query(Task).filter(
                Task.meeting_id.in_(current_meeting_ids),
                Task.status == 'completed'
            ).count()
        else:
            current_tasks = 0
            current_completed = 0
        
        # Current duration
        current_duration_sum = sum(get_meeting_duration(m) for m in current_meetings)
        current_avg_duration = current_duration_sum / current_meeting_count if current_meeting_count else 0
        
        # Previous period metrics
        previous_meetings = db.session.query(Meeting).filter(
            Meeting.workspace_id == workspace_id,
            Meeting.created_at >= previous_start,
            Meeting.created_at < previous_end
        ).all()
        
        previous_meeting_count = len(previous_meetings)
        previous_meeting_ids = [m.id for m in previous_meetings]
        
        if previous_meeting_ids:
            previous_tasks = db.session.query(Task).filter(
                Task.meeting_id.in_(previous_meeting_ids)
            ).count()
            previous_completed = db.session.query(Task).filter(
                Task.meeting_id.in_(previous_meeting_ids),
                Task.status == 'completed'
            ).count()
        else:
            previous_tasks = 0
            previous_completed = 0
        
        previous_duration_sum = sum(get_meeting_duration(m) for m in previous_meetings)
        previous_avg_duration = previous_duration_sum / previous_meeting_count if previous_meeting_count else 0
        
        # Calculate percentage changes
        def calc_change(current, previous):
            if previous == 0:
                return 100 if current > 0 else 0
            return round(((current - previous) / previous) * 100, 1)
        
        def calc_completion_rate(completed, total):
            return round((completed / total * 100), 1) if total > 0 else 0
        
        # Hours saved estimate (based on meeting efficiency improvements)
        current_analytics = db.session.query(Analytics).join(Meeting).filter(
            Meeting.workspace_id == workspace_id,
            Meeting.created_at >= current_start,
            Analytics.analysis_status == 'completed'
        ).all()
        
        # Estimate hours saved based on task automation and meeting efficiency
        hours_saved = len(current_analytics) * 0.5  # 30 min per analyzed meeting
        previous_analytics_count = db.session.query(Analytics).join(Meeting).filter(
            Meeting.workspace_id == workspace_id,
            Meeting.created_at >= previous_start,
            Meeting.created_at < previous_end,
            Analytics.analysis_status == 'completed'
        ).count()
        previous_hours_saved = previous_analytics_count * 0.5
        
        return jsonify({
            'success': True,
            'kpis': {
                'total_meetings': {
                    'value': current_meeting_count,
                    'previous': previous_meeting_count,
                    'change': calc_change(current_meeting_count, previous_meeting_count),
                    'trend': 'up' if current_meeting_count > previous_meeting_count else ('down' if current_meeting_count < previous_meeting_count else 'stable')
                },
                'action_items': {
                    'value': current_tasks,
                    'previous': previous_tasks,
                    'change': calc_change(current_tasks, previous_tasks),
                    'completion_rate': calc_completion_rate(current_completed, current_tasks),
                    'trend': 'up' if current_tasks > previous_tasks else ('down' if current_tasks < previous_tasks else 'stable')
                },
                'hours_saved': {
                    'value': round(hours_saved, 1),
                    'previous': round(previous_hours_saved, 1),
                    'change': calc_change(hours_saved, previous_hours_saved),
                    'trend': 'up' if hours_saved > previous_hours_saved else ('down' if hours_saved < previous_hours_saved else 'stable')
                },
                'avg_duration': {
                    'value': round(current_avg_duration, 0),
                    'previous': round(previous_avg_duration, 0),
                    'change': calc_change(current_avg_duration, previous_avg_duration),
                    'trend': 'down' if current_avg_duration < previous_avg_duration else ('up' if current_avg_duration > previous_avg_duration else 'stable')
                }
            },
            'period': {
                'current': {'start': current_start.isoformat(), 'end': current_end.isoformat()},
                'previous': {'start': previous_start.isoformat(), 'end': previous_end.isoformat()},
                'days': days
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@api_analytics_bp.route('/health-score', methods=['GET'])
@login_required
def get_meeting_health_score():
    """
    Get composite Meeting Health Score (0-100).
    Combines: effectiveness, engagement, follow-through, decision velocity.
    """
    try:
        workspace_id = current_user.workspace_id
        days = request.args.get('days', 30, type=int)
        cutoff_date = datetime.now() - timedelta(days=days)
        previous_cutoff = cutoff_date - timedelta(days=days)
        
        # Get current period analytics
        current_analytics = db.session.query(Analytics).join(Meeting).filter(
            Meeting.workspace_id == workspace_id,
            Meeting.created_at >= cutoff_date,
            Analytics.analysis_status == 'completed'
        ).all()
        
        # Get previous period for trend
        previous_analytics = db.session.query(Analytics).join(Meeting).filter(
            Meeting.workspace_id == workspace_id,
            Meeting.created_at >= previous_cutoff,
            Meeting.created_at < cutoff_date,
            Analytics.analysis_status == 'completed'
        ).all()
        
        def calc_health_score(analytics_list):
            if not analytics_list:
                return 0, {}
            
            # Effectiveness (0-100)
            effectiveness_scores = [a.meeting_effectiveness_score or 0 for a in analytics_list]
            avg_effectiveness = (sum(effectiveness_scores) / len(effectiveness_scores)) * 100 if effectiveness_scores else 0
            
            # Engagement (0-100)
            engagement_scores = [a.overall_engagement_score or 0 for a in analytics_list]
            avg_engagement = (sum(engagement_scores) / len(engagement_scores)) * 100 if engagement_scores else 0
            
            # Follow-through (task completion rate)
            meeting_ids = [a.meeting_id for a in analytics_list]
            if meeting_ids:
                total_tasks = db.session.query(Task).filter(Task.meeting_id.in_(meeting_ids)).count()
                completed_tasks = db.session.query(Task).filter(
                    Task.meeting_id.in_(meeting_ids),
                    Task.status == 'completed'
                ).count()
                follow_through = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 50
            else:
                follow_through = 50
            
            # Decision velocity (decisions per meeting)
            decisions = [a.decisions_made_count or 0 for a in analytics_list]
            avg_decisions = sum(decisions) / len(decisions) if decisions else 0
            decision_score = min(100, avg_decisions * 25)  # 4+ decisions = 100
            
            # Weighted composite score
            composite = (
                avg_effectiveness * 0.30 +
                avg_engagement * 0.25 +
                follow_through * 0.30 +
                decision_score * 0.15
            )
            
            return round(composite, 1), {
                'effectiveness': round(avg_effectiveness, 1),
                'engagement': round(avg_engagement, 1),
                'follow_through': round(follow_through, 1),
                'decision_velocity': round(decision_score, 1)
            }
        
        current_score, current_breakdown = calc_health_score(current_analytics)
        previous_score, _ = calc_health_score(previous_analytics)
        
        # Determine trend
        if current_score > previous_score + 5:
            trend = 'improving'
        elif current_score < previous_score - 5:
            trend = 'declining'
        else:
            trend = 'stable'
        
        # Health status
        if current_score >= 80:
            status = 'excellent'
            status_message = 'Your meetings are highly effective'
        elif current_score >= 60:
            status = 'good'
            status_message = 'Your meetings are productive with room for improvement'
        elif current_score >= 40:
            status = 'fair'
            status_message = 'Consider focusing on engagement and follow-through'
        else:
            status = 'needs_attention'
            status_message = 'Your meetings could benefit from more structure'
        
        return jsonify({
            'success': True,
            'health_score': {
                'score': current_score,
                'previous_score': previous_score,
                'change': round(current_score - previous_score, 1),
                'trend': trend,
                'status': status,
                'status_message': status_message,
                'breakdown': current_breakdown,
                'meetings_analyzed': len(current_analytics)
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@api_analytics_bp.route('/actionable-insights', methods=['GET'])
@login_required
def get_actionable_insights():
    """
    Get smart, actionable insights based on meeting patterns.
    Detects: meetings without outcomes, overtime, participation drops, recurring topics.
    """
    try:
        workspace_id = current_user.workspace_id
        days = request.args.get('days', 30, type=int)
        cutoff_date = datetime.now() - timedelta(days=days)
        
        insights = []
        
        # Get meetings and analytics
        meetings = db.session.query(Meeting).filter(
            Meeting.workspace_id == workspace_id,
            Meeting.created_at >= cutoff_date
        ).all()
        
        analytics = db.session.query(Analytics).join(Meeting).filter(
            Meeting.workspace_id == workspace_id,
            Meeting.created_at >= cutoff_date,
            Analytics.analysis_status == 'completed'
        ).all()
        
        meeting_ids = [m.id for m in meetings]
        
        # 1. Meetings without outcomes (no tasks or decisions)
        if analytics:
            no_outcome_meetings = [
                a for a in analytics 
                if (a.action_items_created or 0) == 0 and (a.decisions_made_count or 0) == 0
            ]
            if no_outcome_meetings:
                insights.append({
                    'type': 'warning',
                    'category': 'outcomes',
                    'title': f'{len(no_outcome_meetings)} meetings had no clear outcomes',
                    'description': 'Consider defining clear objectives before meetings to ensure actionable results.',
                    'metric': len(no_outcome_meetings),
                    'priority': 'high' if len(no_outcome_meetings) > 3 else 'medium'
                })
        
        # 2. Overtime meetings (exceeded scheduled duration)
        def get_duration_info(m):
            actual = 0
            scheduled = 0
            if m.actual_start and m.actual_end:
                actual = (m.actual_end - m.actual_start).total_seconds() / 60
            if m.scheduled_start and m.scheduled_end:
                scheduled = (m.scheduled_end - m.scheduled_start).total_seconds() / 60
            return actual, scheduled
        
        overtime_meetings = []
        for m in meetings:
            actual, scheduled = get_duration_info(m)
            if actual > 0 and scheduled > 0 and actual > scheduled * 1.2:  # 20% over
                overtime_meetings.append((m, actual - scheduled))
        
        if overtime_meetings:
            avg_overtime = sum(ot[1] for ot in overtime_meetings) / len(overtime_meetings)
            insights.append({
                'type': 'info',
                'category': 'time_management',
                'title': f'{len(overtime_meetings)} meetings ran overtime',
                'description': f'These meetings averaged {round(avg_overtime)} minutes over their scheduled time.',
                'metric': len(overtime_meetings),
                'priority': 'medium'
            })
        
        # 3. Low participation meetings
        low_engagement = [
            a for a in analytics 
            if a.overall_engagement_score and a.overall_engagement_score < 0.4
        ]
        if low_engagement:
            insights.append({
                'type': 'warning',
                'category': 'engagement',
                'title': f'{len(low_engagement)} meetings had low participation',
                'description': 'Consider smaller meeting sizes or async updates for better engagement.',
                'metric': len(low_engagement),
                'priority': 'high' if len(low_engagement) > 2 else 'medium'
            })
        
        # 4. Task completion rate trend
        if meeting_ids:
            total_tasks = db.session.query(Task).filter(Task.meeting_id.in_(meeting_ids)).count()
            completed_tasks = db.session.query(Task).filter(
                Task.meeting_id.in_(meeting_ids),
                Task.status == 'completed'
            ).count()
            
            if total_tasks > 0:
                completion_rate = (completed_tasks / total_tasks) * 100
                if completion_rate < 50:
                    insights.append({
                        'type': 'warning',
                        'category': 'follow_through',
                        'title': f'Task completion rate is {round(completion_rate)}%',
                        'description': 'Review task assignments and deadlines to improve follow-through.',
                        'metric': round(completion_rate),
                        'priority': 'high'
                    })
                elif completion_rate >= 80:
                    insights.append({
                        'type': 'success',
                        'category': 'follow_through',
                        'title': f'Excellent task completion at {round(completion_rate)}%',
                        'description': 'Your team is following through on action items effectively.',
                        'metric': round(completion_rate),
                        'priority': 'low'
                    })
        
        # 5. High-performing meeting pattern
        high_effectiveness = [
            a for a in analytics 
            if a.meeting_effectiveness_score and a.meeting_effectiveness_score >= 0.8
        ]
        if high_effectiveness and len(high_effectiveness) >= 3:
            insights.append({
                'type': 'success',
                'category': 'effectiveness',
                'title': f'{len(high_effectiveness)} highly effective meetings',
                'description': 'Your effective meetings share clear agendas and active participation.',
                'metric': len(high_effectiveness),
                'priority': 'low'
            })
        
        # Sort by priority
        priority_order = {'high': 0, 'medium': 1, 'low': 2}
        insights.sort(key=lambda x: priority_order.get(x['priority'], 1))
        
        # Generate weekly highlight
        weekly_highlight = None
        if insights:
            top_insight = insights[0]
            weekly_highlight = {
                'title': top_insight['title'],
                'type': top_insight['type'],
                'action': top_insight['description']
            }
        elif len(meetings) > 0:
            weekly_highlight = {
                'title': f'{len(meetings)} meetings this period',
                'type': 'info',
                'action': 'Your meetings are running smoothly. Keep up the good work!'
            }
        
        return jsonify({
            'success': True,
            'insights': insights[:5],  # Top 5 insights
            'weekly_highlight': weekly_highlight,
            'total_insights': len(insights),
            'meetings_analyzed': len(analytics)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@api_analytics_bp.route('/topic-distribution', methods=['GET'])
@login_required
def get_topic_distribution():
    """
    Get actual meeting topic distribution from AI analysis.
    Replaces hardcoded category placeholders.
    """
    try:
        workspace_id = current_user.workspace_id
        days = request.args.get('days', 30, type=int)
        cutoff_date = datetime.now() - timedelta(days=days)
        
        # Get analytics with topic data
        analytics = db.session.query(Analytics).join(Meeting).filter(
            Meeting.workspace_id == workspace_id,
            Meeting.created_at >= cutoff_date,
            Analytics.analysis_status == 'completed'
        ).all()
        
        # Aggregate topics from all meetings
        topic_counts = {}
        total_topics = 0
        
        for a in analytics:
            if a.key_topics:
                topics = a.key_topics if isinstance(a.key_topics, list) else []
                for topic in topics:
                    topic_name = topic.get('name', topic) if isinstance(topic, dict) else str(topic)
                    topic_counts[topic_name] = topic_counts.get(topic_name, 0) + 1
                    total_topics += 1
        
        # Calculate percentages and sort by frequency
        topic_distribution = []
        for topic, count in sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
            percentage = (count / total_topics * 100) if total_topics > 0 else 0
            topic_distribution.append({
                'name': topic,
                'count': count,
                'percentage': round(percentage, 1)
            })
        
        # If no topics found, provide empty state
        if not topic_distribution:
            return jsonify({
                'success': True,
                'topics': [],
                'has_data': False,
                'message': 'Record and analyze meetings to see topic distribution'
            })
        
        return jsonify({
            'success': True,
            'topics': topic_distribution,
            'has_data': True,
            'total_topics': total_topics,
            'meetings_analyzed': len(analytics)
        })
        
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
        last_updated = latest_analytics[0] if latest_analytics else None
        count = (latest_analytics[1] if latest_analytics else 0) or 0
        
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