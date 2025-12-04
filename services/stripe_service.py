from __future__ import annotations
import os
import stripe
import logging
from stripe import InvalidRequestError
from typing import Optional
from models.core_models import Customer, Subscription, SubscriptionTier
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
        sub_id = data.get("subscription")
        if sub_id:
            stripe_sub = stripe.Subscription.retrieve(sub_id)
            price_id = None
            product_id = None
            if stripe_sub.get("items", {}).get("data"):
                item = stripe_sub["items"]["data"][0]
                price_id = item.get("price", {}).get("id")
                product_id = item.get("price", {}).get("product")
            self._upsert_subscription(cust, sub_id, "active", price_id, product_id)

    def handle_subscription_change(self, data: dict):
        customer_id = data.get("customer")
        status = data.get("status")
        sub_id = data.get("id")
        cust = db.session.query(Customer).filter_by(stripe_customer_id=customer_id).first()
        if not cust or not sub_id: return
        
        price_id = None
        product_id = None
        items = data.get("items", {}).get("data", [])
        if items:
            price_id = items[0].get("price", {}).get("id")
            product_id = items[0].get("price", {}).get("product")
        
        self._upsert_subscription(cust, sub_id, status or "active", price_id, product_id)

    def _upsert_subscription(self, cust: Customer, sub_id: str, status: str,
                              price_id: Optional[str] = None, product_id: Optional[str] = None):
        tier = self._determine_tier(price_id, product_id)
        
        s = db.session.query(Subscription).filter_by(stripe_subscription_id=sub_id).first()
        if not s:
            s = Subscription(
                customer_id=cust.id,
                stripe_subscription_id=sub_id,
                stripe_price_id=price_id,
                stripe_product_id=product_id,
                tier=tier,
                status=status
            )
            db.session.add(s)
        else:
            s.status = status
            s.tier = tier
            if price_id:
                s.stripe_price_id = price_id
            if product_id:
                s.stripe_product_id = product_id
        
        db.session.commit()
        logger.info(f"Subscription {sub_id} updated: tier={tier}, status={status}")
    
    def _determine_tier(self, price_id: Optional[str], product_id: Optional[str]) -> str:
        """Determine subscription tier from Stripe product/price."""
        if not price_id and not product_id:
            return SubscriptionTier.FREE
        
        try:
            if product_id:
                product = stripe.Product.retrieve(product_id)
                if hasattr(product, 'metadata') and product.metadata:
                    tier = product.metadata.get('tier')
                    if tier in [SubscriptionTier.PRO, SubscriptionTier.BUSINESS]:
                        return tier
                
                name_lower = (product.name or '').lower()
                if 'business' in name_lower:
                    return SubscriptionTier.BUSINESS
                elif 'pro' in name_lower:
                    return SubscriptionTier.PRO
            
            if price_id:
                price = stripe.Price.retrieve(price_id)
                amount = price.unit_amount or 0
                if amount >= 2500:
                    return SubscriptionTier.BUSINESS
                elif amount >= 1500:
                    return SubscriptionTier.PRO
                    
        except Exception as e:
            logger.error(f"Error determining tier: {e}")
        
        return SubscriptionTier.PRO
    
    def get_products_with_prices(self) -> list:
        """Get all active products with their prices for the pricing page."""
        try:
            products = stripe.Product.list(active=True, limit=10)
            result = []
            
            for product in products.data:
                tier = product.metadata.get('tier') if product.metadata else None
                if tier not in [SubscriptionTier.PRO, SubscriptionTier.BUSINESS]:
                    continue
                
                prices = stripe.Price.list(product=product.id, active=True, limit=5)
                
                for price in prices.data:
                    result.append({
                        'product_id': product.id,
                        'product_name': product.name,
                        'description': product.description,
                        'tier': tier,
                        'price_id': price.id,
                        'amount': price.unit_amount,
                        'currency': price.currency,
                        'interval': price.recurring.interval if price.recurring else 'one_time',
                    })
            
            return sorted(result, key=lambda x: x['amount'])
        except Exception as e:
            logger.error(f"Error fetching products: {e}")
            return []

stripe_svc = StripeService()