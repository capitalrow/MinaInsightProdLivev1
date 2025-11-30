"""
API endpoint for generating insights from transcripts (post-recording workflow).

ANTI-HALLUCINATION: All extracted action items are validated against the transcript
using TextMatcher to ensure they are grounded in what was actually said.
"""

import logging
from datetime import datetime
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from services.text_matcher import TextMatcher

logger = logging.getLogger(__name__)
text_matcher = TextMatcher()

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
    """
    Generate insights directly using OpenAI with STRICT anti-hallucination validation.
    
    All extracted action items are validated against the transcript to ensure
    they were actually stated, not inferred or invented by the AI.
    """
    try:
        import os
        import json
        from openai import OpenAI
        
        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            logger.warning("OpenAI API key not found, using fallback")
            return _generate_fallback_insights(transcript)
        
        client = OpenAI(api_key=api_key)
        
        # STRICT anti-hallucination prompt
        prompt = f"""You are a STRICT evidence-based meeting analyst. Extract ONLY what is EXPLICITLY stated in the transcript.

CRITICAL RULES - ZERO HALLUCINATION:
1. ONLY extract action items that were EXPLICITLY stated by the speaker
2. Each action_item MUST include an "evidence_quote" field with the EXACT words from the transcript
3. Do NOT infer, suggest, or invent tasks that weren't explicitly said
4. If the meeting is about "testing" something, do NOT add tasks like "check pages" or "update systems"
5. When in doubt, DO NOT extract - it's better to miss a task than to invent one

TRANSCRIPT:
{transcript}

Return ONLY valid JSON with these fields:
- summary: Brief 2-3 sentence FACTUAL summary (no embellishment)
- key_points: Array of 3-5 main points that were ACTUALLY discussed
- action_items: Array of objects with "task" and "evidence_quote" fields (ONLY explicit commitments)
- decisions: Array of decisions that were EXPLICITLY made
- next_steps: Array of follow-up actions that were EXPLICITLY stated
- participants: Array of participant roles/names if mentioned
- sentiment: Overall meeting sentiment (positive/neutral/negative)

Example action_items format:
[{{"task": "Work on the AI Copilot page", "evidence_quote": "I will work on the AI Copilot page today"}}]

If no explicit action items were stated, return an empty array: []

Format as valid JSON only."""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a STRICT evidence-based meeting analyst. NEVER invent or infer content. Only extract what is EXPLICITLY stated. Respond with valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2  # Lower temperature for more deterministic output
        )
        
        result_text = response.choices[0].message.content
        if not result_text:
            logger.warning("Empty response from OpenAI")
            return _generate_fallback_insights(transcript)
        
        result = json.loads(result_text)
        
        # ANTI-HALLUCINATION VALIDATION: Validate action items against transcript
        raw_action_items = result.get('action_items', [])
        if raw_action_items:
            logger.info(f"[VALIDATION] Validating {len(raw_action_items)} action items against transcript...")
            
            # Convert to format expected by text_matcher
            tasks_for_validation = []
            for item in raw_action_items:
                if isinstance(item, dict):
                    tasks_for_validation.append({
                        'text': item.get('task', ''),
                        'evidence_quote': item.get('evidence_quote', '')
                    })
                elif isinstance(item, str):
                    tasks_for_validation.append({'text': item, 'evidence_quote': ''})
            
            # Validate against transcript
            validated_tasks = text_matcher.validate_task_list(tasks_for_validation, transcript)
            
            # Convert back to action_items format
            validated_action_items = []
            for task in validated_tasks:
                validated_action_items.append({
                    'task': task.get('text', ''),
                    'evidence_quote': task.get('validation', {}).get('evidence_quote', ''),
                    'confidence': task.get('validation', {}).get('confidence_score', 0)
                })
            
            original_count = len(raw_action_items)
            validated_count = len(validated_action_items)
            rejected_count = original_count - validated_count
            
            if rejected_count > 0:
                logger.warning(f"[HALLUCINATION_FILTER] Rejected {rejected_count}/{original_count} action items as hallucinations")
            
            result['action_items'] = validated_action_items
            result['_validation_metadata'] = {
                'original_count': original_count,
                'validated_count': validated_count,
                'rejected_count': rejected_count,
                'hallucination_rate': round((rejected_count / original_count * 100) if original_count > 0 else 0, 1)
            }
            
            logger.info(f"[VALIDATION_COMPLETE] {validated_count}/{original_count} action items passed validation")
        
        return result
        
    except Exception as e:
        logger.error(f"Direct OpenAI analysis failed: {e}")
        return _generate_fallback_insights(transcript)


def _generate_fallback_insights(transcript):
    """
    Generate basic insights when OpenAI fails.
    
    ANTI-HALLUCINATION: Returns empty action_items since we cannot
    validate anything without AI analysis.
    """
    word_count = len(transcript.split())
    
    return {
        'summary': f"Meeting transcript captured ({word_count} words). AI analysis unavailable.",
        'key_points': [
            f"Transcript contains {word_count} words",
            "Review transcript manually for specific topics"
        ],
        'action_items': [],  # CRITICAL: Empty - we don't hallucinate action items
        'decisions': [],
        'next_steps': [],
        'participants': [],
        'sentiment': 'neutral',
        '_validation_metadata': {
            'fallback_mode': True,
            'reason': 'AI analysis unavailable'
        }
    }