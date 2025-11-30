(function() {
    'use strict';

    const COOKIE_CONSENT_KEY = 'mina_cookie_consent';
    const COOKIE_CONSENT_VERSION = '1';

    function getCookieConsent() {
        try {
            const stored = localStorage.getItem(COOKIE_CONSENT_KEY);
            if (stored) {
                const data = JSON.parse(stored);
                if (data.version === COOKIE_CONSENT_VERSION) {
                    return data;
                }
            }
        } catch (e) {
            console.error('Error reading cookie consent:', e);
        }
        return null;
    }

    function saveCookieConsent(consent) {
        const data = {
            version: COOKIE_CONSENT_VERSION,
            timestamp: new Date().toISOString(),
            essential: true,
            analytics: consent.analytics || false,
            marketing: consent.marketing || false
        };
        
        try {
            localStorage.setItem(COOKIE_CONSENT_KEY, JSON.stringify(data));
            
            fetch('/api/cookie-consent', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || ''
                },
                body: JSON.stringify(data)
            }).catch(function(err) {
                console.warn('Failed to sync cookie consent to server:', err);
            });
        } catch (e) {
            console.error('Error saving cookie consent:', e);
        }
        
        return data;
    }

    function showBanner() {
        var banner = document.getElementById('cookie-consent-banner');
        if (banner) {
            requestAnimationFrame(function() {
                banner.classList.add('visible');
            });
        }
    }

    function hideBanner() {
        var banner = document.getElementById('cookie-consent-banner');
        var settingsLink = document.getElementById('cookie-settings-link');
        if (banner) {
            banner.classList.remove('visible');
        }
        if (settingsLink) {
            setTimeout(function() {
                settingsLink.classList.add('visible');
            }, 300);
        }
    }

    function acceptCookies(type) {
        var consent = { essential: true };
        
        if (type === 'all') {
            consent.analytics = true;
            consent.marketing = true;
        } else if (type === 'selected') {
            var analyticsCheckbox = document.getElementById('consent-analytics');
            var marketingCheckbox = document.getElementById('consent-marketing');
            consent.analytics = analyticsCheckbox ? analyticsCheckbox.checked : false;
            consent.marketing = marketingCheckbox ? marketingCheckbox.checked : false;
        }
        
        saveCookieConsent(consent);
        hideBanner();
        
        if (consent.analytics) {
            enableAnalytics();
        }
        if (consent.marketing) {
            enableMarketing();
        }
    }

    function enableAnalytics() {
        console.log('[Cookie Consent] Analytics enabled');
    }

    function enableMarketing() {
        console.log('[Cookie Consent] Marketing enabled');
    }

    function openCookieSettings() {
        var consent = getCookieConsent();
        
        if (consent) {
            var analyticsCheckbox = document.getElementById('consent-analytics');
            var marketingCheckbox = document.getElementById('consent-marketing');
            if (analyticsCheckbox) analyticsCheckbox.checked = consent.analytics;
            if (marketingCheckbox) marketingCheckbox.checked = consent.marketing;
        }
        
        var settingsLink = document.getElementById('cookie-settings-link');
        if (settingsLink) {
            settingsLink.classList.remove('visible');
        }
        showBanner();
    }

    function init() {
        var existingConsent = getCookieConsent();
        
        if (existingConsent) {
            var settingsLink = document.getElementById('cookie-settings-link');
            if (settingsLink) {
                settingsLink.classList.add('visible');
            }
            
            if (existingConsent.analytics) {
                enableAnalytics();
            }
            if (existingConsent.marketing) {
                enableMarketing();
            }
        } else {
            setTimeout(showBanner, 1000);
        }
        
        document.addEventListener('click', function(e) {
            var target = e.target.closest('[data-cookie-action]');
            if (target) {
                var action = target.getAttribute('data-cookie-action');
                if (action === 'essential') {
                    acceptCookies('essential');
                } else if (action === 'selected') {
                    acceptCookies('selected');
                } else if (action === 'all') {
                    acceptCookies('all');
                } else if (action === 'settings') {
                    openCookieSettings();
                }
            }
        });
    }

    window.MinaCookieConsent = {
        init: init,
        getConsent: getCookieConsent,
        openSettings: openCookieSettings
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
