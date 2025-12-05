import logging
from flask import Blueprint, render_template, abort
from flask_login import login_required, current_user
from jinja2 import TemplateNotFound
from models.core_models import Customer, Subscription, SubscriptionTier
from models import db

logger = logging.getLogger(__name__)

ui_bp = Blueprint('ui', __name__, url_prefix='/ui', template_folder='../templates')

@ui_bp.route('/dashboard')
def dashboard():
    try:
        return render_template('base.html', title='Dashboard')
    except TemplateNotFound:
        abort(404)

@ui_bp.route('/admin/flags')
def admin_flags():
    try:
        return render_template('admin_flags.html', title='Feature Flags')
    except TemplateNotFound:
        abort(404)


def _get_pricing_plans_with_stripe():
    """Get pricing plans with Stripe price IDs from the database or API."""
    from services.stripe_service import stripe_svc
    
    stripe_products = []
    try:
        stripe_products = stripe_svc.get_products_with_prices()
    except Exception as e:
        logger.warning(f"Could not fetch Stripe products: {e}")
    
    stripe_prices = {p['tier']: p for p in stripe_products}
    
    pricing_plans = [
        {
            'id': 'free',
            'name': 'Free',
            'price': 0,
            'currency': 'GBP',
            'billing_period': 'forever',
            'price_id': None,
            'tier': 'free',
            'features': SubscriptionTier.TIERS['free']['features'],
            'recommended': False
        },
        {
            'id': 'pro',
            'name': 'Pro',
            'price': 15,
            'currency': 'GBP',
            'billing_period': 'month',
            'price_id': stripe_prices.get('pro', {}).get('price_id'),
            'tier': 'pro',
            'features': SubscriptionTier.TIERS['pro']['features'],
            'recommended': True
        },
        {
            'id': 'business',
            'name': 'Business',
            'price': 25,
            'currency': 'GBP',
            'billing_period': 'month',
            'price_id': stripe_prices.get('business', {}).get('price_id'),
            'tier': 'business',
            'features': SubscriptionTier.TIERS['business']['features'],
            'recommended': False
        }
    ]
    
    for plan in pricing_plans:
        stripe_data = stripe_prices.get(plan['tier'])
        if stripe_data:
            plan['price'] = stripe_data['amount'] / 100
            plan['currency'] = stripe_data['currency'].upper()
    
    return pricing_plans


@ui_bp.route('/billing')
@login_required
def billing():
    try:
        pricing_plans = _get_pricing_plans_with_stripe()
        
        subscription_status = None
        current_tier = 'free'
        customer = db.session.query(Customer).filter_by(user_id=str(current_user.id)).first()
        
        if customer:
            active_subscription = db.session.query(Subscription).filter(
                Subscription.customer_id == customer.id,
                Subscription.status.in_(['active', 'trialing'])
            ).first()
            
            if active_subscription:
                current_tier = active_subscription.tier or 'free'
                subscription_status = {
                    'status': active_subscription.status,
                    'tier': current_tier,
                    'tier_name': SubscriptionTier.TIERS.get(current_tier, {}).get('name', 'Free'),
                    'has_live_transcription': active_subscription.has_live_transcription,
                    'current_period_end': active_subscription.current_period_end,
                    'cancel_at_period_end': active_subscription.cancel_at_period_end
                }
        
        for plan in pricing_plans:
            if plan['tier'] == current_tier:
                plan['is_current'] = True
                plan['price_id'] = None
            else:
                plan['is_current'] = False
        
        return render_template(
            'billing.html',
            title='Billing',
            pricing_plans=pricing_plans,
            subscription_status=subscription_status,
            current_tier=current_tier,
            user_id=str(current_user.id)
        )
    except TemplateNotFound:
        abort(404)


@ui_bp.route('/usage-monitoring')
@login_required
def usage_monitoring():
    """Usage monitoring dashboard for transcription costs and API usage."""
    try:
        return render_template(
            'dashboard/usage_monitoring.html',
            title='Usage Monitoring'
        )
    except TemplateNotFound:
        abort(404)


@ui_bp.route('/admin/analytics')
@login_required
def admin_analytics():
    """Admin analytics dashboard for system-wide monitoring."""
    if not current_user.is_admin:
        logger.warning(f"Non-admin user {current_user.id} attempted to access admin analytics")
        abort(403)
    
    from services.usage_tracking_service import get_admin_usage_stats, get_per_user_stats
    from services.whisper_api import get_fallback_stats
    from services.voice_activity_detector import get_vad_stats
    from services.audio_payload_optimizer import get_optimization_stats
    
    try:
        admin_stats = get_admin_usage_stats()
        fallback_stats = get_fallback_stats()
        vad_stats = get_vad_stats()
        optimization_stats = get_optimization_stats()
        per_user_stats = get_per_user_stats()
        
        return render_template(
            'admin/analytics.html',
            title='Admin Analytics',
            admin_stats=admin_stats,
            fallback_stats=fallback_stats,
            vad_stats=vad_stats,
            optimization_stats=optimization_stats,
            per_user_stats=per_user_stats
        )
    except TemplateNotFound:
        abort(404)
    except Exception as e:
        logger.error(f"Error loading admin analytics: {e}")
        return render_template(
            'admin/analytics.html',
            title='Admin Analytics',
            admin_stats={},
            fallback_stats={},
            vad_stats={},
            optimization_stats={},
            per_user_stats=[]
        )