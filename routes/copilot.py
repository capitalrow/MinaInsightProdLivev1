"""
AI Copilot routes for Mina.

This module provides the AI Copilot functionality described in the handbook:
- Separate chat tab for natural language queries
- Meeting-aware Q&A with citations
- Task management through chat interface
- Action buttons for common operations
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from collections import Counter

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from openai import OpenAI
from server.models.memory_store import MemoryStore


logger = logging.getLogger(__name__)

copilot_bp = Blueprint('copilot', __name__, url_prefix='/copilot')

# Initialize OpenAI client for chat completions
openai_api_key = os.getenv("OPENAI_API_KEY")
openai_client = None
if openai_api_key:
    try:
        openai_client = OpenAI(api_key=openai_api_key)
        logger.info("OpenAI client initialized for Copilot")
    except Exception as e:
        logger.error(f"Failed to initialize OpenAI client: {e}")

# Memory store for context retrieval (e.g., recent summaries, relevant info)
memory = MemoryStore()

# System prompt defining the Copilot's role and tone
SYSTEM_PROMPT = (
    "You are Mina Copilot, an AI assistant for meeting transcripts and knowledge management. "
    "Answer user queries helpfully using the provided context from past meetings and summaries, if available. "
    "Be concise and professional."
)

@copilot_bp.route('/')
@login_required 
def copilot_dashboard():
    """
    Display the AI Copilot interface.
    
    Returns:
        Rendered copilot chat interface
    """
    try:
        logger.debug(f"Loading AI Copilot for user {current_user.id}")
        return render_template('copilot/chat.html', 
                             page_title="AI Copilot")
    except Exception as e:
        logger.error(f"Error loading AI Copilot: {e}")
        flash('Failed to load AI Copilot. Please try again.', 'error')
        return redirect(url_for('dashboard.index'))


@copilot_bp.route('/settings')
@login_required
def copilot_settings():
    """
    Display the Copilot settings and preferences page.
    
    Returns:
        Rendered copilot settings page
    """
    try:
        logger.debug(f"Loading Copilot settings for user {current_user.id}")
        return render_template('copilot/settings.html',
                             page_title="Copilot Settings")
    except Exception as e:
        logger.error(f"Error loading Copilot settings: {e}")
        flash('Failed to load settings. Please try again.', 'error')
        return redirect(url_for('copilot.copilot_dashboard'))


@copilot_bp.route('/api/chat', methods=['POST'])
@login_required
def chat_with_copilot():
    """
    Process chat messages with AI Copilot.
    
    Request Body:
        {
            "message": "What did we decide about the Q3 budget?",
            "context": "meeting_id_optional",
            "session_id": "optional_session_id",
            "language": "en|es|fr|de|zh|ja|pt|ru|ar|hi"
        }
    
    Returns:
        JSON: Copilot response with citations and action buttons
    """
    # Parse request
    try:
        data = request.get_json(force=True)
    except Exception as e:
        logger.error(f"Invalid JSON in Copilot chat request: {e}")
        return jsonify({"success": False, "error": "Invalid JSON"}), 400
    if not data or 'message' not in data:
        return jsonify({"success": False, "error": "No message provided"}), 400
    user_message = data['message']
    session_id = data.get('session_id')
    logger.info(f"Copilot chat request received. session_id={session_id}, message={user_message[:50]}...")

    # Build the message list for OpenAI (system + optional context + user)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if session_id:
        # Include latest summary of the session as context if available
        try:
            from services.analysis_service import AnalysisService
            summary = AnalysisService.get_session_summary(session_id)
        except Exception as e:
            summary = None
            logger.warning(f"No summary found for context (session {session_id}): {e}")
        if summary and isinstance(summary, dict):
            summary_text = summary.get('summary_md') or summary.get('brief_summary') or ""
            if summary_text:
                context_note = f"Context from meeting {session_id} summary: {summary_text}"
                messages.append({"role": "system", "content": context_note})
    messages.append({"role": "user", "content": user_message})

    if openai_client is None:
        logger.error("OpenAI client not initialized, cannot process chat")
        return jsonify({"success": False, "error": "AI engine not available"}), 500
    try:
        # Use GPT-4 model to generate a response (streaming omitted for simplicity)
        response = openai_client.chat_completions.create(
            model="gpt-4",
            messages=messages,
            temperature=0.7,
            max_tokens=500
        )
        # Extract assistant reply text
        ai_message = None
        if hasattr(response, 'choices') and response.choices:
            choice = response.choices[0]
            ai_message = choice.message.get('content') if hasattr(choice, 'message') else None
        if not ai_message:
            # Fallback: use response content directly if structured differently
            ai_message = response.get('content') if isinstance(response, dict) else str(response)
        logger.debug(f"Copilot response (truncated): {ai_message[:100]}...")
        return jsonify({"success": True, "response": ai_message}), 200
    except Exception as e:
        logger.error(f"Error during Copilot chat completion: {e}")
        return jsonify({"success": False, "error": "Failed to generate AI response"}), 500


@copilot_bp.route('/api/execute-action', methods=['POST'])
@login_required
def execute_copilot_action():
    """
    Execute actions suggested by the Copilot.
    
    Request Body:
        {
            "action": "create_task|mark_done|delete_task|add_to_calendar|export",
            "parameters": {...}
        }
    
    Returns:
        JSON: Success/error response
    """
    try:
        data = request.get_json() or {}
        action = data.get('action')
        parameters = data.get('parameters', {})
        
        if not action:
            return jsonify({
                'success': False,
                'error': 'Action is required'
            }), 400
        
        # Execute the action
        result = _execute_copilot_action(action, parameters, current_user.id)
        
        return jsonify({
            'success': True,
            'result': result
        }), 200
    
    except Exception as e:
        logger.error(f"Error executing copilot action: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to execute action'
        }), 500


@copilot_bp.route('/api/quick-queries', methods=['GET'])
@login_required
def get_quick_queries():
    """
    Get suggested quick queries for the user.
    
    Returns:
        JSON: List of suggested queries
    """
    try:
        queries = [
            "What's due today?",
            "What are my overdue tasks?",
            "Summarize yesterday's meetings",
            "What decisions were made this week?",
            "Show me all risks from recent meetings",
            "What tasks did I create last week?",
            "Which meetings had the most action items?",
            "What topics came up most in my meetings?"
        ]
        
        return jsonify({
            'success': True,
            'queries': queries
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting quick queries: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to get quick queries'
        }), 500


@copilot_bp.route('/api/analyze-patterns', methods=['POST'])
@login_required
def analyze_patterns():
    """
    Analyze meeting patterns and provide data insights.
    
    Request Body:
        {
            "analysis_type": "topics|participants|decisions|trends|risks",
            "time_range": "week|month|quarter|all",
            "filters": {"optional": "filters"}
        }
    
    Returns:
        JSON: Analysis results with insights and visualizations
    """
    try:
        data = request.get_json() or {}
        analysis_type = data.get('analysis_type', 'trends')
        time_range = data.get('time_range', 'month')
        filters = data.get('filters', {})
        
        # Perform pattern analysis
        insights = _analyze_meeting_patterns(
            analysis_type=analysis_type,
            time_range=time_range,
            filters=filters,
            user_id=current_user.id
        )
        
        return jsonify({
            'success': True,
            'insights': insights
        }), 200
    
    except Exception as e:
        import traceback
        logger.error(f"Error analyzing patterns: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': 'Failed to analyze meeting patterns'
        }), 500


@copilot_bp.route('/api/generate-draft', methods=['POST'])
@login_required
def generate_draft():
    """
    Generate drafts for emails, notes, or updates based on meeting context.
    
    Request Body:
        {
            "draft_type": "email|note|update",
            "meeting_id": "optional_meeting_id",
            "context": "additional context",
            "recipients": ["optional list for emails"],
            "tone": "formal|casual|professional"
        }
    
    Returns:
        JSON: Generated draft with subject/title and body
    """
    try:
        data = request.get_json() or {}
        draft_type = data.get('draft_type', 'email')
        meeting_id = data.get('meeting_id')
        context_info = data.get('context', '')
        recipients = data.get('recipients', [])
        tone = data.get('tone', 'professional')
        
        if draft_type not in ['email', 'note', 'update']:
            return jsonify({
                'success': False,
                'error': 'Invalid draft type. Must be email, note, or update.'
            }), 400
        
        # Generate the draft
        draft = _generate_draft_content(
            draft_type=draft_type,
            meeting_id=meeting_id,
            context_info=context_info,
            recipients=recipients,
            tone=tone,
            user_id=current_user.id
        )
        
        return jsonify({
            'success': True,
            'draft': draft
        }), 200
    
    except Exception as e:
        import traceback
        logger.error(f"Error generating draft: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': 'Failed to generate draft'
        }), 500


@copilot_bp.route('/api/clear', methods=['POST'])
def clear_conversation():
    """
    Clear/reset the Copilot conversation context (no persistent server-side state in this implementation).
    """
    logger.info("Copilot conversation cleared by user request.")
    # If conversation state were stored on the server, we would reset it here.
    return jsonify({"success": True, "message": "Conversation context cleared"}), 200


def _analyze_meeting_patterns(
    analysis_type: str,
    time_range: str,
    filters: Dict[str, Any],
    user_id: int
) -> Dict[str, Any]:
    """
    Analyze patterns across meetings to provide data insights.
    
    Args:
        analysis_type: Type of analysis (topics, participants, decisions, trends, risks)
        time_range: Time window for analysis (week, month, quarter, all)
        filters: Additional filters for analysis
        user_id: Current user ID
    
    Returns:
        Dict with analysis results and insights
    """
    try:
        from models import Meeting, Summary, User, db as models_db
        from datetime import timedelta
        from collections import Counter
        import json
        
        # Get user's workspace
        user = models_db.session.get(User, user_id)
        if not user or not user.workspace_id:
            return {'error': 'Unable to access workspace'}
        
        # Calculate date range
        now = datetime.now()
        if time_range == 'week':
            start_date = now - timedelta(days=7)
        elif time_range == 'month':
            start_date = now - timedelta(days=30)
        elif time_range == 'quarter':
            start_date = now - timedelta(days=90)
        else:  # all
            start_date = datetime(2020, 1, 1)  # Far back default
        
        # Get meetings in the time range
        meetings = models_db.session.query(Meeting)\
            .filter(Meeting.workspace_id == user.workspace_id)\
            .filter(Meeting.created_at >= start_date)\
            .order_by(Meeting.created_at.desc())\
            .all()
        
        if not meetings:
            return {
                'type': analysis_type,
                'time_range': time_range,
                'message': 'No meetings found in the selected time range',
                'count': 0
            }
        
        # Perform analysis based on type
        if analysis_type == 'topics':
            return _analyze_topics(meetings, models_db)
        elif analysis_type == 'participants':
            return _analyze_participants(meetings, models_db)
        elif analysis_type == 'decisions':
            return _analyze_decisions(meetings, models_db)
        elif analysis_type == 'risks':
            return _analyze_risks(meetings, models_db)
        else:  # trends
            return _analyze_trends(meetings, models_db)
    
    except Exception as e:
        logger.error(f"Error in pattern analysis: {e}")
        return {'error': str(e)}


def _analyze_topics(meetings, db):
    """Analyze frequently discussed topics across meetings."""
    from models import Summary
    
    topics_counter = Counter()
    topic_meetings = {}
    
    for meeting in meetings:
        if meeting.session:
            summary = db.session.query(Summary)\
                .filter_by(session_id=meeting.session.id)\
                .first()
            
            if summary and summary.topics:
                topics_list = summary.topics if isinstance(summary.topics, list) else []
                for topic in topics_list:
                    topic_name = topic.get('topic', topic) if isinstance(topic, dict) else str(topic)
                    topics_counter[topic_name] += 1
                    if topic_name not in topic_meetings:
                        topic_meetings[topic_name] = []
                    topic_meetings[topic_name].append({
                        'meeting_id': meeting.id,
                        'title': meeting.title,
                        'date': meeting.created_at.isoformat()
                    })
    
    top_topics = topics_counter.most_common(10)
    
    return {
        'type': 'topics',
        'total_meetings': len(meetings),
        'total_topics': len(topics_counter),
        'top_topics': [
            {
                'topic': topic,
                'count': count,
                'meetings': topic_meetings.get(topic, [])[:3]  # Top 3 meetings for each topic
            }
            for topic, count in top_topics
        ],
        'insight': f"The most discussed topic is '{top_topics[0][0]}' appearing in {top_topics[0][1]} meetings" if top_topics else "No topics identified"
    }


def _analyze_decisions(meetings, db):
    """Analyze decision-making patterns across meetings."""
    from models import Summary
    
    all_decisions = []
    decision_categories = Counter()
    
    for meeting in meetings:
        if meeting.session:
            summary = db.session.query(Summary)\
                .filter_by(session_id=meeting.session.id)\
                .first()
            
            if summary and summary.decisions:
                decisions_list = summary.decisions if isinstance(summary.decisions, list) else []
                for decision in decisions_list:
                    decision_text = decision.get('decision', decision) if isinstance(decision, dict) else str(decision)
                    all_decisions.append({
                        'decision': decision_text,
                        'meeting': meeting.title,
                        'date': meeting.created_at.isoformat()
                    })
                    
                    # Simple categorization based on keywords
                    decision_lower = decision_text.lower()
                    if any(word in decision_lower for word in ['approve', 'accept', 'agree']):
                        decision_categories['Approvals'] += 1
                    elif any(word in decision_lower for word in ['reject', 'decline', 'disagree']):
                        decision_categories['Rejections'] += 1
                    elif any(word in decision_lower for word in ['delay', 'postpone', 'defer']):
                        decision_categories['Deferrals'] += 1
                    else:
                        decision_categories['General'] += 1
    
    return {
        'type': 'decisions',
        'total_meetings': len(meetings),
        'total_decisions': len(all_decisions),
        'decisions_per_meeting': round(len(all_decisions) / len(meetings), 1) if meetings else 0,
        'categories': dict(decision_categories),
        'recent_decisions': all_decisions[:10],  # Most recent 10
        'insight': f"Average of {round(len(all_decisions) / len(meetings), 1)} decisions per meeting" if meetings else "No decisions tracked"
    }


def _analyze_risks(meetings, db):
    """Analyze risks and blockers mentioned across meetings."""
    from models import Summary
    
    all_risks = []
    risk_severity = Counter()
    
    for meeting in meetings:
        if meeting.session:
            summary = db.session.query(Summary)\
                .filter_by(session_id=meeting.session.id)\
                .first()
            
            if summary and summary.risks:
                risks_list = summary.risks if isinstance(summary.risks, list) else []
                for risk in risks_list:
                    risk_text = risk.get('risk', risk) if isinstance(risk, dict) else str(risk)
                    severity = risk.get('severity', 'medium') if isinstance(risk, dict) else 'medium'
                    
                    all_risks.append({
                        'risk': risk_text,
                        'severity': severity,
                        'meeting': meeting.title,
                        'date': meeting.created_at.isoformat()
                    })
                    risk_severity[severity] += 1
    
    return {
        'type': 'risks',
        'total_meetings': len(meetings),
        'total_risks': len(all_risks),
        'severity_breakdown': dict(risk_severity),
        'high_priority_risks': [r for r in all_risks if r.get('severity') == 'high'][:5],
        'all_risks': all_risks[:15],  # Top 15 most recent
        'insight': f"Identified {len(all_risks)} risks, {risk_severity.get('high', 0)} are high priority" if all_risks else "No risks identified"
    }


def _analyze_trends(meetings, db):
    """Analyze overall trends in meeting activity and outcomes."""
    from models import Summary
    from collections import defaultdict
    
    weekly_meetings = defaultdict(int)
    action_items_count = 0
    total_duration = 0
    meetings_with_summaries = 0
    
    for meeting in meetings:
        # Group by week
        week_key = meeting.created_at.strftime('%Y-W%W')
        weekly_meetings[week_key] += 1
        
        if meeting.session:
            summary = db.session.query(Summary)\
                .filter_by(session_id=meeting.session.id)\
                .first()
            
            if summary:
                meetings_with_summaries += 1
                if summary.actions:
                    actions_list = summary.actions if isinstance(summary.actions, list) else []
                    action_items_count += len(actions_list)
    
    # Calculate trends
    weeks = sorted(weekly_meetings.keys())
    trend_data = [{'week': w, 'count': weekly_meetings[w]} for w in weeks[-8:]]  # Last 8 weeks
    
    avg_meetings_per_week = sum(weekly_meetings.values()) / len(weekly_meetings) if weekly_meetings else 0
    avg_actions_per_meeting = action_items_count / meetings_with_summaries if meetings_with_summaries else 0
    
    return {
        'type': 'trends',
        'total_meetings': len(meetings),
        'meetings_with_insights': meetings_with_summaries,
        'weekly_trend': trend_data,
        'avg_meetings_per_week': round(avg_meetings_per_week, 1),
        'total_action_items': action_items_count,
        'avg_actions_per_meeting': round(avg_actions_per_meeting, 1),
        'insight': f"Averaging {round(avg_meetings_per_week, 1)} meetings per week with {round(avg_actions_per_meeting, 1)} action items per meeting"
    }


def _analyze_participants(meetings, db):
    """Analyze participant involvement and contribution patterns."""
    from models import Summary, Segment
    
    participant_stats = {}
    
    for meeting in meetings:
        if meeting.session:
            # Get segments to analyze speakers
            segments = db.session.query(Segment)\
                .filter_by(session_id=meeting.session.id)\
                .all()
            
            for segment in segments:
                speaker = segment.speaker or 'Unknown'
                if speaker not in participant_stats:
                    participant_stats[speaker] = {
                        'name': speaker,
                        'meetings': set(),
                        'segments_count': 0,
                        'total_words': 0
                    }
                
                participant_stats[speaker]['meetings'].add(meeting.id)
                participant_stats[speaker]['segments_count'] += 1
                if segment.text:
                    participant_stats[speaker]['total_words'] += len(segment.text.split())
    
    # Convert sets to counts
    for speaker in participant_stats:
        participant_stats[speaker]['meetings'] = len(participant_stats[speaker]['meetings'])
        participant_stats[speaker]['avg_words_per_segment'] = round(
            participant_stats[speaker]['total_words'] / participant_stats[speaker]['segments_count'], 1
        ) if participant_stats[speaker]['segments_count'] > 0 else 0
    
    # Sort by meeting count
    top_participants = sorted(
        participant_stats.values(),
        key=lambda x: x['meetings'],
        reverse=True
    )[:10]
    
    return {
        'type': 'participants',
        'total_meetings': len(meetings),
        'total_participants': len(participant_stats),
        'top_participants': top_participants,
        'insight': f"{len(participant_stats)} participants across {len(meetings)} meetings"
    }


def _process_copilot_message(message: str, context: Optional[str], user_id: int, session_id: Optional[str] = None, language: str = 'en') -> Dict[str, Any]:
    """
    Process a message using AI and meeting context with conversation history.
    
    Args:
        message: User's natural language query
        context: Optional meeting ID for context
        user_id: ID of the current user
        session_id: Optional session ID for conversation continuity
        language: Language code for response (en, es, fr, de, zh, ja, etc.)
    
    Returns:
        Dict containing AI response, citations, and action buttons
    """
    try:
        from services.openai_client_manager import get_openai_client
        from models import Meeting, Task, Segment, CopilotConversation, db as models_db
        
        # Generate session_id if not provided
        if not session_id:
            import uuid
            session_id = str(uuid.uuid4())
        
        # Get current user to access workspace_id and preferences
        from models import User
        user = models_db.session.get(User, user_id)
        if not user or not user.workspace_id:
            return {
                'text': "Unable to access your workspace. Please try logging in again.",
                'citations': [],
                'suggested_actions': [],
                'session_id': session_id,
                'timestamp': datetime.now().isoformat()
            }
        
        # Load user preferences if available
        user_preferences = {}
        if user.preferences:
            try:
                user_preferences = json.loads(user.preferences)
            except:
                pass
        
        # Load recent conversation history for context continuity (last 10 messages in this session)
        conversation_history = models_db.session.query(CopilotConversation)\
            .filter_by(user_id=user_id, session_id=session_id)\
            .order_by(CopilotConversation.created_at.desc())\
            .limit(10).all()
        conversation_history.reverse()  # Oldest first for chronological order
        
        # Get relevant meetings and tasks for context
        recent_meetings = models_db.session.query(Meeting)\
            .filter_by(workspace_id=user.workspace_id)\
            .order_by(Meeting.created_at.desc())\
            .limit(10).all()
        
        recent_tasks = models_db.session.query(Task)\
            .filter_by(assigned_to_id=user_id)\
            .order_by(Task.created_at.desc())\
            .limit(20).all()
        
        # Build context for AI with insights
        from models import Summary
        meeting_context = []
        for meeting in recent_meetings:
            meeting_data = {
                'id': meeting.id,
                'title': meeting.title,
                'date': meeting.created_at.isoformat(),
                'status': meeting.status
            }
            
            # Add AI insights if available from Summary
            if meeting.session:
                summary = models_db.session.query(Summary)\
                    .filter_by(session_id=meeting.session.id)\
                    .first()
                
                if summary:
                    # Add summary text
                    if summary.brief_summary:
                        meeting_data['summary'] = summary.brief_summary
                    elif summary.summary_md:
                        meeting_data['summary'] = summary.summary_md[:300]  # Truncate if needed
                    
                    # Add actions (top 3)
                    if summary.actions:
                        meeting_data['actions'] = summary.actions[:3] if isinstance(summary.actions, list) else []
                    
                    # Add decisions (top 2)
                    if summary.decisions:
                        meeting_data['decisions'] = summary.decisions[:2] if isinstance(summary.decisions, list) else []
                else:
                    # Fallback to transcript snippet if no summary
                    segments = models_db.session.query(Segment)\
                        .filter_by(session_id=meeting.session.id)\
                        .order_by(Segment.created_at)\
                        .limit(10).all()  # Just first 10 segments for context
                    
                    transcript = " ".join([seg.text for seg in segments if seg.text])
                    if transcript:
                        meeting_data['transcript_snippet'] = transcript[:500] + "..." if len(transcript) > 500 else transcript
            
            meeting_context.append(meeting_data)
        
        task_context = []
        for task in recent_tasks:
            task_data = {
                'id': task.id,
                'title': task.title,
                'status': task.status,
                'priority': task.priority if hasattr(task, 'priority') else 'medium',
                'due_date': task.due_date.isoformat() if task.due_date else None
            }
            if task.description:
                task_data['description'] = task.description[:200]  # Brief description
            if task.meeting_id:
                task_data['meeting_id'] = task.meeting_id
            task_context.append(task_data)
        
        # Language names mapping for natural instructions
        language_names = {
            'en': 'English',
            'es': 'Spanish (Español)',
            'fr': 'French (Français)',
            'de': 'German (Deutsch)',
            'zh': 'Chinese (中文)',
            'ja': 'Japanese (日本語)',
            'pt': 'Portuguese (Português)',
            'ru': 'Russian (Русский)',
            'ar': 'Arabic (العربية)',
            'hi': 'Hindi (हिन्दी)',
            'it': 'Italian (Italiano)',
            'ko': 'Korean (한국어)',
            'nl': 'Dutch (Nederlands)'
        }
        
        language_name = language_names.get(language, 'English')
        language_instruction = f"\n\n⚠️ IMPORTANT: Respond in {language_name}. All your responses, explanations, and suggestions MUST be in {language_name}." if language != 'en' else ""
        
        # Prepare AI prompt with user preferences awareness
        system_prompt = f"""You are Mina's AI Copilot. You help users understand their meetings, manage tasks, and find information.{language_instruction}

You have access to:
- Recent meeting transcripts and summaries
- Task lists and status
- Meeting decisions and action items
- Conversation history for context continuity
- User preferences and work patterns

Always:
- Provide specific, actionable responses
- Include citations to meetings or tasks when possible
- Suggest relevant actions users can take
- Be concise but helpful
- Remember context from earlier in the conversation
- Use markdown for formatting
- When generating code, use proper markdown code blocks with language tags

Code Generation:
- When asked to generate code, API examples, scripts, or technical solutions, use markdown code blocks
- Format: ```language\ncode here\n```
- Supported languages: python, javascript, typescript, bash, sql, json, yaml, html, css, and more
- Include helpful comments in the code
- Provide context or explanations before/after code blocks

Available actions you can suggest:
- create_task: Create a new task
- mark_done: Mark a task as complete  
- delete_task: Remove a task
- add_to_calendar: Add item to calendar
- export: Export to Slack/Notion/etc
"""
        
        # Add user preferences to system prompt if available
        if user_preferences:
            pref_lines = []
            if user_preferences.get('timezone'):
                pref_lines.append(f"- User timezone: {user_preferences['timezone']}")
            if user_preferences.get('work_hours'):
                pref_lines.append(f"- Work hours: {user_preferences['work_hours']}")
            if user_preferences.get('communication_style'):
                pref_lines.append(f"- Communication style: {user_preferences['communication_style']}")
            
            if pref_lines:
                system_prompt += "\n\nUser Preferences:\n" + "\n".join(pref_lines)
        
        # Build context string with token management
        context_parts = []
        context_parts.append(f"User Query: {message}\n")
        
        if meeting_context:
            context_parts.append(f"\nRecent Meetings ({len(meeting_context)}):")
            for m in meeting_context[:5]:  # Limit to 5 most recent
                context_parts.append(f"- {m['title']} ({m['date']})")
                if 'summary' in m:
                    context_parts.append(f"  Summary: {m['summary'][:200]}")
                if 'actions' in m and m['actions']:
                    action_list = [str(a.get('task', a)) if isinstance(a, dict) else str(a) for a in m['actions'][:3]]
                    context_parts.append(f"  Actions: {', '.join(action_list)}")
                if 'decisions' in m and m['decisions']:
                    decision_list = [str(d.get('decision', d)) if isinstance(d, dict) else str(d) for d in m['decisions'][:2]]
                    context_parts.append(f"  Decisions: {', '.join(decision_list)}")
                if 'transcript_snippet' in m:
                    context_parts.append(f"  Context: {m['transcript_snippet'][:150]}...")
        
        if task_context:
            context_parts.append(f"\n\nRecent Tasks ({len(task_context)}):")
            for t in task_context[:10]:  # Limit to 10 most recent
                due_status = f" (Due: {t['due_date']})" if t['due_date'] else ""
                context_parts.append(f"- [{t['status']}] {t['title']}{due_status}")
                if 'description' in t:
                    context_parts.append(f"  {t['description'][:100]}")
        
        user_prompt = "\n".join(context_parts) + "\n\nPlease provide a helpful, specific response based on this context. Include citations to meetings or tasks when relevant, and suggest actionable next steps."
        
        # Call OpenAI with conversation history
        client = get_openai_client()
        if not client:
            return {
                'text': "AI service is not configured. Please check your API key settings.",
                'citations': [],
                'suggested_actions': [],
                'session_id': session_id,
                'timestamp': datetime.now().isoformat()
            }
        
        # Build messages array with conversation history
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add conversation history for context
        for conv in conversation_history:
            messages.append({
                "role": conv.role,
                "content": conv.message
            })
        
        # Add current user message
        messages.append({"role": "user", "content": user_prompt})
            
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=800,  # Increased for better responses
            temperature=0.7,
            presence_penalty=0.1,  # Encourage diverse responses
            frequency_penalty=0.1  # Reduce repetition
        )
        
        ai_response = response.choices[0].message.content or ""
        
        # Parse response for action suggestions and follow-up questions
        actions = _extract_suggested_actions(ai_response, message)
        citations = _extract_citations(ai_response, meeting_context, task_context)
        follow_up_questions = _generate_follow_up_questions(message, ai_response, meeting_context, task_context)
        
        # Save conversation to database for future context
        try:
            # Save user message
            user_conv = CopilotConversation(
                user_id=user_id,
                role='user',
                message=message,
                session_id=session_id,
                context_filter=context,
                prompt_tokens=response.usage.prompt_tokens if hasattr(response, 'usage') else None,
                completion_tokens=0
            )
            models_db.session.add(user_conv)
            
            # Save assistant response
            assistant_conv = CopilotConversation(
                user_id=user_id,
                role='assistant',
                message=ai_response,
                session_id=session_id,
                context_filter=context,
                prompt_tokens=0,
                completion_tokens=response.usage.completion_tokens if hasattr(response, 'usage') else None
            )
            models_db.session.add(assistant_conv)
            models_db.session.commit()
            
            logger.debug(f"Saved conversation for user {user_id}, session {session_id}")
        except Exception as e:
            logger.error(f"Failed to save conversation history: {e}")
            # Don't fail the response if saving fails
            models_db.session.rollback()
        
        return {
            'text': ai_response,
            'citations': citations,
            'suggested_actions': actions,
            'follow_up_questions': follow_up_questions,
            'session_id': session_id,
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        import traceback
        logger.error(f"Error in _process_copilot_message: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return {
            'text': "I'm having trouble processing your request right now. Please try again.",
            'citations': [],
            'suggested_actions': [],
            'follow_up_questions': [],
            'session_id': session_id if 'session_id' in locals() else None,
            'timestamp': datetime.now().isoformat()
        }


def _extract_suggested_actions(response: str, original_query: str) -> List[Dict[str, Any]]:
    """Extract suggested actions from AI response."""
    actions = []
    
    # Simple heuristics for action suggestions
    if "overdue" in original_query.lower() or "due" in original_query.lower():
        actions.append({
            'type': 'mark_done',
            'label': 'Mark task as done',
            'icon': 'check-circle'
        })
    
    if "create" in original_query.lower() or "add" in original_query.lower():
        actions.append({
            'type': 'create_task',
            'label': 'Create new task',
            'icon': 'plus-circle'
        })
    
    if "calendar" in original_query.lower() or "schedule" in original_query.lower():
        actions.append({
            'type': 'add_to_calendar',
            'label': 'Add to calendar',
            'icon': 'calendar'
        })
    
    return actions


def _extract_citations(response: str, meetings: List[Dict], tasks: List[Dict]) -> List[Dict[str, Any]]:
    """Extract citations from AI response based on mentioned meetings/tasks."""
    citations = []
    
    # Simple citation extraction based on content matches
    for meeting in meetings:
        if meeting['title'].lower() in response.lower():
            citations.append({
                'type': 'meeting',
                'id': meeting['id'],
                'title': meeting['title'],
                'date': meeting['date']
            })
    
    for task in tasks:
        if task['title'].lower() in response.lower():
            citations.append({
                'type': 'task',
                'id': task['id'],
                'title': task['title'],
                'status': task['status']
            })
    
    return citations


def _generate_follow_up_questions(original_query: str, ai_response: str, meetings: List[Dict], tasks: List[Dict]) -> List[str]:
    """
    Generate contextual follow-up questions based on the conversation.
    
    Args:
        original_query: The user's original question
        ai_response: The AI's response
        meetings: List of meeting context
        tasks: List of task context
    
    Returns:
        List of 3-5 suggested follow-up questions
    """
    follow_ups = []
    query_lower = original_query.lower()
    response_lower = ai_response.lower()
    
    # Question generation based on query type
    
    # Meeting-related queries
    if any(word in query_lower for word in ['meeting', 'discussed', 'decision', 'agenda']):
        if 'decision' in response_lower or 'decided' in response_lower:
            follow_ups.append("What were the alternatives considered?")
        if len(meetings) > 0:
            follow_ups.append("Who were the key participants in these discussions?")
            follow_ups.append("Are there any follow-up meetings scheduled?")
        if 'action' in response_lower or 'task' in response_lower:
            follow_ups.append("What are the timelines for these action items?")
    
    # Task-related queries
    elif any(word in query_lower for word in ['task', 'due', 'overdue', 'action']):
        if 'overdue' in response_lower or 'late' in response_lower:
            follow_ups.append("Which tasks are highest priority?")
            follow_ups.append("Are there any blockers preventing completion?")
        if len(tasks) > 0:
            follow_ups.append("Show me tasks by priority")
            follow_ups.append("What tasks are due this week?")
        follow_ups.append("Can you create a summary of pending tasks?")
    
    # Summary/overview queries
    elif any(word in query_lower for word in ['summary', 'overview', 'status', 'progress']):
        follow_ups.append("What are the main risks or concerns?")
        follow_ups.append("Are we on track with our goals?")
        if len(meetings) > 1:
            follow_ups.append("How does this compare to last week?")
        follow_ups.append("What should I focus on next?")
    
    # Time-based queries
    elif any(word in query_lower for word in ['today', 'week', 'yesterday', 'month']):
        follow_ups.append("What's coming up tomorrow?")
        follow_ups.append("Show me last week's highlights")
        follow_ups.append("What are this month's key achievements?")
    
    # Risk/blocker queries
    elif any(word in query_lower for word in ['risk', 'blocker', 'issue', 'problem']):
        follow_ups.append("What mitigation strategies were discussed?")
        follow_ups.append("Who is responsible for resolving these?")
        follow_ups.append("Are there any dependencies?")
    
    # General fallback questions
    else:
        if meetings:
            follow_ups.append("Tell me more about recent meetings")
        if tasks:
            follow_ups.append("What tasks need my attention?")
        follow_ups.append("Summarize this week's progress")
        follow_ups.append("What decisions were made recently?")
    
    # Limit to 5 questions and ensure no duplicates
    follow_ups = list(dict.fromkeys(follow_ups))[:5]
    
    # If we have less than 3, add generic useful questions
    if len(follow_ups) < 3:
        generic_questions = [
            "What are the key takeaways?",
            "Who should I follow up with?",
            "Are there any pending approvals?",
            "Show me related action items",
            "What's the status of ongoing projects?"
        ]
        for q in generic_questions:
            if q not in follow_ups and len(follow_ups) < 5:
                follow_ups.append(q)
    
    return follow_ups


def _generate_draft_content(
    draft_type: str,
    meeting_id: Optional[int],
    context_info: str,
    recipients: List[str],
    tone: str,
    user_id: int
) -> Dict[str, Any]:
    """
    Generate draft content using AI based on meeting context.
    
    Args:
        draft_type: Type of draft (email, note, update)
        meeting_id: Optional meeting ID for context
        context_info: Additional context information
        recipients: List of recipients (for emails)
        tone: Tone of the draft (formal, casual, professional)
        user_id: Current user ID
    
    Returns:
        Dict with subject/title and body of the draft
    """
    try:
        from services.openai_client_manager import get_openai_client
        from models import Meeting, Summary, Segment, User, db as models_db
        
        # Get user info
        user = models_db.session.get(User, user_id)
        if not user:
            return {
                'subject': 'Error',
                'body': 'Unable to access user information.'
            }
        
        # Build context from meeting if provided
        meeting_context = ""
        if meeting_id:
            meeting = models_db.session.get(Meeting, meeting_id)
            if meeting and meeting.session:
                # Get summary if available
                summary = models_db.session.query(Summary)\
                    .filter_by(session_id=meeting.session.id)\
                    .first()
                
                if summary:
                    meeting_context = f"""
Meeting: {meeting.title}
Date: {meeting.created_at.strftime('%B %d, %Y')}

Summary: {summary.brief_summary or summary.summary_md[:500]}

Key Decisions:
{chr(10).join([f"- {d}" for d in (summary.decisions[:3] if summary.decisions else [])])}

Action Items:
{chr(10).join([f"- {a}" for a in (summary.actions[:5] if summary.actions else [])])}
"""
                else:
                    # Fallback to transcript
                    segments = models_db.session.query(Segment)\
                        .filter_by(session_id=meeting.session.id)\
                        .order_by(Segment.created_at)\
                        .limit(20).all()
                    
                    transcript = " ".join([seg.text for seg in segments if seg.text])
                    meeting_context = f"""
Meeting: {meeting.title}
Date: {meeting.created_at.strftime('%B %d, %Y')}

Key Discussion Points:
{transcript[:800]}...
"""
        
        # Build prompts based on draft type
        system_prompts = {
            'email': f"""You are a professional email writer. Generate a well-structured {tone} follow-up email based on the meeting context. 
Include:
- Clear, professional subject line
- Proper greeting
- Summary of key points
- Action items with owners
- Next steps
- Professional closing

Tone: {tone}
""",
            'note': f"""You are a professional note-taker. Generate structured meeting notes that are clear and actionable.
Include:
- Meeting overview
- Key discussion points
- Decisions made
- Action items
- Next steps

Format: Well-organized with bullet points and sections.
Tone: {tone}
""",
            'update': f"""You are a professional communicator. Generate a concise status update for the team.
Include:
- Progress summary
- Key achievements
- Challenges or blockers
- Next priorities

Format: Brief and to-the-point.
Tone: {tone}
"""
        }
        
        user_prompts = {
            'email': f"""Generate a follow-up email based on this meeting:

{meeting_context}

Additional Context: {context_info}
Recipients: {', '.join(recipients) if recipients else 'Team'}

Provide a JSON response with "subject" and "body" fields.""",
            
            'note': f"""Generate structured meeting notes based on:

{meeting_context}

Additional Context: {context_info}

Provide a JSON response with "title" and "body" fields.""",
            
            'update': f"""Generate a status update based on:

{meeting_context}

Additional Context: {context_info}

Provide a JSON response with "title" and "body" fields."""
        }
        
        # Call OpenAI
        client = get_openai_client()
        if not client:
            return {
                'subject': 'AI Service Unavailable',
                'body': 'Please configure your OpenAI API key to generate drafts.'
            }
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompts[draft_type]},
                {"role": "user", "content": user_prompts[draft_type]}
            ],
            max_tokens=1000,
            temperature=0.7
        )
        
        ai_response = response.choices[0].message.content or ""
        
        # Try to parse JSON response
        try:
            import json
            draft_data = json.loads(ai_response)
            return {
                'subject': draft_data.get('subject') or draft_data.get('title', 'Draft'),
                'body': draft_data.get('body', ai_response)
            }
        except:
            # If not JSON, use the response as body
            subject = f"{'Follow-up from' if draft_type == 'email' else 'Notes for'} Meeting"
            if meeting_context:
                meeting_lines = meeting_context.split('\n')
                for line in meeting_lines:
                    if line.startswith('Meeting:'):
                        subject = f"{'Follow-up:' if draft_type == 'email' else 'Notes:'} {line.replace('Meeting:', '').strip()}"
                        break
            
            return {
                'subject': subject,
                'body': ai_response
            }
    
    except Exception as e:
        logger.error(f"Error generating draft: {e}")
        return {
            'subject': 'Draft Generation Error',
            'body': f'An error occurred while generating the draft: {str(e)}'
        }


def _execute_copilot_action(action: str, parameters: Dict[str, Any], user_id: int) -> Dict[str, Any]:
    """Execute an action suggested by the Copilot."""
    try:
        from models import Task, db as models_db
        
        if action == 'create_task':
            title = parameters.get('title')
            description = parameters.get('description', '')
            due_date = parameters.get('due_date')
            
            if not title:
                return {'error': 'Task title is required'}
            
            task = Task(
                title=title,
                description=description,
                assigned_to_id=user_id,
                status='pending',
                due_date=datetime.fromisoformat(due_date) if due_date else None
            )
            models_db.session.add(task)
            models_db.session.commit()
            
            return {'task_id': task.id, 'message': f'Created task: {title}'}
        
        elif action == 'mark_done':
            task_id = parameters.get('task_id')
            if not task_id:
                return {'error': 'Task ID is required'}
            
            task = models_db.session.query(Task).filter_by(id=task_id, assigned_to_id=user_id).first()
            if not task:
                return {'error': 'Task not found'}
            
            task.status = 'completed'
            task.completed_at = datetime.now()
            models_db.session.commit()
            
            return {'message': f'Marked task as done: {task.title}'}
        
        elif action == 'delete_task':
            task_id = parameters.get('task_id')
            if not task_id:
                return {'error': 'Task ID is required'}
            
            task = models_db.session.query(Task).filter_by(id=task_id, assigned_to_id=user_id).first()
            if not task:
                return {'error': 'Task not found'}
            
            task_title = task.title
            models_db.session.delete(task)
            models_db.session.commit()
            
            return {'message': f'Deleted task: {task_title}'}
        
        else:
            return {'error': f'Unknown action: {action}'}
    
    except Exception as e:
        logger.error(f"Error executing action {action}: {e}")
        return {'error': 'Failed to execute action'}