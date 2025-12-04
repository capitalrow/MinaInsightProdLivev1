console.log('🚀 Billing.js loaded!');

function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.content : '';
}

function showNotification(message, type = 'info') {
    if (window.showToast) {
        window.showToast(message, type);
        return;
    }
    const colors = { success: '#10b981', error: '#ef4444', info: '#6366f1' };
    const notification = document.createElement('div');
    notification.style.cssText = `
        position: fixed; top: 20px; right: 20px; padding: 16px 24px;
        background: ${colors[type] || colors.info}; color: white;
        border-radius: 12px; box-shadow: 0 10px 40px rgba(0,0,0,0.3);
        z-index: 9999; animation: slideIn 0.3s ease-out;
    `;
    notification.textContent = message;
    document.body.appendChild(notification);
    setTimeout(() => {
        notification.style.opacity = '0';
        notification.style.transform = 'translateX(100%)';
        notification.style.transition = 'all 0.3s ease-out';
        setTimeout(() => notification.remove(), 300);
    }, 4000);
}

function checkUrlParams() {
    const params = new URLSearchParams(window.location.search);
    if (params.get('success') === 'true') {
        showNotification('Subscription activated! Welcome to your new plan.', 'success');
        window.history.replaceState({}, document.title, window.location.pathname);
    }
    if (params.get('canceled') === 'true') {
        showNotification('Checkout was canceled. Try again when ready.', 'info');
        window.history.replaceState({}, document.title, window.location.pathname);
    }
}

document.addEventListener('DOMContentLoaded', function() {
    console.log('🎬 DOM Content Loaded - Billing page ready');
    
    checkUrlParams();
    
    const container = document.querySelector('[data-user-id]');
    const userId = container ? container.getAttribute('data-user-id') : null;
    console.log('👤 User ID from data attribute:', userId);
    
    const checkoutButtons = document.querySelectorAll('.start-checkout-btn');
    console.log('🔘 Found checkout buttons:', checkoutButtons.length);
    
    checkoutButtons.forEach((btn, index) => {
        console.log(`📋 Button ${index + 1}:`, btn.getAttribute('data-plan-name'), btn.getAttribute('data-price-id'));
        
        btn.addEventListener('click', async function(e) {
            e.preventDefault();
            console.log('🖱️ Button clicked!', this.getAttribute('data-plan-name'));
            
            const priceId = this.getAttribute('data-price-id');
            const planName = this.getAttribute('data-plan-name');
            
            this.classList.add('btn-loading');
            this.disabled = true;
            const originalText = this.textContent;
            this.textContent = 'Processing...';
            
            try {
                console.log('📤 Sending checkout request...', { userId, priceId });
                
                const response = await fetch('/billing/create-checkout-session', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken()
                    },
                    body: JSON.stringify({
                        user_id: userId,
                        price_id: priceId
                    })
                });
                
                console.log('📥 Response status:', response.status);
                
                if (!response.ok) {
                    const errorText = await response.text();
                    console.error('❌ Server error:', errorText);
                    throw new Error('Failed to create checkout session');
                }
                
                const data = await response.json();
                console.log('✅ Checkout session created:', data);
                
                if (data.checkout_url) {
                    console.log('🔗 Redirecting to:', data.checkout_url);
                    window.location.href = data.checkout_url;
                } else {
                    throw new Error('No checkout URL returned');
                }
            } catch (error) {
                console.error('💥 Checkout error:', error);
                alert('Failed to start checkout. Please try again.');
                
                this.classList.remove('btn-loading');
                this.disabled = false;
                this.textContent = originalText;
            }
        });
    });
    
    const portalBtn = document.getElementById('openPortalBtn');
    if (portalBtn) {
        console.log('🔧 Found billing portal button');
        portalBtn.addEventListener('click', async function() {
            this.classList.add('btn-loading');
            this.disabled = true;
            const originalText = this.textContent;
            this.textContent = 'Opening...';
            
            try {
                const response = await fetch('/billing/create-portal-session', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken()
                    },
                    body: JSON.stringify({
                        user_id: userId
                    })
                });
                
                if (!response.ok) {
                    throw new Error('Failed to create portal session');
                }
                
                const data = await response.json();
                
                if (data.portal_url) {
                    window.location.href = data.portal_url;
                } else {
                    throw new Error('No portal URL returned');
                }
            } catch (error) {
                console.error('Portal error:', error);
                alert('Failed to open billing portal. Please try again.');
                
                this.classList.remove('btn-loading');
                this.disabled = false;
                this.textContent = originalText;
            }
        });
    }
});
