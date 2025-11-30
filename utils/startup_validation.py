"""
Production Startup Validation Module

Implements Google SRE best practices for production readiness:
1. Configuration validation - fail fast on missing critical settings
2. Dependency health checks - verify all services are accessible
3. Feature audit - track which features are loaded vs degraded
4. Structured startup logging for observability

Reference: Google SRE Book - Chapter 32: The Evolving SRE Engagement Model
"""

import os
import sys
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of a validation check."""
    name: str
    passed: bool
    message: str
    severity: str = "error"  # error, warning, info
    remediation: Optional[str] = None


@dataclass
class StartupReport:
    """Comprehensive startup validation report."""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    environment: str = "unknown"
    validations: List[ValidationResult] = field(default_factory=list)
    features_loaded: List[str] = field(default_factory=list)
    features_degraded: List[str] = field(default_factory=list)
    ready_for_production: bool = False
    
    def add_validation(self, result: ValidationResult):
        self.validations.append(result)
    
    def add_feature_loaded(self, name: str):
        self.features_loaded.append(name)
    
    def add_feature_degraded(self, name: str, reason: str):
        self.features_degraded.append(f"{name}: {reason}")
    
    def has_critical_failures(self) -> bool:
        return any(v.severity == "error" and not v.passed for v in self.validations)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "environment": self.environment,
            "ready_for_production": self.ready_for_production,
            "validations": [
                {
                    "name": v.name,
                    "passed": v.passed,
                    "message": v.message,
                    "severity": v.severity,
                    "remediation": v.remediation
                }
                for v in self.validations
            ],
            "features": {
                "loaded": self.features_loaded,
                "degraded": self.features_degraded
            },
            "summary": {
                "total_validations": len(self.validations),
                "passed": sum(1 for v in self.validations if v.passed),
                "failed": sum(1 for v in self.validations if not v.passed),
                "features_loaded": len(self.features_loaded),
                "features_degraded": len(self.features_degraded)
            }
        }


class StartupValidator:
    """
    Production startup validator following Google SRE PRR standards.
    
    Validates:
    1. Required environment variables
    2. Database connectivity
    3. Redis connectivity (if configured)
    4. External service dependencies
    5. Feature module loading
    """
    
    # Required environment variables for production
    REQUIRED_ENV_VARS = [
        ("SESSION_SECRET", "Session encryption key - CRITICAL for security"),
        ("DATABASE_URL", "PostgreSQL connection string"),
    ]
    
    # Recommended (warn if missing) environment variables
    RECOMMENDED_ENV_VARS = [
        ("SENTRY_DSN", "Error tracking - highly recommended for production"),
        ("REDIS_URL", "Redis for sessions/caching - recommended for scalability"),
        ("OPENAI_API_KEY", "OpenAI API for transcription features"),
    ]
    
    def __init__(self):
        self.report = StartupReport()
        self._detect_environment()
    
    def _detect_environment(self):
        """Detect the current environment (development/production)."""
        if os.getenv("REPLIT_DEPLOYMENT"):
            self.report.environment = "production"
        elif os.getenv("FLASK_ENV") == "production":
            self.report.environment = "production"
        elif os.getenv("REPLIT_DEV_ENV") or os.getenv("REPLIT_RUNTIME_TYPE") == "interactivedev":
            self.report.environment = "development"
        else:
            self.report.environment = os.getenv("FLASK_ENV", "development")
    
    def is_production(self) -> bool:
        return self.report.environment == "production"
    
    def validate_required_env_vars(self) -> None:
        """Check all required environment variables are set."""
        for var_name, description in self.REQUIRED_ENV_VARS:
            value = os.getenv(var_name)
            if value:
                self.report.add_validation(ValidationResult(
                    name=f"env:{var_name}",
                    passed=True,
                    message=f"{var_name} is configured",
                    severity="error"
                ))
            else:
                self.report.add_validation(ValidationResult(
                    name=f"env:{var_name}",
                    passed=False,
                    message=f"Missing required: {var_name}",
                    severity="error",
                    remediation=f"Set {var_name} environment variable. {description}"
                ))
    
    def validate_recommended_env_vars(self) -> None:
        """Check recommended environment variables."""
        for var_name, description in self.RECOMMENDED_ENV_VARS:
            value = os.getenv(var_name)
            if value:
                self.report.add_validation(ValidationResult(
                    name=f"env:{var_name}",
                    passed=True,
                    message=f"{var_name} is configured",
                    severity="warning"
                ))
            else:
                self.report.add_validation(ValidationResult(
                    name=f"env:{var_name}",
                    passed=True,  # Pass but warn
                    message=f"Optional: {var_name} not set - {description}",
                    severity="warning",
                    remediation=f"Consider setting {var_name}. {description}"
                ))
    
    def validate_database_connection(self) -> None:
        """Test database connectivity."""
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            self.report.add_validation(ValidationResult(
                name="db:connection",
                passed=False,
                message="DATABASE_URL not configured",
                severity="error",
                remediation="Set DATABASE_URL to a valid PostgreSQL connection string"
            ))
            return
        
        try:
            import psycopg2
            conn = psycopg2.connect(database_url)
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            conn.close()
            
            self.report.add_validation(ValidationResult(
                name="db:connection",
                passed=True,
                message="Database connection successful",
                severity="error"
            ))
        except Exception as e:
            self.report.add_validation(ValidationResult(
                name="db:connection",
                passed=False,
                message=f"Database connection failed: {str(e)[:100]}",
                severity="error",
                remediation="Check DATABASE_URL and ensure PostgreSQL is accessible"
            ))
    
    def validate_redis_connection(self) -> None:
        """Test Redis connectivity if configured."""
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            self.report.add_validation(ValidationResult(
                name="redis:connection",
                passed=True,
                message="Redis not configured (optional)",
                severity="info"
            ))
            return
        
        try:
            import redis
            r = redis.from_url(redis_url, socket_connect_timeout=5)
            r.ping()
            
            self.report.add_validation(ValidationResult(
                name="redis:connection",
                passed=True,
                message="Redis connection successful",
                severity="warning"
            ))
        except Exception as e:
            self.report.add_validation(ValidationResult(
                name="redis:connection",
                passed=False,
                message=f"Redis connection failed: {str(e)[:100]}",
                severity="warning",
                remediation="Check REDIS_URL or remove it to use filesystem sessions"
            ))
    
    def validate_secret_key_strength(self) -> None:
        """Validate session secret key meets security requirements."""
        secret = os.getenv("SESSION_SECRET", "")
        
        if not secret:
            self.report.add_validation(ValidationResult(
                name="security:session_secret",
                passed=False,
                message="SESSION_SECRET not set",
                severity="error",
                remediation="Generate a strong random key: python -c 'import secrets; print(secrets.token_hex(32))'"
            ))
            return
        
        if len(secret) < 32:
            self.report.add_validation(ValidationResult(
                name="security:session_secret",
                passed=False if self.is_production() else True,
                message=f"SESSION_SECRET too short ({len(secret)} chars, need 32+)",
                severity="error" if self.is_production() else "warning",
                remediation="Use at least 32 characters for SESSION_SECRET"
            ))
        else:
            self.report.add_validation(ValidationResult(
                name="security:session_secret",
                passed=True,
                message="SESSION_SECRET meets length requirements",
                severity="error"
            ))
    
    def run_all_validations(self) -> StartupReport:
        """Run all validation checks and return the report."""
        logger.info("=" * 60)
        logger.info("PRODUCTION READINESS VALIDATION")
        logger.info("=" * 60)
        logger.info(f"Environment: {self.report.environment}")
        
        # Run validations
        self.validate_required_env_vars()
        self.validate_recommended_env_vars()
        self.validate_database_connection()
        self.validate_redis_connection()
        self.validate_secret_key_strength()
        
        # Determine overall readiness
        self.report.ready_for_production = not self.report.has_critical_failures()
        
        # Log summary
        summary = self.report.to_dict()["summary"]
        logger.info("-" * 60)
        logger.info(f"Validations: {summary['passed']}/{summary['total_validations']} passed")
        
        if self.report.ready_for_production:
            logger.info("✅ READY FOR PRODUCTION")
        else:
            logger.error("❌ NOT READY FOR PRODUCTION")
            for v in self.report.validations:
                if not v.passed and v.severity == "error":
                    logger.error(f"  - {v.name}: {v.message}")
                    if v.remediation:
                        logger.error(f"    Fix: {v.remediation}")
        
        logger.info("=" * 60)
        
        return self.report
    
    def fail_if_not_ready(self) -> None:
        """
        Fail fast if critical validations fail in production.
        
        In development, log warnings but continue.
        In production, exit with error code.
        """
        if not self.report.ready_for_production:
            if self.is_production():
                logger.critical("Application cannot start - critical configuration missing")
                sys.exit(1)
            else:
                logger.warning("Development mode: continuing despite validation failures")


class BlueprintRegistry:
    """
    Track blueprint/feature loading for production observability.
    
    Implements graceful degradation pattern:
    - Log which features loaded successfully
    - Log which features failed to load (and why)
    - Report degraded capabilities clearly
    """
    
    def __init__(self, app=None):
        self.app = app
        self.loaded: List[str] = []
        self.failed: List[Tuple[str, str]] = []
    
    def register(self, module_path: str, blueprint_name: str, url_prefix: Optional[str] = None,
                 critical: bool = False) -> bool:
        """
        Attempt to register a blueprint with proper error handling.
        
        Args:
            module_path: Python module path (e.g., 'routes.auth')
            blueprint_name: Name of blueprint variable in module
            url_prefix: Optional URL prefix for blueprint
            critical: If True, raise exception on failure
            
        Returns:
            True if registered successfully, False otherwise
        """
        try:
            module = __import__(module_path, fromlist=[blueprint_name])
            blueprint = getattr(module, blueprint_name)
            
            if url_prefix:
                self.app.register_blueprint(blueprint, url_prefix=url_prefix)
            else:
                self.app.register_blueprint(blueprint)
            
            self.loaded.append(f"{module_path}.{blueprint_name}")
            self.app.logger.info(f"✅ Loaded: {module_path}.{blueprint_name}")
            return True
            
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)[:100]}"
            self.failed.append((f"{module_path}.{blueprint_name}", error_msg))
            
            if critical:
                self.app.logger.error(f"❌ CRITICAL - Failed to load {module_path}: {error_msg}")
                raise
            else:
                self.app.logger.warning(f"⚠️ Degraded - Failed to load {module_path}: {error_msg}")
                return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get registration status summary."""
        return {
            "loaded_count": len(self.loaded),
            "failed_count": len(self.failed),
            "loaded": self.loaded,
            "failed": [{"name": n, "error": e} for n, e in self.failed],
            "health": "healthy" if not self.failed else "degraded"
        }
    
    def log_summary(self) -> None:
        """Log a summary of blueprint loading."""
        self.app.logger.info("=" * 50)
        self.app.logger.info("BLUEPRINT LOADING SUMMARY")
        self.app.logger.info(f"Loaded: {len(self.loaded)} | Failed: {len(self.failed)}")
        
        if self.failed:
            self.app.logger.warning("Degraded features:")
            for name, error in self.failed:
                self.app.logger.warning(f"  - {name}: {error}")
        
        self.app.logger.info("=" * 50)


def run_startup_validation() -> StartupReport:
    """
    Convenience function to run startup validation.
    
    Call this at application startup before serving requests.
    """
    validator = StartupValidator()
    report = validator.run_all_validations()
    
    # In production, fail if not ready
    validator.fail_if_not_ready()
    
    return report
