"""
Enterprise-Grade OpenAI Client Manager
Centralized, robust initialization and management of OpenAI clients with circuit breaker protection
Includes ThreadPoolExecutor for true async transcription support
"""

import os
import logging
import asyncio
import threading
from typing import Optional
from concurrent.futures import ThreadPoolExecutor
from openai import OpenAI
from openai._exceptions import OpenAIError, RateLimitError, APIConnectionError, APITimeoutError
from services.circuit_breaker import get_openai_circuit_breaker, CircuitBreakerOpenError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

class OpenAIClientManager:
    """Centralized OpenAI client management with robust error handling and circuit breaker protection"""
    
    _instance: Optional['OpenAIClientManager'] = None
    _client: Optional[OpenAI] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._initialized = True
            self._api_key = None
            self._initialization_error = None
            from services.circuit_breaker import get_openai_circuit_breaker
            self._circuit_breaker = get_openai_circuit_breaker()
            
            # Initialize ThreadPoolExecutor for true async transcription
            try:
                max_workers = int(os.environ.get("OPENAI_EXECUTOR_MAX_WORKERS", "15"))
                # Validate range: 1-50 workers
                max_workers = max(1, min(50, max_workers))
            except (ValueError, TypeError):
                logger.warning("Invalid OPENAI_EXECUTOR_MAX_WORKERS, using default: 15")
                max_workers = 15
            
            self._executor = ThreadPoolExecutor(
                max_workers=max_workers,
                thread_name_prefix="OpenAI-Worker"
            )
            self._executor_lock = threading.Lock()
            self._active_tasks = 0
            self._total_tasks_submitted = 0
            self._total_tasks_completed = 0
            self._total_tasks_failed = 0
            
            logger.info(f"✅ OpenAI Client Manager initialized with circuit breaker protection and {max_workers} worker threads")
    
    def get_client(self, force_reinit: bool = False) -> Optional[OpenAI]:
        """
        Get OpenAI client with robust error handling
        
        Args:
            force_reinit: Force re-initialization even if client exists
            
        Returns:
            OpenAI client instance or None if initialization failed
        """
        if self._client is None or force_reinit:
            self._initialize_client()
        
        return self._client
    
    def _initialize_client(self) -> None:
        """Initialize OpenAI client with proper error handling"""
        try:
            # Get API key
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                self._initialization_error = "OPENAI_API_KEY environment variable not set"
                logger.warning(self._initialization_error)
                return
            
            # Store for validation
            self._api_key = api_key
            
            # Initialize client with clean parameters (no proxies or other legacy args)
            client_config = {
                "api_key": api_key,
            }
            
            # Add optional configurations if needed
            timeout = os.environ.get("OPENAI_TIMEOUT")
            if timeout:
                try:
                    client_config["timeout"] = float(timeout)
                except ValueError:
                    logger.warning(f"Invalid OPENAI_TIMEOUT value: {timeout}")
            
            max_retries = os.environ.get("OPENAI_MAX_RETRIES")
            if max_retries:
                try:
                    client_config["max_retries"] = int(max_retries)
                except ValueError:
                    logger.warning(f"Invalid OPENAI_MAX_RETRIES value: {max_retries}")
            
            # Initialize client with only clean, supported parameters
            self._client = OpenAI(**client_config)
            self._initialization_error = None
            
            logger.info("✅ OpenAI client initialized successfully")
            
        except Exception as e:
            self._initialization_error = str(e)
            self._client = None
            logger.error(f"❌ OpenAI client initialization failed: {e}")
    
    def is_available(self) -> bool:
        """Check if OpenAI client is available and working"""
        return self._client is not None and self._initialization_error is None
    
    def get_initialization_error(self) -> Optional[str]:
        """Get the last initialization error message"""
        return self._initialization_error
    
    def test_connection(self) -> tuple[bool, Optional[str]]:
        """
        Test OpenAI connection
        
        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        client = self.get_client()
        if not client:
            return False, self._initialization_error
        
        try:
            # Simple test - try to list models (lightweight operation)
            models = client.models.list()
            if models:
                logger.info("✅ OpenAI connection test successful")
                return True, None
            else:
                return False, "No models returned from OpenAI API"
                
        except OpenAIError as e:
            error_msg = f"OpenAI API error: {e}"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Unexpected error testing OpenAI connection: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    async def transcribe_audio_async(self, audio_file, model: str = "whisper-1", **kwargs) -> Optional[str]:
        """
        TRUE async transcription using ThreadPoolExecutor to offload blocking OpenAI SDK calls.
        Now supports concurrent transcription without blocking the event loop!
        
        Args:
            audio_file: Audio file object or path
            model: Whisper model to use
            **kwargs: Additional parameters for transcription
            
        Returns:
            Transcribed text or None if failed
        """
        client = self.get_client()
        if not client:
            logger.error("❌ OpenAI client not available for transcription")
            return None
        
        # Track executor stats
        with self._executor_lock:
            self._active_tasks += 1
            self._total_tasks_submitted += 1
        
        try:
            # Clean kwargs to avoid unsupported parameters
            clean_kwargs = {
                "file": audio_file,
                "model": model,
            }
            
            # Add supported optional parameters
            if "language" in kwargs and kwargs["language"]:
                clean_kwargs["language"] = kwargs["language"]
            if "response_format" in kwargs:
                clean_kwargs["response_format"] = kwargs["response_format"]
            if "temperature" in kwargs:
                clean_kwargs["temperature"] = kwargs["temperature"]
            
            # Define blocking transcription callable
            def _blocking_transcribe():
                """Blocking transcription call to run in executor thread."""
                if self._circuit_breaker:
                    def _transcribe():
                        return self._transcribe_with_retry(client, clean_kwargs)
                    return self._circuit_breaker.call(_transcribe)
                else:
                    # Fallback when circuit breaker unavailable
                    return self._transcribe_with_retry(client, clean_kwargs)
            
            # Offload blocking call to thread pool executor
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(self._executor, _blocking_transcribe)
            
            # Update stats on success
            with self._executor_lock:
                self._active_tasks -= 1
                self._total_tasks_completed += 1
            
            logger.info(f"✅ TRUE async transcription successful ({len(result or '')} chars)")
            return result
            
        except CircuitBreakerOpenError:
            logger.error("🔴 Circuit breaker OPEN - OpenAI service unavailable")
            with self._executor_lock:
                self._active_tasks -= 1
                self._total_tasks_failed += 1
            return None
        except RateLimitError as e:
            logger.error(f"❌ OpenAI rate limit exceeded after retries: {e}")
            with self._executor_lock:
                self._active_tasks -= 1
                self._total_tasks_failed += 1
            return None
        except (APIConnectionError, APITimeoutError) as e:
            logger.error(f"❌ OpenAI connection failed after retries: {e}")
            with self._executor_lock:
                self._active_tasks -= 1
                self._total_tasks_failed += 1
            return None
        except OpenAIError as e:
            logger.error(f"❌ OpenAI transcription error: {e}")
            with self._executor_lock:
                self._active_tasks -= 1
                self._total_tasks_failed += 1
            return None
        except Exception as e:
            logger.error(f"❌ Unexpected transcription error: {e}", exc_info=True)
            with self._executor_lock:
                self._active_tasks -= 1
                self._total_tasks_failed += 1
            return None

    @retry(
        retry=retry_if_exception_type((RateLimitError, APIConnectionError, APITimeoutError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    def _transcribe_with_retry(self, client: OpenAI, clean_kwargs: dict) -> Optional[str]:
        """
        Internal method to transcribe with automatic retry for transient errors.
        
        Args:
            client: OpenAI client instance
            clean_kwargs: Cleaned transcription parameters
            
        Returns:
            Transcribed text or None if failed
        """
        try:
            response = client.audio.transcriptions.create(**clean_kwargs)
            return getattr(response, "text", "") or ""
        except RateLimitError:
            logger.warning("⚠️ OpenAI rate limit hit, retrying with exponential backoff")
            raise
        except (APIConnectionError, APITimeoutError) as e:
            logger.warning(f"⚠️ OpenAI connection issue ({type(e).__name__}), retrying")
            raise

    def transcribe_audio(self, audio_file, model: str = "whisper-1", **kwargs) -> Optional[str]:
        """
        Transcribe audio with robust error handling, circuit breaker protection, and automatic retries.
        
        Args:
            audio_file: Audio file object or path
            model: Whisper model to use
            **kwargs: Additional parameters for transcription
            
        Returns:
            Transcribed text or None if failed
        """
        client = self.get_client()
        if not client:
            logger.error("❌ OpenAI client not available for transcription")
            return None
        
        try:
            # Clean kwargs to avoid unsupported parameters
            clean_kwargs = {
                "file": audio_file,
                "model": model,
            }
            
            # Add supported optional parameters
            if "language" in kwargs and kwargs["language"]:
                clean_kwargs["language"] = kwargs["language"]
            if "response_format" in kwargs:
                clean_kwargs["response_format"] = kwargs["response_format"]
            if "temperature" in kwargs:
                clean_kwargs["temperature"] = kwargs["temperature"]
            
            # Execute with circuit breaker protection if available, otherwise direct call
            if self._circuit_breaker:
                def _transcribe():
                    return self._transcribe_with_retry(client, clean_kwargs)
                result = self._circuit_breaker.call(_transcribe)
            else:
                # Fallback when circuit breaker unavailable
                result = self._transcribe_with_retry(client, clean_kwargs)
            
            logger.info(f"✅ Transcription successful ({len(result or '')} chars)")
            return result
            
        except CircuitBreakerOpenError:
            logger.error("🔴 Circuit breaker OPEN - OpenAI service unavailable")
            return None
        except RateLimitError as e:
            logger.error(f"❌ OpenAI rate limit exceeded after retries: {e}")
            return None
        except (APIConnectionError, APITimeoutError) as e:
            logger.error(f"❌ OpenAI connection failed after retries: {e}")
            return None
        except OpenAIError as e:
            logger.error(f"❌ OpenAI transcription error: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Unexpected transcription error: {e}", exc_info=True)
            return None
    
    def shutdown(self, wait: bool = True, timeout: float = 30.0) -> None:
        """
        Gracefully shutdown the thread pool executor.
        
        Args:
            wait: Whether to wait for pending tasks to complete
            timeout: Maximum time to wait for shutdown (seconds)
        """
        if hasattr(self, '_executor'):
            logger.info(f"🔄 Shutting down OpenAI executor (wait={wait}, timeout={timeout}s)")
            self._executor.shutdown(wait=wait, cancel_futures=not wait)
            logger.info("✅ OpenAI executor shutdown complete")
    
    def get_executor_stats(self) -> dict:
        """
        Get executor health and performance statistics.
        
        Returns:
            Dictionary with executor metrics
        """
        with self._executor_lock:
            return {
                'active_tasks': self._active_tasks,
                'total_submitted': self._total_tasks_submitted,
                'total_completed': self._total_tasks_completed,
                'total_failed': self._total_tasks_failed,
                'success_rate': (
                    self._total_tasks_completed / self._total_tasks_submitted 
                    if self._total_tasks_submitted > 0 
                    else 1.0
                ),
                'max_workers': self._executor._max_workers if hasattr(self, '_executor') else 0,
            }

# Global singleton instance
openai_manager = OpenAIClientManager()

def get_openai_client() -> Optional[OpenAI]:
    """Get OpenAI client instance - convenience function"""
    return openai_manager.get_client()

def test_openai_connection() -> tuple[bool, Optional[str]]:
    """Test OpenAI connection - convenience function"""
    return openai_manager.test_connection()

def get_openai_client_manager() -> OpenAIClientManager:
    """Get OpenAI client manager instance - convenience function"""
    return openai_manager