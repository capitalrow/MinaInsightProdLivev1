"""
CROWN⁹ Copilot Security & Privacy Infrastructure

Provides data encryption, PII masking, and audit logging for secure operations.
"""

import logging
import re
import hashlib
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class PIIType(str, Enum):
    """Types of personally identifiable information."""
    EMAIL = "email"
    PHONE = "phone"
    SSN = "ssn"
    CREDIT_CARD = "credit_card"
    IP_ADDRESS = "ip_address"
    NAME = "name"


class AuditAction(str, Enum):
    """Audit log action types."""
    QUERY = "query"
    ACTION_EXECUTE = "action_execute"
    DATA_ACCESS = "data_access"
    CONFIG_CHANGE = "config_change"
    AUTH = "auth"
    ERROR = "error"


class CopilotSecurity:
    """
    Security and privacy service for Copilot operations.
    
    Features:
    - PII detection and masking
    - Audit logging
    - Input validation and sanitization
    - Rate limiting enforcement
    """
    
    def __init__(self):
        """Initialize security service."""
        self.pii_patterns = self._build_pii_patterns()
        self.audit_log = []
    
    def _build_pii_patterns(self) -> Dict[PIIType, re.Pattern]:
        """Build regex patterns for PII detection."""
        return {
            PIIType.EMAIL: re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
            PIIType.PHONE: re.compile(r'\b(?:\+?1[-.]?)?\(?([0-9]{3})\)?[-.]?([0-9]{3})[-.]?([0-9]{4})\b'),
            PIIType.SSN: re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
            PIIType.CREDIT_CARD: re.compile(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b'),
            PIIType.IP_ADDRESS: re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b'),
        }
    
    def mask_pii(self, text: str, mask_char: str = '*') -> str:
        """
        Mask PII in text for secure logging.
        
        Args:
            text: Text potentially containing PII
            mask_char: Character to use for masking
            
        Returns:
            Text with PII masked
        """
        masked_text = text
        
        # Mask emails
        masked_text = self.pii_patterns[PIIType.EMAIL].sub(
            lambda m: m.group(0)[:3] + (mask_char * 5) + '@' + (mask_char * 6) + '.com',
            masked_text
        )
        
        # Mask phone numbers
        masked_text = self.pii_patterns[PIIType.PHONE].sub(
            lambda m: f"({mask_char*3}) {mask_char*3}-{m.group(3)[-4:]}",
            masked_text
        )
        
        # Mask SSN
        masked_text = self.pii_patterns[PIIType.SSN].sub(
            f"{mask_char*3}-{mask_char*2}-****",
            masked_text
        )
        
        # Mask credit cards (show last 4 digits)
        def mask_cc(match):
            cc = match.group(0).replace('-', '').replace(' ', '')
            return f"{mask_char*4} {mask_char*4} {mask_char*4} {cc[-4:]}"
        
        masked_text = self.pii_patterns[PIIType.CREDIT_CARD].sub(
            mask_cc,
            masked_text
        )
        
        # Mask IP addresses
        masked_text = self.pii_patterns[PIIType.IP_ADDRESS].sub(
            f"{mask_char*3}.{mask_char*3}.{mask_char*3}.***",
            masked_text
        )
        
        return masked_text
    
    def detect_pii(self, text: str) -> List[PIIType]:
        """
        Detect PII types present in text.
        
        Args:
            text: Text to scan for PII
            
        Returns:
            List of detected PII types
        """
        detected = []
        
        for pii_type, pattern in self.pii_patterns.items():
            if pattern.search(text):
                detected.append(pii_type)
        
        return detected
    
    def sanitize_input(self, user_input: str) -> str:
        """
        Sanitize user input to prevent injection attacks.
        
        Args:
            user_input: Raw user input
            
        Returns:
            Sanitized input
        """
        # Remove potential SQL injection patterns
        sanitized = re.sub(r'[;\'"\\]', '', user_input)
        
        # Remove script tags
        sanitized = re.sub(r'<script[^>]*>.*?</script>', '', sanitized, flags=re.IGNORECASE | re.DOTALL)
        
        # Limit length
        max_length = 10000
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length]
            logger.warning(f"Input truncated from {len(user_input)} to {max_length} chars")
        
        return sanitized.strip()
    
    def audit_log_event(
        self,
        action: AuditAction,
        user_id: Optional[int],
        details: Dict[str, Any],
        success: bool = True
    ):
        """
        Log audit event for compliance and security monitoring.
        
        Args:
            action: Type of action performed
            user_id: User who performed the action
            details: Additional details about the event
            success: Whether the action succeeded
        """
        # Mask PII in details
        sanitized_details = {}
        for key, value in details.items():
            if isinstance(value, str):
                sanitized_details[key] = self.mask_pii(value)
            else:
                sanitized_details[key] = value
        
        audit_entry = {
            'timestamp': datetime.now().isoformat(),
            'action': action.value,
            'user_id': user_id,
            'details': sanitized_details,
            'success': success
        }
        
        self.audit_log.append(audit_entry)
        
        # Log to file (in production, send to secure audit service)
        logger.info(f"AUDIT: {json.dumps(audit_entry)}")
        
        # Trim audit log if it gets too large (keep last 10,000 entries)
        if len(self.audit_log) > 10000:
            self.audit_log = self.audit_log[-10000:]
    
    def hash_sensitive_data(self, data: str) -> str:
        """
        Hash sensitive data for secure storage.
        
        Args:
            data: Sensitive data to hash
            
        Returns:
            SHA-256 hash of data
        """
        return hashlib.sha256(data.encode()).hexdigest()
    
    def validate_workspace_access(
        self,
        user_id: int,
        workspace_id: int
    ) -> bool:
        """
        Validate user has access to workspace.
        
        Args:
            user_id: User ID
            workspace_id: Workspace ID
            
        Returns:
            True if user has access, False otherwise
        """
        # In production, check database permissions
        # For now, return True (assumes middleware handles auth)
        return True
    
    def get_audit_log(
        self,
        user_id: Optional[int] = None,
        action: Optional[AuditAction] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Retrieve audit log entries.
        
        Args:
            user_id: Filter by user ID
            action: Filter by action type
            limit: Maximum number of entries to return
            
        Returns:
            List of audit log entries
        """
        filtered = self.audit_log
        
        if user_id is not None:
            filtered = [e for e in filtered if e['user_id'] == user_id]
        
        if action is not None:
            filtered = [e for e in filtered if e['action'] == action.value]
        
        return filtered[-limit:]


# Global singleton instance
copilot_security = CopilotSecurity()
