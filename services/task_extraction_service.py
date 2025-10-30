"""
Task Extraction Service
AI-powered service for extracting actionable tasks from meeting transcripts and content.
"""

import json
import re
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta, date
from dataclasses import dataclass
from models import db, Task, Meeting, Segment
from services.openai_client_manager import get_openai_client


@dataclass
class ExtractedTask:
    """Represents a task extracted from meeting content."""
    title: str
    description: Optional[str] = None
    priority: str = "medium"  # low, medium, high, urgent
    category: Optional[str] = None
    confidence: float = 0.0  # AI confidence score 0-1
    context: Optional[Dict] = None  # Context from transcript
    assigned_to: Optional[str] = None  # Mentioned assignee
    due_date_text: Optional[str] = None  # Natural language due date


class TaskExtractionService:
    """Service for AI-powered task extraction from meeting content."""
    
    def __init__(self):
        self.client = get_openai_client()
        self.task_patterns = [
            r"(?:action item|task|todo|follow up|next step)s?[:\-\s]+(.+)",
            r"(.+)\s+(?:needs to|should|must|will)\s+(.+)",
            r"(?:assign|give|delegate)\s+(.+)\s+to\s+(\w+)",
            r"(.+)\s+by\s+(next week|tomorrow|end of week|friday|monday)",
            r"let['\s]*s\s+(.+)",
            r"we need to\s+(.+)",
            r"someone should\s+(.+)",
            r"(?:I|we|you)['\s]*ll\s+(.+)"
        ]
        
        self.priority_keywords = {
            "urgent": ["urgent", "asap", "immediately", "critical", "emergency"],
            "high": ["important", "priority", "soon", "this week", "tomorrow"],
            "medium": ["should", "need to", "follow up", "next week"],
            "low": ["eventually", "when possible", "nice to have", "consider"]
        }
        
        self.assignee_patterns = [
            r"(\w+)\s+(?:will|should|needs to|is going to)\s+(.+)",
            r"assign\s+(.+)\s+to\s+(\w+)",
            r"(\w+)\s+is\s+responsible\s+for\s+(.+)",
            r"(\w+)\s+can you\s+(.+)"
        ]

    async def extract_tasks_from_meeting(self, meeting_id: int) -> List[ExtractedTask]:
        """Extract tasks from a complete meeting using AI and pattern matching."""
        from sqlalchemy import select
        meeting = db.session.get(Meeting, meeting_id)
        if not meeting or not meeting.session:
            return []
        
        # Get meeting transcript
        stmt = select(Segment).filter_by(
            session_id=meeting.session.id,
            is_final=True
        ).order_by(Segment.start_ms)
        segments = db.session.execute(stmt).scalars().all()
        
        if not segments:
            return []
        
        transcript = self._build_transcript(segments)
        
        # Extract tasks using AI
        ai_tasks = await self._extract_tasks_with_ai(transcript, meeting)
        
        # Extract tasks using pattern matching (backup/supplement)
        pattern_tasks = self._extract_tasks_with_patterns(transcript)
        
        # Combine and deduplicate
        all_tasks = self._merge_and_deduplicate_tasks(ai_tasks, pattern_tasks)
        
        return all_tasks

    async def _extract_tasks_with_ai(self, transcript: str, meeting: Meeting) -> List[ExtractedTask]:
        """Use OpenAI to extract tasks from meeting transcript."""
        if not self.client:
            return []
        
        system_prompt = """You are an AI assistant specialized in extracting actionable tasks from meeting transcripts.
        
        Extract all action items, tasks, and follow-ups mentioned in the meeting. For each task, provide:
        1. A clear, concise title
        2. A brief description if available
        3. Priority level (low, medium, high, urgent)
        4. Category if apparent (e.g., "development", "marketing", "operations")
        5. Confidence score (0.0 to 1.0) in your extraction
        6. Any mentioned assignee
        7. Any mentioned due date or timeline
        
        Focus on explicit action items, commitments, and next steps. Avoid including general discussion points.
        
        Return a JSON array of tasks with this structure:
        {
          "tasks": [
            {
              "title": "Clear action title",
              "description": "Optional description",
              "priority": "medium",
              "category": "optional category",
              "confidence": 0.85,
              "assigned_to": "person name if mentioned",
              "due_date_text": "timeline if mentioned",
              "context": "relevant quote from transcript"
            }
          ]
        }"""
        
        user_prompt = f"""Meeting: {meeting.title}
        Date: {meeting.created_at.strftime('%Y-%m-%d')}
        
        Transcript:
        {transcript[:4000]}  # Limit to first 4000 chars for API limits
        
        Extract all actionable tasks from this meeting transcript."""
        
        try:
            # Use unified AI model manager with GPT-4.1 fallback
            from services.ai_model_manager import AIModelManager
            
            def make_api_call(model: str):
                return self.client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.3,
                    max_tokens=1500
                )
            
            result_obj = AIModelManager.call_with_fallback(
                make_api_call,
                operation_name="task extraction"
            )
            
            if not result_obj.success:
                raise Exception(f"All AI models failed")
            
            response = result_obj.response
            
            content = response.choices[0].message.content
            if not content:
                return []
            result = json.loads(content)
            tasks = []
            
            for task_data in result.get("tasks", []):
                task = ExtractedTask(
                    title=task_data.get("title", "").strip(),
                    description=task_data.get("description", "").strip() or None,
                    priority=task_data.get("priority", "medium"),
                    category=task_data.get("category", "").strip() or None,
                    confidence=float(task_data.get("confidence", 0.5)),
                    assigned_to=task_data.get("assigned_to", "").strip() or None,
                    due_date_text=task_data.get("due_date_text", "").strip() or None,
                    context={"source": "ai", "quote": task_data.get("context", "")}
                )
                
                if task.title and len(task.title) > 3:  # Basic validation
                    tasks.append(task)
            
            return tasks
            
        except Exception as e:
            print(f"AI task extraction failed: {e}")
            return []

    def _extract_tasks_with_patterns(self, transcript: str) -> List[ExtractedTask]:
        """Extract tasks using regex patterns as backup method."""
        tasks = []
        lines = transcript.split('\n')
        
        for line in lines:
            line = line.strip()
            if len(line) < 10:  # Skip very short lines
                continue
            
            # Try each pattern
            for pattern in self.task_patterns:
                matches = re.finditer(pattern, line, re.IGNORECASE)
                for match in matches:
                    task_text = match.group(1).strip()
                    
                    if len(task_text) > 5:  # Basic validation
                        priority = self._determine_priority(line)
                        assignee = self._extract_assignee(line)
                        
                        task = ExtractedTask(
                            title=task_text[:100],  # Limit title length
                            priority=priority,
                            confidence=0.6,  # Lower confidence for pattern matching
                            assigned_to=assignee,
                            context={"source": "pattern", "line": line}
                        )
                        tasks.append(task)
        
        return tasks

    def _determine_priority(self, text: str) -> str:
        """Determine task priority based on keywords."""
        text_lower = text.lower()
        
        for priority, keywords in self.priority_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                return priority
        
        return "medium"  # Default priority

    def _extract_assignee(self, text: str) -> Optional[str]:
        """Extract assignee from text using patterns."""
        for pattern in self.assignee_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None

    def _build_transcript(self, segments) -> str:
        """Build a readable transcript from segments."""
        transcript_lines = []
        current_speaker = None
        
        for segment in segments:
            speaker = getattr(segment, 'speaker', 'Speaker')
            text = segment.text.strip()
            
            if speaker != current_speaker:
                transcript_lines.append(f"\n{speaker}: {text}")
                current_speaker = speaker
            else:
                transcript_lines.append(f" {text}")
        
        return " ".join(transcript_lines)

    def _merge_and_deduplicate_tasks(self, ai_tasks: List[ExtractedTask], 
                                   pattern_tasks: List[ExtractedTask]) -> List[ExtractedTask]:
        """Merge AI and pattern-extracted tasks, removing duplicates."""
        all_tasks = ai_tasks + pattern_tasks
        
        # Simple deduplication based on title similarity
        unique_tasks = []
        for task in all_tasks:
            is_duplicate = False
            for existing in unique_tasks:
                if self._are_tasks_similar(task.title, existing.title):
                    # Keep the higher confidence task
                    if task.confidence > existing.confidence:
                        unique_tasks.remove(existing)
                        unique_tasks.append(task)
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                unique_tasks.append(task)
        
        return unique_tasks

    def _are_tasks_similar(self, title1: str, title2: str, threshold: float = 0.7) -> bool:
        """Check if two task titles are similar enough to be considered duplicates."""
        # Simple similarity check - could be enhanced with more sophisticated NLP
        words1 = set(title1.lower().split())
        words2 = set(title2.lower().split())
        
        if not words1 or not words2:
            return False
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        similarity = len(intersection) / len(union)
        return similarity >= threshold

    def create_tasks_in_database(self, meeting_id: int, extracted_tasks: List[ExtractedTask]) -> List[Task]:
        """Create Task objects in database from extracted tasks."""
        created_tasks = []
        
        for extracted_task in extracted_tasks:
            try:
                # Parse due date if mentioned
                due_date = self._parse_due_date(extracted_task.due_date_text)
                
                # Find assignee if mentioned
                assigned_to_id = self._find_user_by_name(extracted_task.assigned_to)
                
                task = Task(
                    meeting_id=meeting_id,
                    title=extracted_task.title,
                    description=extracted_task.description,
                    priority=extracted_task.priority,
                    category=extracted_task.category,
                    due_date=due_date,
                    assigned_to_id=assigned_to_id,
                    extracted_by_ai=True,
                    confidence_score=extracted_task.confidence,
                    extraction_context=extracted_task.context
                )
                
                db.session.add(task)
                created_tasks.append(task)
                
            except Exception as e:
                print(f"Failed to create task: {e}")
                continue
        
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"Failed to save tasks: {e}")
            return []
        
        return created_tasks

    def _parse_due_date(self, due_date_text: Optional[str]) -> Optional[date]:
        """Parse natural language due date into datetime.date."""
        if not due_date_text:
            return None
        
        due_date_text = due_date_text.lower().strip()
        today = datetime.now().date()
        
        # Simple date parsing - could be enhanced
        if "tomorrow" in due_date_text:
            return today + timedelta(days=1)
        elif "next week" in due_date_text:
            return today + timedelta(weeks=1)
        elif "end of week" in due_date_text or "friday" in due_date_text:
            days_until_friday = (4 - today.weekday()) % 7
            if days_until_friday == 0:  # Today is Friday
                days_until_friday = 7
            return today + timedelta(days=days_until_friday)
        elif "monday" in due_date_text:
            days_until_monday = (0 - today.weekday()) % 7
            if days_until_monday == 0:  # Today is Monday
                days_until_monday = 7
            return today + timedelta(days=days_until_monday)
        
        return None

    def _find_user_by_name(self, name: Optional[str]) -> Optional[int]:
        """Find user ID by name (fuzzy matching)."""
        if not name:
            return None
        
        from models import User
        from sqlalchemy import select, or_
        
        name = name.strip().lower()
        
        # Try exact matches first
        stmt = select(User).filter(
            or_(
                User.username.ilike(f"%{name}%"),
                User.first_name.ilike(f"%{name}%"),
                User.last_name.ilike(f"%{name}%"),
                User.display_name.ilike(f"%{name}%")
            )
        )
        user = db.session.execute(stmt).scalar_one_or_none()
        
        return user.id if user else None

    async def process_meeting_for_tasks(self, meeting_id: int) -> Dict:
        """Complete workflow: extract and create tasks for a meeting."""
        try:
            # Extract tasks
            extracted_tasks = await self.extract_tasks_from_meeting(meeting_id)
            
            if not extracted_tasks:
                return {
                    "success": True,
                    "message": "No tasks found in meeting",
                    "tasks_created": 0,
                    "tasks": []
                }
            
            # Create tasks in database
            created_tasks = self.create_tasks_in_database(meeting_id, extracted_tasks)
            
            return {
                "success": True,
                "message": f"Successfully extracted {len(created_tasks)} tasks",
                "tasks_created": len(created_tasks),
                "tasks": [task.to_dict() for task in created_tasks]
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Task extraction failed: {str(e)}",
                "tasks_created": 0,
                "tasks": []
            }


# Singleton instance
task_extraction_service = TaskExtractionService()