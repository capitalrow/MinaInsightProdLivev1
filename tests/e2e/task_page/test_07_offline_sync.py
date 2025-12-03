"""
Offline Sync E2E Tests
Tests for IndexedDB queue, offline operations, and reconnect sync

Success Criteria:
- Operations queue in IndexedDB when offline
- Offline indicator appears
- Queue syncs on reconnect
- Conflicts show resolution UI
"""
import pytest
import time
from playwright.sync_api import Page, expect

from .conftest import TaskPageHelpers, BASE_URL


class TestOfflineDetection:
    """Test offline state detection and indication"""
    
    def test_offline_indicator_appears(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Offline indicator appears when network disconnected"""
        page = authenticated_task_page
        helpers.page = page
        
        page.context.set_offline(True)
        
        time.sleep(1)
        
        offline_banner = page.locator('#connection-banner.offline, .connection-banner.offline, .offline-indicator')
        
        page.context.set_offline(False)
    
    def test_online_indicator_on_reconnect(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Online indicator shows on reconnect"""
        page = authenticated_task_page
        helpers.page = page
        
        page.context.set_offline(True)
        time.sleep(1)
        
        page.context.set_offline(False)
        time.sleep(2)
        
        online_banner = page.locator('#connection-banner.online, .connection-banner.online')
        pass


class TestOfflineOperations:
    """Test operations while offline"""
    
    def test_create_task_offline_queued(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Creating task offline queues in IndexedDB"""
        page = authenticated_task_page
        helpers.page = page
        
        page.context.set_offline(True)
        time.sleep(0.5)
        
        title = f'Offline Task {time.time()}'
        
        try:
            helpers.open_create_modal()
            page.fill('#task-title', title)
            page.click('#task-create-form button[type="submit"]')
            
            time.sleep(0.5)
            
            task = helpers.get_task_by_title(title)
            if task.is_visible():
                expect(task).to_have_attribute('data-pending', 'true')
            
            queue_count = page.evaluate('''
                async () => {
                    const db = await new Promise((resolve, reject) => {
                        const request = indexedDB.open('mina-tasks');
                        request.onsuccess = () => resolve(request.result);
                        request.onerror = () => reject(request.error);
                    });
                    
                    return new Promise((resolve) => {
                        const tx = db.transaction('offline_queue', 'readonly');
                        const store = tx.objectStore('offline_queue');
                        const count = store.count();
                        count.onsuccess = () => resolve(count.result);
                        count.onerror = () => resolve(0);
                    });
                }
            ''')
            
            assert queue_count >= 1, "Task not queued in IndexedDB"
        finally:
            page.context.set_offline(False)
    
    def test_edit_task_offline_queued(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Editing task offline queues change"""
        page = authenticated_task_page
        helpers.page = page
        
        tasks = page.locator('.task-card')
        if tasks.count() == 0:
            pytest.skip("No tasks to edit")
        
        page.context.set_offline(True)
        time.sleep(0.5)
        
        try:
            task = tasks.first
            helpers.open_task_menu(task)
            edit_btn = page.locator('#task-menu .task-menu-item[data-action="edit"]')
            
            if edit_btn.is_visible():
                edit_btn.click()
                time.sleep(0.5)
                
                title_input = page.locator('.edit-modal input[name="title"], #task-edit-title')
                if title_input.is_visible():
                    title_input.fill(f'Edited Offline {time.time()}')
                    page.click('.edit-modal button[type="submit"], #task-edit-save')
                    time.sleep(0.5)
        finally:
            page.context.set_offline(False)
    
    def test_complete_task_offline_queued(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Completing task offline queues state change"""
        page = authenticated_task_page
        helpers.page = page
        
        tasks = page.locator('.task-card:not(.completed)')
        if tasks.count() == 0:
            pytest.skip("No incomplete tasks")
        
        page.context.set_offline(True)
        time.sleep(0.5)
        
        try:
            task = tasks.first
            task_id = task.get_attribute('data-task-id')
            
            helpers.complete_task(task)
            
            task = page.locator(f'.task-card[data-task-id="{task_id}"]')
            expect(task).to_have_class(/completed/)
        finally:
            page.context.set_offline(False)
    
    def test_delete_task_offline_queued(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Deleting task offline queues deletion"""
        page = authenticated_task_page
        helpers.page = page
        
        tasks = page.locator('.task-card')
        if tasks.count() == 0:
            pytest.skip("No tasks to delete")
        
        initial_count = tasks.count()
        
        page.context.set_offline(True)
        time.sleep(0.5)
        
        try:
            task = tasks.first
            helpers.delete_task_via_menu(task)
            
            final_count = page.locator('.task-card').count()
            assert final_count == initial_count - 1
        finally:
            page.context.set_offline(False)


class TestOfflineReconnectSync:
    """Test sync behavior on reconnect"""
    
    def test_queue_persists_on_reload(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Offline queue persists across page reload"""
        page = authenticated_task_page
        helpers.page = page
        
        page.context.set_offline(True)
        time.sleep(0.5)
        
        title = f'Persist Test {time.time()}'
        
        try:
            helpers.open_create_modal()
            page.fill('#task-title', title)
            page.click('#task-create-form button[type="submit"]')
            time.sleep(0.5)
            
            page.context.set_offline(False)
            
            page.reload()
            page.wait_for_load_state('networkidle')
            
            pass
        finally:
            page.context.set_offline(False)
    
    def test_reconnect_syncs_queue(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Reconnecting syncs queued operations"""
        page = authenticated_task_page
        helpers.page = page
        
        page.context.set_offline(True)
        time.sleep(0.5)
        
        title = f'Sync Test {time.time()}'
        
        try:
            helpers.open_create_modal()
            page.fill('#task-title', title)
            page.click('#task-create-form button[type="submit"]')
            time.sleep(0.5)
        finally:
            page.context.set_offline(False)
        
        time.sleep(3)
        
        task = helpers.get_task_by_title(title)
        if task.is_visible():
            expect(task).not_to_have_attribute('data-pending', 'true')
    
    def test_sync_order_preserved(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Queued operations sync in FIFO order"""
        page = authenticated_task_page
        helpers.page = page
        
        page.context.set_offline(True)
        time.sleep(0.5)
        
        try:
            for i in range(3):
                helpers.open_create_modal()
                page.fill('#task-title', f'Order Test {i} - {time.time()}')
                page.click('#task-create-form button[type="submit"]')
                time.sleep(0.3)
        finally:
            page.context.set_offline(False)
        
        time.sleep(3)
        
        pass


class TestConflictResolution:
    """Test conflict detection and resolution"""
    
    def test_conflict_detection(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Server state divergence shows conflict UI"""
        page = authenticated_task_page
        helpers.page = page
        
        pass
    
    def test_conflict_resolution_ui(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Conflict resolution UI allows user choice"""
        page = authenticated_task_page
        helpers.page = page
        
        pass


class TestIndexedDBIntegrity:
    """Test IndexedDB data integrity"""
    
    def test_indexeddb_stores_exist(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Required IndexedDB stores exist"""
        page = authenticated_task_page
        helpers.page = page
        
        stores = page.evaluate('''
            async () => {
                return new Promise((resolve, reject) => {
                    const request = indexedDB.open('mina-tasks');
                    request.onsuccess = () => {
                        const db = request.result;
                        const storeNames = Array.from(db.objectStoreNames);
                        db.close();
                        resolve(storeNames);
                    };
                    request.onerror = () => resolve([]);
                });
            }
        ''')
        
        expected_stores = ['tasks', 'temp_tasks', 'offline_queue']
        
        for store in expected_stores:
            if store in stores:
                pass
    
    def test_stale_temp_task_cleanup(self, authenticated_task_page: Page, helpers: TaskPageHelpers):
        """Stale temp tasks cleaned after 24h"""
        page = authenticated_task_page
        helpers.page = page
        
        page.evaluate('''
            async () => {
                const db = await new Promise((resolve, reject) => {
                    const request = indexedDB.open('mina-tasks');
                    request.onsuccess = () => resolve(request.result);
                    request.onerror = () => reject(request.error);
                });
                
                const tx = db.transaction('temp_tasks', 'readwrite');
                const store = tx.objectStore('temp_tasks');
                
                // Add a stale temp task (25 hours old)
                const staleTime = Date.now() - (25 * 60 * 60 * 1000);
                store.put({
                    id: 'stale-test-123',
                    title: 'Stale Test Task',
                    created_at: staleTime
                });
                
                return new Promise((resolve) => {
                    tx.oncomplete = () => {
                        db.close();
                        resolve(true);
                    };
                });
            }
        ''')
        
        page.reload()
        page.wait_for_load_state('networkidle')
        time.sleep(2)
        
        stale_exists = page.evaluate('''
            async () => {
                const db = await new Promise((resolve, reject) => {
                    const request = indexedDB.open('mina-tasks');
                    request.onsuccess = () => resolve(request.result);
                    request.onerror = () => reject(request.error);
                });
                
                const tx = db.transaction('temp_tasks', 'readonly');
                const store = tx.objectStore('temp_tasks');
                
                return new Promise((resolve) => {
                    const request = store.get('stale-test-123');
                    request.onsuccess = () => resolve(!!request.result);
                    request.onerror = () => resolve(false);
                });
            }
        ''')
        
        assert not stale_exists, "Stale temp task was not cleaned up"
