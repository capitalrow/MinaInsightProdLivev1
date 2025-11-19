# Offline/Sync Resilience Testing Guide

**CROWN 4.6 Offline & Multi-Tab Synchronization Validation**

---

## Overview

This test suite validates the resilience and data integrity of Mina Tasks across offline scenarios, multi-tab synchronization, and network partitions. It ensures zero data loss and graceful degradation.

## Test Coverage

### 1. Multi-Tab BroadcastChannel Sync
**File:** `test_offline_sync_resilience.py::test_01_multi_tab_broadcast_sync`

**What it tests:**
- Task creation in Tab 1 syncs to Tab 2
- Task updates in Tab 2 sync to Tab 1
- Task deletion syncs across tabs
- Sync latency meets <500ms threshold

**How it works:**
- Uses two independent Playwright browser contexts
- Measures sync latency for each operation
- Validates p95 latency <500ms

**Requirements:**
```javascript
// Production code must implement BroadcastChannel
window.taskStore.broadcastSync = new BroadcastChannel('mina-tasks-sync');
```

---

### 2. Conflict Resolution with Vector Clocks
**File:** `test_offline_sync_resilience.py::test_02_conflict_resolution_vector_clocks`

**What it tests:**
- Concurrent updates from multiple tabs
- Vector clock comparison
- Conflict merge or last-write-wins strategy
- 100% successful conflict resolution

**How it works:**
- Creates task visible in both tabs
- Simultaneous updates from Tab 1 (priority) and Tab 2 (description)
- Validates eventual consistency

**Requirements:**
```javascript
window.taskStore.vectorClock = {
  nodeId: '...',
  counter: 0
};

window.taskStore.resolveConflict = (localVersion, remoteVersion) => {
  // Merge or choose winner based on vector clocks
  return mergedVersion;
};
```

---

### 3. Offline Queue Replay & Zero Data Loss
**File:** `test_offline_sync_resilience.py::test_03_offline_queue_replay_zero_loss`

**What it tests:**
- Tasks created while offline are queued
- Queue replays in FIFO order when back online
- Zero data loss (100% integrity)

**How it works:**
- Simulates offline mode using `page.context.set_offline(True)`
- Creates tasks while offline
- Validates all tasks appear when back online

**Requirements:**
```javascript
window.taskStore.offlineQueue = [];

window.taskStore.queueOfflineAction = (action) => {
  offlineQueue.push(action);
};

window.taskStore.getOfflineQueueSize = () => {
  return offlineQueue.length;
};
```

---

### 4. Checksum Data Integrity
**File:** `test_offline_sync_resilience.py::test_04_checksum_data_integrity`

**What it tests:**
- Checksums generated for all tasks
- Checksums validated on retrieval
- 100% integrity (no corruption)

**How it works:**
- Creates tasks and retrieves with checksums
- Recalculates checksums and validates match
- Detects any data corruption

**Requirements:**
```javascript
window.taskStore.calculateChecksum = (taskData) => {
  // Calculate SHA-256 or similar
  return checksum;
};

window.taskStore.validateChecksum = (task) => {
  const calculated = calculateChecksum(task);
  return calculated === task.checksum;
};
```

---

### 5. Network Partition Recovery
**File:** `test_offline_sync_resilience.py::test_05_network_partition_recovery`

**What it tests:**
- Graceful degradation during network issues
- Automatic recovery when network restored
- No data loss across multiple offline/online cycles

**How it works:**
- Cycles offline/online 3 times
- Creates tasks during each offline period
- Validates full recovery

---

## Running the Tests

### Run all offline/sync tests:
```bash
pytest tests/crown46/test_offline_sync_resilience.py -v -s
```

### Run specific test:
```bash
pytest tests/crown46/test_offline_sync_resilience.py::TestCROWN46OfflineSyncResilience::test_01_multi_tab_broadcast_sync -v
```

### Generate JSON report:
```bash
pytest tests/crown46/test_offline_sync_resilience.py -v
# Report saved to: tests/results/offline_sync_resilience_report.json
```

---

## Production Code Requirements

### 1. BroadcastChannel API
```javascript
// Initialize BroadcastChannel for multi-tab sync
const syncChannel = new BroadcastChannel('mina-tasks-sync');

syncChannel.onmessage = (event) => {
  const { action, taskId, data } = event.data;
  
  switch (action) {
    case 'task_created':
      // Add task to local store
      break;
    case 'task_updated':
      // Update task in local store
      break;
    case 'task_deleted':
      // Remove task from local store
      break;
  }
};

// Broadcast changes
function broadcastChange(action, taskId, data) {
  syncChannel.postMessage({ action, taskId, data });
}
```

### 2. Vector Clock Implementation
```javascript
// Vector clock structure
const vectorClock = {
  nodeId: generateUniqueId(),  // Unique per tab/client
  counter: 0,
  clocks: {}  // Map of nodeId -> counter
};

// Increment on each update
function incrementVectorClock() {
  vectorClock.counter++;
  vectorClock.clocks[vectorClock.nodeId] = vectorClock.counter;
}

// Compare vector clocks
function compareVectorClocks(v1, v2) {
  // Returns: 'before', 'after', 'concurrent', 'equal'
  // Implementation depends on your conflict resolution strategy
}

// Resolve conflicts
function resolveConflict(localTask, remoteTask) {
  const comparison = compareVectorClocks(
    localTask.vector_clock,
    remoteTask.vector_clock
  );
  
  if (comparison === 'concurrent') {
    // Merge strategy or last-write-wins
    return mergeStrategy(localTask, remoteTask);
  }
  
  return comparison === 'after' ? localTask : remoteTask;
}
```

### 3. Offline Queue
```javascript
// Offline queue for actions
const offlineQueue = [];

// Queue action while offline
function queueOfflineAction(action) {
  offlineQueue.push({
    action,
    timestamp: Date.now(),
    id: generateUniqueId()
  });
  
  // Persist to IndexedDB
  saveOfflineQueueToStorage(offlineQueue);
}

// Replay queue when back online
async function replayOfflineQueue() {
  const queue = [...offlineQueue];
  
  for (const item of queue) {
    try {
      await executeAction(item.action);
      // Remove from queue on success
      removeFromQueue(item.id);
    } catch (error) {
      console.error('Replay failed:', error);
      // Keep in queue for retry
    }
  }
}

// Listen for online event
window.addEventListener('online', () => {
  replayOfflineQueue();
});
```

### 4. Checksum Calculation
```javascript
// Calculate checksum for task data
async function calculateChecksum(taskData) {
  // Normalize data (remove volatile fields)
  const normalized = {
    id: taskData.id,
    title: taskData.title,
    description: taskData.description,
    priority: taskData.priority,
    // ... other stable fields
  };
  
  const jsonString = JSON.stringify(normalized);
  
  // Use Web Crypto API for SHA-256
  const encoder = new TextEncoder();
  const data = encoder.encode(jsonString);
  const hashBuffer = await crypto.subtle.digest('SHA-256', data);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
  
  return hashHex;
}

// Validate task integrity
async function validateTaskIntegrity(task) {
  if (!task.checksum) {
    return false;
  }
  
  const calculated = await calculateChecksum(task);
  return calculated === task.checksum;
}
```

---

## Thresholds & Success Criteria

| Metric | Threshold | Test |
|--------|-----------|------|
| Multi-tab sync latency | <500ms | test_01 |
| Conflict resolution rate | 100% | test_02 |
| Data loss tolerance | 0% (zero loss) | test_03 |
| Checksum match rate | 100% | test_04 |
| Network recovery rate | 100% | test_05 |

---

## Troubleshooting

### Issue: "BroadcastChannel sync not detected"
**Solution:** Implement BroadcastChannel in production code:
```javascript
window.taskStore.broadcastSync = new BroadcastChannel('mina-tasks-sync');
```

### Issue: "Vector clock conflict resolution not detected"
**Solution:** Implement vector clock system:
```javascript
window.taskStore.vectorClock = { nodeId: '...', counter: 0 };
window.taskStore.resolveConflict = (local, remote) => { /* ... */ };
```

### Issue: "Offline queue not detected"
**Solution:** Implement offline queue:
```javascript
window.taskStore.offlineQueue = [];
window.taskStore.queueOfflineAction = (action) => { /* ... */ };
```

### Issue: "Checksum validation not detected"
**Solution:** Implement checksum functions:
```javascript
window.taskStore.calculateChecksum = (data) => { /* ... */ };
window.taskStore.validateChecksum = (task) => { /* ... */ };
```

### Issue: Tests fail with "Multi-tab sync latency exceeds threshold"
**Possible causes:**
1. Network latency too high
2. Inefficient BroadcastChannel handling
3. Heavy rendering blocking sync

**Solution:** Optimize BroadcastChannel message handling and use debouncing for rapid updates.

### Issue: "Data loss detected" after offline replay
**Possible causes:**
1. Offline queue not persisted to IndexedDB
2. Queue replay logic has errors
3. Server rejects offline changes

**Solution:**
1. Persist queue to IndexedDB immediately
2. Add retry logic for failed replays
3. Validate offline changes before replay

---

## CI/CD Integration

### GitHub Actions Example
```yaml
- name: Run Offline/Sync Resilience Tests
  run: |
    pytest tests/crown46/test_offline_sync_resilience.py \
      --html=offline_sync_report.html \
      --self-contained-html \
      -v

- name: Check Data Loss Threshold
  run: |
    # Fail build if any data loss detected
    python -c "
    import json
    with open('tests/results/offline_sync_resilience_report.json') as f:
      report = json.load(f)
      integrity = report['data_integrity']
      if integrity['min_integrity'] < 1.0:
        raise Exception(f'Data loss: {integrity}')
    "
```

---

## Best Practices

### 1. Multi-Tab Sync
- Use BroadcastChannel for efficient cross-tab communication
- Debounce rapid updates to avoid flooding
- Include operation type in messages (create/update/delete)

### 2. Conflict Resolution
- Implement vector clocks for accurate causality tracking
- Choose merge strategy vs last-write-wins based on use case
- Log conflicts for debugging

### 3. Offline Queue
- Persist queue to IndexedDB (survives tab closure)
- Use FIFO ordering for replay
- Add retry logic with exponential backoff
- Include operation IDs to prevent duplicates

### 4. Data Integrity
- Calculate checksums on write
- Validate checksums on read
- Use SHA-256 for cryptographic strength
- Exclude volatile fields (timestamps, counters)

### 5. Network Recovery
- Listen for `online` event
- Implement exponential backoff for retries
- Show sync status to user
- Handle partial failures gracefully

---

## Architecture Diagram

```
┌─────────────┐         BroadcastChannel          ┌─────────────┐
│   Tab 1     │◄──────────────────────────────────►│   Tab 2     │
│             │         (sync <500ms)              │             │
│ TaskStore   │                                    │ TaskStore   │
│ VectorClock │                                    │ VectorClock │
└──────┬──────┘                                    └──────┬──────┘
       │                                                  │
       │ offline                                          │ offline
       ▼                                                  ▼
┌──────────────┐                                  ┌──────────────┐
│ OfflineQueue │                                  │ OfflineQueue │
│ (IndexedDB)  │                                  │ (IndexedDB)  │
└──────┬───────┘                                  └──────┬───────┘
       │                                                  │
       │ online → replay                                  │
       ▼                                                  ▼
┌────────────────────────────────────────────────────────────────┐
│                         Server                                  │
│                  (conflict resolution)                          │
└────────────────────────────────────────────────────────────────┘
```

---

## Next Steps

After implementing offline/sync features:
1. Run tests to validate implementation
2. Monitor sync latency in production
3. Track conflict resolution success rate
4. Set up alerts for data integrity issues
5. Implement metrics dashboard

---

**Questions?** See main testing documentation in `tests/crown46/README.md`
