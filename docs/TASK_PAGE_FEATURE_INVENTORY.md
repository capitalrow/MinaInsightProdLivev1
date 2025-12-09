# Task Page Feature Inventory
## Complete End-to-End Flow Documentation for Debugging

**Last Updated:** December 2025  
**Page:** `/dashboard/tasks`

---

## Table of Contents
1. [Core CRUD Operations](#core-crud-operations)
2. [Task Menu Actions (13 Actions)](#task-menu-actions)
3. [Tab Filtering](#tab-filtering)
4. [Keyboard Shortcuts](#keyboard-shortcuts)
5. [Drag & Drop Reordering](#drag-and-drop-reordering)
6. [Inline Editing](#inline-editing)
7. [Background Sync Systems](#background-sync-systems)
8. [Multi-Tab Sync](#multi-tab-sync)
9. [WebSocket Events](#websocket-events)
10. [Task Action Lock System](#task-action-lock-system)

---

## Core CRUD Operations

### 1. CREATE TASK

| Aspect | Details |
|--------|---------|
| **User Interaction** | Click "New Task" button OR press `N` key |
| **Frontend Handler** | `task-page-master-init.js` → `initNewTaskButton()` |
| **OptimisticUI Method** | `window.optimisticUI.createTask(taskData)` |
| **API Endpoint** | `POST /api/tasks/` |
| **Backend Function** | `routes/api_tasks.py` → `create_task()` |
| **Expected Outcome** | Task appears in DOM immediately, syncs to server, temp ID replaced with real ID |
| **Console Logs** | `[Checkbox] CLICK`, `[UpdateTask] START`, `[TaskActionLock] Acquired lock` |

**Flow:**
```
User clicks "New Task" 
  → task-page-master-init.js dispatches 'task:create-modal-open'
  → Modal opens for task input
  → User fills form, clicks Save
  → optimisticUI.createTask(taskData)
    → Generates temp ID (ulid)
    → Adds optimistic card to DOM
    → Saves to IndexedDB
    → Calls _syncToServer('create')
      → WebSocket emit 'task_create' or HTTP POST fallback
  → Server returns real ID
  → _reconcileSuccess() replaces temp ID with real ID
  → _finalizeCreate() clears syncing badge
```

---

### 2. COMPLETE TASK (Checkbox Toggle)

| Aspect | Details |
|--------|---------|
| **User Interaction** | Click checkbox on task card |
| **Frontend Handler** | `task-page-master-init.js` → `initCheckboxHandlers()` (line 165) |
| **OptimisticUI Method** | `window.optimisticUI.toggleTaskStatus(taskId)` |
| **API Endpoint** | `PUT /api/tasks/<id>` or WebSocket `task_update` |
| **Backend Function** | `routes/api_tasks.py` → `update_task(task_id)` |
| **Expected Outcome** | Checkbox checked, strikethrough, confetti animation, persists to DB |
| **Console Logs** | See detailed flow below |

**Detailed Flow with Log Points:**
```
1. [Checkbox] CLICK - Task {id}, checked: {bool}
   └── task-page-master-init.js line 186-188
   
2. [Checkbox] Prepared updates: {status, completed_at}
   └── task-page-master-init.js line 198
   
3. [Checkbox] Calling optimisticUI.toggleTaskStatus({id})
   └── task-page-master-init.js line 203
   
4. [ToggleStatus] START - Task {id}
   └── task-optimistic-ui.js line 644
   
5. [ToggleStatus] Task {id}: {oldStatus} → {newStatus}
   └── task-optimistic-ui.js line 654
   
6. [UpdateTask] START - Task {id}
   └── task-optimistic-ui.js line 332
   
7. [TaskActionLock] Acquired lock {lockId} for task {id}
   └── task-action-lock.js line 41
   
8. [UpdateTask] Lock acquired: {lockId}
   └── task-optimistic-ui.js line 340
   
9. [UpdateTask] Current task state: {id, status}
   └── task-optimistic-ui.js line 353
   
10. DOM Updated immediately (optimistic)
    └── _updateTaskInDOM()
    
11. IndexedDB cache updated
    └── cache.saveTask()
    
12. [UpdateTask] Calling _syncToServer()
    └── task-optimistic-ui.js line 418
    
13. WebSocket emit or HTTP PUT /api/tasks/{id}
    └── _syncToServer() or _syncViaHTTP()
    
14. Server processes update, commits to DB
    └── routes/api_tasks.py update_task()
    
15. Server returns updated task
    
16. [Reconcile] Released action lock {lockId}
    └── _reconcileSuccess() line 1681
    
17. [Checkbox] Task {id} toggle returned: {status}
    └── task-page-master-init.js line 205
```

**What Can Go Wrong:**
- Lock not acquired → sync systems overwrite optimistic update
- API fails → _reconcileFailure() rolls back and shows error
- WebSocket disconnected → HTTP fallback used
- Background sync (IdleSync/ReconciliationCycle) runs before lock acquired → state reverts

---

### 3. UPDATE TASK

| Aspect | Details |
|--------|---------|
| **User Interaction** | Various: edit title, change priority, set due date, assign, etc. |
| **Frontend Handler** | `task-optimistic-ui.js` → `updateTask(taskId, updates)` |
| **API Endpoint** | `PUT /api/tasks/<id>` |
| **Backend Function** | `routes/api_tasks.py` → `update_task(task_id)` |
| **Expected Outcome** | Field updated in DOM, cache, and server |
| **Console Logs** | `[UpdateTask] START`, `[TaskActionLock] Acquired`, `[UpdateTask] _syncToServer` |

---

### 4. DELETE TASK (Soft Delete)

| Aspect | Details |
|--------|---------|
| **User Interaction** | Task menu → Delete, or swipe gesture |
| **Frontend Handler** | `task-optimistic-ui.js` → `deleteTask(taskId)` |
| **API Endpoint** | `PUT /api/tasks/<id>` with `deleted_at` timestamp |
| **Backend Function** | `routes/api_tasks.py` → `update_task()` (soft delete) |
| **Expected Outcome** | Task removed from view, 15s undo toast, preserved in DB with deleted_at |
| **Console Logs** | `[DeleteTask] Soft-deleted in cache`, `Undo toast shown` |

---

## Task Menu Actions

The task menu provides **13 actions** accessible via the 3-dot menu on each task card.

### Action Routing
All actions flow through: `TaskMenuController.executeAction(action, taskId)`
Located in: `static/js/task-menu-controller.js`

| # | Action | Menu Label | Handler Method | OptimisticUI Method | API Endpoint |
|---|--------|------------|----------------|---------------------|--------------|
| 1 | `view-details` | View Details | `handleViewDetails()` | N/A (navigation) | N/A |
| 2 | `edit` / `edit-title` | Edit Title | `handleEdit()` | `updateTask({title})` | PUT /api/tasks/{id} |
| 3 | `toggle-status` | Complete/Uncomplete | `handleToggleStatus()` | `toggleTaskStatus()` | PUT /api/tasks/{id} |
| 4 | `priority` | Set Priority | `handlePriority()` | `updatePriority()` | PUT /api/tasks/{id} |
| 5 | `due-date` | Set Due Date | `handleDueDate()` | `updateTask({due_date})` | PUT /api/tasks/{id} |
| 6 | `assign` | Assign | `handleAssign()` | `updateTask({assigned_to_id})` | PUT /api/tasks/{id} |
| 7 | `labels` | Labels | `handleLabels()` | `addLabel()` / `removeLabel()` | PUT /api/tasks/{id} |
| 8 | `duplicate` | Duplicate | `handleDuplicate()` | `duplicateTask()` | POST /api/tasks/ |
| 9 | `snooze` | Snooze | `handleSnooze()` | `snoozeTask()` | PUT /api/tasks/{id} |
| 10 | `merge` | Merge | `handleMerge()` | `mergeTask()` | POST /api/tasks/{id}/merge |
| 11 | `jump-to-transcript` | Jump to Transcript | `handleJumpToTranscript()` | N/A | GET /api/tasks/{id}/context |
| 12 | `archive` | Archive | `handleArchive()` | `archiveTask()` | PUT /api/tasks/{id} |
| 13 | `delete` | Delete | `handleDelete()` | `deleteTask()` | PUT /api/tasks/{id} |

### Menu Action Flow
```
User clicks 3-dot menu
  → task-actions-menu.js shows dropdown
  → User clicks action item
  → Event: 'task:menu-action' with {action, taskId}
  → TaskMenuController.executeAction(action, taskId)
    → Dispatches to appropriate handler method
    → Handler calls OptimisticUI method
    → OptimisticUI updates DOM + cache + syncs to server
  → Toast confirmation shown
```

---

## Tab Filtering

| Tab | Filter | Shows |
|-----|--------|-------|
| **All** | No filter | All non-deleted tasks |
| **Active** | `status != 'completed' AND status != 'archived'` | Incomplete tasks |
| **Archived** | `status == 'archived'` | Archived tasks |

### Tab Click Flow
```
User clicks tab (All/Active/Archived)
  → task-page-master-init.js → initFilterTabs() line 558
  → Updates URL: ?filter={value}
  → Calls window.taskSearchSort.setFilter(filter)
  → DOM filtering via CSS class visibility
  → TaskStateStore updates activeFilter
  → Tab counters update from TaskStateStore
```

**Files Involved:**
- `task-page-master-init.js` - Tab click handlers
- `task-search-sort.js` - Filter application
- `task-state-store.js` - Counter source of truth

---

## Keyboard Shortcuts

| Key | Action | Handler | Global? |
|-----|--------|---------|---------|
| `N` | Create new task | `_handleNewTask()` | Yes |
| `Cmd+K` / `Ctrl+K` | Open command palette | `_handleCommandPalette()` | Yes |
| `Cmd+Enter` / `Ctrl+Enter` | Toggle task completion | `_handleQuickComplete()` | No (needs selection) |
| `S` | Snooze selected task | `_handleSnooze()` | No |
| `Escape` | Close dialogs/menus | `_handleEscape()` | Yes |
| `↑` / `↓` | Navigate tasks | `_handleNavigation()` | No |
| `/` | Focus search input | `_handleSearch()` | Yes |
| `?` | Show shortcuts help | `_handleHelp()` | Yes |

**File:** `static/js/task-keyboard-shortcuts.js`

---

## Drag and Drop Reordering

| Aspect | Details |
|--------|---------|
| **User Interaction** | Drag task card by handle, drop in new position |
| **Frontend Handler** | `task-drag-drop.js` |
| **API Endpoint** | `POST /api/tasks/reorder` |
| **Backend Function** | `routes/api_tasks.py` → `reorder_tasks()` |
| **Expected Outcome** | Task moves visually, order_index updated in DB |

**Flow:**
```
User starts dragging task card
  → task-drag-drop.js captures dragstart
  → Visual placeholder shown
  → User drops in new position
  → Calculate new order_index based on neighbors
  → optimisticUI.updateTask(taskId, {order_index})
  → POST /api/tasks/reorder with task_ids array
  → Server updates order_index for affected tasks
```

---

## Inline Editing

| Feature | Trigger | Handler |
|---------|---------|---------|
| Title edit | Double-click title OR menu Edit | `task-inline-editing.js` → `enableTitleEdit()` |
| Description edit | Click description area | `task-inline-editing.js` → `enableDescriptionEdit()` |

**Flow:**
```
User double-clicks task title
  → task-inline-editing.js detects dblclick
  → Creates input field, hides title span
  → User types new value
  → On blur or Enter:
    → optimisticUI.updateTask(taskId, {title: newValue})
    → Input removed, title span restored with new value
```

---

## Background Sync Systems

### 1. IdleSync (30-second interval)

| Aspect | Details |
|--------|---------|
| **File** | `static/js/task-idle-sync.js` |
| **Interval** | 30 seconds (when user idle) |
| **Purpose** | Fetch latest tasks from server, update cache |
| **Lock Check** | `window.taskActionLock.shouldBlockSync()` at line 167 |

**Flow:**
```
Every 30 seconds (if user inactive):
  → Check taskActionLock.shouldBlockSync()
    → If blocked: Skip sync, log "[Idle Sync] Skipping - action lock active"
    → If allowed: Proceed
  → GET /api/tasks/
  → Update IndexedDB cache with server data
  → Reconcile DOM if no active edits
```

### 2. ReconciliationCycle (30-second interval)

| Aspect | Details |
|--------|---------|
| **File** | `static/js/reconciliation-cycle.js` |
| **Interval** | 30 seconds |
| **Purpose** | ETag-based drift detection, reconcile if server data changed |
| **Lock Check** | `window.taskActionLock.shouldBlockSync()` at line 86 |

**Flow:**
```
Every 30 seconds:
  → Check taskActionLock.shouldBlockSync()
    → If blocked: Skip cycle, log "[Reconciliation] Skipping cycle - action lock active"
    → If allowed: Proceed
  → HEAD /api/tasks/stats, /api/meetings/recent, /api/analytics/dashboard
  → Compare ETags
  → If changed: Fetch fresh data, update cache/DOM
```

---

## Multi-Tab Sync

| Aspect | Details |
|--------|---------|
| **File** | `static/js/task-multi-tab-sync.js` |
| **Mechanism** | BroadcastChannel API |
| **Channel** | `mina_sync_default` |

**Events Broadcast:**
- `TASK_CREATE` - New task created
- `TASK_UPDATE` - Task modified
- `TASK_DELETE` - Task deleted
- `full_sync` - Tab connected/disconnected

**Flow:**
```
Tab A: User completes task
  → optimisticUI.updateTask()
  → broadcastSync.broadcast('TASK_UPDATE', {taskId, changes})
  
Tab B: Receives broadcast
  → Updates local cache
  → Updates DOM to match
```

---

## WebSocket Events

**Namespace:** `/tasks`  
**File (Client):** `static/js/task-websocket-handlers.js`  
**File (Server):** `routes/tasks_websocket.py`

| Event | Direction | Purpose |
|-------|-----------|---------|
| `task_create` | Client → Server | Create new task |
| `task_update` | Client → Server | Update existing task |
| `task_delete` | Client → Server | Delete task |
| `task_created` | Server → Client | Broadcast new task to workspace |
| `task_updated` | Server → Client | Broadcast task update to workspace |
| `task_deleted` | Server → Client | Broadcast task deletion to workspace |
| `bootstrap` | Server → Client | Initial task list on connect |
| `request_replay` | Client → Server | Request missed events |

---

## Task Action Lock System

**File:** `static/js/task-action-lock.js`  
**Purpose:** Prevent background sync systems from overwriting optimistic UI updates during active user operations.

### How It Works

```javascript
// When user clicks checkbox:
lockId = window.taskActionLock.acquire(taskId, 'update:status,completed_at');
// Lock is held for 3 seconds OR until server confirms

// Background sync systems check before syncing:
if (window.taskActionLock.shouldBlockSync()) {
    return; // Skip this sync cycle
}

// On server success/failure:
window.taskActionLock.release(lockId);
```

### Lock States

| State | Meaning |
|-------|---------|
| `_locks.size > 0` | Active operations in progress |
| `elapsed < _globalLockDuration` | Within 3-second protection window |
| `shouldBlockSync() = true` | Sync systems must wait |

### Console Logs

```
[TaskActionLock] Acquired lock lock_xxx for task 123 (update:status)
[TaskActionLock] 🔒 Sync BLOCKED - 1 active locks, 500ms since last action
[TaskActionLock] 📋 Active locks: Task 123: update:status
[TaskActionLock] Released lock lock_xxx for task 123
[TaskActionLock] ✅ Sync ALLOWED - 3500ms since last action (threshold: 3000ms)
```

---

## Complete Logging Reference

All features now have comprehensive end-to-end logging with consistent prefixes:

### Frontend Console Log Prefixes
| Prefix | Source File | Feature |
|--------|-------------|---------|
| `[Checkbox]` | task-page-master-init.js | Checkbox click handling |
| `[ToggleStatus]` | task-optimistic-ui.js | Status toggle flow |
| `[UpdateTask]` | task-optimistic-ui.js | Task update operations |
| `[TaskActionLock]` | task-action-lock.js | Lock acquire/release/block |
| `[Reconcile]` | task-optimistic-ui.js | Server reconciliation |
| `[Idle Sync]` | task-idle-sync.js | 30-second background sync |
| `[Reconciliation]` | reconciliation-cycle.js | ETag drift detection |
| `[FilterTabs]` | task-page-master-init.js | Tab switching |
| `[SearchSort]` | task-search-sort.js | Filter/sort operations |
| `[Keyboard]` | task-keyboard-shortcuts.js | Keyboard shortcuts |
| `[DragDrop]` | task-drag-drop.js | Drag and drop reordering |
| `[InlineEdit]` | task-inline-editing.js | Inline title/field editing |
| `[Menu]` | task-page-master-init.js | Menu action events |
| `[TaskMenuController]` | task-menu-controller.js | Menu action execution |
| `[NewTask]` | task-page-master-init.js | Task creation |
| `[MasterInit]` | task-page-master-init.js | Page initialization |

### Backend Server Log Prefixes
| Prefix | Source File | Feature |
|--------|-------------|---------|
| `[API]` | routes/api_tasks.py | All task API endpoints |

### Log Level Guide
- ✅ = Success/completion
- ❌ = Error/failure
- 📥 = Incoming request
- 📤 = Outgoing request/API call
- 📝 = Data/payload info
- 🔄 = State transition
- 🔒 = Lock blocked
- ⌨️ = Keyboard input
- 🎯 = Event start
- 📍 = Position/drop
- ✏️ = Edit start

---

## Quick Debugging Checklist

### Task Not Persisting After Completion?

1. Check console for `[TaskActionLock] Acquired lock` - Lock acquired?
2. Check for `[UpdateTask] Calling _syncToServer` - Sync initiated?
3. Check for `[HTTP Fallback]` or WebSocket emit - Which transport?
4. Check server logs for `PUT /api/tasks/{id}` - Request received?
5. Check for `[Reconcile] Released action lock` - Sync completed?
6. Check for `[Idle Sync] Skipping - action lock active` - Lock respected?

### Task Reverting After 30 Seconds?

1. Verify `[TaskActionLock]` messages show lock acquisition
2. Check `[Idle Sync]` and `[Reconciliation]` logs for "BLOCKED" vs "ALLOWED"
3. If showing "ALLOWED" too soon, lock may have been released prematurely
4. Check server response - was update committed?

### Console Debug Commands

```javascript
// Check lock status
window.taskActionLock?.getDebugInfo()

// Check pending operations
window.optimisticUI?.pendingOperations

// Check cache state
await window.taskCache?.getTask(taskId)

// Force sync
window.idleSync?.sync({force: true})
```

---

## File Reference

| Category | Files |
|----------|-------|
| **Initialization** | task-page-master-init.js, task-bootstrap.js, task-page-init.js |
| **State Management** | task-state-store.js, task-cache.js |
| **Optimistic UI** | task-optimistic-ui.js |
| **Sync Protection** | task-action-lock.js |
| **Background Sync** | task-idle-sync.js, reconciliation-cycle.js |
| **Multi-Tab** | task-multi-tab-sync.js, broadcast-sync.js |
| **Menu Actions** | task-menu-controller.js, task-actions-menu.js |
| **Keyboard** | task-keyboard-shortcuts.js |
| **Drag/Drop** | task-drag-drop.js |
| **Inline Edit** | task-inline-editing.js |
| **WebSocket** | task-websocket-handlers.js |
| **API Routes** | routes/api_tasks.py |
| **Template** | templates/dashboard/tasks.html |
