"""
CROWN⁹ Copilot Idle Detection Service

Monitors user activity and triggers re-engagement.
Implements Events #4 and #12:
- Event #4: idle_listen (2-5s after last interaction)
- Event #12: idle_prompt (60s after last interaction)
"""

import logging
import time
import threading
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


class CopilotIdleDetectionService:
    """
    Service for monitoring idle copilot sessions and triggering re-engagement.
    
    Responsibilities:
    - Monitor session activity timestamps
    - Detect idle sessions (2-5s for passive listening, 60s for active prompts)
    - Generate contextual re-engagement prompts
    - Emit idle_listen and idle_prompt events
    """
    
    def __init__(self, socketio=None):
        """Initialize idle detection service."""
        self.socketio = socketio
        self.monitoring = False
        self.monitor_thread = None
        self.check_interval = 2.0
        logger.info("Copilot Idle Detection Service initialized")
    
    def set_socketio(self, socketio):
        """Set SocketIO instance after initialization."""
        self.socketio = socketio
    
    def start_monitoring(self):
        """Start background thread for idle monitoring."""
        if self.monitoring:
            logger.warning("Idle monitoring already started")
            return
        
        self.monitoring = True
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True
        )
        self.monitor_thread.start()
        logger.info("Idle monitoring started")
    
    def stop_monitoring(self):
        """Stop background monitoring thread."""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("Idle monitoring stopped")
    
    def _monitor_loop(self):
        """Background loop that checks for idle sessions."""
        from services.copilot_lifecycle_service import (
            copilot_lifecycle_service,
            LifecycleEvent
        )
        
        while self.monitoring:
            try:
                # Check all active sessions for idle timeouts
                idle_sessions = copilot_lifecycle_service.check_idle_sessions()
                
                # Send re-engagement prompts for idle sessions
                for session_id in idle_sessions:
                    self._send_idle_prompt(session_id)
                
                # Sleep before next check
                time.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"Idle monitoring error: {e}", exc_info=True)
                time.sleep(self.check_interval)
    
    def _send_idle_prompt(self, session_id: str):
        """
        Send re-engagement prompt to idle session (Event #12).
        
        Args:
            session_id: Session ID that has been idle for 60s+
        """
        from services.copilot_lifecycle_service import (
            copilot_lifecycle_service,
            LifecycleEvent
        )
        
        try:
            session = copilot_lifecycle_service.get_session(session_id)
            if not session:
                return
            
            # Check if we already sent a prompt recently (prevent spam)
            # Only send if idle duration >= 60s AND we haven't prompted in last 60s
            idle_duration = session.get_idle_duration()
            if idle_duration < 60:
                return  # Not idle long enough
            
            # Check last prompt time to prevent spam
            last_prompt_time = session.context.get('last_idle_prompt_time', 0)
            if time.time() - last_prompt_time < 60:
                return  # Already prompted recently
            
            # Generate contextual re-engagement prompt
            prompt = self._generate_idle_prompt(session)
            
            # Emit Event #12: idle_prompt
            copilot_lifecycle_service.emit_event(
                session_id=session_id,
                event=LifecycleEvent.IDLE_PROMPT,
                data={'prompt': prompt}
            )
            
            # Send prompt to client via WebSocket
            if self.socketio:
                self.socketio.emit(
                    'copilot_idle_prompt',
                    {
                        'prompt': prompt,
                        'session_id': session_id,
                        'timestamp': time.time()
                    },
                    namespace='/copilot'
                )
            
            # Update last prompt time to prevent repeated prompts
            session.context['last_idle_prompt_time'] = time.time()
            
            logger.info(f"Sent idle prompt to session {session_id}")
            
        except Exception as e:
            logger.error(f"Failed to send idle prompt: {e}", exc_info=True)
    
    def _generate_idle_prompt(self, session) -> str:
        """
        Generate contextual re-engagement prompt based on session state.
        
        Args:
            session: LifecycleState instance
            
        Returns:
            Re-engagement prompt text
        """
        prompts = [
            "Need help with anything?",
            "Want to review your tasks?",
            "Looking for something specific?",
            "Ready when you are.",
            "Anything I can assist with?"
        ]
        
        # TODO: Make prompts more contextual based on:
        # - Time of day
        # - Recent activity
        # - Workspace state
        # - User preferences
        
        # For now, rotate through prompts
        index = hash(session.session_id) % len(prompts)
        return prompts[index]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get idle detection service statistics."""
        from services.copilot_lifecycle_service import copilot_lifecycle_service
        
        total_sessions = len(copilot_lifecycle_service.sessions)
        idle_count = sum(
            1 for s in copilot_lifecycle_service.sessions.values()
            if s.is_idle
        )
        
        return {
            'monitoring': self.monitoring,
            'total_sessions': total_sessions,
            'idle_sessions': idle_count,
            'check_interval': self.check_interval
        }


# Singleton instance
copilot_idle_detection_service = CopilotIdleDetectionService()
