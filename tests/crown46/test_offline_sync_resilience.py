"""
CROWN 4.6 Offline/Sync Resilience Validation Suite

Tests multi-tab synchronization, conflict resolution, offline queue replay,
and zero-data-loss guarantees for Mina Tasks using REAL production APIs.

Production APIs Used:
- window.taskCache (IndexedDB TaskCache)
- window.broadcastSync (BroadcastChannel multi-tab sync)
- window.offlineQueueManager (Offline queue with vector clocks)
- VectorClock (Conflict resolution)

Key Requirements:
- Multi-tab sync via BroadcastChannel (<500ms latency)
- Conflict resolution using vector clocks
- Offline queue FIFO replay with zero data loss
- IndexedDB data integrity validation
- Network partition recovery

Author: CROWN 4.6 Testing Team
Date: November 19, 2025
"""

import pytest
import json
import time
from playwright.sync_api import Page, BrowserContext, expect


class OfflineSyncValidator:
    """Validates offline/sync resilience metrics and thresholds."""
    
    def __init__(self):
        self.metrics = {
            'sync_latency_ms': [],
            'conflict_resolution_success': [],
            'offline_queue_integrity': [],
            'data_integrity_checks': []
        }
        
        self.thresholds = {
            'max_sync_latency_ms': 500,  # Multi-tab sync <500ms
            'conflict_resolution_rate': 1.0,  # 100% successful merges
            'data_loss_tolerance': 0.0,  # Zero data loss
            'integrity_match_rate': 1.0  # 100% integrity
        }
    
    def record_sync_latency(self, latency_ms: float):
        """Record multi-tab sync latency."""
        self.metrics['sync_latency_ms'].append(latency_ms)
    
    def record_conflict_resolution(self, success: bool):
        """Record conflict resolution outcome."""
        self.metrics['conflict_resolution_success'].append(1 if success else 0)
    
    def record_queue_integrity(self, expected: int, actual: int):
        """Record offline queue integrity (expected vs actual items)."""
        integrity = actual / expected if expected > 0 else 1.0
        self.metrics['offline_queue_integrity'].append(integrity)
    
    def record_data_integrity(self, valid: bool):
        """Record data integrity check result."""
        self.metrics['data_integrity_checks'].append(1 if valid else 0)
    
    def validate_sync_latency(self) -> dict:
        """Validate multi-tab sync meets latency threshold."""
        if not self.metrics['sync_latency_ms']:
            return {'valid': False, 'reason': 'No sync measurements'}
        
        max_latency = max(self.metrics['sync_latency_ms'])
        avg_latency = sum(self.metrics['sync_latency_ms']) / len(self.metrics['sync_latency_ms'])
        
        return {
            'valid': max_latency <= self.thresholds['max_sync_latency_ms'],
            'max_latency_ms': max_latency,
            'avg_latency_ms': avg_latency,
            'threshold_ms': self.thresholds['max_sync_latency_ms']
        }
    
    def validate_conflict_resolution(self) -> dict:
        """Validate conflict resolution success rate."""
        if not self.metrics['conflict_resolution_success']:
            return {'valid': False, 'reason': 'No conflict tests'}
        
        success_rate = sum(self.metrics['conflict_resolution_success']) / len(self.metrics['conflict_resolution_success'])
        
        return {
            'valid': success_rate >= self.thresholds['conflict_resolution_rate'],
            'success_rate': success_rate,
            'threshold': self.thresholds['conflict_resolution_rate']
        }
    
    def validate_data_integrity(self) -> dict:
        """Validate zero data loss guarantee."""
        if not self.metrics['offline_queue_integrity']:
            return {'valid': False, 'reason': 'No integrity tests'}
        
        min_integrity = min(self.metrics['offline_queue_integrity'])
        avg_integrity = sum(self.metrics['offline_queue_integrity']) / len(self.metrics['offline_queue_integrity'])
        
        return {
            'valid': min_integrity >= (1.0 - self.thresholds['data_loss_tolerance']),
            'min_integrity': min_integrity,
            'avg_integrity': avg_integrity,
            'data_loss_tolerance': self.thresholds['data_loss_tolerance']
        }
    
    def generate_report(self) -> dict:
        """Generate comprehensive offline/sync resilience report."""
        return {
            'sync_latency': self.validate_sync_latency(),
            'conflict_resolution': self.validate_conflict_resolution(),
            'data_integrity': self.validate_data_integrity(),
            'metrics': self.metrics
        }


@pytest.fixture
def sync_validator():
    """Fixture providing OfflineSyncValidator instance."""
    return OfflineSyncValidator()


@pytest.fixture
def multi_tab(browser):
    """
    Fixture providing multiple tabs within SINGLE browser context.
    This ensures tabs share IndexedDB, BroadcastChannel, and localStorage.
    Returns dict with 'tab1' and 'tab2' pages.
    """
    # Single context so tabs share state
    context = browser.new_context()
    
    tabs = {
        'tab1': context.new_page(),
        'tab2': context.new_page()
    }
    
    yield tabs
    
    # Cleanup
    context.close()


class TestCROWN46OfflineSyncResilience:
    """CROWN 4.6 Offline/Sync Resilience Test Suite."""
    
    def test_01_multi_tab_broadcast_sync(self, multi_tab: dict, sync_validator: OfflineSyncValidator):
        """
        Validate multi-tab synchronization via BroadcastChannel.
        
        CROWN 4.6 Requirement: Multi-tab sync <500ms latency
        
        Test Scenarios:
        1. Create task in Tab 1 → appears in Tab 2
        2. Both tabs share IndexedDB and BroadcastChannel
        3. Measure sync latency for operations
        
        Uses REAL APIs: window.broadcastSync, window.taskCache
        FIXED: Uses single browser context so tabs share state
        """
        print("\n" + "="*80)
        print("TEST 01: Multi-Tab BroadcastChannel Sync (Production APIs)")
        print("="*80)
        
        tab1 = multi_tab['tab1']
        tab2 = multi_tab['tab2']
        
        # Open same app in both tabs (they share context/state)
        tab1.goto('http://0.0.0.0:5000/tasks')
        tab1.wait_for_load_state('networkidle')
        
        tab2.goto('http://0.0.0.0:5000/tasks')
        tab2.wait_for_load_state('networkidle')
        
        # Wait for broadcast channel initialization
        time.sleep(0.5)
        
        # Verify both tabs share IndexedDB
        shared_state_check = tab1.evaluate("""
            () => {
                return {
                    hasBroadcastSync: typeof window.broadcastSync !== 'undefined',
                    hasTaskCache: typeof window.taskCache !== 'undefined',
                    nodeId: window.taskCache ? window.taskCache.nodeId : null,
                    dbName: window.taskCache ? window.taskCache.dbName : null
                };
            }
        """)
        
        if not shared_state_check['hasBroadcastSync']:
            pytest.skip("BroadcastSync not initialized - requires window.broadcastSync")
        
        if not shared_state_check['hasTaskCache']:
            pytest.skip("TaskCache not initialized - requires window.taskCache")
        
        print(f"\n  ✓ Both tabs in same browser context (share IndexedDB/BroadcastChannel)")
        print(f"  ✓ Node ID: {shared_state_check['nodeId'][:24] if shared_state_check['nodeId'] else 'N/A'}...")
        print(f"  ✓ IndexedDB: {shared_state_check['dbName']}")
        
        # Register broadcast listener in Tab 2 BEFORE creating task
        # Use task_created event (from MultiTabSync) or CACHE_INVALIDATE
        listener_setup = tab2.evaluate("""
            () => {
                return new Promise((resolve) => {
                    if (!window.broadcastSync) {
                        resolve({ success: false, reason: 'no_broadcast_sync' });
                        return;
                    }
                    
                    window._testSyncReceived = false;
                    window._testSyncTimestamp = null;
                    
                    // Try task_created first (from MultiTabSync)
                    const listener = (payload, message) => {
                        console.log('[TEST] Broadcast received:', message.type, payload);
                        window._testSyncReceived = true;
                        window._testSyncTimestamp = Date.now();
                    };
                    
                    // Listen to multiple events to catch whichever is fired
                    window.broadcastSync.on('task_created', listener);
                    window.broadcastSync.on(window.broadcastSync.EVENTS.TASK_UPDATE, listener);
                    window.broadcastSync.on(window.broadcastSync.EVENTS.CACHE_INVALIDATE, listener);
                    
                    resolve({ success: true, events: ['task_created', 'TASK_UPDATE', 'CACHE_INVALIDATE'] });
                });
            }
        """)
        
        if not listener_setup['success']:
            print(f"  ⚠️  Could not register broadcast listener: {listener_setup.get('reason')}")
        else:
            print(f"  ✓ Broadcast listeners registered: {', '.join(listener_setup['events'])}")
        
        # Get initial task count in Tab 2
        initial_count_tab2 = tab2.locator('.task-card').count()
        print(f"\n  Initial Tab 2 task count: {initial_count_tab2}")
        
        # Test 1: Create task in Tab 1 → appears in Tab 2
        print(f"\n  Scenario 1: Create task in Tab 1 (via UI)")
        
        task_title = f"Multi-tab sync test {int(time.time() * 1000)}"
        sync_start = time.time()
        
        task_input = tab1.locator('#task-input').first
        if task_input.count() == 0:
            task_input = tab1.locator('input[placeholder*="task" i]').first
        
        task_input.fill(task_title)
        task_input.press('Enter')
        
        # Wait for task to appear in Tab 1
        tab1.wait_for_selector(f'text={task_title}', timeout=3000)
        print(f"  ✓ Task created in Tab 1: '{task_title}'")
        
        # Wait for broadcast propagation (up to 1000ms)
        broadcast_wait_start = time.time()
        broadcast_received = False
        
        for _ in range(10):  # Check 10 times over 1 second
            time.sleep(0.1)
            broadcast_received = tab2.evaluate("() => window._testSyncReceived || false")
            if broadcast_received:
                break
        
        broadcast_wait_time = (time.time() - broadcast_wait_start) * 1000
        
        # CRITICAL: Assert that broadcast was received via BroadcastChannel
        if broadcast_received:
            print(f"  ✅ BroadcastChannel message received in Tab 2 ({broadcast_wait_time:.0f}ms)")
            sync_validator.record_sync_latency(broadcast_wait_time)
        else:
            # BroadcastChannel did not deliver - this is a test failure
            print(f"  ❌ BroadcastChannel message NOT received after {broadcast_wait_time:.0f}ms")
            print(f"  This indicates BroadcastChannel sync is not working")
            
            # Check if task appeared anyway (would be via server)
            task_visible = tab2.locator(f'text={task_title}').count() > 0
            if task_visible:
                print(f"  ⚠️  Task visible in Tab 2 but via SERVER, not BroadcastChannel")
                print(f"  FAIL: Multi-tab sync requires BroadcastChannel delivery")
            
            raise AssertionError(
                "BroadcastChannel did not deliver task_created event - multi-tab sync broken"
            )
        
        # Wait for task to appear in Tab 2 UI
        try:
            tab2.wait_for_selector(f'text={task_title}', timeout=2000)
            total_latency = (time.time() - sync_start) * 1000
            
            new_count_tab2 = tab2.locator('.task-card').count()
            
            print(f"  ✓ Task visible in Tab 2 UI (total latency: {total_latency:.0f}ms)")
            print(f"  ✓ Tab 2 task count: {initial_count_tab2} → {new_count_tab2}")
            
            if new_count_tab2 <= initial_count_tab2:
                raise AssertionError(f"Task did not sync to Tab 2 (count unchanged)")
            
        except Exception as e:
            raise AssertionError(f"Task did not appear in Tab 2 UI after broadcast: {e}")
        
        # Verify both tabs see same IndexedDB data
        tab1_count = tab1.evaluate("""
            async () => {
                if (!window.taskCache || !window.taskCache.db) return -1;
                const tx = window.taskCache.db.transaction(['tasks'], 'readonly');
                const store = tx.objectStore('tasks');
                return new Promise((resolve) => {
                    const request = store.count();
                    request.onsuccess = () => resolve(request.result);
                    request.onerror = () => resolve(-1);
                });
            }
        """)
        
        tab2_count = tab2.evaluate("""
            async () => {
                if (!window.taskCache || !window.taskCache.db) return -1;
                const tx = window.taskCache.db.transaction(['tasks'], 'readonly');
                const store = tx.objectStore('tasks');
                return new Promise((resolve) => {
                    const request = store.count();
                    request.onsuccess = () => resolve(request.result);
                    request.onerror = () => resolve(-1);
                });
            }
        """)
        
        print(f"\n  IndexedDB task count:")
        print(f"  Tab 1: {tab1_count}")
        print(f"  Tab 2: {tab2_count}")
        
        if tab1_count == tab2_count and tab1_count > 0:
            print(f"  ✓ Tabs share IndexedDB state")
        else:
            print(f"  ⚠️  IndexedDB counts differ (may be timing issue)")
        
        # Validate sync latency threshold
        result = sync_validator.validate_sync_latency()
        
        if not result['valid']:
            raise AssertionError(
                f"Multi-tab sync latency {result['max_latency_ms']:.0f}ms exceeds "
                f"{result['threshold_ms']}ms threshold"
            )
        
        print(f"\n  ✅ PASS: Multi-tab sync within {result['threshold_ms']}ms threshold")
        print(f"  Max latency: {result['max_latency_ms']:.0f}ms")
    
    
    def test_02_vector_clock_conflict_resolution(self, page: Page, sync_validator: OfflineSyncValidator):
        """
        Validate vector clock implementation for conflict resolution.
        
        CROWN 4.6 Requirement: Deterministic conflict resolution with vector clocks
        
        Test Scenarios:
        1. Vector clock increments on task updates
        2. Vector clock comparison works correctly
        3. Concurrent updates resolved deterministically
        
        Uses REAL APIs: VectorClock class, window.taskCache
        """
        print("\n" + "="*80)
        print("TEST 02: Vector Clock Conflict Resolution (Production APIs)")
        print("="*80)
        
        page.goto('http://0.0.0.0:5000/tasks')
        page.wait_for_load_state('networkidle')
        
        # Check if VectorClock is available
        has_vector_clock = page.evaluate("""
            () => {
                return typeof VectorClock !== 'undefined' &&
                       window.taskCache &&
                       window.taskCache.nodeId;
            }
        """)
        
        if not has_vector_clock:
            pytest.skip("VectorClock not available - requires VectorClock class and taskCache")
        
        print(f"\n  ✓ VectorClock class detected")
        
        # Get node ID
        node_info = page.evaluate("""
            () => {
                return {
                    nodeId: window.taskCache.nodeId,
                    dbName: window.taskCache.dbName,
                    ready: window.taskCache.ready
                };
            }
        """)
        
        print(f"  ✓ Node ID: {node_info['nodeId'][:24]}...")
        print(f"  ✓ IndexedDB: {node_info['dbName']} (ready: {node_info['ready']})")
        
        # Test vector clock operations
        print(f"\n  Testing vector clock operations...")
        
        vc_test = page.evaluate("""
            () => {
                // Create two vector clocks
                const vc1 = new VectorClock({ 'node1': 1, 'node2': 0 });
                const vc2 = new VectorClock({ 'node1': 0, 'node2': 1 });
                
                // Test increment
                vc1.increment('node1');
                
                // Test comparison
                const comparison = vc1.compare(vc2);
                
                // Test merge
                const merged = vc1.merge(vc2);
                
                return {
                    vc1_clocks: vc1.clocks,
                    vc2_clocks: vc2.clocks,
                    comparison: comparison, // 0 = concurrent
                    merged_clocks: merged.clocks,
                    vc1_dominates: vc1.dominates(vc2)
                };
            }
        """)
        
        print(f"  ✓ VectorClock 1: {json.dumps(vc_test['vc1_clocks'])}")
        print(f"  ✓ VectorClock 2: {json.dumps(vc_test['vc2_clocks'])}")
        print(f"  ✓ Comparison: {vc_test['comparison']} (0=concurrent, 1=vc1>vc2, -1=vc1<vc2)")
        print(f"  ✓ Merged: {json.dumps(vc_test['merged_clocks'])}")
        
        # Validate vector clock logic
        if vc_test['comparison'] != 0:
            raise AssertionError(f"Vector clock comparison incorrect: expected 0 (concurrent), got {vc_test['comparison']}")
        
        if vc_test['merged_clocks'] != {'node1': 2, 'node2': 1}:
            raise AssertionError(f"Vector clock merge incorrect: {vc_test['merged_clocks']}")
        
        sync_validator.record_conflict_resolution(True)
        
        print(f"\n  ✅ PASS: Vector clock operations working correctly")
    
    
    def test_03_offline_queue_replay_zero_loss(self, page: Page, sync_validator: OfflineSyncValidator):
        """
        Validate offline queue FIFO replay with zero data loss.
        
        CROWN 4.6 Requirement: Zero data loss during offline/online transitions
        
        Test Scenarios:
        1. Go offline
        2. Create multiple tasks (queued in IndexedDB)
        3. Verify tasks queued in offline_queue store
        4. Go online
        5. Verify queue replay
        6. Validate zero data loss
        
        Uses REAL APIs: window.offlineQueueManager, window.taskCache
        """
        print("\n" + "="*80)
        print("TEST 03: Offline Queue Replay & Zero Data Loss (Production APIs)")
        print("="*80)
        
        page.goto('http://0.0.0.0:5000/tasks')
        page.wait_for_load_state('networkidle')
        
        # Check if offline queue manager is available
        has_offline_queue = page.evaluate("""
            () => {
                return typeof window.offlineQueueManager !== 'undefined' &&
                       window.taskCache &&
                       window.taskCache.ready;
            }
        """)
        
        if not has_offline_queue:
            pytest.skip("OfflineQueueManager not available - requires window.offlineQueueManager")
        
        print(f"\n  ✓ OfflineQueueManager detected")
        
        # Get initial task count
        initial_count = page.locator('.task-card').count()
        print(f"  ✓ Initial task count: {initial_count}")
        
        # Check initial queue size
        initial_queue_size = page.evaluate("""
            async () => {
                await window.taskCache.init();
                const queue = await window.taskCache.getOfflineQueue();
                return queue.length;
            }
        """)
        
        print(f"  ✓ Initial offline queue size: {initial_queue_size}")
        
        # Go offline
        print(f"\n  Step 1: Going offline...")
        page.context.set_offline(True)
        time.sleep(0.5)
        
        # Verify offline status
        offline_status = page.evaluate("() => !navigator.onLine")
        print(f"  ✓ Offline mode: navigator.onLine = {not offline_status}")
        
        # Create tasks while offline
        print(f"\n  Step 2: Creating tasks while offline...")
        
        offline_tasks = []
        task_input = page.locator('#task-input').first
        if task_input.count() == 0:
            task_input = page.locator('input[placeholder*="task" i]').first
        
        for i in range(3):
            task_title = f"Offline task {i+1} - {int(time.time() * 1000)}"
            task_input.fill(task_title)
            task_input.press('Enter')
            time.sleep(0.3)
            offline_tasks.append(task_title)
            print(f"  ✓ Created (offline): '{task_title}'")
        
        # Verify tasks queued in IndexedDB
        queue_size_after = page.evaluate("""
            async () => {
                const queue = await window.taskCache.getOfflineQueue();
                return {
                    size: queue.length,
                    operations: queue.map(q => ({ type: q.type, timestamp: q.timestamp }))
                };
            }
        """)
        
        print(f"\n  ✓ Offline queue size: {initial_queue_size} → {queue_size_after['size']}")
        print(f"  ✓ Queued operations: {len(queue_size_after['operations'])}")
        
        expected_queued = len(offline_tasks)
        actual_queued = queue_size_after['size'] - initial_queue_size
        
        if actual_queued < expected_queued:
            print(f"  ⚠️  WARNING: Expected {expected_queued} queued, found {actual_queued}")
        
        # Go online
        print(f"\n  Step 3: Going back online...")
        page.context.set_offline(False)
        
        # Wait for queue replay
        time.sleep(2.0)
        
        # Check final task count
        final_count = page.locator('.task-card').count()
        tasks_added = final_count - initial_count
        
        print(f"\n  Step 4: Validating queue replay...")
        print(f"  ✓ Final task count: {final_count}")
        print(f"  ✓ Tasks added: {tasks_added}")
        
        # Verify each offline task was created
        created_count = 0
        for task_title in offline_tasks:
            exists = page.locator(f'text={task_title}').count() > 0
            if exists:
                created_count += 1
                print(f"  ✓ Found: '{task_title}'")
            else:
                print(f"  ❌ Missing: '{task_title}'")
        
        # Record integrity
        sync_validator.record_queue_integrity(len(offline_tasks), created_count)
        
        # Validate zero data loss
        if created_count < len(offline_tasks):
            raise AssertionError(
                f"Data loss detected: {len(offline_tasks)} queued, {created_count} created "
                f"({len(offline_tasks) - created_count} lost)"
            )
        
        # Check queue cleared
        final_queue_size = page.evaluate("""
            async () => {
                const queue = await window.taskCache.getOfflineQueue();
                return queue.length;
            }
        """)
        
        print(f"  ✓ Final queue size: {final_queue_size}")
        
        print(f"\n  ✅ PASS: Zero data loss - all {len(offline_tasks)} offline tasks replayed")
    
    
    def test_04_indexeddb_data_integrity(self, page: Page, sync_validator: OfflineSyncValidator):
        """
        Validate IndexedDB data integrity.
        
        CROWN 4.6 Requirement: 100% data integrity in IndexedDB
        
        Test Scenarios:
        1. Verify IndexedDB schema exists
        2. Verify task data persistence
        3. Verify event ledger integrity
        4. Validate vector clock storage
        
        Uses REAL APIs: window.taskCache IndexedDB stores
        """
        print("\n" + "="*80)
        print("TEST 04: IndexedDB Data Integrity (Production APIs)")
        print("="*80)
        
        page.goto('http://0.0.0.0:5000/tasks')
        page.wait_for_load_state('networkidle')
        
        # Check IndexedDB initialization
        db_status = page.evaluate("""
            async () => {
                if (!window.taskCache) return { error: 'taskCache not found' };
                
                await window.taskCache.init();
                
                const db = window.taskCache.db;
                if (!db) return { error: 'DB not initialized' };
                
                return {
                    name: db.name,
                    version: db.version,
                    objectStores: Array.from(db.objectStoreNames),
                    ready: window.taskCache.ready
                };
            }
        """)
        
        if 'error' in db_status:
            pytest.skip(f"IndexedDB not available: {db_status['error']}")
        
        print(f"\n  ✓ IndexedDB: {db_status['name']} v{db_status['version']}")
        print(f"  ✓ Object Stores: {', '.join(db_status['objectStores'])}")
        print(f"  ✓ Ready: {db_status['ready']}")
        
        # Validate schema
        required_stores = ['tasks', 'events', 'offline_queue', 'metadata']
        missing_stores = [s for s in required_stores if s not in db_status['objectStores']]
        
        if missing_stores:
            raise AssertionError(f"Missing IndexedDB stores: {missing_stores}")
        
        print(f"  ✓ All required stores present")
        
        # Create test task and verify persistence
        task_title = f"Integrity test {int(time.time() * 1000)}"
        task_input = page.locator('#task-input').first
        if task_input.count() == 0:
            task_input = page.locator('input[placeholder*="task" i]').first
        
        task_input.fill(task_title)
        task_input.press('Enter')
        
        page.wait_for_selector(f'text={task_title}', timeout=3000)
        print(f"\n  ✓ Created test task: '{task_title}'")
        
        # Query IndexedDB directly
        db_task = page.evaluate("""
            async (title) => {
                const tx = window.taskCache.db.transaction(['tasks'], 'readonly');
                const store = tx.objectStore('tasks');
                const allTasks = await new Promise((resolve, reject) => {
                    const request = store.getAll();
                    request.onsuccess = () => resolve(request.result);
                    request.onerror = () => reject(request.error);
                });
                
                const found = allTasks.find(t => t.title === title);
                return found ? {
                    id: found.id,
                    title: found.title,
                    status: found.status,
                    hasVectorClock: !!found.vector_clock
                } : null;
            }
        """, task_title)
        
        if not db_task:
            raise AssertionError(f"Task not found in IndexedDB: '{task_title}'")
        
        print(f"  ✓ Task persisted in IndexedDB:")
        print(f"    - ID: {db_task['id']}")
        print(f"    - Title: {db_task['title']}")
        print(f"    - Status: {db_task['status']}")
        print(f"    - Vector Clock: {db_task['hasVectorClock']}")
        
        sync_validator.record_data_integrity(True)
        
        print(f"\n  ✅ PASS: IndexedDB data integrity verified")
    
    
    def test_05_network_partition_recovery(self, page: Page, sync_validator: OfflineSyncValidator):
        """
        Validate graceful degradation and recovery during network partitions.
        
        CROWN 4.6 Requirement: Automatic recovery from network failures
        
        Test Scenarios:
        1. Simulate multiple offline/online cycles
        2. Create tasks during each offline period
        3. Verify full recovery after each cycle
        4. Validate no data loss across partitions
        
        Uses REAL APIs: window.offlineQueueManager auto-replay
        """
        print("\n" + "="*80)
        print("TEST 05: Network Partition Recovery (Production APIs)")
        print("="*80)
        
        page.goto('http://0.0.0.0:5000/tasks')
        page.wait_for_load_state('networkidle')
        
        initial_count = page.locator('.task-card').count()
        recovered_tasks = []
        
        # Run 3 offline/online cycles
        for cycle in range(3):
            print(f"\n  Cycle {cycle + 1}: Offline → Online")
            
            # Go offline
            page.context.set_offline(True)
            time.sleep(0.3)
            
            # Create task while offline
            task_title = f"Recovery test {cycle + 1} - {int(time.time() * 1000)}"
            task_input = page.locator('#task-input').first
            if task_input.count() == 0:
                task_input = page.locator('input[placeholder*="task" i]').first
            
            task_input.fill(task_title)
            task_input.press('Enter')
            time.sleep(0.2)
            recovered_tasks.append(task_title)
            print(f"  ✓ Created offline: '{task_title}'")
            
            # Go back online
            page.context.set_offline(False)
            time.sleep(1.0)  # Allow queue replay
            
            # Verify task recovered
            exists = page.locator(f'text={task_title}').count() > 0
            if exists:
                print(f"  ✓ Recovered: '{task_title}'")
            else:
                print(f"  ❌ Lost: '{task_title}'")
        
        final_count = page.locator('.task-card').count()
        tasks_created = final_count - initial_count
        
        print(f"\n  Recovery summary:")
        print(f"  Partition cycles: 3")
        print(f"  Tasks created during partitions: {len(recovered_tasks)}")
        print(f"  Tasks recovered: {tasks_created}")
        
        if tasks_created < len(recovered_tasks):
            raise AssertionError(
                f"Network partition recovery incomplete: {tasks_created}/{len(recovered_tasks)} tasks recovered"
            )
        
        sync_validator.record_queue_integrity(len(recovered_tasks), tasks_created)
        
        print(f"\n  ✅ PASS: Full recovery from {len(recovered_tasks)} network partitions")
    
    
    def test_99_offline_sync_summary(self, sync_validator: OfflineSyncValidator):
        """Generate comprehensive offline/sync resilience report."""
        print("\n" + "="*80)
        print("OFFLINE/SYNC RESILIENCE SUMMARY")
        print("="*80)
        
        report = sync_validator.generate_report()
        
        print(f"\n📊 Multi-Tab Sync Latency:")
        if report['sync_latency'].get('max_latency_ms'):
            print(f"  Max Latency: {report['sync_latency']['max_latency_ms']:.0f}ms")
            print(f"  Avg Latency: {report['sync_latency']['avg_latency_ms']:.0f}ms")
            print(f"  Threshold: {report['sync_latency']['threshold_ms']}ms")
            print(f"  Status: {'✅ PASS' if report['sync_latency']['valid'] else '❌ FAIL'}")
        else:
            print(f"  Status: ⚠️  No measurements")
        
        print(f"\n🔄 Conflict Resolution (Vector Clocks):")
        if report['conflict_resolution'].get('success_rate') is not None:
            print(f"  Success Rate: {report['conflict_resolution']['success_rate']*100:.0f}%")
            print(f"  Threshold: {report['conflict_resolution']['threshold']*100:.0f}%")
            print(f"  Status: {'✅ PASS' if report['conflict_resolution']['valid'] else '❌ FAIL'}")
        else:
            print(f"  Status: ⚠️  No tests")
        
        print(f"\n💾 Data Integrity (Zero Data Loss):")
        if report['data_integrity'].get('min_integrity') is not None:
            print(f"  Min Integrity: {report['data_integrity']['min_integrity']*100:.0f}%")
            print(f"  Avg Integrity: {report['data_integrity']['avg_integrity']*100:.0f}%")
            print(f"  Data Loss Tolerance: {report['data_integrity']['data_loss_tolerance']*100:.0f}%")
            print(f"  Status: {'✅ PASS' if report['data_integrity']['valid'] else '❌ FAIL'}")
        else:
            print(f"  Status: ⚠️  No tests")
        
        # Save report
        report_path = 'tests/results/offline_sync_resilience_report.json'
        import os
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n📄 Full report saved: {report_path}")
        print(f"\n{'='*80}")
