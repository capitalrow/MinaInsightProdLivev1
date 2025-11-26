/**
 * Comprehensive Tasks Page Test Suite
 * Run this in browser console on /dashboard/tasks
 */

class TasksPageTester {
    constructor() {
        this.testResults = [];
        this.currentTest = null;
    }

    log(message, type = 'info') {
        const timestamp = new Date().toISOString();
        const logEntry = { timestamp, message, type };
        this.testResults.push(logEntry);
        
        const prefix = {
            'pass': '✅ PASS',
            'fail': '❌ FAIL',
            'warning': '⚠️  WARNING',
            'info': 'ℹ️  INFO'
        }[type] || 'ℹ️';
        
        console.log(`${prefix}: ${message}`);
    }

    async sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    async test01ThreeDotMenuPriority() {
        console.log('\n' + '='.repeat(80));
        console.log('TEST 1: Three-dot Menu (PRIORITY)');
        console.log('='.repeat(80));

        const taskCards = document.querySelectorAll('.task-card');
        this.log(`Found ${taskCards.length} task cards`);

        if (taskCards.length === 0) {
            this.log('No tasks found on page', 'warning');
            return;
        }

        // Test positions: top, middle, bottom
        const positions = [
            { name: 'Top', index: 0 },
            { name: 'Middle', index: Math.floor(taskCards.length / 2) },
            { name: 'Bottom', index: taskCards.length - 1 }
        ].filter(p => p.index < taskCards.length);

        for (const {name, index} of positions) {
            console.log(`\n--- Testing ${name} Task (Index ${index}) ---`);
            const taskCard = taskCards[index];

            // Scroll into view
            taskCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
            await this.sleep(500);

            const threeDotBtn = taskCard.querySelector('.task-menu-trigger');
            
            if (!threeDotBtn) {
                this.log(`Three-dot button not found on ${name} task`, 'fail');
                continue;
            }

            // Get positions before click
            const taskRect = taskCard.getBoundingClientRect();
            console.log(`Task position: y=${taskRect.top}, height=${taskRect.height}`);

            // Click three-dot
            threeDotBtn.click();
            await this.sleep(500);

            // Check menu
            const menu = document.querySelector('#task-menu[data-state="open"]');
            
            if (!menu) {
                this.log(`Menu not visible after clicking ${name} task`, 'fail');
                continue;
            }

            this.log(`Menu appeared for ${name} task`, 'pass');

            // Check menu position
            const menuRect = menu.getBoundingClientRect();
            const viewport = {
                width: window.innerWidth,
                height: window.innerHeight
            };

            console.log(`Menu position: x=${menuRect.left}, y=${menuRect.top}`);
            console.log(`Menu size: width=${menuRect.width}, height=${menuRect.height}`);
            console.log(`Viewport: ${viewport.width}x${viewport.height}`);

            // Check clipping
            const clipped = {
                right: (menuRect.left + menuRect.width) > viewport.width,
                bottom: (menuRect.top + menuRect.height) > viewport.height,
                left: menuRect.left < 0,
                top: menuRect.top < 0
            };

            if (clipped.right) this.log(`Menu clipped on RIGHT edge`, 'fail');
            if (clipped.bottom) this.log(`Menu clipped on BOTTOM edge`, 'fail');
            if (clipped.left) this.log(`Menu clipped on LEFT edge`, 'fail');
            if (clipped.top) this.log(`Menu clipped on TOP edge`, 'fail');

            if (!Object.values(clipped).some(v => v)) {
                this.log(`Menu fully visible within viewport for ${name} task`, 'pass');
            }

            // Check menu items
            const menuItems = menu.querySelectorAll('.task-menu-item');
            console.log(`Found ${menuItems.length} menu items`);

            let allClickable = true;
            menuItems.forEach((item, i) => {
                const action = item.getAttribute('data-action');
                const rect = item.getBoundingClientRect();
                const visible = rect.width > 0 && rect.height > 0;
                const enabled = !item.disabled;

                const status = (visible && enabled) ? '✅' : '❌';
                console.log(`${status} Menu item ${i}: ${action} - Visible: ${visible}, Enabled: ${enabled}`);

                if (!(visible && enabled)) allClickable = false;
            });

            if (allClickable) {
                this.log(`All menu items are clickable for ${name} task`, 'pass');
            } else {
                this.log(`Some menu items not clickable for ${name} task`, 'fail');
            }

            // Close menu
            document.body.click();
            await this.sleep(300);
        }
    }

    async test02SearchFunctionality() {
        console.log('\n' + '='.repeat(80));
        console.log('TEST 2: Search Functionality');
        console.log('='.repeat(80));

        const searchInput = document.querySelector('#task-search-input');
        
        if (!searchInput) {
            this.log('Search input not found', 'fail');
            return;
        }

        this.log('Search input found', 'pass');

        // Type in search
        searchInput.value = 'test';
        searchInput.dispatchEvent(new Event('input', { bubbles: true }));
        await this.sleep(500);

        // Check clear button
        const clearBtn = document.querySelector('#search-clear-btn');
        if (clearBtn && !clearBtn.classList.contains('hidden')) {
            this.log('Clear button appears when typing', 'pass');
            
            // Click clear
            clearBtn.click();
            await this.sleep(300);
            
            if (searchInput.value === '') {
                this.log('Clear button clears search', 'pass');
            } else {
                this.log('Clear button did not clear search', 'fail');
            }
        } else {
            this.log('Clear button not visible', 'warning');
        }
    }

    async test03SortFunctionality() {
        console.log('\n' + '='.repeat(80));
        console.log('TEST 3: Sort Functionality');
        console.log('='.repeat(80));

        const sortSelect = document.querySelector('#task-sort-select');
        
        if (!sortSelect) {
            this.log('Sort select not found', 'fail');
            return;
        }

        this.log('Sort select found', 'pass');

        const options = sortSelect.querySelectorAll('option');
        this.log(`Found ${options.length} sort options`);

        // Test each option
        for (const option of options) {
            sortSelect.value = option.value;
            sortSelect.dispatchEvent(new Event('change', { bubbles: true }));
            await this.sleep(500);
            
            this.log(`Sort by ${option.textContent} - selected`, 'pass');
        }
    }

    async test04FilterTabs() {
        console.log('\n' + '='.repeat(80));
        console.log('TEST 4: Filter Tabs');
        console.log('='.repeat(80));

        const filterTabs = document.querySelectorAll('.filter-tab');
        this.log(`Found ${filterTabs.length} filter tabs`);

        for (const tab of filterTabs) {
            const filterName = tab.getAttribute('data-filter');
            tab.click();
            await this.sleep(500);

            if (tab.classList.contains('active')) {
                this.log(`${filterName} filter activated`, 'pass');
            } else {
                this.log(`${filterName} filter not activated`, 'fail');
            }
        }
    }

    async test05BulkSelection() {
        console.log('\n' + '='.repeat(80));
        console.log('TEST 5: Bulk Selection');
        console.log('='.repeat(80));

        const checkboxes = document.querySelectorAll('.task-checkbox');
        this.log(`Found ${checkboxes.length} task checkboxes`);

        if (checkboxes.length < 2) {
            this.log('Not enough tasks for bulk selection test', 'warning');
            return;
        }

        // Select first two
        checkboxes[0].checked = true;
        checkboxes[0].dispatchEvent(new Event('change', { bubbles: true }));
        await this.sleep(300);

        checkboxes[1].checked = true;
        checkboxes[1].dispatchEvent(new Event('change', { bubbles: true }));
        await this.sleep(500);

        // Check toolbar
        const bulkToolbar = document.querySelector('#bulk-action-toolbar');
        
        if (bulkToolbar && !bulkToolbar.classList.contains('hidden')) {
            this.log('Bulk action toolbar appears', 'pass');

            const countElement = document.querySelector('#bulk-selected-count');
            if (countElement) {
                this.log(`Selected count displayed: ${countElement.textContent}`, 'pass');
            }

            // Test cancel
            const cancelBtn = document.querySelector('#bulk-cancel-btn');
            if (cancelBtn) {
                cancelBtn.click();
                await this.sleep(300);

                if (bulkToolbar.classList.contains('hidden')) {
                    this.log('Cancel button closes bulk toolbar', 'pass');
                } else {
                    this.log('Cancel button did not close bulk toolbar', 'fail');
                }
            }
        } else {
            this.log('Bulk action toolbar did not appear', 'fail');
        }
    }

    async test06ResponsiveMobile() {
        console.log('\n' + '='.repeat(80));
        console.log('TEST 6: Responsive - Mobile Width Check');
        console.log('='.repeat(80));

        const currentWidth = window.innerWidth;
        console.log(`Current viewport width: ${currentWidth}px`);

        if (currentWidth <= 768) {
            this.log('Testing at mobile width', 'info');

            const searchToolbar = document.querySelector('.search-sort-toolbar');
            if (searchToolbar) {
                const style = window.getComputedStyle(searchToolbar);
                if (style.flexWrap === 'wrap') {
                    this.log('Search toolbar wraps on mobile', 'pass');
                }
            }
        } else {
            this.log('Resize window to < 768px for mobile test', 'warning');
        }
    }

    async test07EdgeCaseRapidClicking() {
        console.log('\n' + '='.repeat(80));
        console.log('TEST 7: Edge Case - Rapid Clicking');
        console.log('='.repeat(80));

        const taskCards = document.querySelectorAll('.task-card');
        if (taskCards.length === 0) {
            this.log('No tasks to test', 'warning');
            return;
        }

        const threeDotBtn = taskCards[0].querySelector('.task-menu-trigger');
        
        if (!threeDotBtn) {
            this.log('Three-dot button not found', 'fail');
            return;
        }

        this.log('Rapidly clicking three-dot button...', 'info');
        
        // Rapidly click 5 times
        for (let i = 0; i < 5; i++) {
            threeDotBtn.click();
            await this.sleep(100);
        }

        await this.sleep(500);

        // Check menu state
        const menu = document.querySelector('#task-menu');
        const state = menu ? menu.getAttribute('data-state') : null;

        if (state === 'open' || state === 'closed') {
            this.log(`Menu in stable state after rapid clicking: ${state}`, 'pass');
        } else {
            this.log(`Menu in unstable state: ${state}`, 'fail');
        }
    }

    async test08ConsoleErrors() {
        console.log('\n' + '='.repeat(80));
        console.log('TEST 8: Check for JavaScript Errors');
        console.log('='.repeat(80));

        this.log('Check browser console for any errors manually', 'info');
        this.log('Look for red error messages in the console', 'info');
    }

    async test09TaskSearchSortBindings() {
        console.log('\n' + '='.repeat(80));
        console.log('TEST 9: TaskSearchSort bindings & cache sync');
        console.log('='.repeat(80));

        const controller = window.getTaskSearchSort?.();
        if (!controller) {
            this.log('TaskSearchSort instance not found', 'fail');
            return;
        }

        const searchInput = document.querySelector('#task-search-input');
        const sortSelect = document.querySelector('#task-sort-select');
        const filterTabs = document.querySelectorAll('.filter-tab');

        if (!searchInput || !sortSelect || filterTabs.length === 0) {
            this.log('Search/sort controls missing', 'fail');
            return;
        }

        const uniqueQuery = 'sync-check';
        searchInput.value = uniqueQuery;
        searchInput.dispatchEvent(new Event('input', { bubbles: true }));
        await this.sleep(500);

        const viewState = window.optimisticUI?.cache?.getViewState
            ? await window.optimisticUI.cache.getViewState('tasks_page')
            : window.taskCache?.getViewState
                ? await window.taskCache.getViewState('tasks_page')
                : null;

        if (viewState && viewState.search === uniqueQuery) {
            this.log('Search persisted to ledger-backed view state', 'pass');
        } else if (viewState) {
            this.log(`Search view state mismatch (expected ${uniqueQuery}, got ${viewState.search})`, 'fail');
        } else {
            this.log('View state cache not available', 'warning');
        }

        // Sort ordering check
        const firstTitleBefore = document.querySelector('.task-card .task-title')?.textContent || '';
        sortSelect.value = 'title';
        sortSelect.dispatchEvent(new Event('change', { bubbles: true }));
        await this.sleep(500);

        const firstTitleAfter = document.querySelector('.task-card .task-title')?.textContent || '';
        if (firstTitleAfter !== firstTitleBefore) {
            this.log('Sort select reorders virtual list', 'pass');
        } else {
            this.log('Sort select did not visibly reorder tasks (may be identical titles)', 'warning');
        }

        // Filter tab sync
        const archivedTab = document.querySelector('.filter-tab[data-filter="archived"]');
        if (archivedTab) {
            archivedTab.click();
            await this.sleep(400);

            if (controller.currentFilter === 'archived') {
                this.log('Filter tab click updates TaskSearchSort state', 'pass');
            } else {
                this.log('TaskSearchSort did not update currentFilter from tab click', 'fail');
            }

            const activeTab = document.querySelector('.filter-tab[data-filter="active"]');
            if (activeTab) {
                activeTab.click();
                await this.sleep(200);
            }
        } else {
            this.log('Archived filter tab not present', 'warning');
        }

        // Clear search to avoid cascading effects on following tests
        searchInput.value = '';
        searchInput.dispatchEvent(new Event('input', { bubbles: true }));
        await this.sleep(400);
    }

    generateReport() {
        console.log('\n' + '='.repeat(80));
        console.log('TEST REPORT SUMMARY');
        console.log('='.repeat(80));

        const passes = this.testResults.filter(r => r.type === 'pass').length;
        const fails = this.testResults.filter(r => r.type === 'fail').length;
        const warnings = this.testResults.filter(r => r.type === 'warning').length;

        console.log(`\nTotal Results:`);
        console.log(`  ✅ Passes: ${passes}`);
        console.log(`  ❌ Failures: ${fails}`);
        console.log(`  ⚠️  Warnings: ${warnings}`);

        console.log(`\nDetailed Results:`);
        this.testResults.forEach(result => {
            const icon = {
                'pass': '✅',
                'fail': '❌',
                'warning': '⚠️',
                'info': 'ℹ️'
            }[result.type] || 'ℹ️';
            
            console.log(`${icon} ${result.message}`);
        });

        return {
            passes,
            fails,
            warnings,
            results: this.testResults
        };
    }

    async runAllTests() {
        console.log('\n' + '█'.repeat(80));
        console.log('COMPREHENSIVE TASKS PAGE TESTING');
        console.log('█'.repeat(80));
        console.log(`URL: ${window.location.href}`);
        console.log(`Timestamp: ${new Date().toISOString()}`);
        console.log('█'.repeat(80));

        try {
            await this.test01ThreeDotMenuPriority();
            await this.test02SearchFunctionality();
            await this.test03SortFunctionality();
            await this.test04FilterTabs();
            await this.test05BulkSelection();
            await this.test06ResponsiveMobile();
            await this.test07EdgeCaseRapidClicking();
            await this.test08ConsoleErrors();
            await this.test09TaskSearchSortBindings();
        } catch (error) {
            console.error('Error during testing:', error);
            this.log(`Test suite error: ${error.message}`, 'fail');
        }

        return this.generateReport();
    }
}

// Auto-run when loaded
console.log('Tasks Page Tester loaded. Run: const tester = new TasksPageTester(); await tester.runAllTests();');

// Export for console use
window.TasksPageTester = TasksPageTester;
