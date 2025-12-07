/**
 * PHASE 2: Command Bar Consolidation
 * Handles collapsible search and filter sync between inline/legacy elements
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
            
            this.init();
        }
        
        init() {
            this.initSearchToggle();
            this.initFilterSync();
            this.initKeyboardShortcuts();
            console.log('[TaskCommandBar] Phase 2 command bar initialized');
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
            
            this.inlineFilters.addEventListener('click', (e) => {
                const filterTab = e.target.closest('.filter-tab');
                if (!filterTab) return;
                
                const filter = filterTab.dataset.filter;
                if (!filter) return;
                
                this.inlineFilters.querySelectorAll('.filter-tab').forEach(tab => {
                    tab.classList.remove('active');
                });
                filterTab.classList.add('active');
                
                if (this.legacyFilters) {
                    this.legacyFilters.querySelectorAll('.filter-tab').forEach(tab => {
                        tab.classList.toggle('active', tab.dataset.filter === filter);
                    });
                }
                
                document.dispatchEvent(new CustomEvent('filterChanged', {
                    detail: { filter: filter }
                }));
                
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
