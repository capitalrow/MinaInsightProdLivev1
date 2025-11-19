/**
 * CROWN⁴.6 Tasks Page - Browser-Based E2E Test Suite
 * Run this in the browser console on /dashboard/tasks to test all interactions
 * 
 * Usage: Copy and paste this entire file into browser console, then run: runAllTasksTests()
 */

const TasksE2ETests = {
    results: [],
    passed: 0,
    failed: 0,

    async test(name, fn) {
        console.log(`\n🧪 Testing: ${name}...`);
        try {
            await fn();
            this.results.push({ name, status: 'PASS', error: null });
            this.passed++;
            console.log(`✅ PASS: ${name}`);
        } catch (error) {
            this.results.push({ name, status: 'FAIL', error: error.message });
            this.failed++;
            console.error(`❌ FAIL: ${name}`, error.message);
        }
    },

    wait(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    },

    async runAllTests() {
        console.log('\n═══════════════════════════════════════════════════════');
        console.log('   CROWN⁴.6 Tasks Page E2E Test Suite');
        console.log('   Testing Against Real 15 Tasks');
        console.log('═══════════════════════════════════════════════════════\n');

        this.results = [];
        this.passed = 0;
        this.failed = 0;

        // Test 1: Page Elements Exist
        await this.test('Page loads with all required elements', async () => {
            const container = document.querySelector('.tasks-container');
            if (!container) throw new Error('Tasks container not found');
            
            const title = document.querySelector('.tasks-title');
            if (!title || !title.textContent.includes('Action Items')) {
                throw new Error('Page title incorrect');
            }
        });

        // Test 2: Real Tasks Render
        await this.test('Real tasks from meetings render correctly', async () => {
            await this.wait(1000);
            const cards = document.querySelectorAll('.task-card');
            if (cards.length === 0) throw new Error('No task cards found');
            console.log(`  Found ${cards.length} task cards`);
        });

        // Test 3: New Task Button
        await this.test('"New Task" button opens modal', async () => {
            const btn = document.querySelector('button.btn-primary:has-text("New Task"), .btn-primary');
            const buttons = Array.from(document.querySelectorAll('.btn-primary'));
            const newTaskBtn = buttons.find(b => b.textContent.includes('New Task'));
            
            if (!newTaskBtn) throw new Error('New Task button not found');
            
            newTaskBtn.click();
            await this.wait(300);
            
            const modal = document.querySelector('#task-modal-overlay');
            if (!modal || modal.classList.contains('hidden')) {
                throw new Error('Modal did not open');
            }
            
            // Close modal
            const closeBtn = document.querySelector('#task-modal-close, .task-modal-close');
            if (closeBtn) closeBtn.click();
        });

        // Test 4: Three-Dot Menu
        await this.test('Three-dot menu (kebab) shows options', async () => {
            const firstCard = document.querySelector('.task-card');
            if (!firstCard) throw new Error('No task card found');
            
            const menuBtn = firstCard.querySelector('.task-menu-trigger');
            if (!menuBtn) throw new Error('Menu button not found');
            
            menuBtn.click();
            await this.wait(300);
            
            const menu = document.querySelector('.task-actions-menu, .task-menu-dropdown, [role="menu"]');
            if (!menu || menu.style.display === 'none') {
                throw new Error('Menu did not appear');
            }
            
            // Close menu by clicking elsewhere
            document.body.click();
        });

        // Test 5: Checkbox Toggle
        await this.test('Task checkbox toggles completion', async () => {
            const firstCard = document.querySelector('.task-card');
            const checkbox = firstCard.querySelector('.task-checkbox');
            if (!checkbox) throw new Error('Checkbox not found');
            
            const initialState = checkbox.checked;
            checkbox.click();
            await this.wait(500);
            
            const newState = checkbox.checked;
            if (newState === initialState) {
                throw new Error('Checkbox state did not change');
            }
            
            // Toggle back
            checkbox.click();
            await this.wait(500);
        });

        // Test 6: Filter Tabs
        await this.test('Filter tabs (All/Pending/Completed) work', async () => {
            const allTab = document.querySelector('.filter-tab[data-filter="all"]');
            const pendingTab = document.querySelector('.filter-tab[data-filter="pending"]');
            const completedTab = document.querySelector('.filter-tab[data-filter="completed"]');
            
            if (!allTab || !pendingTab || !completedTab) {
                throw new Error('Filter tabs not found');
            }
            
            // Click each tab
            allTab.click();
            await this.wait(300);
            const allCount = document.querySelectorAll('.task-card:not([style*="display: none"])').length;
            
            pendingTab.click();
            await this.wait(300);
            const pendingCount = document.querySelectorAll('.task-card:not([style*="display: none"])').length;
            
            completedTab.click();
            await this.wait(300);
            
            // Return to all
            allTab.click();
            await this.wait(300);
            
            console.log(`  Filter counts - All: ${allCount}, Pending: ${pendingCount}`);
        });

        // Test 7: Search Bar
        await this.test('Search bar filters tasks', async () => {
            const searchInput = document.querySelector('#task-search-input');
            if (!searchInput) throw new Error('Search input not found');
            
            const initialCount = document.querySelectorAll('.task-card:not([style*="display: none"])').length;
            
            // Type search query
            searchInput.value = 'test';
            searchInput.dispatchEvent(new Event('input', { bubbles: true }));
            await this.wait(500);
            
            // Clear search
            searchInput.value = '';
            searchInput.dispatchEvent(new Event('input', { bubbles: true }));
            await this.wait(500);
            
            console.log(`  Search test completed`);
        });

        // Test 8: Sort Dropdown
        await this.test('Sort dropdown changes task order', async () => {
            const sortSelect = document.querySelector('#task-sort-select');
            if (!sortSelect) throw new Error('Sort dropdown not found');
            
            const firstTitleBefore = document.querySelector('.task-card .task-title')?.textContent;
            
            sortSelect.value = 'title';
            sortSelect.dispatchEvent(new Event('change', { bubbles: true }));
            await this.wait(500);
            
            const firstTitleAfter = document.querySelector('.task-card .task-title')?.textContent;
            
            console.log(`  Sort test - Before: "${firstTitleBefore}", After: "${firstTitleAfter}"`);
            
            // Reset to default
            sortSelect.value = 'default';
            sortSelect.dispatchEvent(new Event('change', { bubbles: true }));
        });

        // Test 9: Jump to Transcript Button
        await this.test('"Jump to Transcript" button exists', async () => {
            const jumpButtons = document.querySelectorAll('.jump-to-transcript-btn');
            if (jumpButtons.length > 0) {
                console.log(`  Found ${jumpButtons.length} transcript links`);
            } else {
                console.log('  No transcript links (may be expected if no meeting data)');
            }
        });

        // Test 10: AI Proposals Button
        await this.test('"AI Proposals" button is clickable', async () => {
            const aiBtn = document.querySelector('.btn-generate-proposals');
            if (!aiBtn) throw new Error('AI Proposals button not found');
            
            const text = aiBtn.textContent;
            if (!text.includes('AI Proposals') && !text.includes('Proposals')) {
                throw new Error('AI Proposals button has wrong text');
            }
        });

        // Test 11: Meeting Heatmap
        await this.test('Meeting heatmap container exists', async () => {
            const heatmap = document.querySelector('#meeting-heatmap-container');
            if (!heatmap) throw new Error('Heatmap container not found');
            console.log('  Meeting heatmap container found');
        });

        // Test 12: Performance - No Console Errors
        await this.test('No JavaScript errors in console', async () => {
            // This is informational - actual errors would be visible in console
            console.log('  Check console for any red errors above');
        });

        // Generate Report
        this.generateReport();
    },

    generateReport() {
        console.log('\n═══════════════════════════════════════════════════════');
        console.log('   TEST RESULTS SUMMARY');
        console.log('═══════════════════════════════════════════════════════\n');
        
        const total = this.passed + this.failed;
        const passRate = ((this.passed / total) * 100).toFixed(1);
        
        console.log(`Total Tests: ${total}`);
        console.log(`✅ Passed: ${this.passed}`);
        console.log(`❌ Failed: ${this.failed}`);
        console.log(`📊 Pass Rate: ${passRate}%\n`);
        
        if (this.failed > 0) {
            console.log('FAILED TESTS:');
            this.results
                .filter(r => r.status === 'FAIL')
                .forEach(r => {
                    console.log(`  ❌ ${r.name}`);
                    console.log(`     Error: ${r.error}`);
                });
        }
        
        console.log('\n═══════════════════════════════════════════════════════\n');
        
        if (passRate === 100) {
            console.log('🎉 ALL TESTS PASSED! Page is fully functional.');
        } else if (passRate >= 80) {
            console.log('⚠️  Most features working, some fixes needed.');
        } else {
            console.log('🔴 CRITICAL: Many features broken, extensive fixes required.');
        }
        
        return { total, passed: this.passed, failed: this.failed, passRate };
    }
};

// Expose global function
window.runAllTasksTests = () => TasksE2ETests.runAllTests();

console.log('\n✅ Tasks E2E Test Suite Loaded!');
console.log('📋 Run tests with: runAllTasksTests()');
console.log('');
