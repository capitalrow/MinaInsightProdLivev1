"""
Subscription Service for Mina

Handles subscription tier detection, usage tracking, and feature gating.
"""
import logging
from typing import Optional, Dict, Any
from datetime import datetime

from models import db
from models.core_models import Customer, Subscription, SubscriptionTier
from models.user import User

logger = logging.getLogger(__name__)


class SubscriptionService:
    """Service for managing user subscriptions and tier detection."""
    
    TIER_FROM_PRICE_METADATA = True
    
    @staticmethod
    def get_user_tier(user_id: int) -> str:
        """
        Get the subscription tier for a user.
        
        Returns 'free' if no active subscription exists.
        """
        try:
            customer = db.session.query(Customer).filter_by(user_id=str(user_id)).first()
            if not customer:
                return SubscriptionTier.FREE
            
            active_sub = db.session.query(Subscription).filter(
                Subscription.customer_id == customer.id,
                Subscription.status.in_(['active', 'trialing'])
            ).order_by(Subscription.created_at.desc()).first()
            
            if not active_sub:
                return SubscriptionTier.FREE
            
            return active_sub.tier or SubscriptionTier.FREE
            
        except Exception as e:
            logger.error(f"Error getting user tier: {e}")
            return SubscriptionTier.FREE
    
    @staticmethod
    def get_user_subscription(user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get full subscription details for a user.
        
        Returns None if no subscription exists.
        """
        try:
            customer = db.session.query(Customer).filter_by(user_id=str(user_id)).first()
            if not customer:
                return None
            
            active_sub = db.session.query(Subscription).filter(
                Subscription.customer_id == customer.id,
                Subscription.status.in_(['active', 'trialing'])
            ).order_by(Subscription.created_at.desc()).first()
            
            if not active_sub:
                return None
            
            return active_sub.to_dict()
            
        except Exception as e:
            logger.error(f"Error getting user subscription: {e}")
            return None
    
    @staticmethod
    def has_live_transcription(user_id: int) -> bool:
        """
        Check if user has access to live transcription updates.
        
        Only Business tier users have this feature.
        """
        tier = SubscriptionService.get_user_tier(user_id)
        return SubscriptionTier.has_live_transcription(tier)
    
    @staticmethod
    def get_tier_config(user_id: int) -> Dict[str, Any]:
        """Get the full tier configuration for a user."""
        tier = SubscriptionService.get_user_tier(user_id)
        config = SubscriptionTier.get_tier_config(tier)
        return {
            'tier': tier,
            **config
        }
    
    @staticmethod
    def get_hours_remaining(user_id: int) -> Optional[float]:
        """
        Get remaining transcription hours for free tier users.
        
        Returns None for paid tiers (unlimited).
        """
        tier = SubscriptionService.get_user_tier(user_id)
        config = SubscriptionTier.get_tier_config(tier)
        
        if config.get('hours_per_month', -1) == -1:
            return None
        
        return config['hours_per_month']
    
    @staticmethod
    def update_subscription_tier(subscription_id: int, tier: str, 
                                  price_id: Optional[str] = None,
                                  product_id: Optional[str] = None):
        """Update a subscription's tier information."""
        try:
            sub = db.session.query(Subscription).filter_by(id=subscription_id).first()
            if sub:
                sub.tier = tier
                if price_id:
                    sub.stripe_price_id = price_id
                if product_id:
                    sub.stripe_product_id = product_id
                db.session.commit()
                logger.info(f"Updated subscription {subscription_id} to tier: {tier}")
                return True
        except Exception as e:
            logger.error(f"Error updating subscription tier: {e}")
            db.session.rollback()
        return False
    
    @staticmethod
    def determine_tier_from_price(price_id: str) -> str:
        """
        Determine subscription tier from Stripe price ID.
        
        This queries Stripe to get the price's product metadata.
        """
        import stripe
        
        try:
            price = stripe.Price.retrieve(price_id, expand=['product'])
            product = price.product
            
            if isinstance(product, str):
                product = stripe.Product.retrieve(product)
            
            if hasattr(product, 'metadata') and product.metadata:
                tier = product.metadata.get('tier')
                if tier and tier in [SubscriptionTier.PRO, SubscriptionTier.BUSINESS]:
                    return tier
            
            if hasattr(product, 'name') and product.name:
                name_lower = product.name.lower()
                if 'business' in name_lower:
                    return SubscriptionTier.BUSINESS
                elif 'pro' in name_lower:
                    return SubscriptionTier.PRO
            
            amount = price.unit_amount
            if amount and amount >= 2500:
                return SubscriptionTier.BUSINESS
            elif amount and amount >= 1500:
                return SubscriptionTier.PRO
                
        except Exception as e:
            logger.error(f"Error determining tier from price {price_id}: {e}")
        
        return SubscriptionTier.FREE
    
    @staticmethod
    def get_all_tiers() -> Dict[str, Dict[str, Any]]:
        """Get all available subscription tiers with their configurations."""
        return SubscriptionTier.TIERS


subscription_service = SubscriptionService()
