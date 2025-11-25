"""
CROWN⁹ Copilot Intent Classification Service

Classifies user queries into actionable intents and extracts entities
for intelligent routing and response generation.

Intent Types:
- task_creation: Create/update/delete tasks
- meeting_scheduling: Schedule/update meetings
- calendar_query: Ask about calendar/schedule
- data_query: Query workspace data (analytics, tasks, etc.)
- general_conversation: General questions/chat
- action_trigger: Execute specific actions
"""

import logging
import re
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class Intent(str, Enum):
    """Supported intent types."""
    TASK_CREATION = "task_creation"
    TASK_UPDATE = "task_update"
    TASK_QUERY = "task_query"
    MEETING_SCHEDULING = "meeting_scheduling"
    CALENDAR_QUERY = "calendar_query"
    DATA_QUERY = "data_query"
    ANALYTICS_QUERY = "analytics_query"
    GENERAL_CONVERSATION = "general_conversation"
    ACTION_TRIGGER = "action_trigger"
    HELP = "help"


class Entity:
    """Extracted entity from query."""
    def __init__(self, entity_type: str, value: Any, confidence: float = 1.0):
        self.type = entity_type
        self.value = value
        self.confidence = confidence
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'type': self.type,
            'value': self.value,
            'confidence': self.confidence
        }


class IntentClassification:
    """Classification result with intent and entities."""
    def __init__(
        self,
        intent: Intent,
        confidence: float,
        entities: Optional[List[Entity]] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        self.intent = intent
        self.confidence = confidence
        self.entities = entities or []
        self.context = context or {}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'intent': self.intent.value,
            'confidence': self.confidence,
            'entities': [e.to_dict() for e in self.entities],
            'context': self.context
        }


class CopilotIntentClassifier:
    """
    NLP-based intent classifier for Copilot queries.
    
    Uses pattern matching and keyword analysis for fast, reliable classification.
    Can be upgraded to use LLM-based classification for complex queries.
    """
    
    def __init__(self):
        """Initialize intent patterns."""
        self.intent_patterns = self._build_intent_patterns()
        self.entity_extractors = self._build_entity_extractors()
    
    def _build_intent_patterns(self) -> Dict[Intent, List[str]]:
        """Build regex patterns for each intent."""
        return {
            Intent.TASK_CREATION: [
                r'\b(create|add|new|make)\s+(a\s+)?(task|todo|item)',
                r'\bremind\s+me\s+to\b',
                r'\bneed\s+to\s+(do|complete|finish)',
            ],
            Intent.TASK_UPDATE: [
                r'\b(update|edit|change|modify)\s+(task|todo)',
                r'\b(mark|set)\s+(as\s+)?(done|complete|finished)',
                r'\b(delete|remove|cancel)\s+(task|todo)',
            ],
            Intent.TASK_QUERY: [
                r'\b(what|show|list|get)\s+(tasks?|todos?|items?)',
                r'\bmy\s+(tasks?|todos?|pending|assigned)',
                r'\btasks?\s+(for|due|assigned)',
            ],
            Intent.MEETING_SCHEDULING: [
                r'\b(schedule|create|set up|book)\s+(a\s+)?(meeting|call|appointment)',
                r'\bmeet(ing)?\s+with\b',
                r'\b(add|put)\s+.+\s+(on|to)\s+calendar',
            ],
            Intent.CALENDAR_QUERY: [
                r'\b(what|when|show|list).*\s+(calendar|schedule|meetings?|appointments?)',
                r'\bam\s+I\s+(free|available|busy)',
                r'\bmy\s+(schedule|calendar|meetings?)',
            ],
            Intent.ANALYTICS_QUERY: [
                r'\b(show|display|get|analyze)\s+(analytics|stats|metrics|data)',
                r'\bhow\s+(many|much)\b',
                r'\bperformance|progress|report',
            ],
            Intent.ACTION_TRIGGER: [
                r'\b(send|share|export|download|generate)',
                r'\bplease\s+(notify|alert|remind)',
            ],
            Intent.HELP: [
                r'\b(help|how\s+to|what\s+can|show\s+me)',
                r'\bI\s+need\s+help',
            ],
        }
    
    def _build_entity_extractors(self) -> Dict[str, Any]:
        """Build entity extraction patterns."""
        return {
            'date': self._extract_dates,
            'priority': self._extract_priority,
            'person': self._extract_persons,
            'time': self._extract_times,
        }
    
    def classify(self, query: str) -> IntentClassification:
        """
        Classify user query into intent with entities.
        
        Args:
            query: User's natural language query
            
        Returns:
            IntentClassification with intent, confidence, and entities
        """
        query_lower = query.lower().strip()
        
        # Match against intent patterns
        best_intent = Intent.GENERAL_CONVERSATION
        best_confidence = 0.0
        
        for intent, patterns in self.intent_patterns.items():
            for pattern in patterns:
                if re.search(pattern, query_lower, re.IGNORECASE):
                    confidence = 0.9  # High confidence for pattern match
                    if confidence > best_confidence:
                        best_intent = intent
                        best_confidence = confidence
                        break
        
        # If no strong pattern match, use general conversation
        if best_confidence == 0.0:
            best_intent = Intent.GENERAL_CONVERSATION
            best_confidence = 0.7
        
        # Extract entities
        entities = self._extract_all_entities(query)
        
        # Build context
        context = {
            'query': query,
            'query_length': len(query),
            'has_entities': len(entities) > 0
        }
        
        return IntentClassification(
            intent=best_intent,
            confidence=best_confidence,
            entities=entities,
            context=context
        )
    
    def _extract_all_entities(self, query: str) -> List[Entity]:
        """Extract all entities from query."""
        entities = []
        
        for entity_type, extractor in self.entity_extractors.items():
            extracted = extractor(query)
            entities.extend(extracted)
        
        return entities
    
    def _extract_dates(self, query: str) -> List[Entity]:
        """Extract date references from query."""
        entities = []
        query_lower = query.lower()
        
        # Relative dates
        if re.search(r'\btoday\b', query_lower):
            entities.append(Entity('date', datetime.now().date(), 0.95))
        elif re.search(r'\btomorrow\b', query_lower):
            entities.append(Entity('date', (datetime.now() + timedelta(days=1)).date(), 0.95))
        elif re.search(r'\byesterday\b', query_lower):
            entities.append(Entity('date', (datetime.now() - timedelta(days=1)).date(), 0.95))
        elif re.search(r'\bnext\s+week\b', query_lower):
            entities.append(Entity('date_range', 'next_week', 0.9))
        elif re.search(r'\bthis\s+week\b', query_lower):
            entities.append(Entity('date_range', 'this_week', 0.9))
        elif re.search(r'\bnext\s+month\b', query_lower):
            entities.append(Entity('date_range', 'next_month', 0.9))
        
        # Weekdays
        weekdays = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        for day in weekdays:
            if day in query_lower:
                entities.append(Entity('weekday', day, 0.85))
        
        # Absolute dates (basic patterns)
        date_patterns = [
            (r'\b(\d{1,2})/(\d{1,2})/(\d{4})\b', 0.95),  # MM/DD/YYYY
            (r'\b(\d{1,2})-(\d{1,2})-(\d{4})\b', 0.95),  # MM-DD-YYYY
        ]
        
        for pattern, confidence in date_patterns:
            matches = re.findall(pattern, query)
            for match in matches:
                entities.append(Entity('date_string', '/'.join(match), confidence))
        
        return entities
    
    def _extract_priority(self, query: str) -> List[Entity]:
        """Extract priority level from query."""
        entities = []
        query_lower = query.lower()
        
        if re.search(r'\b(urgent|critical|high\s+priority|asap|important)\b', query_lower):
            entities.append(Entity('priority', 'high', 0.9))
        elif re.search(r'\b(low\s+priority|whenever|not\s+urgent)\b', query_lower):
            entities.append(Entity('priority', 'low', 0.9))
        elif re.search(r'\b(medium|normal)\s+priority\b', query_lower):
            entities.append(Entity('priority', 'medium', 0.9))
        
        return entities
    
    def _extract_persons(self, query: str) -> List[Entity]:
        """Extract person names from query."""
        entities = []
        
        # Look for "with [Name]" or "@Name" patterns
        with_pattern = r'\bwith\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b'
        matches = re.findall(with_pattern, query)
        for match in matches:
            entities.append(Entity('person', match, 0.8))
        
        # Mention pattern (@name)
        mention_pattern = r'@([A-Za-z][A-Za-z0-9_]+)'
        matches = re.findall(mention_pattern, query)
        for match in matches:
            entities.append(Entity('mention', match, 0.95))
        
        return entities
    
    def _extract_times(self, query: str) -> List[Entity]:
        """Extract time references from query."""
        entities = []
        
        # Time patterns (e.g., "3pm", "3:30pm", "15:00")
        time_patterns = [
            (r'\b(\d{1,2}):(\d{2})\s*(am|pm)\b', 0.95),
            (r'\b(\d{1,2})\s*(am|pm)\b', 0.9),
            (r'\b(\d{2}):(\d{2})\b', 0.85),  # 24-hour format
        ]
        
        for pattern, confidence in time_patterns:
            matches = re.findall(pattern, query.lower())
            for match in matches:
                time_str = ''.join(match)
                entities.append(Entity('time', time_str, confidence))
        
        return entities


# Global singleton instance
copilot_intent_classifier = CopilotIntentClassifier()
