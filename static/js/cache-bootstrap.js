/**
 * CROWN⁴.6 Unified Cache Bootstrap
 * Centralized initialization for cacheManager across all pages
 * Exposes window.cacheManagerReady promise for dependent modules
 */

(function() {
    'use strict';
    
    console.log('[CacheBootstrap] Starting unified cache initialization...');
    
    // Create promise that resolves when cacheManager is ready
    window.cacheManagerReady = new Promise(async (resolve, reject) => {
        try {
            // Wait for cacheManager to be available
            if (!window.cacheManager) {
                console.error('[CacheBootstrap] window.cacheManager not found!');
                reject(new Error('cacheManager not loaded'));
                return;
            }
            
            // Initialize cacheManager (idempotent - safe to call multiple times)
            console.log('[CacheBootstrap] Initializing cacheManager...');
            await window.cacheManager.init();
            
            console.log('✅ [CacheBootstrap] cacheManager initialized successfully');
            
            // Fire event for legacy event listeners
            window.dispatchEvent(new CustomEvent('cacheManagerReady', { 
                detail: { cacheManager: window.cacheManager } 
            }));
            
            // Resolve promise for modern await-based code
            resolve(window.cacheManager);
            
        } catch (error) {
            console.error('❌ [CacheBootstrap] Failed to initialize cacheManager:', error);
            reject(error);
        }
    });
    
    console.log('[CacheBootstrap] Promise created - dependent modules can await window.cacheManagerReady');
})();
