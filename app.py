# app.py (hardened)
import os
import json
import signal
import logging
import uuid
from typing import Optional
from werkzeug.middleware.proxy_fix import ProxyFix
from flask import Flask, render_template, request, g, jsonify
from flask_socketio import SocketIO
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from server.routes.metrics import metrics_bp
from server.utils.logger import get_logger
from server.routes.memory_api import memory_bp
#from routes.export import export_bp
#from routes.summary import summary_bp
#from routes.flags import flags_bp
#from routes.billing import billing_bp
#from routes.integrations import integrations_bp
#from routes.teams import teams_bp
#from routes.comments import comments_bp
from server.models.memory_store import MemoryStore
import openai
import numpy as np
import psycopg2
from flask_migrate import Migrate
from models import db, Segment, Comment 
from datetime import datetime
from services import memory_persistence as mem

# ---------- Config (fallback if config.Config not present)
try:
    from config import Config  # type: ignore
except Exception:
    class Config:
        JSON_LOGS: bool = os.getenv("JSON_LOGS", "false").lower() == "true"
        METRICS_DIR: str = os.getenv("METRICS_DIR", "./metrics")
        SECRET_KEY: str = os.getenv("SESSION_SECRET", "")  # No fallback - must be set
        SOCKETIO_PATH: str = os.getenv("SOCKETIO_PATH", "/socket.io")
        CORS_ALLOWLIST: str = os.getenv("CORS_ALLOWLIST", "*")
        MAX_CONTENT_LENGTH: int = int(os.getenv("MAX_CONTENT_LENGTH", str(32 * 1024 * 1024)))  # 32 MB

# ---------- Structured Logging
class _JsonFormatter(logging.Formatter):
    """
    Production-ready JSON log formatter with structured fields.
    
    Includes: timestamp, level, logger name, message, request context,
    user context, trace IDs, and custom fields.
    """
    def format(self, record: logging.LogRecord) -> str:
        import socket
        import threading
        from datetime import datetime, timezone
        
        # Base payload with standard fields
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add process and thread information
        payload["process_id"] = record.process
        payload["process_name"] = record.processName
        payload["thread_id"] = record.thread
        payload["thread_name"] = record.threadName
        
        # Add hostname
        try:
            payload["hostname"] = socket.gethostname()
        except Exception:
            payload["hostname"] = "unknown"
        
        # Include request context if available (request_id, trace_id, user_id)
        try:
            from flask import has_request_context, request, g
            from flask_login import current_user
            
            if has_request_context():
                # Request ID (correlation ID)
                request_id = getattr(g, "request_id", None)
                if request_id:
                    payload["request_id"] = request_id
                
                # HTTP context
                payload["http"] = {
                    "method": request.method,
                    "path": request.path,
                    "ip": request.remote_addr,
                    "user_agent": request.headers.get("User-Agent", "unknown")[:200],  # Truncate
                }
                
                # User context (if authenticated)
                try:
                    if current_user and current_user.is_authenticated:
                        payload["user"] = {
                            "id": str(current_user.id),
                            "username": current_user.username
                        }
                except Exception:
                    pass  # User context not available
        except Exception:
            pass  # Flask context not available (e.g., background task)
        
        # Add exception info if present
        if record.exc_info:
            payload["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": self.formatException(record.exc_info) if record.exc_info else None
            }
        
        # Add custom extra fields from LogRecord
        # Logger can add custom fields like: logger.info("msg", extra={"custom_field": "value"})
        for key, value in record.__dict__.items():
            if key not in {
                "name", "msg", "args", "created", "filename", "funcName", "levelname",
                "levelno", "lineno", "module", "msecs", "message", "pathname", "process",
                "processName", "relativeCreated", "thread", "threadName", "exc_info",
                "exc_text", "stack_info", "getMessage", "asctime"
            }:
                payload[key] = value
        
        return json.dumps(payload, ensure_ascii=False, default=str)

def _configure_logging(json_logs: bool = False) -> None:
    """
    Configure logging with optional JSON formatting.
    
    This sets up a single handler on the root logger and ensures
    Flask/Werkzeug loggers propagate to it (avoiding duplicates).
    """
    root = logging.getLogger()
    root.handlers[:] = []  # reset
    handler = logging.StreamHandler()
    handler.setFormatter(
        _JsonFormatter() if json_logs
        else logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)  # Temporarily DEBUG to diagnose OpenAI parsing issue
    
    # Prevent duplicate logs by ensuring Flask/Werkzeug loggers propagate to root
    # instead of having their own handlers
    for logger_name in ['flask.app', 'werkzeug', 'socketio', 'engineio']:
        logger = logging.getLogger(logger_name)
        logger.handlers.clear()
        logger.propagate = True

def _sentry_before_send(event, hint):
    """
    Filter function to sanitize events before sending to Sentry.
    
    This allows us to:
    - Filter out sensitive data
    - Ignore specific error types
    - Add custom context
    """
    # Don't send HTTP 404 errors (too noisy)
    if 'exc_info' in hint:
        exc_type, exc_value, tb = hint['exc_info']
        if isinstance(exc_value, Exception):
            # Filter out common non-critical exceptions
            exc_name = exc_value.__class__.__name__
            if exc_name in ['NotFound', 'Unauthorized', 'Forbidden']:
                return None
    
    # Sanitize sensitive data from request body
    if 'request' in event and 'data' in event['request']:
        sensitive_keys = ['password', 'token', 'api_key', 'secret', 'authorization']
        data = event['request']['data']
        if isinstance(data, dict):
            for key in sensitive_keys:
                if key in data:
                    data[key] = '[REDACTED]'
    
    return event

# ---------- Create the SocketIO singleton with eventlet for production WebSocket support
# SECURITY: Restrict CORS origins with custom validator
def _validate_socketio_origin(origin):
    """
    Validate Socket.IO origin against allowed patterns.
    
    Socket.IO doesn't support wildcard patterns in cors_allowed_origins,
    so we use a callable validator to check origins against patterns.
    """
    if not origin:
        return False
    
    # Check environment variable for explicit allowed origins
    env_origins = os.getenv('SOCKETIO_ALLOWED_ORIGINS', '').split(',')
    if env_origins and env_origins != ['']:
        return origin in [o.strip() for o in env_origins]
    
    # Development: Allow localhost
    if origin.startswith('http://localhost:') or origin.startswith('https://localhost:'):
        return True
    
    # Production: Allow all Replit domains
    # Primary workspace domains
    if origin.endswith('.repl.co'):
        return True
    
    # Deployment domains
    if origin.endswith('.replit.dev') or origin.endswith('.replit.app'):
        return True
    
    # Base Replit domains
    if origin in ['https://replit.dev', 'https://replit.app', 'https://repl.co']:
        return True
    
    return False

socketio = SocketIO(
    cors_allowed_origins=_validate_socketio_origin,  # Custom validator for pattern matching
    async_mode="eventlet",  # Changed from threading to eventlet for proper WebSocket support
    ping_timeout=60,
    ping_interval=25,
    path="/socket.io",
    engineio_logger=False,
    socketio_logger=False,
    max_http_buffer_size=int(os.getenv("SIO_MAX_HTTP_BUFFER", str(10 * 1024 * 1024))),  # 10 MB per message
    allow_upgrades=True,  # Allow WebSocket upgrades
    transports=['websocket', 'polling']  # WebSocket first, polling fallback
)

def create_app() -> Flask:
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.from_object(Config)
    
    # Initialize Sentry error tracking
    sentry_dsn = os.environ.get("SENTRY_DSN")
    if sentry_dsn:
        sentry_environment = os.environ.get("SENTRY_ENVIRONMENT", "development")
        sentry_release = os.environ.get("SENTRY_RELEASE", "mina@unknown")
        
        sentry_sdk.init(
            dsn=sentry_dsn,
            integrations=[
                FlaskIntegration(),
                SqlalchemyIntegration(),
                LoggingIntegration(
                    level=logging.INFO,  # Capture info and above as breadcrumbs
                    event_level=logging.ERROR  # Send errors as events
                ),
            ],
            environment=sentry_environment,
            release=sentry_release,
            traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.1")),  # 10% of transactions
            profiles_sample_rate=float(os.environ.get("SENTRY_PROFILES_SAMPLE_RATE", "0.1")),  # 10% profiling
            send_default_pii=False,  # Don't send personally identifiable information
            attach_stacktrace=True,
            before_send=_sentry_before_send,  # Custom filter function
        )
        app.logger.info(f"✅ Sentry initialized: env={sentry_environment}, release={sentry_release}")
    else:
        app.logger.warning("⚠️ SENTRY_DSN not set - error tracking disabled")
    
    # Enforce SESSION_SECRET is set - fail fast in production
    app.secret_key = os.environ.get("SESSION_SECRET") or getattr(Config, "SECRET_KEY")
    if not app.secret_key:
        # Only allow fallback in development
        if os.getenv("REPLIT_DEV_ENV") or os.getenv("REPLIT_RUNTIME_TYPE") == "interactivedev":
            app.secret_key = "dev-session-secret-only-for-testing-change-in-production"  # pragma: allowlist secret
            app.logger.warning("SESSION_SECRET not set, using development key")
        else:
            raise ValueError("SESSION_SECRET environment variable must be set for production")
    app.config["MAX_CONTENT_LENGTH"] = getattr(Config, "MAX_CONTENT_LENGTH", 32 * 1024 * 1024)

    # logging
    _configure_logging(json_logs=getattr(Config, "JSON_LOGS", False))
    
    # Clear Flask's default handlers to prevent duplicate logs
    # Flask adds its own handler during initialization, but we want only our configured handler
    app.logger.handlers.clear()
    app.logger.propagate = True
    
    app.logger.info("Booting Mina…")

    # reverse proxy (Replit)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)
    
    # Set security headers (production hardening)
    app.config["SESSION_COOKIE_SECURE"] = True
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["PERMANENT_SESSION_LIFETIME"] = 1800  # 30 minutes
    
    # Initialize CSRF protection  
    csrf = CSRFProtect(app)
    app.config["WTF_CSRF_TIME_LIMIT"] = None  # Don't expire tokens
    app.config["WTF_CSRF_SSL_STRICT"] = True  # Enforce HTTPS referer/origin checks (ProxyFix sets is_secure)
    app.config["WTF_CSRF_CHECK_DEFAULT"] = True  # Enable CSRF by default
    
    # Exempt Socket.IO Engine.IO endpoint from CSRF (polling/handshake POST requests)
    # Socket.IO uses its own connection-level authentication
    # We wrap the error handler to allow Socket.IO requests through
    original_error_handler = csrf._error_response
    def custom_csrf_error(reason):
        if request.path.startswith('/socket.io'):
            return None  # Allow request to proceed
        return original_error_handler(reason)
    csrf._error_response = custom_csrf_error

    # Configure Flask-Limiter for production-grade rate limiting
    # Use Redis if available, fallback to memory storage
    redis_url = os.environ.get("REDIS_URL")
    storage_uri = redis_url if redis_url else "memory://"
    
    limiter = Limiter(
        get_remote_address,
        app=app,
        storage_uri=storage_uri,
        default_limits=["100 per minute", "1000 per hour"],
        strategy="fixed-window",
        headers_enabled=True,  # Include X-RateLimit-* headers in responses
        swallow_errors=True,  # Don't crash app if rate limiter fails
    )
    
    # Make limiter available for route decorators
    app.limiter = limiter
    
    storage_type = "Redis" if redis_url else "Memory"
    app.logger.info(f"✅ Flask-Limiter configured ({storage_type} backend): 100/min, 1000/hour per IP")

    # gzip (optional)
    try:
        from flask_compress import Compress  # type: ignore
        Compress(app)
        app.logger.info("Compression enabled")
    except Exception:
        app.logger.info("Compression unavailable (flask-compress not installed)")

    # middlewares with proper error handling and logging
    try:
        from middleware.request_context import request_context_middleware  # type: ignore
        request_context_middleware(app)
        app.logger.info("✅ Request context middleware enabled")
    except Exception as e:
        app.logger.warning(f"⚠️ Request context middleware failed to load: {e}")

    # Body size limits (Flask-Limiter handles rate limiting now)
    app.config.setdefault("MAX_JSON_BODY_BYTES", 5 * 1024 * 1024)  # 5MB
    app.config.setdefault("MAX_FORM_BODY_BYTES", 50 * 1024 * 1024)  # 50MB
    
    # Apply body size checks via before_request (rate limiting now handled by Flask-Limiter)
    @app.before_request
    def check_body_size():
        cl = request.content_length or 0
        if request.method in ("POST", "PUT", "PATCH"):
            ct = (request.content_type or "").lower()
            max_json = app.config.get("MAX_JSON_BODY_BYTES", 5 * 1024 * 1024)
            max_form = app.config.get("MAX_FORM_BODY_BYTES", 50 * 1024 * 1024)
            
            if "application/json" in ct and cl > max_json:
                from flask import abort
                abort(413)
            if "multipart/form-data" in ct and cl > max_form:
                from flask import abort
                abort(413)

    # Set CORS defaults - secure for both production and development
    env = os.environ.get("FLASK_ENV", "development")
    if env == "production":
        app.config.setdefault("ALLOWED_ORIGINS", [])  # Require explicit config in production
    else:
        # Development: Allow localhost only, never use ["*"] to prevent reflection attacks
        app.config.setdefault("ALLOWED_ORIGINS", [
            "http://localhost:5000",
            "https://localhost:5000",
            "http://127.0.0.1:5000",
            "https://127.0.0.1:5000"
        ])
    
    try:
        from middleware.cors import cors_middleware  # type: ignore
        cors_middleware(app)
        app.logger.info("✅ CORS middleware enabled")
    except Exception as e:
        app.logger.warning(f"⚠️ CORS middleware failed to load: {e}")

    # per-request id for tracing
    @app.before_request
    def assign_request_id():
        g.request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())

    # Content Security Policy with nonce-based inline script protection
    try:
        from middleware.csp import csp_middleware  # type: ignore
        csp_middleware(app)
        app.logger.info("✅ CSP middleware enabled with nonce-based inline script protection")
    except Exception as e:
        app.logger.warning(f"⚠️ CSP middleware failed to load: {e}")
    
    # Session security configuration and middleware
    try:
        from middleware.session_security import configure_session_security, session_security_middleware  # type: ignore
        configure_session_security(app)
        session_security_middleware(app)
        app.logger.info("✅ Session security hardening enabled: timeouts, rotation, fixation prevention")
    except Exception as e:
        app.logger.warning(f"⚠️ Session security middleware failed to load: {e}")
    
    # HSTS (Strict Transport Security) - only for production HTTPS
    @app.after_request
    def add_hsts_header(resp):
        if app.config.get('ENV') == 'production':
            resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
        return resp

    # ensure metrics directories
    metrics_dir = getattr(Config, "METRICS_DIR", "./metrics")
    os.makedirs(metrics_dir, exist_ok=True)
    os.makedirs(os.path.join(metrics_dir, "sessions"), exist_ok=True)

    # Database configuration (optional for graceful degradation)
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        app.config["SQLALCHEMY_DATABASE_URI"] = database_url
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
            "pool_recycle": 300,
            "pool_pre_ping": True,
        }
        
        # Initialize database models
        try:
            from models import db
            from flask_migrate import Migrate

            db.init_app(app)
            migrate = Migrate(app, db)

            # Create all tables that don't exist yet (development fallback)
            with app.app_context():
                db.create_all()

            app.logger.info("✅ Database connected and initialized (migrations enabled)")
        except Exception as e:
            app.logger.warning(f"⚠️ Database initialization failed: {e}")
            app.logger.info("Continuing without database persistence")
        
        # Initialize Flask-Login
        login_manager = LoginManager()
        login_manager.init_app(app)
        login_manager.login_view = 'auth.login'  # type: ignore
        login_manager.login_message = 'Please log in to access this page.'
        login_manager.login_message_category = 'info'
        
        @login_manager.user_loader
        def load_user(user_id):
            try:
                from models import User, db as models_db
                return models_db.session.query(User).get(int(user_id))
            except Exception:
                return None
    else:
        app.logger.info("No DATABASE_URL found, running without database persistence")

    # pages blueprint or fallback /live
    try:
        from routes.pages import pages_bp  # type: ignore
        app.register_blueprint(pages_bp)
    except Exception:
        @app.route("/live")
        def live():
            return render_template("live.html")

    # WebSocket routes (required) - import to bind handlers
    import routes.websocket  # noqa: F401
    import routes.transcription_websocket  # noqa: F401
    
    # Register enhanced WebSocket handlers
    try:
        from routes.enhanced_transcription_websocket import register_enhanced_websocket_handlers
        register_enhanced_websocket_handlers(socketio)
        app.logger.info("Enhanced WebSocket handlers registered")
    except Exception as e:
        app.logger.warning(f"Failed to register enhanced WebSocket handlers: {e}")
    
    # Register comprehensive WebSocket handlers
    try:
        from routes.comprehensive_transcription_api import register_comprehensive_websocket_handlers
        register_comprehensive_websocket_handlers(socketio)
        app.logger.info("Comprehensive WebSocket handlers registered")
    except Exception as e:
        app.logger.warning(f"Failed to register comprehensive WebSocket handlers: {e}")
    
    # Register live transcription Socket.IO handlers
    try:
        from routes.live_socketio import register_live_socketio
        register_live_socketio()
        app.logger.info("✅ Live transcription Socket.IO handlers registered")
    except Exception as e:
        app.logger.warning(f"Failed to register live Socket.IO handlers: {e}")
    
    # Register CROWN⁴ WebSocket namespaces for real-time synchronization
    try:
        from routes.dashboard_websocket import register_dashboard_namespace
        from routes.tasks_websocket import register_tasks_namespace
        from routes.analytics_websocket import register_analytics_namespace
        from routes.meetings_websocket import register_meetings_namespace
        from services.event_broadcaster import event_broadcaster
        
        # Initialize event broadcaster with socketio instance
        event_broadcaster.set_socketio(socketio)
        
        # Register namespace handlers
        register_dashboard_namespace(socketio)
        register_tasks_namespace(socketio)
        register_analytics_namespace(socketio)
        register_meetings_namespace(socketio)
        
        app.logger.info("✅ CROWN⁴ WebSocket namespaces registered: /dashboard, /tasks, /analytics, /meetings")
    except Exception as e:
        app.logger.warning(f"Failed to register CROWN⁴ WebSocket namespaces: {e}")

    # Register transcription APIs
    # FIXED: Only register the working unified transcription API to avoid route conflicts
    try:
        from routes.unified_transcription_api import unified_api_bp
        app.register_blueprint(unified_api_bp)
        app.logger.info("✅ Unified Transcription API registered (ACTIVE)")
    except Exception as e:
        app.logger.warning(f"Failed to register unified transcription API: {e}")
    
    # Disable conflicting transcription endpoints to prevent route conflicts
    # try:
    #     from routes.transcription_api import transcription_api_bp
    #     app.register_blueprint(transcription_api_bp)
    #     app.logger.info("Transcription API registered")
    # except Exception as e:
    #     app.logger.warning(f"Failed to register transcription API: {e}")
    
    # try:
    #     from routes.enhanced_transcription_api import enhanced_api_bp
    #     app.register_blueprint(enhanced_api_bp)
    #     app.logger.info("Enhanced Transcription API registered")
    # except Exception as e:
    #     app.logger.warning(f"Failed to register enhanced transcription API: {e}")
    
    # try:
    #     from routes.comprehensive_transcription_api import comprehensive_bp
    #     app.register_blueprint(comprehensive_bp)
    #     app.logger.info("Comprehensive Transcription API registered")
    # except Exception as e:
    #     app.logger.warning(f"Failed to register comprehensive transcription API: {e}")
    
    # Register WORKING live transcription API (priority)
    try:
        from routes.live_transcription_working import live_transcription_bp
        app.register_blueprint(live_transcription_bp)
        app.logger.info("✅ Working Live Transcription API registered")
    except Exception as e:
        app.logger.warning(f"Failed to register working live transcription API: {e}")

    # Register authentication and dashboard blueprints
    try:
        from routes.auth import auth_bp
        app.register_blueprint(auth_bp)
        app.logger.info("Authentication routes registered")
    except Exception as e:
        app.logger.warning(f"Failed to register auth routes: {e}")
    
    try:
        from routes.dashboard import dashboard_bp
        app.register_blueprint(dashboard_bp)
        app.logger.info("Dashboard routes registered")
    except Exception as e:
        app.logger.warning(f"Failed to register dashboard routes: {e}")
    
    # Register sessions blueprint for refined view and session management
    try:
        from routes.sessions import sessions_bp
        app.register_blueprint(sessions_bp)
        app.logger.info("✅ Sessions routes registered (refined view enabled)")
    except Exception as e:
        app.logger.warning(f"Failed to register sessions routes: {e}")

    # Register API blueprints for REST endpoints
    try:
        from routes.api_meetings import api_meetings_bp
        app.register_blueprint(api_meetings_bp)
        app.logger.info("Meetings API routes registered")
    except Exception as e:
        app.logger.warning(f"Failed to register meetings API routes: {e}")
    
    try:
        from routes.api_tasks import api_tasks_bp
        app.register_blueprint(api_tasks_bp)
        app.logger.info("Tasks API routes registered")
    except Exception as e:
        app.logger.warning(f"Failed to register tasks API routes: {e}")
    
    try:
        from routes.api_analytics import api_analytics_bp
        app.register_blueprint(api_analytics_bp)
        app.logger.info("Analytics API routes registered")
    except Exception as e:
        app.logger.warning(f"Failed to register analytics API routes: {e}")
    
    try:
        from routes.api_markers import api_markers_bp
        app.register_blueprint(api_markers_bp)
        app.logger.info("Markers API routes registered")
    except Exception as e:
        app.logger.warning(f"Failed to register markers API routes: {e}")
    
    try:
        from routes.api_generate_insights import api_generate_insights_bp
        app.register_blueprint(api_generate_insights_bp)
        app.logger.info("API Generate Insights route registered")
    except Exception as e:
        app.logger.warning(f"Failed to register API Generate Insights route: {e}")
    
    try:
        from routes.api_transcript import api_transcript_bp
        app.register_blueprint(api_transcript_bp)
        app.logger.info("Transcript API routes registered")
    except Exception as e:
        app.logger.warning(f"Failed to register transcript API routes: {e}")
    
    try:
        from routes.api_ai_insights import api_ai_insights_bp
        app.register_blueprint(api_ai_insights_bp)
        app.logger.info("AI Insights API routes registered")
    except Exception as e:
        app.logger.warning(f"Failed to register AI Insights API routes: {e}")
    
    try:
        from routes.api_sharing import sharing_bp
        app.register_blueprint(sharing_bp)
        app.logger.info("Sharing API routes registered")
    except Exception as e:
        app.logger.warning(f"Failed to register Sharing API routes: {e}")

    # --- Session Finalization API ---
    try:
        from routes.api_session_finalize import api_session_finalize_bp
        app.register_blueprint(api_session_finalize_bp)  # bp already has url_prefix="/api/sessions"
        csrf.exempt(api_session_finalize_bp)  # POST endpoint; avoid CSRF block from browser fetch
        app.logger.info("Session Finalization API routes registered")
    except Exception as e:
        app.logger.warning(f"Failed to register Session Finalization API: {e}")

    # --- CROWN+ Monitoring API ---
    try:
        from routes.api_crown_monitoring import crown_monitoring_bp
        app.register_blueprint(crown_monitoring_bp)
        app.logger.info("CROWN+ Monitoring API routes registered (/api/crown/)")
    except Exception as e:
        app.logger.warning(f"Failed to register CROWN+ Monitoring API: {e}")

    # Settings routes
    try:
        from routes.settings import settings_bp
        app.register_blueprint(settings_bp)
        app.logger.info("Settings routes registered")
    except Exception as e:
        app.logger.error(f"Failed to register settings routes: {e}")

    # Calendar routes
    try:
        from routes.calendar import calendar_bp
        app.register_blueprint(calendar_bp)
        app.logger.info("Calendar routes registered")
    except Exception as e:
        app.logger.error(f"Failed to register calendar routes: {e}")
    
    # AI Copilot routes
    try:
        from routes.copilot import copilot_bp
        app.register_blueprint(copilot_bp)
        
        from routes.copilot_templates import copilot_templates_bp
        app.register_blueprint(copilot_templates_bp)
        app.logger.info("AI Copilot routes registered")
    except Exception as e:
        app.logger.error(f"Failed to register AI Copilot routes: {e}")

    # Register Memory API routes
    try:
        from server.routes.memory_api import memory_bp
        app.register_blueprint(memory_bp, url_prefix="/api")
        csrf.exempt(memory_bp)
        app.logger.info("✅ Memory API routes registered (/api/memory)")
    except Exception as e:
        app.logger.error(f"❌ Failed to register Memory API routes: {e}")

    # Register Export API routes
    try:
        from routes.export import export_bp
        app.register_blueprint(export_bp, url_prefix="/api")
        csrf.exempt(export_bp)
        app.logger.info("✅ Export API routes registered (/api/export)")
    except Exception as e:
        app.logger.error(f"❌ Failed to register Export API routes: {e}")

    
    # --- Summary Routes ---
    try:
        from routes.summary import summary_bp
        app.register_blueprint(summary_bp)
        app.logger.info("Blueprint registered: summary_bp")
    except Exception as e:
        app.logger.warning(f"Failed to register summary_bp: {e}")
        
    # --- Flags Routes ---
    try:
        from routes.flags import flags_bp
        app.register_blueprint(flags_bp)
        app.logger.info("Blueprint registered: flags_bp")
    except Exception as e:
        app.logger.warning(f"Failed to register flags_bp: {e}")
        
    # --- Billing Routes ---
    try:
        from routes.billing import billing_bp
        app.register_blueprint(billing_bp)
        app.logger.info("Blueprint registered: billing_bp")
    except Exception as e:
        app.logger.warning(f"Failed to register billing_bp: {e}")
        
    # --- Integrations Routes ---
    try:
        from routes.integrations import integrations_bp
        app.register_blueprint(integrations_bp)
        app.logger.info("Blueprint registered: integrations_bp")
    except Exception as e:
        app.logger.warning(f"Failed to register integrations_bp: {e}")
        
    # --- Teams Routes ---
    try:
        from routes.teams import teams_bp
        app.register_blueprint(teams_bp)
        app.logger.info("Blueprint registered: teams_bp")
    except Exception as e:
        app.logger.warning(f"Failed to register teams_bp: {e}")
        
    # --- Comments Routes ---
    try:
        from routes.comments import comments_bp
        app.register_blueprint(comments_bp)
        app.logger.info("Blueprint registered: comments_bp")
    except Exception as e:
        app.logger.warning(f"Failed to register comments_bp: {e}")
        
    # Production Monitoring Dashboard
    try:
        from monitoring_dashboard import monitoring_bp
        app.register_blueprint(monitoring_bp)
        app.logger.info("Production Monitoring Dashboard registered")
    except Exception as e:
        app.logger.error(f"Failed to register Production Monitoring Dashboard: {e}")
        
    # Operations routes (Sentry testing, performance monitoring)
    try:
        from routes.ops import ops_bp
        app.register_blueprint(ops_bp)
        app.logger.info("Ops routes registered (Sentry testing, performance monitoring)")
    except Exception as e:
        app.logger.error(f"Failed to register ops routes: {e}")

    try:
        from routes.ui import ui_bp
        app.register_blueprint(ui_bp)
        app.logger.info("Ops routes registered (Sentry testing, performance monitoring)")
    except Exception as e:
        app.logger.error(f"Failed to register ops routes: {e}")
    
    # Missing API endpoints - temporarily disabled due to circular import
    # Quick fix for analytics and meetings endpoints
    try:
        from routes.quick_analytics_fix import quick_analytics_bp
        app.register_blueprint(quick_analytics_bp)
        app.logger.info("Quick analytics fix registered")
    except Exception as e:
        app.logger.error(f"Failed to register quick analytics fix: {e}")
        
    try:
        from routes.meetings_api_fix import meetings_api_fix_bp
        app.register_blueprint(meetings_api_fix_bp)
        app.logger.info("Quick meetings API fix registered")
    except Exception as e:
        app.logger.error(f"Failed to register meetings API fix: {e}")

    # other blueprints (guarded)
    _optional = [
        ("routes.final_upload", "final_bp", "/api"),
        #("routes.export", "export_bp", "/api"),
        ("routes.insights", "insights_bp", "/api"),
        ("routes.nudges", "nudges_bp", "/api"),
        ("routes.team_collaboration", "team_bp", "/api"),
        ("routes.advanced_analytics", "analytics_bp", "/api"),
        ("routes.integration_marketplace", "integrations_bp", "/api"),
        ("routes.health", "health_bp", "/health"),
        ("routes.metrics_stream", "metrics_stream_bp", "/api"),
        ("routes.error_handlers", "errors_bp", None),
    ]
    for mod_name, bp_name, prefix in _optional:
        try:
            mod = __import__(mod_name, fromlist=[bp_name])
            bp = getattr(mod, bp_name)
            app.register_blueprint(bp, url_prefix=prefix) if prefix else app.register_blueprint(bp)
        except Exception:
            pass

    # basic /healthz if health blueprint absent
    @app.get("/healthz")
    def healthz():
        return {"ok": True, "uptime": True}, 200
    
    # alias /health for CI/testing compatibility
    @app.get("/health")
    def health():
        return {"ok": True, "uptime": True}, 200

    # Security-hardened error handlers - prevent information leakage
    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({
            'error': 'bad_request',
            'message': 'The request could not be understood',
            'request_id': g.get('request_id')
        }), 400

    @app.errorhandler(401)
    def unauthorized(e):
        return jsonify({
            'error': 'unauthorized',
            'message': 'Authentication required',
            'request_id': g.get('request_id')
        }), 401

    @app.errorhandler(403)
    def forbidden(e):
        return jsonify({
            'error': 'forbidden',
            'message': 'You do not have permission to access this resource',
            'request_id': g.get('request_id')
        }), 403

    @app.errorhandler(404)
    def not_found(e):
        # Return HTML page for browser requests, JSON for API requests
        if request.accept_mimetypes.accept_html and \
           not request.path.startswith('/api/'):
            return render_template('errors/404.html'), 404
        
        return jsonify({
            'error': 'not_found',
            'message': 'The requested resource was not found',
            'request_id': g.get('request_id')
        }), 404

    @app.errorhandler(413)
    def payload_too_large(e):
        return jsonify({
            'error': 'payload_too_large',
            'message': 'Request payload too large',
            'request_id': g.get('request_id')
        }), 413

    @app.errorhandler(429)
    def rate_limit_exceeded(e):
        return jsonify({
            'error': 'rate_limit_exceeded',
            'message': 'Too many requests. Please try again later.',
            'request_id': g.get('request_id')
        }), 429

    @app.errorhandler(500)
    def internal_server_error(e):
        # Log full error internally with stack trace
        app.logger.error(f"Internal server error: {str(e)}", exc_info=True)
        
        # Return generic message to client (no stack trace)
        return jsonify({
            'error': 'internal_server_error',
            'message': 'An internal error occurred. Please try again later.',
            'request_id': g.get('request_id')
        }), 500

    @app.errorhandler(Exception)
    def handle_unexpected_error(e):
        # Log unexpected errors with full context
        app.logger.error(f"Unexpected error: {type(e).__name__}: {str(e)}", exc_info=True)
        
        # Return generic error (never expose exception details)
        return jsonify({
            'error': 'server_error',
            'message': 'An unexpected error occurred',
            'request_id': g.get('request_id')
        }), 500

    # hook Socket.IO to app
    socketio.init_app(app)
    app.extensions["socketio"] = socketio

    # Socket.IO origin guard (optional tighten)
    allowed = [o.strip() for o in str(getattr(Config, "CORS_ALLOWLIST", "*")).split(",") if o.strip()]
    if allowed and allowed != ["*"]:
        @socketio.on("connect")
        def _check_origin(auth: Optional[dict] = None):
            origin = request.headers.get("Origin") or ""
            if not any(origin.endswith(x) or origin == x for x in allowed):
                app.logger.warning("Rejecting WS from origin=%s", origin)
                return False  # refuse connection

    # Start resource cleanup service to prevent memory leaks
    try:
        from services.resource_cleanup import resource_cleanup_manager
        
        # Register default cleanup tasks
        resource_cleanup_manager.register_cleanup_task('memory_gc', resource_cleanup_manager.force_garbage_collection, 60)
        resource_cleanup_manager.register_cleanup_task('temp_files', resource_cleanup_manager.cleanup_temp_files, 600)
        resource_cleanup_manager.register_cleanup_task('websocket_buffers', resource_cleanup_manager.cleanup_websocket_buffers, 300)
        
        # Start the background service
        resource_cleanup_manager.start_cleanup_service()
        app.logger.info("✅ Resource cleanup service started with default tasks registered")
    except Exception as e:
        app.logger.error(f"❌ Failed to start resource cleanup service: {e}")
    
    # Start background task manager for reliable job processing
    try:
        from services.background_tasks import background_task_manager
        
        # Start worker pool and retry scheduler
        background_task_manager.start()
        app.logger.info("✅ Background task manager started with 2 workers and retry scheduler")
    except Exception as e:
        app.logger.error(f"❌ Failed to start background task manager: {e}")
    
    # Initialize Redis connection manager with failover support
    try:
        from services.redis_failover import init_redis_manager
        
        redis_url = os.getenv('REDIS_URL')
        if redis_url:
            redis_manager = init_redis_manager(redis_url)
            app.logger.info("✅ Redis connection manager initialized with failover support")
        else:
            app.logger.info("ℹ️  No REDIS_URL configured - using in-memory fallback for caching")
    except Exception as e:
        app.logger.error(f"❌ Failed to initialize Redis manager: {e}")
    
    app.logger.info("Mina app ready")
    return app

# WSGI entrypoints
app = create_app()

@app.route("/api/memory/search", methods=["POST"])
def search_memory():
    try:
        data = request.get_json()
        query = data.get("query")
        if not query:
            return jsonify({"error": "Missing query"}), 400

        # 1. Create embedding for the query
        embed_response = openai.embeddings.create(
            input=query,
            model="text-embedding-3-large"
        )
        query_embedding = embed_response.data[0].embedding

        # 2. Run similarity search
        conn = get_pg_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT id, content,
                   1 - (embedding <=> %s::vector) AS similarity
            FROM memory_embeddings
            ORDER BY similarity DESC
            LIMIT 5;
        """, (query_embedding,))

        results = [
            {"id": r[0], "content": r[1], "similarity": round(r[2], 4)}
            for r in cur.fetchall()
        ]

        cur.close()
        conn.close()

        return jsonify({"results": results, "count": len(results)}), 200

    except Exception as e:
        print("❌ Error in search_memory:", e)
        return jsonify({"error": str(e)}), 500
        
logger = get_logger()
logger.info("🚀 Starting Mina backend...")

app.register_blueprint(metrics_bp)

@app.before_request
def before_request():
    logger.info(f"Incoming request: {request.method} {request.path}")

@app.after_request
def after_request(response):
    logger.info(f"Completed: {request.path} [{response.status_code}]")
    return response

# graceful shutdown for local/threading runs
def _shutdown(*_):
    app.logger.info("Shutting down gracefully…")
    # In threading mode, there is no socketio.stop(); process will exit.
signal.signal(signal.SIGTERM, _shutdown)
signal.signal(signal.SIGINT, _shutdown)

app = create_app()

# Initialize Memory Persistence safely after Flask app context is ready
with app.app_context():
    try:
        mem.init_db()
        app.logger.info("✅ Memory persistence initialized successfully")
    except Exception as e:
        app.logger.error(f"❌ Failed to initialize memory persistence: {e}")

# Register metrics blueprint (keep if not already registered)
app.register_blueprint(metrics_bp)

@app.route("/api/memory/search", methods=["POST"])
def search_memory():
    """
    Perform semantic similarity search against stored memory embeddings.
    """
    try:
        data = request.get_json(force=True)
        query = data.get("query")
        if not query:
            return jsonify({"error": "Missing query"}), 400

        # Generate embedding for the query using OpenAI’s embedding API
        embed_response = openai.embeddings.create(
            input=query,
            model="text-embedding-3-large"
        )
        query_embedding = embed_response.data[0].embedding

        # Use SQLAlchemy for vector similarity search
        from sqlalchemy import text
        results = db.session.execute(text("""
            SELECT id, content,
                   1 - (embedding <=> :query_embedding::vector) AS similarity
            FROM memory_embeddings
            ORDER BY similarity DESC
            LIMIT 5;
        """), {"query_embedding": query_embedding}).fetchall()

        formatted = [
            {"id": r.id, "content": r.content, "similarity": round(r.similarity, 4)}
            for r in results
        ]
        return jsonify({"results": formatted, "count": len(formatted)}), 200

    except Exception as e:
        app.logger.error(f"❌ Error in /api/memory/search: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

# ============================================
# Analytics API Endpoint
# ============================================
@app.route("/api/v1/analytics/<meeting_id>", methods=["GET"])
def analytics_api():
    """
    Returns aggregated analytics data for the dashboard.
    Pulls sentiment and impact scores from memory persistence.
    """
    try:
        all_memories = mem.get_memory("M-123")  # placeholder meeting_id
        sentiment_data = []
        impact_data = []

        for entry in all_memories:
            date_str = entry["created_at"].split(" ")[0]
            sentiment_val = (
                1 if entry["sentiment"] == "positive"
                else -1 if entry["sentiment"] == "negative"
                else 0
            )
            sentiment_data.append({"date": date_str, "value": sentiment_val})
            impact_data.append({"user": entry["user_id"], "score": entry["impact_score"]})

        return jsonify({
            "sentiment": sentiment_data,
            "impact": impact_data
        })

    except Exception as e:
        print(f"[ERROR] analytics_api failed: {e}")
        return jsonify({
            "sentiment": [],
            "impact": [],
            "error": str(e)
        }), 500


# Graceful shutdown handlers (keep as-is)
def _shutdown(*_):
    app.logger.info("Shutting down gracefully…")

signal.signal(signal.SIGTERM, _shutdown)
signal.signal(signal.SIGINT, _shutdown)

if __name__ == "__main__":
    app.logger.info(
        "🚀 Mina running at http://0.0.0.0:5000 (Socket.IO path %s)",
        app.config.get("SOCKETIO_PATH", "/socket.io")
    )
    socketio.run(app, host="0.0.0.0", port=5000, use_reloader=False, log_output=True)

if __name__ == "__main__":
    app.logger.info("🚀 Mina at http://0.0.0.0:5000  (Socket.IO path %s)", app.config.get("SOCKETIO_PATH", "/socket.io"))
    socketio.run(app, host="0.0.0.0", port=5000, use_reloader=False, log_output=True)

