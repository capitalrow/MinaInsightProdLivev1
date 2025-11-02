console.log('🚀 Billing.js loaded!');

document.addEventListener('DOMContentLoaded', function() {
    console.log('🎬 DOM Content Loaded - Billing page ready');
    
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
