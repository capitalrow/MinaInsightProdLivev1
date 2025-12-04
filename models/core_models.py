from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB as PostgresJSONB
from sqlalchemy import TypeDecorator
from models import db


class JSONBCompatible(TypeDecorator):
    """
    A JSONB type that falls back to JSON for non-PostgreSQL databases (e.g., SQLite in tests).
    This allows tests to run with SQLite while production uses PostgreSQL JSONB.
    """
    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(PostgresJSONB())
        return dialect.type_descriptor(JSON())

class FeatureFlag(db.Model):
    __tablename__ = "feature_flags"
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(80), unique=True, nullable=False, index=True)
    enabled = db.Column(db.Boolean, default=False, nullable=False)
    note = db.Column(db.String(255))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    def to_dict(self): return {"key": self.key, "enabled": self.enabled, "note": self.note, "updated_at": self.updated_at.isoformat()}

class FlagAuditLog(db.Model):
    __tablename__ = "flag_audit_logs"
    id = db.Column(db.Integer, primary_key=True)
    flag_key = db.Column(db.String(80), nullable=False, index=True)
    action = db.Column(db.String(16), nullable=False)  # "create", "update", "delete", "toggle"
    user_id = db.Column(db.String(64), nullable=False, index=True)
    old_value = db.Column(JSONBCompatible)  # {"enabled": false, "note": "..."}
    new_value = db.Column(JSONBCompatible)  # {"enabled": true, "note": "..."}
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True, nullable=False)
    
    def to_dict(self):
        return {
            "id": self.id,
            "flag_key": self.flag_key,
            "action": self.action,
            "user_id": self.user_id,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

class Customer(db.Model):
    __tablename__ = "customers"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(64), unique=True, nullable=False, index=True)
    stripe_customer_id = db.Column(db.String(255), unique=True, nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    subscriptions = db.relationship('Subscription', back_populates='customer', cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "stripe_customer_id": self.stripe_customer_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

class Subscription(db.Model):
    __tablename__ = "subscriptions"
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False, index=True)
    stripe_subscription_id = db.Column(db.String(255), unique=True, nullable=False, index=True)
    stripe_price_id = db.Column(db.String(255), nullable=True, index=True)
    stripe_product_id = db.Column(db.String(255), nullable=True, index=True)
    tier = db.Column(db.String(32), nullable=False, default='free')
    status = db.Column(db.String(32), nullable=False)
    current_period_start = db.Column(db.DateTime, nullable=True)
    current_period_end = db.Column(db.DateTime, nullable=True)
    cancel_at_period_end = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    customer = db.relationship('Customer', back_populates='subscriptions')
    
    @property
    def is_active(self) -> bool:
        """Check if subscription is active."""
        return self.status in ('active', 'trialing')
    
    @property
    def has_live_transcription(self) -> bool:
        """Check if subscription tier includes live transcription updates."""
        return self.tier == 'business' and self.is_active
    
    def to_dict(self):
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "stripe_subscription_id": self.stripe_subscription_id,
            "stripe_price_id": self.stripe_price_id,
            "stripe_product_id": self.stripe_product_id,
            "tier": self.tier,
            "status": self.status,
            "is_active": self.is_active,
            "has_live_transcription": self.has_live_transcription,
            "current_period_start": self.current_period_start.isoformat() if self.current_period_start else None,
            "current_period_end": self.current_period_end.isoformat() if self.current_period_end else None,
            "cancel_at_period_end": self.cancel_at_period_end,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class SubscriptionTier:
    """Subscription tier constants and configuration."""
    FREE = 'free'
    PRO = 'pro'
    BUSINESS = 'business'
    
    TIERS = {
        FREE: {
            'name': 'Free',
            'price_monthly': 0,
            'currency': 'gbp',
            'hours_per_month': 5,
            'live_transcription': False,
            'features': [
                'Final-only transcription',
                '5 hours/month',
                'AI-powered summaries',
                'Action item extraction',
            ]
        },
        PRO: {
            'name': 'Pro',
            'price_monthly': 1500,
            'currency': 'gbp',
            'hours_per_month': -1,
            'live_transcription': False,
            'features': [
                'Final-only transcription',
                'Unlimited hours',
                'AI-powered summaries',
                'Action item extraction',
                'Export to PDF/DOCX',
                'Priority processing',
            ]
        },
        BUSINESS: {
            'name': 'Business',
            'price_monthly': 2500,
            'currency': 'gbp',
            'hours_per_month': -1,
            'live_transcription': True,
            'features': [
                'Live transcription updates (15-20s)',
                'Unlimited hours',
                'AI-powered summaries',
                'Action item extraction',
                'Export to PDF/DOCX',
                'Priority processing',
                'Calendar integrations',
                'Team collaboration',
            ]
        }
    }
    
    @classmethod
    def get_tier_config(cls, tier: str) -> dict:
        """Get configuration for a tier."""
        return cls.TIERS.get(tier, cls.TIERS[cls.FREE])
    
    @classmethod
    def has_live_transcription(cls, tier: str) -> bool:
        """Check if tier includes live transcription."""
        return cls.TIERS.get(tier, {}).get('live_transcription', False)
