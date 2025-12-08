from __future__ import annotations
import os
import logging
from flask import Blueprint, request, jsonify, abort, render_template
from flask_login import login_required, current_user
from services.stripe_service import stripe_svc
from models.core_models import Customer, Subscription
from models import db

logger = logging.getLogger(__name__)
billing_bp = Blueprint("billing", __name__, url_prefix="/billing")


@billing_bp.route("/")
@login_required
def billing_page():
    """Render the billing/subscription management page."""
    subscription = None
    customer = None
    
    try:
        customer = Customer.query.filter_by(user_id=current_user.id).first()
        if customer:
            subscription = Subscription.query.filter_by(customer_id=customer.id).first()
    except Exception as e:
        logger.warning(f"Error fetching subscription info: {e}")
    
    return render_template(
        "billing.html",
        subscription=subscription,
        customer=customer,
        user=current_user
    )


@billing_bp.post("/create-checkout-session")
def create_checkout():
    body = request.get_json(force=True)
    user_id = body.get("user_id")
    price_id = body.get("price_id")
    if not user_id or not price_id:
        abort(400, "user_id and price_id required")
    try:
        url = stripe_svc.create_checkout_session(user_id=user_id, price_id=price_id)
        return jsonify({"checkout_url": url})
    except Exception as e:
        logger.error(f"Checkout session creation failed: {e}")
        abort(500, "Failed to create checkout session")

@billing_bp.post("/create-portal-session")
def create_portal():
    body = request.get_json(force=True)
    user_id = body.get("user_id")
    if not user_id:
        abort(400, "user_id required")
    try:
        url = stripe_svc.create_billing_portal(user_id=user_id)
        return jsonify({"portal_url": url})
    except Exception as e:
        logger.error(f"Portal session creation failed: {e}")
        abort(500, "Failed to create portal session")

@billing_bp.post("/webhook")
def webhook():
    sig = request.headers.get("Stripe-Signature")
    payload = request.data
    
    if not os.getenv("STRIPE_WEBHOOK_SECRET"):
        logger.warning("STRIPE_WEBHOOK_SECRET not configured - webhook signature not verified")
    
    event = stripe_svc.verify_webhook(payload, sig)
    if not event:
        logger.error("Webhook signature verification failed")
        abort(400, "Webhook signature verification failed")
    
    event_type = event["type"]
    data = event.get("data", {}).get("object", {})
    
    logger.info(f"Stripe webhook received: {event_type}")
    
    if event_type == "checkout.session.completed":
        stripe_svc.handle_checkout_completed(data)
    elif event_type in ("customer.subscription.created", "customer.subscription.updated", "customer.subscription.deleted"):
        stripe_svc.handle_subscription_change(data)
    elif event_type == "invoice.payment_succeeded":
        logger.info(f"Invoice payment succeeded: {data.get('id')}")
    elif event_type == "invoice.payment_failed":
        logger.warning(f"Invoice payment failed: {data.get('id')}")
    else:
        logger.debug(f"Unhandled webhook event type: {event_type}")
    
    return jsonify({"ok": True})