"""
API endpoint for generating insights from transcripts (post-recording workflow).
"""

import logging
from datetime import datetime
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user

logger = logging.getLogger(__name__)

api_generate_insights_bp = Blueprint('api_generate_insights', __name__)


@api_generate_insights_bp.route('/api/generate-insights', methods=['POST'])
@login_required
def generate_insights():
    """
    Generate AI-powered insights from transcript (for post-recording workflow).
    
    Request Body:
        {
            "transcript": "meeting transcript text",
            "sessionId": "session_id",
            "duration": 1800000,
            "speakerCount": 2
        }
    
    Returns:
        JSON: Generated insights including summary, key points, and action items
    """
    try:
        if not current_user.is_authenticated:
            return jsonify({'success': False, 'error': 'Authentication required'}), 401

        data = request.get_json() or {}
        transcript = data.get('transcript', '').strip()
        session_id = data.get('sessionId')
        duration = data.get('duration', 0)
        speaker_count = data.get('speakerCount', 1)
        
        # Validate input
        if not transcript:
            return jsonify({
                'success': False,
                'error': 'Transcript is required'
            }), 400
            
        if len(transcript) < 10:
            return jsonify({
                'success': False,
                'error': 'Transcript too short for meaningful analysis'
            }), 400
        
        # Generate insights using OpenAI directly (avoiding import issues)
        try:
            analysis_result = _generate_insights_directly(transcript)
            
            # Format response for frontend
            insights = {
                'success': True,
                'summary': analysis_result.get('summary', ''),
                'keyPoints': analysis_result.get('key_points', []),
                'actionItems': analysis_result.get('action_items', []),
                'decisions': analysis_result.get('decisions', []),
                'nextSteps': analysis_result.get('next_steps', []),
                'participants': analysis_result.get('participants', []),
                'sentiment': analysis_result.get('sentiment', 'neutral'),
                'metadata': {
                    'sessionId': session_id,
                    'duration': duration,
                    'speakerCount': speaker_count,
                    'wordCount': len(transcript.split()),
                    'generatedAt': datetime.utcnow().isoformat()
                }
            }
            
            logger.info(f"✅ Generated insights for session {session_id}: {len(insights.get('keyPoints', []))} key points, {len(insights.get('actionItems', []))} action items")
            
            return jsonify(insights)
            
        except Exception as analysis_error:
            logger.error(f"OpenAI analysis failed: {analysis_error}")
            
            # Fallback: Generate basic insights from transcript analysis
            fallback_insights = {
                'success': True,
                'summary': f"Meeting transcript processed ({len(transcript.split())} words, {duration//60000} minutes)",
                'keyPoints': [
                    "Meeting transcript has been captured and processed",
                    f"Involved approximately {speaker_count} speaker(s)",
                    f"Meeting duration: {duration//60000} minutes"
                ],
                'actionItems': [
                    "Review transcript for specific action items",
                    "Follow up on discussed topics"
                ],
                'decisions': [],
                'nextSteps': ["Review and act on meeting outcomes"],
                'participants': [],
                'sentiment': 'neutral',
                'metadata': {
                    'sessionId': session_id,
                    'duration': duration,
                    'speakerCount': speaker_count,
                    'wordCount': len(transcript.split()),
                    'generatedAt': datetime.utcnow().isoformat(),
                    'fallback': True
                }
            }
            
            logger.warning(f"⚠️ Using fallback insights for session {session_id}")
            return jsonify(fallback_insights)
        
    except Exception as e:
        logger.error(f"Error generating insights: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to generate insights'
        }), 500


def _generate_insights_directly(transcript):
    """Generate insights directly using OpenAI without complex dependencies."""
    try:
        import os
        import json
        from openai import OpenAI
        
        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            logger.warning("OpenAI API key not found, using fallback")
            return _generate_fallback_insights(transcript)
        
        client = OpenAI(api_key=api_key)
        
        prompt = f"""Analyze this meeting transcript and provide insights in JSON format:

TRANSCRIPT:
{transcript}

Please provide a JSON response with these fields:
- summary: Brief 2-3 sentence summary of the meeting
- key_points: Array of 3-5 main discussion points
- action_items: Array of specific action items mentioned
- decisions: Array of decisions made
- next_steps: Array of follow-up actions
- participants: Array of participant roles/names if mentioned
- sentiment: Overall meeting sentiment (positive/neutral/negative)

Format as valid JSON only."""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a professional meeting analyst. Respond with valid JSON only. Format your response as JSON with the requested structure."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        
        result_text = response.choices[0].message.content
        if not result_text:
            logger.warning("Empty response from OpenAI")
            return _generate_fallback_insights(transcript)
        return json.loads(result_text)
        
    except Exception as e:
        logger.error(f"Direct OpenAI analysis failed: {e}")
        return _generate_fallback_insights(transcript)


def _generate_fallback_insights(transcript):
    """Generate basic insights when OpenAI fails."""
    word_count = len(transcript.split())
    
    return {
        'summary': f"Meeting transcript analyzed ({word_count} words). OpenAI processing unavailable.",
        'key_points': [
            "Meeting transcript successfully captured",
            f"Transcript contains {word_count} words",
            "Review transcript for specific topics and decisions"
        ],
        'action_items': [
            "Review meeting transcript for action items",
            "Follow up on discussed topics",
            "Share meeting outcomes with stakeholders"
        ],
        'decisions': [],
        'next_steps': ["Review transcript and extract specific action items"],
        'participants': [],
        'sentiment': 'neutral'
    }