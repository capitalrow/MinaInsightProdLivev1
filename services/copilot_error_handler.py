"""
CROWN⁹ Copilot Error Handling & Graceful Degradation

Provides comprehensive error handling, recovery strategies, and graceful degradation
to maintain ≥99.95% uptime target.
"""

import logging
import traceback
from typing import Optional, Dict, Any, Callable
from functools import wraps
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class ErrorSeverity(str, Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(str, Enum):
    """Error categories for classification."""
    NETWORK = "network"
    DATABASE = "database"
    AUTHENTICATION = "authentication"
    OPENAI_API = "openai_api"
    VALIDATION = "validation"
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    UNKNOWN = "unknown"


class CopilotError(Exception):
    """Base exception for Copilot errors."""
    def __init__(
        self,
        message: str,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        recoverable: bool = True,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.category = category
        self.severity = severity
        self.recoverable = recoverable
        self.context = context or {}
        self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'message': self.message,
            'category': self.category.value,
            'severity': self.severity.value,
            'recoverable': self.recoverable,
            'context': self.context,
            'timestamp': self.timestamp.isoformat()
        }


class CopilotErrorHandler:
    """
    Centralized error handling for Copilot operations.
    
    Features:
    - Error classification and severity assessment
    - Automatic retry logic for recoverable errors
    - Graceful degradation strategies
    - Error logging and monitoring
    - User-friendly error messages
    """
    
    def __init__(self):
        """Initialize error handler."""
        self.error_counts = {}
        self.circuit_breakers = {}
    
    def handle_error(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Handle error with appropriate recovery strategy.
        
        Args:
            error: Exception that occurred
            context: Additional context about the error
            user_id: User ID for tracking
            
        Returns:
            Error response dict with user-friendly message
        """
        # Classify error
        if isinstance(error, CopilotError):
            copilot_error = error
        else:
            copilot_error = self._classify_error(error, context)
        
        # Log error
        self._log_error(copilot_error, user_id)
        
        # Track error frequency
        self._track_error(copilot_error)
        
        # Generate user-friendly response
        return self._generate_error_response(copilot_error)
    
    def _classify_error(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None
    ) -> CopilotError:
        """Classify generic exception into CopilotError."""
        error_str = str(error).lower()
        error_type = type(error).__name__
        
        # Network errors
        if 'connection' in error_str or 'timeout' in error_str:
            return CopilotError(
                message=str(error),
                category=ErrorCategory.NETWORK,
                severity=ErrorSeverity.HIGH,
                recoverable=True,
                context=context
            )
        
        # OpenAI API errors
        if 'openai' in error_str or 'api' in error_str:
            return CopilotError(
                message=str(error),
                category=ErrorCategory.OPENAI_API,
                severity=ErrorSeverity.HIGH,
                recoverable=True,
                context=context
            )
        
        # Database errors
        if 'database' in error_str or 'sql' in error_str:
            return CopilotError(
                message=str(error),
                category=ErrorCategory.DATABASE,
                severity=ErrorSeverity.CRITICAL,
                recoverable=False,
                context=context
            )
        
        # Rate limit errors
        if 'rate limit' in error_str or 'quota' in error_str:
            return CopilotError(
                message=str(error),
                category=ErrorCategory.RATE_LIMIT,
                severity=ErrorSeverity.MEDIUM,
                recoverable=True,
                context=context
            )
        
        # Default unknown error
        return CopilotError(
            message=str(error),
            category=ErrorCategory.UNKNOWN,
            severity=ErrorSeverity.MEDIUM,
            recoverable=True,
            context=context
        )
    
    def _log_error(self, error: CopilotError, user_id: Optional[int] = None):
        """Log error with appropriate level."""
        log_data = {
            'user_id': user_id,
            **error.to_dict()
        }
        
        if error.severity == ErrorSeverity.CRITICAL:
            logger.error(f"CRITICAL ERROR: {error.message}", extra=log_data, exc_info=True)
        elif error.severity == ErrorSeverity.HIGH:
            logger.error(f"HIGH severity error: {error.message}", extra=log_data)
        elif error.severity == ErrorSeverity.MEDIUM:
            logger.warning(f"MEDIUM severity error: {error.message}", extra=log_data)
        else:
            logger.info(f"LOW severity error: {error.message}", extra=log_data)
    
    def _track_error(self, error: CopilotError):
        """Track error frequency for circuit breaker."""
        error_key = f"{error.category}:{error.message[:50]}"
        
        if error_key not in self.error_counts:
            self.error_counts[error_key] = {
                'count': 0,
                'first_seen': datetime.now(),
                'last_seen': datetime.now()
            }
        
        self.error_counts[error_key]['count'] += 1
        self.error_counts[error_key]['last_seen'] = datetime.now()
    
    def _generate_error_response(self, error: CopilotError) -> Dict[str, Any]:
        """Generate user-friendly error response."""
        # User-friendly messages
        user_messages = {
            ErrorCategory.NETWORK: "I'm having trouble connecting right now. Please try again in a moment.",
            ErrorCategory.OPENAI_API: "I'm experiencing some difficulties processing your request. Please try again.",
            ErrorCategory.DATABASE: "I'm having trouble accessing your data. Please try again later.",
            ErrorCategory.RATE_LIMIT: "I've reached my processing limit. Please wait a moment and try again.",
            ErrorCategory.TIMEOUT: "That's taking longer than expected. Let's try again.",
            ErrorCategory.UNKNOWN: "Something went wrong. Please try again."
        }
        
        user_message = user_messages.get(
            error.category,
            "I encountered an issue. Please try again."
        )
        
        response = {
            'type': 'error',
            'message': user_message,
            'severity': error.severity.value,
            'recoverable': error.recoverable,
            'timestamp': error.timestamp.isoformat()
        }
        
        # Add retry suggestion for recoverable errors
        if error.recoverable:
            response['suggestion'] = 'retry'
            response['retry_delay_ms'] = self._get_retry_delay(error)
        
        return response
    
    def _get_retry_delay(self, error: CopilotError) -> int:
        """Get recommended retry delay in milliseconds."""
        delays = {
            ErrorCategory.NETWORK: 2000,
            ErrorCategory.OPENAI_API: 3000,
            ErrorCategory.RATE_LIMIT: 5000,
            ErrorCategory.TIMEOUT: 1000,
        }
        return delays.get(error.category, 2000)
    
    def with_error_handling(
        self,
        fallback_value: Any = None,
        category: ErrorCategory = ErrorCategory.UNKNOWN
    ):
        """
        Decorator for automatic error handling.
        
        Usage:
            @error_handler.with_error_handling(fallback_value={}, category=ErrorCategory.OPENAI_API)
            def risky_function():
                ...
        """
        def decorator(func: Callable):
            @wraps(func)
            def wrapper(*args, **kwargs):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    error = CopilotError(
                        message=str(e),
                        category=category,
                        context={'function': func.__name__}
                    )
                    self.handle_error(error)
                    return fallback_value
            return wrapper
        return decorator


# Global singleton instance
copilot_error_handler = CopilotErrorHandler()
