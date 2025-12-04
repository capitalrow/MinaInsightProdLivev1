#!/usr/bin/env python3
"""
Seed Stripe Products Script for Mina Subscription Tiers

Creates the Pro and Business subscription products in Stripe.
Free tier doesn't need a Stripe product (no payment required).

Usage:
    python scripts/seed_stripe_products.py

Products created:
    - Pro: £15/month - Unlimited final-only transcription
    - Business: £25/month - Live transcription updates + all features
"""
import os
import sys
import stripe
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.replit_connectors import get_stripe_credentials_sync

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PRODUCTS = {
    'pro': {
        'name': 'Mina Pro',
        'description': 'Unlimited final-only transcription with AI insights',
        'metadata': {
            'tier': 'pro',
            'live_transcription': 'false',
            'hours_per_month': 'unlimited',
        },
        'price': {
            'unit_amount': 1500,
            'currency': 'gbp',
            'recurring': {'interval': 'month'},
        }
    },
    'business': {
        'name': 'Mina Business',
        'description': 'Live transcription updates with full collaboration features',
        'metadata': {
            'tier': 'business',
            'live_transcription': 'true',
            'hours_per_month': 'unlimited',
        },
        'price': {
            'unit_amount': 2500,
            'currency': 'gbp',
            'recurring': {'interval': 'month'},
        }
    }
}


def init_stripe():
    """Initialize Stripe with credentials from Replit connector."""
    try:
        credentials = get_stripe_credentials_sync()
        stripe.api_key = credentials["secret_key"]
        stripe.api_version = "2024-11-20.acacia"
        logger.info(f"Stripe initialized ({credentials['environment']})")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize Stripe: {e}")
        return False


def find_existing_product(tier: str):
    """Check if a product with this tier already exists."""
    try:
        products = stripe.Product.search(
            query=f"metadata['tier']:'{tier}'",
            limit=1
        )
        if products.data:
            return products.data[0]
    except Exception as e:
        logger.warning(f"Product search failed: {e}")
    return None


def find_active_price(product_id: str):
    """Find active price for a product."""
    try:
        prices = stripe.Price.list(
            product=product_id,
            active=True,
            limit=1
        )
        if prices.data:
            return prices.data[0]
    except Exception as e:
        logger.warning(f"Price lookup failed: {e}")
    return None


def create_product(tier: str, config: dict):
    """Create a Stripe product with price."""
    existing = find_existing_product(tier)
    
    if existing:
        logger.info(f"Product '{config['name']}' already exists: {existing.id}")
        price = find_active_price(existing.id)
        if price:
            logger.info(f"  Active price: {price.id} ({price.unit_amount/100:.2f} {price.currency.upper()}/month)")
            return existing, price
        else:
            logger.info(f"  Creating new price...")
            price = stripe.Price.create(
                product=existing.id,
                **config['price']
            )
            logger.info(f"  Created price: {price.id}")
            return existing, price
    
    logger.info(f"Creating product: {config['name']}")
    product = stripe.Product.create(
        name=config['name'],
        description=config['description'],
        metadata=config['metadata']
    )
    logger.info(f"  Created product: {product.id}")
    
    price = stripe.Price.create(
        product=product.id,
        **config['price']
    )
    logger.info(f"  Created price: {price.id} ({config['price']['unit_amount']/100:.2f} GBP/month)")
    
    return product, price


def main():
    """Seed all Stripe products."""
    print("\n" + "="*60)
    print("  Mina Stripe Product Seeder")
    print("="*60 + "\n")
    
    if not init_stripe():
        print("Failed to initialize Stripe. Check your credentials.")
        sys.exit(1)
    
    results = {}
    
    for tier, config in PRODUCTS.items():
        try:
            product, price = create_product(tier, config)
            results[tier] = {
                'product_id': product.id,
                'price_id': price.id,
                'name': config['name'],
                'amount': config['price']['unit_amount'] / 100
            }
        except Exception as e:
            logger.error(f"Failed to create {tier} product: {e}")
            results[tier] = {'error': str(e)}
    
    print("\n" + "="*60)
    print("  Summary")
    print("="*60)
    
    for tier, result in results.items():
        if 'error' in result:
            print(f"\n  {tier.upper()}: FAILED - {result['error']}")
        else:
            print(f"\n  {tier.upper()}:")
            print(f"    Product ID: {result['product_id']}")
            print(f"    Price ID:   {result['price_id']}")
            print(f"    Amount:     £{result['amount']:.2f}/month")
    
    print("\n" + "="*60)
    print("  Next Steps:")
    print("  1. Copy price IDs to your pricing page")
    print("  2. Test checkout flow with test cards")
    print("  3. Configure webhook endpoint in Stripe Dashboard")
    print("="*60 + "\n")
    
    return results


if __name__ == '__main__':
    main()
