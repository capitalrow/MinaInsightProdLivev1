"""
AI Model Manager - Unified OpenAI model fallback with retry logic and degradation tracking.

This service provides:
- Intelligent model fallback (GPT-4.1 → GPT-4.1 mini → GPT-4o → GPT-3.5 Turbo)
- Retry logic with exponential backoff (3 attempts per model)
- Comprehensive API error logging
- Degradation event tracking for monitoring
"""

import logging
import time
from typing import Optional, Dict, Any, Callable, List
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ModelAttempt:
    """Records a single model attempt for logging and analytics."""
    model_name: str
    attempt_number: int
    success: bool
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    duration_ms: Optional[float] = None
    timestamp: Optional[datetime] = None


@dataclass
class ModelFallbackResult:
    """Result of model fallback operation."""
    success: bool
    model_used: Optional[str] = None
    response: Optional[Any] = None
    attempts: List[ModelAttempt] = None
    degraded: bool = False
    degradation_reason: Optional[str] = None
    
    def __post_init__(self):
        if self.attempts is None:
            self.attempts = []


class AIModelManager:
    """
    Manages OpenAI model selection with intelligent fallback and retry logic.
    
    Production Features:
    - 4-model fallback chain for maximum reliability
    - 3 retries per model with exponential backoff
    - Comprehensive error classification and logging
    - Degradation tracking for monitoring
    - Zero tolerance for mock data
    """
    
    # Model priority order (Replit AI Integrations compatible)
    # Uses models supported by Replit's modelfarm proxy
    MODEL_FALLBACK_CHAIN = [
        "gpt-4.1",           # Latest, smartest non-reasoning model (Replit AI supported)
        "gpt-4.1-mini",      # Same family, 83% cheaper, 50% faster (Replit AI supported)
        "gpt-4o-mini",       # Fast, cost-effective fallback (Replit AI supported)
        "gpt-4o"             # Proven reliable fallback (Replit AI supported)
    ]
    
    # Retry configuration
    MAX_RETRIES_PER_MODEL = 3
    INITIAL_RETRY_DELAY_MS = 1000  # 1 second
    RETRY_BACKOFF_MULTIPLIER = 2   # Exponential backoff
    
    @classmethod
    async def call_with_fallback_async(
        cls,
        api_call: Callable,
        operation_name: str = "AI operation",
        custom_model_chain: Optional[List[str]] = None
    ) -> ModelFallbackResult:
        """
        Async version of call_with_fallback for async API calls.
        
        Args:
            api_call: Async function that takes model name and returns API response
            operation_name: Description for logging
            custom_model_chain: Optional custom model order
            
        Returns:
            ModelFallbackResult with success status, model used, and response
        """
        import asyncio
        
        models_to_try = custom_model_chain or cls.MODEL_FALLBACK_CHAIN
        primary_model = models_to_try[0]
        all_attempts = []
        
        logger.info(f"🚀 Starting {operation_name} with model chain: {' → '.join(models_to_try)}")
        
        for model_index, model in enumerate(models_to_try):
            is_primary = (model_index == 0)
            
            for attempt in range(1, cls.MAX_RETRIES_PER_MODEL + 1):
                attempt_start = time.time()
                attempt_record = ModelAttempt(
                    model_name=model,
                    attempt_number=attempt,
                    success=False,
                    timestamp=datetime.utcnow()
                )
                
                try:
                    logger.info(f"🔄 [{operation_name}] Attempting {model} (try {attempt}/{cls.MAX_RETRIES_PER_MODEL})")
                    
                    # Execute async API call
                    response = await api_call(model)
                    
                    # Success!
                    duration_ms = (time.time() - attempt_start) * 1000
                    attempt_record.success = True
                    attempt_record.duration_ms = duration_ms
                    all_attempts.append(attempt_record)
                    
                    degraded = not is_primary
                    degradation_reason = None
                    if degraded:
                        degradation_reason = f"Primary model {primary_model} unavailable, using {model}"
                    
                    logger.info(
                        f"✅ [{operation_name}] SUCCESS with {model} "
                        f"(attempt {attempt}/{cls.MAX_RETRIES_PER_MODEL}, {duration_ms:.0f}ms)"
                    )
                    
                    if degraded:
                        logger.warning(f"⚠️ [{operation_name}] DEGRADED: Using {model} instead of {primary_model}")
                    
                    return ModelFallbackResult(
                        success=True,
                        model_used=model,
                        response=response,
                        attempts=all_attempts,
                        degraded=degraded,
                        degradation_reason=degradation_reason
                    )
                    
                except Exception as e:
                    duration_ms = (time.time() - attempt_start) * 1000
                    error_type = type(e).__name__
                    error_message = str(e)
                    
                    attempt_record.error_type = error_type
                    attempt_record.error_message = error_message
                    attempt_record.duration_ms = duration_ms
                    all_attempts.append(attempt_record)
                    
                    is_permission_error = cls._is_permission_error(error_message)
                    is_rate_limit = cls._is_rate_limit(error_message)
                    is_server_error = cls._is_server_error(error_message)
                    is_timeout = cls._is_timeout(error_message)
                    
                    logger.warning(
                        f"❌ [{operation_name}] FAILED: {model} "
                        f"(attempt {attempt}/{cls.MAX_RETRIES_PER_MODEL}) - "
                        f"{error_type}: {error_message[:200]}"
                    )
                    
                    if is_permission_error:
                        logger.info(f"⏭️  [{operation_name}] Skipping to next model (permission denied)")
                        break
                    elif is_rate_limit or is_server_error or is_timeout:
                        if attempt < cls.MAX_RETRIES_PER_MODEL:
                            backoff_delay_ms = cls._calculate_backoff_delay(attempt)
                            logger.info(f"⏳ [{operation_name}] Retrying after {backoff_delay_ms}ms backoff...")
                            await asyncio.sleep(backoff_delay_ms / 1000.0)  # Use asyncio.sleep for async
                            continue
                        else:
                            logger.warning(f"⚠️ [{operation_name}] Exhausted retries for {model}, trying next model")
                            break
                    else:
                        logger.warning(f"⚠️ [{operation_name}] Unknown error type, skipping to next model")
                        break
        
        # All models failed
        logger.error(f"❌ [{operation_name}] ALL MODELS FAILED after {len(all_attempts)} attempts")
        cls._log_failure_summary(operation_name, all_attempts)
        
        return ModelFallbackResult(
            success=False,
            model_used=None,
            response=None,
            attempts=all_attempts,
            degraded=False
        )
    
    @classmethod
    def call_with_fallback(
        cls,
        api_call: Callable,
        operation_name: str = "AI operation",
        custom_model_chain: Optional[List[str]] = None
    ) -> ModelFallbackResult:
        """
        Execute an OpenAI API call with intelligent model fallback and retry logic.
        
        Args:
            api_call: Function that takes model name and returns API response
            operation_name: Description for logging (e.g., "insights generation")
            custom_model_chain: Optional custom model order (defaults to standard chain)
            
        Returns:
            ModelFallbackResult with success status, model used, and response
            
        Example:
            ```python
            def make_api_call(model: str):
                return client.chat.completions.create(
                    model=model,
                    messages=[...]
                )
            
            result = AIModelManager.call_with_fallback(
                make_api_call,
                operation_name="task extraction"
            )
            
            if result.success:
                response = result.response
                if result.degraded:
                    logger.warning(f"Degraded to {result.model_used}")
            ```
        """
        models_to_try = custom_model_chain or cls.MODEL_FALLBACK_CHAIN
        primary_model = models_to_try[0]
        all_attempts = []
        
        logger.info(f"🚀 Starting {operation_name} with model chain: {' → '.join(models_to_try)}")
        
        for model_index, model in enumerate(models_to_try):
            is_primary = (model_index == 0)
            
            # Try this model with retries
            for attempt in range(1, cls.MAX_RETRIES_PER_MODEL + 1):
                attempt_start = time.time()
                attempt_record = ModelAttempt(
                    model_name=model,
                    attempt_number=attempt,
                    success=False,
                    timestamp=datetime.utcnow()
                )
                
                try:
                    logger.info(f"🔄 [{operation_name}] Attempting {model} (try {attempt}/{cls.MAX_RETRIES_PER_MODEL})")
                    
                    # Execute API call
                    response = api_call(model)
                    
                    # Success!
                    duration_ms = (time.time() - attempt_start) * 1000
                    attempt_record.success = True
                    attempt_record.duration_ms = duration_ms
                    all_attempts.append(attempt_record)
                    
                    # Determine if degraded
                    degraded = not is_primary
                    degradation_reason = None
                    if degraded:
                        degradation_reason = f"Primary model {primary_model} unavailable, using {model}"
                    
                    logger.info(
                        f"✅ [{operation_name}] SUCCESS with {model} "
                        f"(attempt {attempt}/{cls.MAX_RETRIES_PER_MODEL}, {duration_ms:.0f}ms)"
                    )
                    
                    if degraded:
                        logger.warning(
                            f"⚠️ [{operation_name}] DEGRADED: Using {model} instead of {primary_model}"
                        )
                    
                    return ModelFallbackResult(
                        success=True,
                        model_used=model,
                        response=response,
                        attempts=all_attempts,
                        degraded=degraded,
                        degradation_reason=degradation_reason
                    )
                    
                except Exception as e:
                    duration_ms = (time.time() - attempt_start) * 1000
                    error_type = type(e).__name__
                    error_message = str(e)
                    
                    attempt_record.error_type = error_type
                    attempt_record.error_message = error_message
                    attempt_record.duration_ms = duration_ms
                    all_attempts.append(attempt_record)
                    
                    # Classify error type
                    is_permission_error = cls._is_permission_error(error_message)
                    is_rate_limit = cls._is_rate_limit(error_message)
                    is_server_error = cls._is_server_error(error_message)
                    is_timeout = cls._is_timeout(error_message)
                    
                    # Log error with details
                    logger.warning(
                        f"❌ [{operation_name}] FAILED: {model} "
                        f"(attempt {attempt}/{cls.MAX_RETRIES_PER_MODEL}) - "
                        f"{error_type}: {error_message[:200]}"
                    )
                    
                    # Decide whether to retry or skip to next model
                    if is_permission_error:
                        # Permission errors won't fix with retry, skip to next model
                        logger.info(f"⏭️  [{operation_name}] Skipping to next model (permission denied)")
                        break
                    
                    elif is_rate_limit or is_server_error or is_timeout:
                        # Transient errors - retry with backoff
                        if attempt < cls.MAX_RETRIES_PER_MODEL:
                            backoff_delay_ms = cls._calculate_backoff_delay(attempt)
                            logger.info(
                                f"⏳ [{operation_name}] Retrying after {backoff_delay_ms}ms backoff..."
                            )
                            time.sleep(backoff_delay_ms / 1000.0)
                            continue
                        else:
                            # Exhausted retries for this model
                            logger.warning(
                                f"⚠️ [{operation_name}] Exhausted retries for {model}, trying next model"
                            )
                            break
                    else:
                        # Unknown error type - try next model immediately
                        logger.warning(
                            f"⚠️ [{operation_name}] Unknown error type, skipping to next model"
                        )
                        break
        
        # All models failed
        logger.error(
            f"❌ [{operation_name}] ALL MODELS FAILED after {len(all_attempts)} attempts across "
            f"{len(models_to_try)} models"
        )
        
        # Log summary of all attempts
        cls._log_failure_summary(operation_name, all_attempts)
        
        return ModelFallbackResult(
            success=False,
            model_used=None,
            response=None,
            attempts=all_attempts,
            degraded=False
        )
    
    @staticmethod
    def _is_permission_error(error_message: str) -> bool:
        """Check if error is a permission/access denied error."""
        return any(keyword in error_message.lower() for keyword in [
            "403", "permission", "does not have access", "model_not_found",
            "unauthorized", "forbidden"
        ])
    
    @staticmethod
    def _is_rate_limit(error_message: str) -> bool:
        """Check if error is a rate limit error."""
        return any(keyword in error_message.lower() for keyword in [
            "429", "rate limit", "too many requests", "quota"
        ])
    
    @staticmethod
    def _is_server_error(error_message: str) -> bool:
        """Check if error is a server error."""
        return any(keyword in error_message.lower() for keyword in [
            "500", "502", "503", "504", "internal server", "bad gateway",
            "service unavailable", "gateway timeout"
        ])
    
    @staticmethod
    def _is_timeout(error_message: str) -> bool:
        """Check if error is a timeout."""
        return any(keyword in error_message.lower() for keyword in [
            "timeout", "timed out", "deadline exceeded"
        ])
    
    @classmethod
    def _calculate_backoff_delay(cls, attempt: int) -> int:
        """Calculate exponential backoff delay in milliseconds."""
        return cls.INITIAL_RETRY_DELAY_MS * (cls.RETRY_BACKOFF_MULTIPLIER ** (attempt - 1))
    
    @staticmethod
    def _log_failure_summary(operation_name: str, attempts: List[ModelAttempt]):
        """Log a comprehensive summary of all failed attempts."""
        logger.error(f"\n{'='*80}")
        logger.error(f"FAILURE SUMMARY: {operation_name}")
        logger.error(f"{'='*80}")
        
        for i, attempt in enumerate(attempts, 1):
            status = "✅ SUCCESS" if attempt.success else "❌ FAILED"
            logger.error(
                f"{i}. {attempt.model_name} (attempt {attempt.attempt_number}): {status}"
            )
            if not attempt.success:
                logger.error(f"   Error: {attempt.error_type} - {attempt.error_message[:150]}")
            logger.error(f"   Duration: {attempt.duration_ms:.0f}ms")
        
        logger.error(f"{'='*80}\n")
