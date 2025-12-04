from flask import Blueprint, render_template, abort
from flask_login import login_required, current_user
from jinja2 import TemplateNotFound
from models.core_models import Customer, Subscription
from models import db

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

@ui_bp.route('/billing')
@login_required
def billing():
    try:
        pricing_plans = [
            {
                'id': 'starter',
                'name': 'Starter',
                'price': 0,
                'billing_period': 'forever',
                'price_id': None,
                'features': [
                    'Up to 5 meetings per month',
                    'Real-time transcription',
                    'Basic speaker identification',
                    'Download transcripts',
                    '7 days of history'
                ],
                'recommended': False
            },
            {
                'id': 'pro',
                'name': 'Pro',
                'price': 12,
                'currency': 'GBP',
                'billing_period': 'month',
                'price_id': 'price_1SP46vLIJSqSqVnkHDu6LfRt',
                'features': [
                    'Unlimited meetings',
                    'Advanced AI insights',
                    'Multi-speaker diarization',
                    'Task extraction & tracking',
                    'Calendar integration',
                    'Unlimited storage',
                    'Priority support'
                ],
                'recommended': True
            },
            {
                'id': 'team',
                'name': 'Team',
                'price': 30,
                'currency': 'GBP',
                'billing_period': 'month',
                'price_id': 'price_1SP4ArLIJSqSqVnksFm2zFmp',
                'features': [
                    'Everything in Pro',
                    'Team workspaces',
                    'Shared meeting library',
                    'Custom integrations',
                    'Advanced analytics',
                    'SSO & SAML',
                    'Dedicated support'
                ],
                'recommended': False
            }
        ]
        
        subscription_status = None
        customer = db.session.query(Customer).filter_by(user_id=str(current_user.id)).first()
        
        if customer:
            active_subscription = db.session.query(Subscription).filter_by(
                customer_id=customer.id,
                status='active'
            ).first()
            
            if active_subscription:
                subscription_status = {
                    'status': active_subscription.status,
                    'current_period_end': active_subscription.current_period_end,
                    'cancel_at_period_end': active_subscription.cancel_at_period_end
                }
        
        return render_template(
            'billing.html',
            title='Billing',
            pricing_plans=pricing_plans,
            subscription_status=subscription_status,
            user_id=str(current_user.id)
        )
    except TemplateNotFound:
        abort(404)