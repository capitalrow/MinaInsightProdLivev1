"""
AI Insights Service
Comprehensive AI-powered analysis for meeting transcripts.
Implements T2.11-T2.22: Summarization, key points, action items, questions, decisions,
sentiment analysis, topic detection, language detection, custom prompts, and quality scoring.
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from openai import OpenAI
from openai._exceptions import OpenAIError

logger = logging.getLogger(__name__)


class AIInsightsService:
    """
    Service for generating AI-powered insights from meeting transcripts.
    Uses OpenAI GPT-4 for intelligent analysis.
    """
    
    def __init__(self):
        """Initialize the AI Insights Service with OpenAI client."""
        self.api_key = os.environ.get('OPENAI_API_KEY')
        self.client = None
        if self.api_key:
            try:
                self.client = OpenAI(api_key=self.api_key)
                logger.info("✅ AI Insights Service initialized with OpenAI")
            except Exception as e:
                logger.error(f"❌ Failed to initialize OpenAI client: {e}")
        else:
            logger.warning("⚠️ OPENAI_API_KEY not set - AI features disabled")
    
    def is_available(self) -> bool:
        """Check if AI service is available."""
        return bool(self.client)
    
    # ============================================
    # Core AI Analysis Methods
    # ============================================
    
    def generate_comprehensive_insights(
        self, 
        transcript_text: str, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate all AI insights in a single call for efficiency.
        Implements T2.11-T2.17 in one optimized request.
        """
        if not self.is_available():
            return self._get_fallback_insights()
        
        try:
            prompt = self._build_comprehensive_prompt(transcript_text, metadata)
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert meeting analyst. Extract structured insights from meeting transcripts."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,
                max_tokens=2000,
                response_format={"type": "json_object"}
            )
            
            insights_json = response.choices[0].message.content
            insights = json.loads(insights_json)
            
            # Add metadata
            insights['generated_at'] = datetime.utcnow().isoformat()
            insights['model'] = 'gpt-4o-mini'
            insights['confidence_score'] = self._calculate_confidence(insights)
            
            logger.info(f"✅ Generated comprehensive insights: {len(insights.get('key_points', []))} key points, {len(insights.get('action_items', []))} actions")
            
            return insights
            
        except OpenAIError as e:
            logger.error(f"❌ OpenAI API error: {e}")
            return self._get_fallback_insights(error=str(e))
        except Exception as e:
            logger.error(f"❌ Failed to generate AI insights: {e}")
            return self._get_fallback_insights(error=str(e))
    
    def _build_comprehensive_prompt(self, transcript: str, metadata: Optional[Dict] = None) -> str:
        """Build optimized prompt for comprehensive analysis."""
        prompt = f"""Analyze this meeting transcript and provide structured insights in JSON format.

TRANSCRIPT:
{transcript[:8000]}  # Limit to ~8k chars for token efficiency

Provide the following in JSON format:
{{
    "summary": "3-paragraph summary of the meeting",
    "key_points": ["list of 5-10 key points discussed"],
    "action_items": [
        {{"task": "description", "assignee": "person or null", "due_date": "date or null", "priority": "high/medium/low"}}
    ],
    "questions": [
        {{"question": "text", "answered": true/false, "answer": "text or null"}}
    ],
    "decisions": [
        {{"decision": "text", "rationale": "text", "timestamp": "approximate time"}}
    ],
    "topics": ["list of main topics discussed"],
    "sentiment": {{"overall": "positive/neutral/negative", "score": 0.0-1.0, "explanation": "brief"}},
    "risks_concerns": ["list of risks or concerns mentioned"],
    "next_steps": ["list of agreed next steps"]
}}

Be concise, accurate, and actionable. Use null for missing information."""
        
        if metadata:
            prompt += f"\n\nMeeting Metadata: {json.dumps(metadata)}"
        
        return prompt
    
    # ============================================
    # Individual Analysis Methods (T2.11-T2.17)
    # ============================================
    
    def generate_summary(self, transcript: str) -> Dict[str, Any]:
        """T2.11: Generate auto-summary of meeting transcript."""
        if not self.is_available():
            return {"summary": "AI summary not available (API key not configured)", "paragraphs": []}
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at summarizing meetings concisely and professionally."
                    },
                    {
                        "role": "user",
                        "content": f"Summarize this meeting transcript in 3 clear paragraphs:\n\n{transcript[:6000]}"
                    }
                ],
                temperature=0.5,
                max_tokens=500
            )
            
            summary = response.choices[0].message.content.strip()
            paragraphs = [p.strip() for p in summary.split('\n\n') if p.strip()]
            
            return {
                "summary": summary,
                "paragraphs": paragraphs,
                "word_count": len(summary.split()),
                "generated_at": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to generate summary: {e}")
            return {"summary": f"Error generating summary: {str(e)}", "paragraphs": []}
    
    def extract_key_points(self, transcript: str) -> List[Dict[str, Any]]:
        """T2.12: Extract 5-10 key points from transcript."""
        if not self.is_available():
            return []
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "Extract 5-10 key points from meeting transcripts. Be specific and actionable."
                    },
                    {
                        "role": "user",
                        "content": f"Extract key points from this meeting:\n\n{transcript[:6000]}\n\nReturn as JSON array: [{{\"point\": \"text\", \"importance\": \"high/medium/low\"}}]"
                    }
                ],
                temperature=0.3,
                max_tokens=600,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            return result.get('key_points', [])
        except Exception as e:
            logger.error(f"Failed to extract key points: {e}")
            return []
    
    def extract_action_items(self, transcript: str) -> List[Dict[str, Any]]:
        """T2.13: Extract action items (who, what, when)."""
        if not self.is_available():
            return []
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": """Extract ALL action items and tasks mentioned in meeting transcripts.

EXTRACTION PHILOSOPHY:
- Be GENEROUS in extraction - capture all potential tasks mentioned
- Include work tasks, personal tasks, and commitments
- Extract even if phrased conversationally (e.g., "I need to...", "I'm going to...")
- Quality filtering happens in the next pipeline stage

EXAMPLES of what to extract:
- Business: "Send proposal to client", "Review Q4 budget", "Schedule team meeting"
- Personal: "Buy groceries", "Clean office", "Call dentist"  
- Conversational: "I need to prepare the report", "We should follow up with John"
- Commitments: "Get cash from ATM", "Book train ticket", "Define handover tasks"

Extract everything that represents a task, action, or commitment - err on the side of inclusion."""
                    },
                    {
                        "role": "user",
                        "content": f"""Extract ALL action items and tasks from this transcript. Be generous - include any task, commitment, or to-do item mentioned, whether business or personal.

TRANSCRIPT:
{transcript[:6000]}

Return as JSON array with ALL tasks found:
{{"action_items": [{{"task": "text", "assignee": "person or null", "due_date": "date or null", "priority": "high/medium/low"}}]}}"""
                    }
                ],
                temperature=0.2,
                max_tokens=800,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            action_items = result.get('action_items', [])
            logger.info(f"[AI Extraction] Extracted {len(action_items)} raw action items before validation")
            for i, item in enumerate(action_items):
                logger.debug(f"  [{i+1}] {item.get('task', 'NO_TASK')[:80]}")
            return action_items
        except Exception as e:
            logger.error(f"Failed to extract action items: {e}")
            return []
    
    def extract_questions(self, transcript: str) -> List[Dict[str, Any]]:
        """T2.14: Extract questions asked in meeting."""
        if not self.is_available():
            return []
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "Extract questions from meeting transcripts and identify if they were answered."
                    },
                    {
                        "role": "user",
                        "content": f"Extract questions:\n\n{transcript[:6000]}\n\nReturn as JSON: {{\"questions\": [{{\"question\": \"text\", \"answered\": true/false, \"answer\": \"text or null\", \"asker\": \"person or null\"}}]}}"
                    }
                ],
                temperature=0.3,
                max_tokens=700,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            return result.get('questions', [])
        except Exception as e:
            logger.error(f"Failed to extract questions: {e}")
            return []
    
    def extract_decisions(self, transcript: str) -> List[Dict[str, Any]]:
        """T2.15: Extract decisions made in meeting."""
        if not self.is_available():
            return []
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "Extract key decisions from meeting transcripts with context and rationale."
                    },
                    {
                        "role": "user",
                        "content": f"Extract decisions:\n\n{transcript[:6000]}\n\nReturn as JSON: {{\"decisions\": [{{\"decision\": \"text\", \"rationale\": \"text\", \"impact\": \"high/medium/low\", \"decided_by\": \"person or null\"}}]}}"
                    }
                ],
                temperature=0.2,
                max_tokens=700,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            return result.get('decisions', [])
        except Exception as e:
            logger.error(f"Failed to extract decisions: {e}")
            return []
    
    def analyze_sentiment(self, transcript: str) -> Dict[str, Any]:
        """T2.16: Analyze sentiment of meeting."""
        if not self.is_available():
            return {"overall": "neutral", "score": 0.5, "explanation": "AI not available"}
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "Analyze the overall sentiment of meeting transcripts."
                    },
                    {
                        "role": "user",
                        "content": f"Analyze sentiment:\n\n{transcript[:6000]}\n\nReturn as JSON: {{\"overall\": \"positive/neutral/negative\", \"score\": 0.0-1.0, \"explanation\": \"brief\", \"key_moments\": [\"positive/negative moments\"]}}"
                    }
                ],
                temperature=0.3,
                max_tokens=400,
                response_format={"type": "json_object"}
            )
            
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            logger.error(f"Failed to analyze sentiment: {e}")
            return {"overall": "neutral", "score": 0.5, "explanation": f"Error: {str(e)}"}
    
    def detect_topics(self, transcript: str) -> List[str]:
        """T2.17: Detect topics discussed in meeting."""
        if not self.is_available():
            return []
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "Identify main topics discussed in meeting transcripts."
                    },
                    {
                        "role": "user",
                        "content": f"Identify topics:\n\n{transcript[:6000]}\n\nReturn as JSON: {{\"topics\": [\"topic1\", \"topic2\", ...]}}"
                    }
                ],
                temperature=0.3,
                max_tokens=300,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            return result.get('topics', [])
        except Exception as e:
            logger.error(f"Failed to detect topics: {e}")
            return []
    
    def detect_language(self, transcript: str) -> Dict[str, Any]:
        """T2.18: Detect language of meeting transcript."""
        if not self.is_available():
            return {"language": "unknown", "confidence": 0.0, "code": "und"}
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "Identify the primary language of the provided text."
                    },
                    {
                        "role": "user",
                        "content": f"Detect language:\n\n{transcript[:2000]}\n\nReturn as JSON: {{\"language\": \"English\", \"code\": \"en\", \"confidence\": 0.95, \"multilingual\": false, \"other_languages\": []}}"
                    }
                ],
                temperature=0.1,
                max_tokens=100,
                response_format={"type": "json_object"}
            )
            
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            logger.error(f"Failed to detect language: {e}")
            return {"language": "unknown", "confidence": 0.0, "code": "und", "error": str(e)}
    
    # ============================================
    # Advanced Features (T2.19-T2.22)
    # ============================================
    
    def execute_custom_prompt(self, transcript: str, custom_prompt: str) -> Dict[str, Any]:
        """T2.19: Execute user-defined custom AI prompt."""
        if not self.is_available():
            return {"result": "AI not available", "success": False}
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are analyzing a meeting transcript based on user's custom requirements."
                    },
                    {
                        "role": "user",
                        "content": f"TRANSCRIPT:\n{transcript[:6000]}\n\nUSER PROMPT:\n{custom_prompt}\n\nProvide response in JSON format."
                    }
                ],
                temperature=0.5,
                max_tokens=1000,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            return {"result": result, "success": True, "prompt": custom_prompt}
        except Exception as e:
            logger.error(f"Failed to execute custom prompt: {e}")
            return {"result": str(e), "success": False}
    
    def _calculate_confidence(self, insights: Dict[str, Any]) -> float:
        """T2.22: Calculate confidence score for AI-generated insights."""
        # Simple heuristic-based confidence calculation
        score = 0.7  # Base confidence
        
        # Increase confidence if multiple insights were generated
        if insights.get('key_points') and len(insights['key_points']) >= 5:
            score += 0.1
        
        if insights.get('action_items') and len(insights['action_items']) >= 3:
            score += 0.1
        
        if insights.get('summary') and len(insights['summary']) > 100:
            score += 0.05
        
        # Cap at 0.95 (never 100% confident)
        return min(score, 0.95)
    
    def _get_fallback_insights(self, error: Optional[str] = None) -> Dict[str, Any]:
        """Return fallback insights when AI is unavailable."""
        return {
            "summary": "AI-powered summary not available. Please configure OPENAI_API_KEY.",
            "key_points": [],
            "action_items": [],
            "questions": [],
            "decisions": [],
            "topics": [],
            "sentiment": {"overall": "neutral", "score": 0.5, "explanation": "AI not available"},
            "risks_concerns": [],
            "next_steps": [],
            "error": error,
            "ai_available": False,
            "generated_at": datetime.utcnow().isoformat()
        }
    
    # ============================================
    # Meeting Title Generation
    # ============================================
    
    def generate_meeting_title(self, transcript: str, max_length: int = 60) -> Dict[str, Any]:
        """
        Generate a contextual, descriptive meeting title from transcript content.
        
        Args:
            transcript: The meeting transcript text
            max_length: Maximum length for the title (default 60 chars)
            
        Returns:
            Dict with 'title' and metadata
        """
        if not self.is_available():
            return {"title": None, "fallback": True, "error": "AI not available"}
        
        if not transcript or len(transcript.strip()) < 20:
            return {"title": None, "fallback": True, "error": "Transcript too short"}
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": """You are an expert at creating concise, descriptive meeting titles.
Generate a short, contextual title that captures the main topic or purpose of the meeting.

RULES:
- Maximum 60 characters
- Be specific and descriptive (e.g., "Q4 Budget Review with Finance Team")
- Include key topics, people mentioned, or action focus
- Avoid generic titles like "Meeting" or "Discussion"
- Use title case
- No quotes or special characters"""
                    },
                    {
                        "role": "user",
                        "content": f"Generate a concise meeting title for this transcript:\n\n{transcript[:3000]}\n\nRespond with ONLY the title, nothing else."
                    }
                ],
                temperature=0.3,
                max_tokens=30
            )
            
            title = response.choices[0].message.content.strip()
            # Clean up: remove quotes if AI added them
            title = title.strip('"\'')
            # Enforce max length
            if len(title) > max_length:
                title = title[:max_length-3] + "..."
            
            logger.info(f"✅ Generated meeting title: '{title}'")
            return {
                "title": title,
                "fallback": False,
                "model": "gpt-4o-mini",
                "generated_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to generate meeting title: {e}")
            return {"title": None, "fallback": True, "error": str(e)}
    
    # ============================================
    # Cost Optimization (T2.20)
    # ============================================
    
    def estimate_cost(self, transcript_length: int) -> Dict[str, Any]:
        """Estimate API cost for processing transcript."""
        # GPT-4 pricing: ~$0.03/1K input tokens, ~$0.06/1K output tokens
        # Rough estimate: 1 char ≈ 0.25 tokens
        estimated_tokens = transcript_length * 0.25
        estimated_cost = (estimated_tokens / 1000) * 0.03 + (500 / 1000) * 0.06  # ~500 output tokens
        
        return {
            "estimated_input_tokens": int(estimated_tokens),
            "estimated_output_tokens": 500,
            "estimated_cost_usd": round(estimated_cost, 4),
            "model": "gpt-4o-mini"
        }


# Singleton instance
ai_insights_service = AIInsightsService()
