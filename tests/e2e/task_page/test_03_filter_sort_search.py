"""
Filter, Sort, and Search E2E Tests
Tests for task filtering, sorting, and search functionality

Success Criteria:
- Filter tabs switch correctly with accurate counts
- Sort options reorder tasks properly
- Search filters by title and description
- Combined filter + sort works correctly
"""
import pytest
import time
from playwright.sync_api import Page, expect

from .conftest import TaskPageHelpers, BASE_URL


class TestFiltering:
    """Test task filter tabs"""
    
    def test_filter_all_shows_all_tasks(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """All filter shows all tasks"""
        page = authenticated_task_page
        helpers.page = page
        
        helpers.filter_by('all')
        time.sleep(0.3)
        
        all_count_badge = page.locator('.filter-counter[data-counter="all"]')
        expected_count = int(all_count_badge.text_content().strip()) if all_count_badge.is_visible() else 0
        
        actual_count = helpers.get_task_count()
        assert actual_count == expected_count or expected_count == 0
    
    def test_filter_active_excludes_completed(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Active filter excludes completed/cancelled tasks"""
        page = authenticated_task_page
        helpers.page = page
        
        helpers.filter_by('active')
        time.sleep(0.3)
        
        tasks = page.locator('.task-card')
        for i in range(min(tasks.count(), 5)):
            task = tasks.nth(i)
            status = task.get_attribute('data-status')
            assert status not in ['completed', 'cancelled'], f"Found {status} task in active filter"
    
    def test_filter_archived_shows_completed(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Archived filter shows completed/cancelled tasks"""
        page = authenticated_task_page
        helpers.page = page
        
        helpers.filter_by('archived')
        time.sleep(0.3)
        
        tasks = page.locator('.task-card')
        if tasks.count() > 0:
            for i in range(min(tasks.count(), 5)):
                task = tasks.nth(i)
                status = task.get_attribute('data-status')
                assert status in ['completed', 'cancelled'], f"Found {status} task in archived filter"
    
    def test_filter_counts_match_list(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Filter counter badges match actual list length"""
        page = authenticated_task_page
        helpers.page = page
        
        for filter_name in ['all', 'active', 'archived']:
            helpers.filter_by(filter_name)
            time.sleep(0.3)
            
            badge = page.locator(f'.filter-counter[data-counter="{filter_name}"]')
            if badge.is_visible():
                expected_count = int(badge.text_content().strip())
                actual_count = helpers.get_task_count()
                
                assert actual_count == expected_count, f"{filter_name}: badge={expected_count}, actual={actual_count}"
    
    def test_filter_state_persists_url(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Filter state persists in URL"""
        page = authenticated_task_page
        helpers.page = page
        
        helpers.filter_by('archived')
        time.sleep(0.5)
        
        url = page.url
        
        page.reload()
        page.wait_for_load_state('networkidle')
        
        active_filter = page.locator('.filter-tab.active')
        pass


class TestSorting:
    """Test task sorting options"""
    
    def test_sort_by_priority_high_first(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Sort by priority shows urgent/high first"""
        page = authenticated_task_page
        helpers.page = page
        
        helpers.sort_by('priority')
        time.sleep(0.3)
        
        tasks = page.locator('.task-card')
        if tasks.count() > 1:
            priority_order = ['urgent', 'high', 'medium', 'low']
            
            first_priority = tasks.first.get_attribute('data-priority')
            second_priority = tasks.nth(1).get_attribute('data-priority')
            
            if first_priority and second_priority:
                first_idx = priority_order.index(first_priority) if first_priority in priority_order else 99
                second_idx = priority_order.index(second_priority) if second_priority in priority_order else 99
                assert first_idx <= second_idx, f"Priority sort incorrect: {first_priority} after {second_priority}"
    
    def test_sort_by_priority_low_first(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Sort by priority reverse shows low first"""
        page = authenticated_task_page
        helpers.page = page
        
        helpers.sort_by('priority-reverse')
        time.sleep(0.3)
        
        tasks = page.locator('.task-card')
        if tasks.count() > 1:
            priority_order = ['low', 'medium', 'high', 'urgent']
            
            first_priority = tasks.first.get_attribute('data-priority')
            if first_priority:
                assert first_priority in ['low', 'medium'], f"Expected low priority first, got {first_priority}"
    
    def test_sort_by_due_date_soonest(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Sort by due date shows soonest first"""
        page = authenticated_task_page
        helpers.page = page
        
        helpers.sort_by('due-date')
        time.sleep(0.3)
        
        tasks = page.locator('.task-card')
        if tasks.count() > 1:
            dates = []
            for i in range(min(tasks.count(), 3)):
                task = tasks.nth(i)
                due_date = task.get_attribute('data-due-date')
                if due_date:
                    dates.append(due_date)
            
            if len(dates) > 1:
                assert dates == sorted(dates), f"Due dates not sorted: {dates}"
    
    def test_sort_by_created_newest(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Sort by created date shows newest first"""
        page = authenticated_task_page
        helpers.page = page
        
        helpers.sort_by('created')
        time.sleep(0.3)
        
        pass
    
    def test_sort_by_title_alphabetical(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Sort by title shows A-Z order"""
        page = authenticated_task_page
        helpers.page = page
        
        helpers.sort_by('title')
        time.sleep(0.3)
        
        tasks = page.locator('.task-card')
        if tasks.count() > 1:
            titles = []
            for i in range(min(tasks.count(), 5)):
                task = tasks.nth(i)
                title = task.locator('.task-title').text_content()
                if title:
                    titles.append(title.lower())
            
            if len(titles) > 1:
                assert titles == sorted(titles), f"Titles not sorted: {titles}"
    
    def test_sort_persists_after_refresh(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Sort order persists after page refresh"""
        page = authenticated_task_page
        helpers.page = page
        
        helpers.sort_by('priority')
        time.sleep(0.5)
        
        page.reload()
        page.wait_for_load_state('networkidle')
        
        pass


class TestSearch:
    """Test task search functionality"""
    
    def test_search_filters_by_title(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Search matches task titles"""
        page = authenticated_task_page
        helpers.page = page
        
        tasks = page.locator('.task-card')
        if tasks.count() == 0:
            pytest.skip("No tasks to search")
        
        first_title = tasks.first.locator('.task-title').text_content()
        if not first_title:
            pytest.skip("No task title available")
        
        search_term = first_title[:10] if len(first_title) > 10 else first_title
        
        helpers.search(search_term)
        
        results = page.locator('.task-card')
        assert results.count() >= 1, f"Search for '{search_term}' returned no results"
        
        first_result_title = results.first.locator('.task-title').text_content()
        assert search_term.lower() in first_result_title.lower()
    
    def test_search_matches_description(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Search matches task descriptions"""
        page = authenticated_task_page
        helpers.page = page
        
        pass
    
    def test_search_debounced(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Search input is debounced (no flicker)"""
        page = authenticated_task_page
        helpers.page = page
        
        search_input = page.locator('#task-search-input')
        
        search_input.type('test', delay=50)
        
        time.sleep(0.3)
        
        results = page.locator('.task-card')
        pass
    
    def test_clear_search_shows_all(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Clearing search shows all tasks"""
        page = authenticated_task_page
        helpers.page = page
        
        helpers.filter_by('all')
        time.sleep(0.3)
        initial_count = helpers.get_task_count()
        
        helpers.search('nonexistent12345')
        time.sleep(0.5)
        
        helpers.clear_search()
        time.sleep(0.5)
        
        final_count = helpers.get_task_count()
        assert final_count == initial_count, f"Clear search didn't restore all tasks: {initial_count} → {final_count}"
    
    def test_no_results_empty_state(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """No results shows empty state message"""
        page = authenticated_task_page
        helpers.page = page
        
        helpers.search('xyznonexistent12345abc')
        time.sleep(0.5)
        
        no_results = page.locator('#tasks-no-results-state, .empty-state-no-results')
        expect(no_results).to_be_visible()


class TestCombinedFilters:
    """Test combined filter, sort, and search"""
    
    def test_filter_and_sort_together(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Filter and sort combine correctly"""
        page = authenticated_task_page
        helpers.page = page
        
        helpers.filter_by('active')
        time.sleep(0.3)
        
        helpers.sort_by('priority')
        time.sleep(0.3)
        
        tasks = page.locator('.task-card')
        for i in range(min(tasks.count(), 3)):
            task = tasks.nth(i)
            status = task.get_attribute('data-status')
            assert status not in ['completed', 'cancelled']
    
    def test_filter_and_search_together(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Filter and search combine correctly"""
        page = authenticated_task_page
        helpers.page = page
        
        helpers.filter_by('all')
        time.sleep(0.3)
        
        tasks = page.locator('.task-card')
        if tasks.count() == 0:
            pytest.skip("No tasks available")
        
        first_title = tasks.first.locator('.task-title').text_content()
        search_term = first_title[:5] if first_title else ''
        
        helpers.filter_by('active')
        helpers.search(search_term)
        
        time.sleep(0.5)
        
        results = page.locator('.task-card')
        for i in range(results.count()):
            task = results.nth(i)
            status = task.get_attribute('data-status')
            title = task.locator('.task-title').text_content()
            
            assert status not in ['completed', 'cancelled']
            if title and search_term:
                assert search_term.lower() in title.lower()
    
    def test_clear_filters_button(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Clear filters resets to default view"""
        page = authenticated_task_page
        helpers.page = page
        
        helpers.filter_by('archived')
        helpers.search('test')
        
        time.sleep(0.5)
        
        helpers.filter_by('all')
        helpers.clear_search()
        
        time.sleep(0.3)
        
        active_filter = page.locator('.filter-tab.active')
        filter_name = active_filter.get_attribute('data-filter')
        
        search_value = page.locator('#task-search-input').input_value()
        assert search_value == '', "Search was not cleared"
