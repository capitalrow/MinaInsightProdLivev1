from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from sqlalchemy.dialects.postgresql import JSONB
from models import db

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
    old_value = db.Column(JSONB)  # {"enabled": false, "note": "..."}
    new_value = db.Column(JSONB)  # {"enabled": true, "note": "..."}
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
    status = db.Column(db.String(32), nullable=False)
    current_period_start = db.Column(db.DateTime, nullable=True)
    current_period_end = db.Column(db.DateTime, nullable=True)
    cancel_at_period_end = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    customer = db.relationship('Customer', back_populates='subscriptions')
    
    def to_dict(self):
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "stripe_subscription_id": self.stripe_subscription_id,
            "status": self.status,
            "current_period_start": self.current_period_start.isoformat() if self.current_period_start else None,
            "current_period_end": self.current_period_end.isoformat() if self.current_period_end else None,
            "cancel_at_period_end": self.cancel_at_period_end,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
