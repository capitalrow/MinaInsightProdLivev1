/**
 * CROWN⁴.6 AI Semantic Search
 * Toggle and handle semantic search mode for tasks
 */

(function() {
    'use strict';
    
    let semanticSearchEnabled = false;
    
    // Initialize on DOM ready
    document.addEventListener('DOMContentLoaded', () => {
        const toggle = document.getElementById('semantic-search-toggle');
        if (!toggle) {
            console.warn('[SemanticSearch] Toggle button not found');
            return;
        }
        
        // Initialize state from URL
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get('semantic') === 'true') {
            semanticSearchEnabled = true;
            toggle.classList.add('active');
        }
        
        // Toggle semantic search mode
        toggle.addEventListener('click', () => {
            semanticSearchEnabled = !semanticSearchEnabled;
            toggle.classList.toggle('active', semanticSearchEnabled);
            
            // Log mode change
            console.log(`[SemanticSearch] ${semanticSearchEnabled ? 'Enabled' : 'Disabled'} AI semantic search`);
            
            // If there's an active search, retrigger it with the new mode
            const searchInput = document.getElementById('task-search-input');
            if (searchInput && searchInput.value.trim()) {
                // Trigger a search event to reload results
                triggerSearch(searchInput.value);
            }
        });
        
        // Listen to search input changes (Enter key or search button)
        const searchInput = document.getElementById('task-search-input');
        if (searchInput) {
            searchInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    triggerSearch(searchInput.value);
                }
            });
        }
        
        console.log('[SemanticSearch] Initialized');
    });
    
    /**
     * Check if semantic search is enabled
     */
    function isSemanticSearchEnabled() {
        return semanticSearchEnabled;
    }
    
    /**
     * Trigger search with current mode
     */
    function triggerSearch(query) {
        // Build URL with semantic parameter
        const url = new URL(window.location.href);
        const searchParams = new URLSearchParams(url.search);
        
        if (query && query.trim()) {
            searchParams.set('search', query.trim());
            if (semanticSearchEnabled) {
                searchParams.set('semantic', 'true');
            } else {
                searchParams.delete('semantic');
            }
        } else {
            searchParams.delete('search');
            searchParams.delete('semantic');
        }
        
        // Reload page with new search parameters
        window.location.href = url.pathname + '?' + searchParams.toString();
    }
    
    // Expose to global scope for tasks app integration
    window.semanticSearch = {
        isEnabled: isSemanticSearchEnabled,
        trigger: triggerSearch
    };
})();
