"""
CROWN⁹ Copilot Lifecycle Service

Manages the 12-event lifecycle for the AI Copilot consciousness layer.

Events:
1. copilot_bootstrap - Load context on page arrival
2. context_rehydrate - Sync active sessions/meetings
3. chips_generate - Generate adaptive quick-actions
4. idle_listen - Activate after 2-5s no input
5. query_detect - Parse user input/voice
6. context_merge - Assemble related data
7. reasoning_stream - Progressive token generation
8. response_commit - Persist reply + update memory
9. action_trigger - Execute mutation + broadcast
10. cross_surface_sync - Other pages reconcile deltas
11. context_retrain - Adjust embeddings post-interaction
12. idle_prompt - Re-engagement after 60s inactivity
"""

import logging
import time
from typing import Dict, Any, Optional, Callable
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class LifecycleEvent(str, Enum):
    """CROWN⁹ Copilot lifecycle events."""
    COPILOT_BOOTSTRAP = "copilot_bootstrap"
    CONTEXT_REHYDRATE = "context_rehydrate"
    CHIPS_GENERATE = "chips_generate"
    IDLE_LISTEN = "idle_listen"
    QUERY_DETECT = "query_detect"
    CONTEXT_MERGE = "context_merge"
    REASONING_STREAM = "reasoning_stream"
    RESPONSE_COMMIT = "response_commit"
    ACTION_TRIGGER = "action_trigger"
    CROSS_SURFACE_SYNC = "cross_surface_sync"
    CONTEXT_RETRAIN = "context_retrain"
    IDLE_PROMPT = "idle_prompt"


class LifecycleState:
    """Tracks state for a copilot session."""
    
    def __init__(self, session_id: str, user_id: int, workspace_id: Optional[int]):
        self.session_id = session_id
        self.user_id = user_id
        self.workspace_id = workspace_id
        self.created_at = time.time()
        self.last_activity = time.time()
        self.last_query = None
        self.context = {}
        self.chips = []
        self.event_history = []
        self.is_idle = False
        self.idle_start = None
        
    def update_activity(self):
        """Update last activity timestamp."""
        self.last_activity = time.time()
        self.is_idle = False
        self.idle_start = None
    
    def mark_idle(self):
        """Mark session as idle."""
        if not self.is_idle:
            self.is_idle = True
            self.idle_start = time.time()
    
    def get_idle_duration(self) -> float:
        """Get duration in seconds since idle started."""
        if not self.is_idle or not self.idle_start:
            return 0
        return time.time() - self.idle_start
    
    def add_event(self, event: LifecycleEvent, data: Optional[Dict[str, Any]] = None):
        """Record lifecycle event in history."""
        self.event_history.append({
            'event': event.value,
            'timestamp': time.time(),
            'data': data or {}
        })
        # Keep only last 50 events
        if len(self.event_history) > 50:
            self.event_history = self.event_history[-50:]


class CopilotLifecycleService:
    """
    Service for managing CROWN⁹ copilot lifecycle events.
    
    Ensures deterministic event ordering, state tracking, and
    emotional coherence across all 12 lifecycle phases.
    """
    
    def __init__(self):
        """Initialize lifecycle service."""
        self.sessions: Dict[str, LifecycleState] = {}
        self.event_handlers: Dict[LifecycleEvent, list] = {
            event: [] for event in LifecycleEvent
        }
        logger.info("Copilot Lifecycle Service initialized")
    
    def create_session(
        self,
        session_id: str,
        user_id: int,
        workspace_id: Optional[int] = None
    ) -> LifecycleState:
        """
        Create new lifecycle session.
        
        Args:
            session_id: Unique session identifier
            user_id: User ID
            workspace_id: Workspace ID
            
        Returns:
            LifecycleState instance
        """
        state = LifecycleState(session_id, user_id, workspace_id)
        self.sessions[session_id] = state
        logger.debug(f"Created copilot session: {session_id}")
        return state
    
    def get_session(self, session_id: str) -> Optional[LifecycleState]:
        """Get session state by ID."""
        return self.sessions.get(session_id)
    
    def destroy_session(self, session_id: str):
        """Destroy session and cleanup."""
        if session_id in self.sessions:
            del self.sessions[session_id]
            logger.debug(f"Destroyed copilot session: {session_id}")
    
    def emit_event(
        self,
        session_id: str,
        event: LifecycleEvent,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Emit lifecycle event and execute handlers.
        
        Args:
            session_id: Session ID
            event: Lifecycle event type
            data: Optional event data
            
        Returns:
            Event result with timing and state
        """
        session = self.get_session(session_id)
        if not session:
            logger.warning(f"Session {session_id} not found for event {event.value}")
            return {'success': False, 'error': 'Session not found'}
        
        start_time = time.time()
        
        try:
            # Record event in session history
            session.add_event(event, data)
            
            # Execute event handlers
            result = self._execute_event_handlers(event, session, data)
            
            # Update session state based on event
            self._update_session_state(event, session, result)
            
            duration_ms = (time.time() - start_time) * 1000
            
            logger.debug(f"Lifecycle event {event.value} completed in {duration_ms:.0f}ms")
            
            return {
                'success': True,
                'event': event.value,
                'duration_ms': duration_ms,
                'session_id': session_id,
                'result': result,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Lifecycle event {event.value} failed: {e}", exc_info=True)
            return {
                'success': False,
                'event': event.value,
                'error': str(e)
            }
    
    def register_handler(self, event: LifecycleEvent, handler: Callable):
        """
        Register event handler.
        
        Args:
            event: Lifecycle event type
            handler: Callable that receives (session, data) and returns result
        """
        self.event_handlers[event].append(handler)
        logger.debug(f"Registered handler for {event.value}")
    
    def _execute_event_handlers(
        self,
        event: LifecycleEvent,
        session: LifecycleState,
        data: Optional[Dict[str, Any]]
    ) -> Any:
        """Execute all registered handlers for an event."""
        handlers = self.event_handlers.get(event, [])
        results = []
        
        for handler in handlers:
            try:
                result = handler(session, data or {})
                results.append(result)
            except Exception as e:
                logger.error(f"Handler error for {event.value}: {e}", exc_info=True)
                results.append({'error': str(e)})
        
        # Return combined results
        if len(results) == 0:
            return None
        elif len(results) == 1:
            return results[0]
        else:
            return results
    
    def _update_session_state(
        self,
        event: LifecycleEvent,
        session: LifecycleState,
        result: Any
    ):
        """Update session state based on lifecycle event."""
        
        if event == LifecycleEvent.COPILOT_BOOTSTRAP:
            # Bootstrap loads initial context
            if isinstance(result, dict) and 'context' in result:
                session.context = result['context']
            session.update_activity()
        
        elif event == LifecycleEvent.CONTEXT_REHYDRATE:
            # Rehydrate merges additional context
            if isinstance(result, dict) and 'context' in result:
                session.context.update(result['context'])
            session.update_activity()
        
        elif event == LifecycleEvent.CHIPS_GENERATE:
            # Store generated chips
            if isinstance(result, dict) and 'chips' in result:
                session.chips = result['chips']
        
        elif event == LifecycleEvent.QUERY_DETECT:
            # Record last query AND reset idle state
            if isinstance(result, dict) and 'message' in result:
                session.last_query = result['message']
            session.update_activity()  # This resets idle flag
        
        elif event == LifecycleEvent.IDLE_LISTEN:
            # Mark as idle
            session.mark_idle()
        
        elif event == LifecycleEvent.RESPONSE_COMMIT:
            # Update activity on response
            session.update_activity()
        
        elif event == LifecycleEvent.ACTION_TRIGGER:
            # Update activity on action (resets idle)
            session.update_activity()
        
        elif event == LifecycleEvent.IDLE_PROMPT:
            # After sending idle prompt, don't immediately reset idle
            # User must interact to reset
            pass
    
    def check_idle_sessions(self) -> list:
        """
        Check all sessions for idle timeouts.
        
        Returns:
            List of session IDs that need idle prompts
        """
        idle_sessions = []
        current_time = time.time()
        
        for session_id, session in self.sessions.items():
            time_since_activity = current_time - session.last_activity
            
            # Idle listen after 2-5s (Event #4)
            if 2 <= time_since_activity < 5 and not session.is_idle:
                self.emit_event(session_id, LifecycleEvent.IDLE_LISTEN)
            
            # Idle prompt after 60s (Event #12)
            elif time_since_activity >= 60:
                idle_sessions.append(session_id)
        
        return idle_sessions
    
    def get_session_stats(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session statistics and state."""
        session = self.get_session(session_id)
        if not session:
            return None
        
        return {
            'session_id': session.session_id,
            'user_id': session.user_id,
            'workspace_id': session.workspace_id,
            'created_at': session.created_at,
            'last_activity': session.last_activity,
            'is_idle': session.is_idle,
            'idle_duration': session.get_idle_duration(),
            'event_count': len(session.event_history),
            'last_events': session.event_history[-5:] if session.event_history else [],
            'chips_count': len(session.chips),
            'has_context': bool(session.context)
        }


# Singleton instance
copilot_lifecycle_service = CopilotLifecycleService()
