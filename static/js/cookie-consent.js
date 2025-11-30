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
            console.error('[Cookie Consent] Error reading consent:', e);
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
            
            fetch('/settings/api/cookie-consent', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || ''
                },
                body: JSON.stringify(data)
            }).catch(function(err) {
                console.warn('[Cookie Consent] Failed to sync to server:', err);
            });
        } catch (e) {
            console.error('[Cookie Consent] Error saving consent:', e);
        }
        
        return data;
    }

    function setBannerState(showBanner) {
        var banner = document.getElementById('cookie-consent-banner');
        var settingsLink = document.getElementById('cookie-settings-link');
        
        if (showBanner) {
            if (settingsLink) {
                settingsLink.classList.remove('visible');
                settingsLink.style.display = 'none';
            }
            if (banner) {
                banner.style.display = 'block';
                requestAnimationFrame(function() {
                    requestAnimationFrame(function() {
                        banner.classList.add('visible');
                    });
                });
            }
        } else {
            if (banner) {
                banner.classList.remove('visible');
                setTimeout(function() {
                    banner.style.display = 'none';
                }, 300);
            }
            if (settingsLink) {
                setTimeout(function() {
                    settingsLink.style.display = 'flex';
                    settingsLink.classList.add('visible');
                }, 350);
            }
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
        setBannerState(false);
        
        if (consent.analytics) {
            enableAnalytics();
        }
        if (consent.marketing) {
            enableMarketing();
        }
        
        console.log('[Cookie Consent] Preferences saved:', consent);
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
        
        setBannerState(true);
    }

    function init() {
        var banner = document.getElementById('cookie-consent-banner');
        var settingsLink = document.getElementById('cookie-settings-link');
        
        if (banner) banner.style.display = 'none';
        if (settingsLink) settingsLink.style.display = 'none';
        
        var existingConsent = getCookieConsent();
        
        if (existingConsent) {
            console.log('[Cookie Consent] Existing consent found:', existingConsent);
            
            if (settingsLink) {
                settingsLink.style.display = 'flex';
                settingsLink.classList.add('visible');
            }
            
            if (existingConsent.analytics) {
                enableAnalytics();
            }
            if (existingConsent.marketing) {
                enableMarketing();
            }
        } else {
            console.log('[Cookie Consent] No consent found, showing banner');
            setTimeout(function() {
                setBannerState(true);
            }, 800);
        }
        
        document.addEventListener('click', function(e) {
            var target = e.target.closest('[data-cookie-action]');
            if (target) {
                e.preventDefault();
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
        openSettings: openCookieSettings,
        clearConsent: function() {
            localStorage.removeItem(COOKIE_CONSENT_KEY);
            console.log('[Cookie Consent] Consent cleared');
        }
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
