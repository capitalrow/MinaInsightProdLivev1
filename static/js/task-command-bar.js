/**
 * PHASE 2: Command Bar Consolidation
 * Handles collapsible search and filter sync between inline/legacy elements
 * CROWN⁴.18: URL-based filter state for flicker-free SSR
 */

(function() {
    'use strict';
    
    class TaskCommandBar {
        constructor() {
            this.searchToggleBtn = document.getElementById('search-toggle-btn');
            this.searchInputContainer = document.querySelector('.search-input-container');
            this.searchInput = document.getElementById('task-search-input');
            this.inlineFilters = document.querySelector('.task-filters-inline');
            this.legacyFilters = document.querySelector('.task-filters');
            
            this.isSearchExpanded = false;
            
            // CROWN⁴.18: Track current filter from URL
            this.currentFilter = this.getFilterFromURL();
            
            this.init();
        }
        
        /**
         * CROWN⁴.18: Read filter from URL query parameter
         * @returns {string} Current filter (default: 'active')
         */
        getFilterFromURL() {
            const params = new URLSearchParams(window.location.search);
            const filter = params.get('filter');
            const validFilters = ['active', 'completed', 'archived', 'all'];
            return validFilters.includes(filter) ? filter : 'active';
        }
        
        /**
         * CROWN⁴.18: Update URL with new filter using pushState (no page reload)
         * @param {string} filter - New filter value
         */
        updateURLFilter(filter) {
            const url = new URL(window.location.href);
            if (filter === 'active') {
                // Active is default, remove param for cleaner URL
                url.searchParams.delete('filter');
            } else {
                url.searchParams.set('filter', filter);
            }
            window.history.pushState({ filter }, '', url.toString());
            this.currentFilter = filter;
            console.log(`[TaskCommandBar] URL updated to: ${url.pathname}${url.search}`);
        }
        
        init() {
            this.initSearchToggle();
            this.initFilterSync();
            this.initKeyboardShortcuts();
            this.initPopStateHandler();
            console.log(`[TaskCommandBar] Phase 2 command bar initialized (filter: ${this.currentFilter})`);
        }
        
        /**
         * CROWN⁴.18: Handle browser back/forward navigation
         */
        initPopStateHandler() {
            window.addEventListener('popstate', (e) => {
                const filter = e.state?.filter || this.getFilterFromURL();
                this.applyFilter(filter, false); // Don't update URL again
            });
        }
        
        /**
         * CROWN⁴.18: Apply filter and optionally update URL
         * @param {string} filter - Filter to apply
         * @param {boolean} updateURL - Whether to update URL (default: true)
         */
        applyFilter(filter, updateURL = true) {
            // Update tab UI
            this.inlineFilters?.querySelectorAll('.filter-tab').forEach(tab => {
                tab.classList.toggle('active', tab.dataset.filter === filter);
            });
            this.legacyFilters?.querySelectorAll('.filter-tab').forEach(tab => {
                tab.classList.toggle('active', tab.dataset.filter === filter);
            });
            
            // Update URL if needed
            if (updateURL) {
                this.updateURLFilter(filter);
            }
            
            // Dispatch filter change event for other modules
            document.dispatchEvent(new CustomEvent('filterChanged', {
                detail: { filter: filter, fromURL: !updateURL }
            }));
            
            this.currentFilter = filter;
        }
        
        initSearchToggle() {
            if (!this.searchToggleBtn || !this.searchInputContainer) {
                console.log('[TaskCommandBar] Search toggle elements not found');
                return;
            }
            
            this.searchToggleBtn.addEventListener('click', () => this.toggleSearch());
            
            if (this.searchInput) {
                this.searchInput.addEventListener('keydown', (e) => {
                    if (e.key === 'Escape') {
                        this.collapseSearch();
                    }
                });
                
                this.searchInput.addEventListener('blur', (e) => {
                    if (!this.searchInput.value) {
                        setTimeout(() => this.collapseSearch(), 150);
                    }
                });
            }
        }
        
        toggleSearch() {
            if (this.isSearchExpanded) {
                this.collapseSearch();
            } else {
                this.expandSearch();
            }
        }
        
        expandSearch() {
            if (!this.searchInputContainer) return;
            
            this.searchInputContainer.classList.remove('collapsed');
            this.searchInputContainer.classList.add('expanded');
            this.isSearchExpanded = true;
            this.searchToggleBtn?.classList.add('active');
            
            setTimeout(() => {
                this.searchInput?.focus();
            }, 200);
        }
        
        collapseSearch() {
            if (!this.searchInputContainer) return;
            
            if (this.searchInput?.value) return;
            
            this.searchInputContainer.classList.remove('expanded');
            this.searchInputContainer.classList.add('collapsed');
            this.isSearchExpanded = false;
            this.searchToggleBtn?.classList.remove('active');
        }
        
        initFilterSync() {
            if (!this.inlineFilters) {
                console.log('[TaskCommandBar] Inline filters not found');
                return;
            }
            
            // CROWN⁴.18: Filter tab clicks now use URL-based state
            this.inlineFilters.addEventListener('click', (e) => {
                const filterTab = e.target.closest('.filter-tab');
                if (!filterTab) return;
                
                const filter = filterTab.dataset.filter;
                if (!filter) return;
                
                // Use applyFilter which updates URL and dispatches event
                this.applyFilter(filter, true);
                
                console.log(`[TaskCommandBar] Filter changed to: ${filter}`);
            });
            
            document.addEventListener('task:counters-updated', (e) => {
                if (!e.detail) return;
                const { all, active, archived } = e.detail;
                
                this.updateCounter('all', all);
                this.updateCounter('active', active);
                this.updateCounter('archived', archived);
            });
        }
        
        updateCounter(filterType, count) {
            const inlineCounter = this.inlineFilters?.querySelector(`[data-counter="${filterType}"]`);
            if (inlineCounter) {
                inlineCounter.textContent = count;
            }
            
            const legacyCounter = this.legacyFilters?.querySelector(`[data-counter="${filterType}"]`);
            if (legacyCounter) {
                legacyCounter.textContent = count;
            }
        }
        
        initKeyboardShortcuts() {
            document.addEventListener('keydown', (e) => {
                if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
                    return;
                }
                
                if (e.key === '/' && !e.ctrlKey && !e.metaKey) {
                    e.preventDefault();
                    this.expandSearch();
                }
            });
        }
    }
    
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => new TaskCommandBar());
    } else {
        new TaskCommandBar();
    }
    
    window.TaskCommandBar = TaskCommandBar;
})();
