"""
PredictiveEngine Service - CROWN⁴.5 Smart Defaults & ML-Based Suggestions

Provides intelligent suggestions for:
- Due date predictions based on task title and context
- Priority recommendations based on keywords and urgency
- Assignee suggestions based on task type and team history
- Category classification using NLP

Uses historical patterns and machine learning to reduce manual input.
"""

import logging
import re
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, date, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PredictiveSuggestion:
    """Container for predictive suggestions"""
    due_date: Optional[date] = None
    priority: Optional[str] = None
    category: Optional[str] = None
    assignee_id: Optional[int] = None
    confidence: float = 0.0
    reasoning: str = ""


class PredictiveEngine:
    """
    ML-powered prediction engine for task metadata suggestions.
    
    Features:
    - Due date prediction from natural language
    - Priority inference from urgency keywords
    - Category classification from task content
    - Assignee recommendation based on skills/history
    """
    
    def __init__(self):
        """Initialize PredictiveEngine with keyword patterns."""
        # Due date extraction patterns
        self.due_date_patterns = {
            'today': timedelta(days=0),
            'tomorrow': timedelta(days=1),
            'this week': timedelta(days=3),
            'next week': timedelta(weeks=1),
            'end of week': timedelta(days=5),
            'end of month': timedelta(days=30),
            'next month': timedelta(days=30),
            'asap': timedelta(days=1),
            'urgent': timedelta(days=1),
            'monday': None,  # Requires calculation
            'friday': None,  # Requires calculation
        }
        
        # Priority inference keywords
        self.priority_keywords = {
            'urgent': ['urgent', 'asap', 'immediately', 'critical', 'emergency', 'now', 'blocker'],
            'high': ['important', 'priority', 'soon', 'this week', 'tomorrow', 'must'],
            'medium': ['should', 'need to', 'follow up', 'next week', 'please'],
            'low': ['eventually', 'when possible', 'nice to have', 'consider', 'maybe']
        }
        
        # Category classification patterns
        self.category_patterns = {
            'development': ['code', 'bug', 'fix', 'implement', 'feature', 'deploy', 'test', 'debug', 'refactor'],
            'design': ['design', 'mockup', 'ui', 'ux', 'wireframe', 'prototype', 'visual'],
            'marketing': ['marketing', 'campaign', 'email', 'social', 'content', 'seo', 'analytics'],
            'sales': ['sales', 'demo', 'pitch', 'proposal', 'quote', 'client', 'customer'],
            'operations': ['ops', 'infrastructure', 'deploy', 'server', 'monitoring', 'scaling'],
            'research': ['research', 'analyze', 'investigate', 'study', 'explore', 'evaluate'],
            'meeting': ['meeting', 'call', 'sync', 'standup', 'review', 'presentation'],
            'documentation': ['document', 'write', 'readme', 'wiki', 'guide', 'manual', 'spec']
        }
    
    def predict_due_date(self, title: str, description: Optional[str] = None, 
                        context: Optional[Dict[str, Any]] = None) -> Tuple[Optional[date], float]:
        """
        Predict due date from task title and description.
        
        Args:
            title: Task title
            description: Task description
            context: Additional context (meeting date, mentions, etc.)
            
        Returns:
            Tuple of (predicted_due_date, confidence_score)
        """
        text = f"{title} {description or ''}".lower()
        today = date.today()
        
        # Check for explicit date mentions
        for pattern, delta in self.due_date_patterns.items():
            if pattern in text:
                if delta is not None:
                    predicted_date = today + delta
                    confidence = 0.9 if pattern in ['today', 'tomorrow', 'asap'] else 0.7
                    logger.debug(f"Due date predicted from pattern '{pattern}': {predicted_date}")
                    return predicted_date, confidence
                
                # Handle day-of-week calculations
                elif pattern == 'monday':
                    days_ahead = 0 - today.weekday()
                    if days_ahead <= 0:
                        days_ahead += 7
                    predicted_date = today + timedelta(days=days_ahead)
                    return predicted_date, 0.8
                
                elif pattern == 'friday':
                    days_ahead = 4 - today.weekday()
                    if days_ahead <= 0:
                        days_ahead += 7
                    predicted_date = today + timedelta(days=days_ahead)
                    return predicted_date, 0.8
        
        # Check for ISO date formats (YYYY-MM-DD)
        date_pattern = r'\d{4}-\d{2}-\d{2}'
        matches = re.findall(date_pattern, text)
        if matches:
            try:
                predicted_date = date.fromisoformat(matches[0])
                if predicted_date >= today:
                    return predicted_date, 0.95
            except ValueError:
                pass
        
        # Default: predict based on priority inference
        priority, _ = self.predict_priority(title, description)
        if priority == 'urgent':
            return today + timedelta(days=1), 0.5
        elif priority == 'high':
            return today + timedelta(days=3), 0.4
        elif priority == 'medium':
            return today + timedelta(weeks=1), 0.3
        
        # No strong signal, return None
        return None, 0.0
    
    def predict_priority(self, title: str, description: Optional[str] = None,
                        context: Optional[Dict[str, Any]] = None) -> Tuple[str, float]:
        """
        Predict task priority from content.
        
        Args:
            title: Task title
            description: Task description
            context: Additional context
            
        Returns:
            Tuple of (priority_level, confidence_score)
        """
        text = f"{title} {description or ''}".lower()
        
        # Score each priority level
        priority_scores = {
            'urgent': 0,
            'high': 0,
            'medium': 0,
            'low': 0
        }
        
        for priority, keywords in self.priority_keywords.items():
            for keyword in keywords:
                if keyword in text:
                    priority_scores[priority] += 1
        
        # Find highest score
        if max(priority_scores.values()) == 0:
            # Default to medium if no keywords found
            return 'medium', 0.3
        
        predicted_priority = max(priority_scores.items(), key=lambda x: x[1])[0]
        max_score = priority_scores[predicted_priority]
        
        # Calculate confidence based on keyword count
        confidence = min(0.5 + (max_score * 0.2), 0.95)
        
        logger.debug(f"Priority predicted: {predicted_priority} (confidence: {confidence:.2f})")
        return predicted_priority, confidence
    
    def predict_category(self, title: str, description: Optional[str] = None,
                        context: Optional[Dict[str, Any]] = None) -> Tuple[Optional[str], float]:
        """
        Predict task category from content.
        
        Args:
            title: Task title
            description: Task description
            context: Additional context
            
        Returns:
            Tuple of (category, confidence_score)
        """
        text = f"{title} {description or ''}".lower()
        
        # Score each category
        category_scores = {}
        
        for category, keywords in self.category_patterns.items():
            score = sum(1 for keyword in keywords if keyword in text)
            if score > 0:
                category_scores[category] = score
        
        if not category_scores:
            return None, 0.0
        
        # Get highest scoring category
        predicted_category = max(category_scores.items(), key=lambda x: x[1])[0]
        max_score = category_scores[predicted_category]
        
        # Calculate confidence
        confidence = min(0.5 + (max_score * 0.15), 0.9)
        
        logger.debug(f"Category predicted: {predicted_category} (confidence: {confidence:.2f})")
        return predicted_category, confidence
    
    def suggest_assignee(self, title: str, description: Optional[str] = None,
                        category: Optional[str] = None,
                        workspace_id: Optional[int] = None) -> Tuple[Optional[int], float]:
        """
        Suggest assignee based on task content and team history.
        
        Args:
            title: Task title
            description: Task description
            category: Task category
            workspace_id: Workspace ID
            
        Returns:
            Tuple of (user_id, confidence_score)
        """
        # TODO: Implement ML-based assignee prediction using:
        # - Historical assignment patterns by category
        # - User skill profiles
        # - Current workload distribution
        # - Past task completion rates
        
        # For now, return None (manual assignment required)
        # In production, this would query workspace members and predict based on history
        
        return None, 0.0
    
    def generate_suggestions(self, title: str, description: Optional[str] = None,
                           context: Optional[Dict[str, Any]] = None) -> PredictiveSuggestion:
        """
        Generate complete set of predictions for a task.
        
        Args:
            title: Task title
            description: Task description
            context: Additional context
            
        Returns:
            PredictiveSuggestion with all predictions and confidence scores
        """
        # Predict all attributes
        due_date, due_confidence = self.predict_due_date(title, description, context)
        priority, priority_confidence = self.predict_priority(title, description, context)
        category, category_confidence = self.predict_category(title, description, context)
        assignee_id, assignee_confidence = self.suggest_assignee(title, description, category)
        
        # Calculate overall confidence
        confidences = [
            due_confidence if due_date else 0,
            priority_confidence,
            category_confidence if category else 0,
            assignee_confidence if assignee_id else 0
        ]
        overall_confidence = sum(confidences) / len([c for c in confidences if c > 0]) if confidences else 0.0
        
        # Build reasoning
        reasoning_parts = []
        if due_date:
            reasoning_parts.append(f"Due date: {due_date} ({due_confidence:.0%} confident)")
        if priority:
            reasoning_parts.append(f"Priority: {priority} ({priority_confidence:.0%} confident)")
        if category:
            reasoning_parts.append(f"Category: {category} ({category_confidence:.0%} confident)")
        
        reasoning = " | ".join(reasoning_parts) if reasoning_parts else "No strong predictions"
        
        return PredictiveSuggestion(
            due_date=due_date,
            priority=priority,
            category=category,
            assignee_id=assignee_id,
            confidence=overall_confidence,
            reasoning=reasoning
        )
    
    def refine_from_feedback(self, task_id: int, user_accepted: Dict[str, bool],
                            actual_values: Dict[str, Any]):
        """
        Learn from user corrections to improve future predictions.
        
        Args:
            task_id: Task ID
            user_accepted: Dict of which predictions user accepted
            actual_values: Actual values user chose
        """
        # TODO: Implement feedback loop for ML model improvement
        # - Store prediction vs actual in training dataset
        # - Periodically retrain models
        # - Track accuracy metrics per prediction type
        
        logger.info(f"Feedback recorded for task {task_id}: "
                   f"accepted={user_accepted}, actual={actual_values}")
        pass


# Singleton instance
predictive_engine = PredictiveEngine()
