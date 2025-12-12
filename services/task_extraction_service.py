"""
Task Extraction Service
AI-powered service for extracting actionable tasks from meeting transcripts and content.
"""

import json
import re
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta, date
from dataclasses import dataclass
from sqlalchemy import func
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
    task_type: str = "action_item"  # decision, action_item, follow_up, research


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
        
        # Get meeting transcript - try 'final' segments first, fallback to all
        stmt = select(Segment).filter_by(
            session_id=meeting.session.id,
            kind='final'
        ).order_by(Segment.start_ms)
        segments = db.session.execute(stmt).scalars().all()
        
        # Fallback: if no 'final' segments, get all segments with text
        if not segments:
            stmt = select(Segment).filter(
                Segment.session_id == meeting.session.id,
                Segment.text.isnot(None),
                Segment.text != ''
            ).order_by(Segment.start_ms)
            segments = db.session.execute(stmt).scalars().all()
        
        if not segments:
            return []
        
        transcript = self._build_transcript(segments)
        
        # Extract tasks using AI with segment tracking
        ai_tasks = await self._extract_tasks_with_ai(transcript, meeting, segments)
        
        # Extract tasks using pattern matching (backup/supplement)
        pattern_tasks = self._extract_tasks_with_patterns(transcript, segments)
        
        # Combine and deduplicate
        all_tasks = self._merge_and_deduplicate_tasks(ai_tasks, pattern_tasks)
        
        # Link tasks to transcript segments for "Jump to Transcript" feature
        self._link_tasks_to_segments(all_tasks, segments)
        
        return all_tasks

    async def _extract_tasks_with_ai(self, transcript: str, meeting: Meeting, segments=None) -> List[ExtractedTask]:
        """Use OpenAI to extract tasks from meeting transcript with segment tracking."""
        if not self.client:
            return []
        
        system_prompt = """You are an AI assistant specialized in extracting actionable tasks from meeting transcripts.
        
        Extract all action items, tasks, decisions, and follow-ups mentioned in the meeting. For each item, provide:
        1. A clear, concise title
        2. A brief description if available
        3. Priority level (low, medium, high, urgent)
        4. Category if apparent (e.g., "development", "marketing", "operations")
        5. Confidence score (0.0 to 1.0) in your extraction
        6. Any mentioned assignee
        7. Any mentioned due date or timeline
        8. The exact quote from the transcript where this was mentioned
        9. If known, who said it (speaker name)
        10. Task type classification - IMPORTANT: Classify each item as one of:
            - "decision": Final conclusions or choices made ("We decided to...", "Let's go with...", "The plan is...")
            - "action_item": Specific tasks assigned to someone ("You need to...", "Can you...", "I'll handle...")
            - "follow_up": Items to revisit or continue later ("Let's circle back...", "We'll revisit...", "Next meeting we should...")
            - "research": Questions to investigate or explore ("We need to find out...", "Look into...", "Research whether...")
        
        Focus on explicit action items, commitments, decisions, and next steps. Avoid including general discussion points.
        
        Return a JSON array of tasks with this structure:
        {
          "tasks": [
            {
              "title": "Clear action title",
              "description": "Optional description",
              "priority": "medium",
              "category": "optional category",
              "confidence": 0.85,
              "task_type": "action_item",
              "assigned_to": "person name if mentioned",
              "due_date_text": "timeline if mentioned",
              "context": "relevant quote from transcript",
              "speaker": "name of person who said it if identifiable"
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
                # Validate task_type
                raw_task_type = task_data.get("task_type", "action_item").strip().lower()
                valid_types = ["decision", "action_item", "follow_up", "research"]
                task_type = raw_task_type if raw_task_type in valid_types else "action_item"
                
                # Extract speaker and quote from AI response
                speaker = task_data.get("speaker", "").strip() or None
                evidence_quote = task_data.get("context", "").strip() or None
                
                task = ExtractedTask(
                    title=task_data.get("title", "").strip(),
                    description=task_data.get("description", "").strip() or None,
                    priority=task_data.get("priority", "medium"),
                    category=task_data.get("category", "").strip() or None,
                    confidence=float(task_data.get("confidence", 0.5)),
                    assigned_to=task_data.get("assigned_to", "").strip() or None,
                    due_date_text=task_data.get("due_date_text", "").strip() or None,
                    task_type=task_type,
                    context={
                        "source": "ai",
                        "quote": evidence_quote,  # For segment matching
                        "evidence_quote": evidence_quote,  # For template display
                        "speaker": speaker,
                        "refined_text": task_data.get("title", "").strip()  # AI-refined version
                    }
                )
                
                if task.title and len(task.title) > 3:  # Basic validation
                    tasks.append(task)
            
            return tasks
            
        except Exception as e:
            print(f"AI task extraction failed: {e}")
            return []

    def _extract_tasks_with_patterns(self, transcript: str, segments=None) -> List[ExtractedTask]:
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
                        
                        # Infer task_type from pattern/keywords
                        task_type = self._infer_task_type(line)
                        
                        task = ExtractedTask(
                            title=task_text[:100],  # Limit title length
                            priority=priority,
                            confidence=0.6,  # Lower confidence for pattern matching
                            assigned_to=assignee,
                            task_type=task_type,
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

    def _infer_task_type(self, text: str) -> str:
        """Infer task type from text using keyword patterns."""
        text_lower = text.lower()
        
        # Decision patterns
        decision_keywords = [
            "decided", "agreed", "confirmed", "approved", "finalized",
            "conclusion", "let's go with", "we'll use", "the plan is",
            "we're going to", "settled on"
        ]
        
        # Follow-up patterns
        followup_keywords = [
            "follow up", "circle back", "revisit", "next meeting",
            "touch base", "check in", "later", "schedule", "follow-up",
            "get back to", "reconnect"
        ]
        
        # Research patterns
        research_keywords = [
            "research", "investigate", "find out", "look into",
            "explore", "analyze", "study", "discover", "learn about",
            "figure out", "understand", "evaluate", "assess"
        ]
        
        if any(kw in text_lower for kw in decision_keywords):
            return "decision"
        elif any(kw in text_lower for kw in followup_keywords):
            return "follow_up"
        elif any(kw in text_lower for kw in research_keywords):
            return "research"
        else:
            return "action_item"

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

    def _link_tasks_to_segments(self, tasks: List[ExtractedTask], segments) -> None:
        """Link extracted tasks to transcript segments for jump-to-transcript feature.
        
        CROWN⁴.6: Uses fuzzy matching and prevents overwrites during deduplication.
        Each task instance gets its own transcript_span - dedupe doesn't clobber it.
        """
        if not segments:
            return
        
        for task in tasks:
            # Skip if already has a transcript_span (prevents deduplication overwrites)
            if task.context and task.context.get("transcript_span"):
                continue
            
            if not task.context or not task.context.get("quote"):
                continue
            
            quote = task.context.get("quote", "").strip().lower()
            if not quote or len(quote) < 10:  # Skip very short quotes
                continue
            
            # Find the segment(s) that contain this quote using fuzzy matching
            matched_segments = []
            for segment in segments:
                segment_text = segment.text.lower()
                
                # Exact substring match
                if quote in segment_text:
                    matched_segments.append(segment)
                # Fuzzy match: check if significant words overlap (>70%)
                elif self._fuzzy_match_quote(quote, segment_text):
                    matched_segments.append(segment)
            
            if matched_segments:
                # Use the first matched segment (or combine nearby ones within 5 seconds)
                first_segment = matched_segments[0]
                last_segment = matched_segments[-1] if len(matched_segments) > 1 else first_segment
                
                # Only combine segments if they're within 5 seconds of each other
                if last_segment.start_ms and first_segment.start_ms:
                    time_diff_ms = last_segment.start_ms - first_segment.start_ms
                    if time_diff_ms > 5000:  # More than 5 seconds apart
                        last_segment = first_segment
                        matched_segments = [first_segment]
                
                # Store transcript span in task context (unique to this task instance)
                if not task.context:
                    task.context = {}
                
                task.context["transcript_span"] = {
                    "start_ms": first_segment.start_ms,
                    "end_ms": last_segment.end_ms,
                    "segment_ids": [seg.id for seg in matched_segments]
                }

    def _fuzzy_match_quote(self, quote: str, segment_text: str, threshold: float = 0.7) -> bool:
        """Fuzzy match quote to segment text based on significant word overlap.
        
        CROWN⁴.6: Handles cases where AI paraphrases the quote.
        """
        # Extract significant words (>3 chars, not common stop words)
        stop_words = {'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'her', 'was', 'one', 'our', 'out', 'day', 'get', 'has', 'him', 'his', 'how', 'its', 'may', 'new', 'now', 'old', 'see', 'two', 'who', 'boy', 'did', 'its', 'let', 'put', 'say', 'she', 'too', 'use'}
        
        quote_words = set(word for word in quote.split() if len(word) > 3 and word not in stop_words)
        segment_words = set(word for word in segment_text.split() if len(word) > 3 and word not in stop_words)
        
        if not quote_words or not segment_words:
            return False
        
        # Calculate overlap ratio
        intersection = quote_words.intersection(segment_words)
        overlap_ratio = len(intersection) / len(quote_words)
        
        return overlap_ratio >= threshold

    def create_tasks_in_database(self, meeting_id: int, extracted_tasks: List[ExtractedTask]) -> List[Task]:
        """Create Task objects in database from extracted tasks."""
        created_tasks = []
        
        # CROWN⁴.5 Phase 3: Calculate next position for drag-drop ordering
        # Get meeting to determine workspace, then find max position
        meeting = db.session.query(Meeting).filter_by(id=meeting_id).first()
        if not meeting:
            return []
        
        max_position = db.session.query(func.max(Task.position)).join(Meeting).filter(
            Meeting.workspace_id == meeting.workspace_id,
            Task.deleted_at.is_(None)
        ).scalar() or -1
        
        current_position = max_position + 1
        
        for extracted_task in extracted_tasks:
            try:
                # Parse due date if mentioned
                due_date = self._parse_due_date(extracted_task.due_date_text)
                
                # Find assignee if mentioned
                assigned_to_id = self._find_user_by_name(extracted_task.assigned_to)
                
                # Extract transcript_span from context if available
                transcript_span = extracted_task.context.get("transcript_span") if extracted_task.context else None
                
                task = Task(
                    meeting_id=meeting_id,
                    title=extracted_task.title,
                    description=extracted_task.description,
                    priority=extracted_task.priority,
                    category=extracted_task.category,
                    task_type=extracted_task.task_type,
                    due_date=due_date,
                    assigned_to_id=assigned_to_id,
                    extracted_by_ai=True,
                    confidence_score=extracted_task.confidence,
                    extraction_context=extracted_task.context,
                    transcript_span=transcript_span,
                    position=current_position
                )
                
                db.session.add(task)
                created_tasks.append(task)
                current_position += 1  # Increment for next task
                
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