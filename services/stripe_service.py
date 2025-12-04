from __future__ import annotations
import os
import stripe
import logging
from stripe import InvalidRequestError
from typing import Optional
from models.core_models import Customer, Subscription
from models import db

logger = logging.getLogger(__name__)

def _init_stripe_from_connector():
    """Initialize Stripe with credentials from Replit connector or env vars"""
    try:
        from services.replit_connectors import get_stripe_credentials_sync
        credentials = get_stripe_credentials_sync()
        stripe.api_key = credentials["secret_key"]
        stripe.api_version = "2024-11-20.acacia"
        logger.info(f"Stripe initialized from Replit connector ({credentials['environment']})")
    except Exception as e:
        # Fallback to environment variable
        stripe.api_key = os.getenv("STRIPE_SECRET_KEY") or os.getenv("STRIPE_TEST_API_KEY", "")
        stripe.api_version = "2024-11-20.acacia"
        if stripe.api_key:
            logger.info("Stripe initialized from environment variables")
        else:
            logger.warning(f"Stripe not configured: {e}")

_init_stripe_from_connector()

class StripeService:
    def _get_base_url(self) -> str:
        """Get the base URL for the application based on Replit environment."""
        # Check if this is a deployment
        if os.getenv("REPLIT_DEPLOYMENT"):
            # Get deployment domain
            domain = os.getenv("REPLIT_DEV_DOMAIN", "")
            if domain:
                return f"https://{domain}"
        
        # Development: Use the first Replit domain
        domains = os.getenv("REPLIT_DOMAINS", "")
        if domains:
            first_domain = domains.split(",")[0].strip()
            return f"https://{first_domain}"
        
        # Fallback
        return "http://localhost:5000"
    
    def _ensure_customer(self, user_id: str) -> Customer:
        cust = db.session.query(Customer).filter_by(user_id=user_id).first()
        
        # Check if existing customer ID is valid in current mode (test/live)
        if cust and cust.stripe_customer_id:
            try:
                stripe.Customer.retrieve(cust.stripe_customer_id)
                return cust
            except InvalidRequestError:
                # Customer doesn't exist in current mode, need to create new one
                pass
        
        # Create new Stripe customer
        sc = stripe.Customer.create(metadata={"user_id": user_id})
        if not cust:
            cust = Customer(user_id=user_id, stripe_customer_id=sc["id"])
            db.session.add(cust)
        else:
            cust.stripe_customer_id = sc["id"]
        db.session.commit()
        return cust

    def create_checkout_session(self, user_id: str, price_id: str) -> str:
        cust = self._ensure_customer(user_id)
        base_url = self._get_base_url()
        sess = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            customer=cust.stripe_customer_id,
            success_url=f"{base_url}/ui/billing?success=true",
            cancel_url=f"{base_url}/ui/billing?canceled=true",
        )
        return sess["url"]

    def create_billing_portal(self, user_id: str) -> str:
        cust = self._ensure_customer(user_id)
        base_url = self._get_base_url()
        sess = stripe.billing_portal.Session.create(
            customer=cust.stripe_customer_id,
            return_url=f"{base_url}/ui/billing"
        )
        return sess["url"]

    def verify_webhook(self, payload: bytes, sig_header: Optional[str]):
        secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")
        try:
            return stripe.Webhook.construct_event(payload, sig_header, secret)
        except Exception:
            return None

    def handle_checkout_completed(self, data: dict):
        customer_id = data.get("customer")
        cust = db.session.query(Customer).filter_by(stripe_customer_id=customer_id).first()
        if not cust: return
        # link subscription if provided
        sub_id = data.get("subscription")
        if sub_id:
            self._upsert_subscription(cust, sub_id, "active")

    def handle_subscription_change(self, data: dict):
        customer_id = data.get("customer"); status = data.get("status"); sub_id = data.get("id")
        cust = db.session.query(Customer).filter_by(stripe_customer_id=customer_id).first()
        if not cust or not sub_id: return
        self._upsert_subscription(cust, sub_id, status or "active")

    def _upsert_subscription(self, cust: Customer, sub_id: str, status: str):
        s = db.session.query(Subscription).filter_by(stripe_subscription_id=sub_id).first()
        if not s:
            s = Subscription(customer_id=cust.id, stripe_subscription_id=sub_id, status=status)
            db.session.add(s)
        else:
            s.status = status
        db.session.commit()

stripe_svc = StripeService()