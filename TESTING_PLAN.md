# Mina Tasks Page - Comprehensive E2E Testing Plan

## Overview
This document outlines end-to-end testing procedures for all task management functionality on the Mina platform, following industry best practices from Linear, Notion, and Asana.

---

## 🎯 Testing Objectives

1. **Optimistic UI Validation**: Verify instant UI updates before server confirmation
2. **Real-Time Sync**: Confirm WebSocket broadcasts update all connected clients
3. **Offline Support**: Test offline queue, reconnection, and data persistence
4. **Cache Consistency**: Validate IndexedDB cache stays in sync (target: 80-95% hit ratio)
5. **Performance**: Measure sync latency (<300ms), TTI (<200ms), WER metrics
6. **Rollback Mechanisms**: Ensure graceful failure handling with error recovery

---

## 📋 Test Categories

### A. Core CRUD Operations (13 Menu Actions)

#### 1. **View Details**
- **Action**: Click "View Details" from task menu
- **Expected**: Opens task detail page in new tab
- **Validation**: URL matches `/tasks/{task_id}`, page loads successfully

#### 2. **Edit Title (Inline)**
- **Action**: Click "Edit" → modify title → press Enter/blur
- **Expected**: 
  - Title updates instantly in UI
  - OptimisticUI.updateTask() called (not raw fetch)
  - IndexedDB cache updated
  - WebSocket broadcast to other tabs
  - Server confirms update
- **Validation**: 
  - Title persists after page refresh
  - Other tabs show new title within 300ms
  - Network tab shows PATCH `/api/tasks/{id}` with title update
- **Rollback Test**: Simulate server error → title reverts to original

#### 3. **Toggle Status (Complete/Incomplete)**
- **Action**: Click checkbox on task card
- **Expected**:
  - Checkbox state toggles instantly
  - Card styling updates (strikethrough if completed)
  - Status updated to 'completed' or 'todo'
  - WebSocket broadcast
- **Multi-Tab Test**: Toggle in Tab 1 → verify Tab 2 checkbox updates
- **Offline Test**: Toggle while offline → verify queued → syncs on reconnect

#### 4. **Change Priority**
- **Action**: Menu → Priority → select new priority
- **Expected**:
  - Priority badge updates instantly
  - OptimisticUI.updateTask() called
  - WebSocket broadcast with TASK_PRIORITY_CHANGED event
- **Validation**: Dashboard metrics reflect new priority distribution

#### 5. **Set Due Date**
- **Action**: Menu → Due Date → pick date
- **Expected**:
  - Date badge appears/updates
  - Smart parsing works ("tomorrow", "next week")
  - Clear date option works
- **Edge Cases**: Past dates, invalid dates, null handling

#### 6. **Assign Task**
- **Action**: Menu → Assign → select users (multi-select)
- **Expected**:
  - Assignee avatars update instantly
  - Multi-assignee support works (assignee_ids array)
  - TaskAssignee junction table updates
  - WebSocket broadcasts TASK_ASSIGNED/UNASSIGNED events
- **Validation**: Assigned user sees task in "My Tasks" filter

#### 7. **Edit Labels**
- **Action**: Menu → Labels → add/remove labels
- **Expected**:
  - Label badges update instantly
  - Create new labels on-the-fly
  - Color coding works
- **Validation**: Labels persist, searchable, filterable

#### 8. **Duplicate Task**
- **Action**: Menu → Duplicate → confirm
- **Expected**:
  - New task created with "[Copy]" suffix
  - OptimisticUI.createTask() called (not raw POST)
  - All fields copied except ID
  - Temp ID assigned, replaced on server confirmation
- **Validation**: Both original and duplicate exist after refresh

#### 9. **Snooze Task**
- **Action**: Menu → Snooze → select time
- **Expected**:
  - Task hidden from main view
  - `snoozed_until` timestamp set
  - Reappears after snooze expires
- **Validation**: Snoozed tasks excluded from default filters

#### 10. **Merge Tasks**
- **Action**: Menu → Merge → select target task
- **Expected**:
  - Source task labels merged into target
  - Higher priority wins
  - Source task soft-deleted
  - OptimisticUI.mergeTasks() called
- **Validation**: Only merged task remains after refresh

#### 11. **Jump to Transcript**
- **Action**: Menu → Jump to Transcript
- **Expected**:
  - Navigates to `/sessions/{meeting_id}#transcript`
  - Scrolls to relevant segment (if segment_id exists)
- **Edge Case**: Task without meeting → show error toast

#### 12. **Archive Task**
- **Action**: Menu → Archive → confirm
- **Expected**:
  - OptimisticUI.archiveTask() called
  - `archived_at` timestamp set
  - Status changed to 'archived'
  - Card fades out and removes from view
  - Undo toast shown (15s window)
- **Undo Test**: Click undo → task restored instantly
- **Validation**: Archived tasks appear in "Archived" filter tab

#### 13. **Delete Task**
- **Action**: Menu → Delete → confirm
- **Expected**:
  - OptimisticUI.deleteTask() called (soft delete)
  - `deleted_at` timestamp set (not hard delete)
  - Card animates out with task:deleted event
  - Undo toast shown (15s window)
- **Undo Test**: Click undo within 15s → task restored
- **Validation**: Soft-deleted tasks excluded by default, hard-deleted after retention period

---

### B. Real-Time Multi-Tab Sync Tests

**Setup**: Open Tasks page in 2+ browser tabs

| Action in Tab 1 | Expected in Tab 2 | Latency Target |
|----------------|-------------------|----------------|
| Create new task | New task appears instantly | <300ms |
| Toggle task complete | Checkbox updates | <300ms |
| Edit title | Title updates | <300ms |
| Change priority | Badge updates | <300ms |
| Assign to user | Assignee avatar appears | <300ms |
| Delete task | Card fades out | <300ms |
| Archive task | Card disappears | <300ms |
| Bulk delete 10 tasks | All 10 remove | <500ms |

**WebSocket Event Validation**:
- Open browser DevTools → Network → WS
- Verify events emitted:
  - `task.create.manual`
  - `task.update.core`
  - `task.priority.changed`
  - `task.status.changed`
  - `task.assigned` / `task.unassigned`
  - `task.delete.soft`
  - `task.restore`

---

### C. Offline Support Tests

#### Test 1: Offline Queue
1. Open DevTools → Network → Throttling → **Offline**
2. Perform 5 actions:
   - Create task "Test Offline 1"
   - Edit title to "Test Offline 2"
   - Toggle complete
   - Change priority to High
   - Delete task "Old Task"
3. **Expected**:
   - All actions apply optimistically in UI
   - Offline banner appears: "Offline - changes will sync when reconnected (5 pending)"
   - IndexedDB stores pending operations
4. **Go online**: Network → Online
5. **Expected**:
   - Offline queue replays in order
   - All 5 operations sync successfully
   - Temp IDs replaced with real IDs
   - Toast: "Synced 5 pending changes"
6. **Validation**: Hard refresh → all changes persisted

#### Test 2: Offline with Browser Close
1. Go offline
2. Create 3 tasks
3. **Close browser entirely**
4. Reopen browser (still offline)
5. **Expected**: 3 pending operations still queued
6. Go online
7. **Expected**: Queue replays, tasks sync to server

#### Test 3: Partial Sync Failure
1. Go offline
2. Create 5 tasks
3. **Simulate**: Server rejects task #3 (e.g., validation error)
4. Go online
5. **Expected**:
   - Tasks 1, 2, 4, 5 sync successfully
   - Task 3 rolls back with error toast
   - Retry button available

---

### D. Cache Consistency & Performance Tests

#### Test 1: Cache Hit Ratio (Target: 80-95%)
1. Clear IndexedDB cache
2. Load Tasks page (cold start)
   - **Measure**: Network requests, cache miss
3. Navigate to Dashboard → back to Tasks
   - **Measure**: Cache hits (no network calls)
4. Hard refresh (Ctrl+Shift+R)
   - **Measure**: Revalidation, partial cache hit
5. **Tools**: Chrome DevTools → Application → IndexedDB → `taskCache`
6. **Expected**: 80-95% cache hit ratio after warm-up

#### Test 2: Sync Latency (Target: <300ms)
1. Create task in Tab 1
2. **Measure**: Time until visible in Tab 2
3. **Tools**: `performance.now()` in WebSocket handler
4. **Expected**: <300ms end-to-end

#### Test 3: Time to Interactive (Target: <200ms)
1. Clear cache
2. Load Tasks page
3. **Measure**: TTI using Lighthouse
4. **Expected**: First Contentful Paint <1s, TTI <200ms with cache

---

### E. Error Handling & Rollback Tests

#### Test 1: Server Validation Error
1. Edit task title to empty string ""
2. Save
3. **Expected**:
   - Server rejects (400 Bad Request)
   - Title reverts to original
   - Error toast: "Failed to update title - Title cannot be empty"
   - OptimisticUI._reconcileFailure() called

#### Test 2: Network Timeout
1. Throttle network to Slow 3G
2. Create task with large description (>5000 chars)
3. **Expected**:
   - Task appears optimistically
   - Timeout after 30s
   - Retry toast appears
   - Manual retry succeeds

#### Test 3: Conflict Resolution (409)
1. Edit task title in Tab 1: "Version A"
2. **Simultaneously** edit same task in Tab 2: "Version B"
3. **Expected**:
   - One wins (last-write-wins)
   - Other gets 409 Conflict
   - Warning toast: "Changes conflict detected - reloading latest version"
   - Losing tab reloads task from server

#### Test 4: WebSocket Disconnect
1. **Simulate**: Close WebSocket connection (DevTools → Network → WS → Close)
2. Make changes
3. **Expected**:
   - Offline queue activates
   - Reconnection banner: "Reconnecting..."
   - Auto-reconnect after 3 retries
   - Queue replays on reconnect

---

### F. Cross-Dashboard Metrics Validation

**Setup**: Open multiple pages side-by-side

| Action | Dashboard | Tasks Page | Session Page |
|--------|-----------|------------|--------------|
| Complete task | Total tasks ↓1, Completed ↑1 | Task marked complete | Meeting stats update |
| Create high-priority task | Priority distribution updates | Task appears in list | Action items count ↑1 |
| Delete overdue task | Overdue count ↓1 | Task removed | Meeting metrics refresh |
| Archive completed task | Active tasks ↓1 | Moves to Archived tab | — |

**Validation Method**:
1. Open Dashboard in Tab 1
2. Open Tasks in Tab 2
3. Perform action in Tab 2
4. **Verify**: Tab 1 Dashboard updates within 500ms without manual refresh

---

### G. Filter & Search Tests

#### Archive Filter UI
1. **Navigate**: Tasks Page → Filter tabs
2. **Tabs**: All | Active | Archived
3. **Test**:
   - All: Shows all tasks (including archived)
   - Active: Excludes archived tasks (default)
   - Archived: Shows only archived tasks
4. **Restore Test**: Click "Restore" on archived task → moves to Active tab

#### Search Functionality
- Search by title
- Search by assignee
- Search by label
- Search by priority
- Combined filters (e.g., "High priority + Overdue")

---

## 🛠️ Testing Tools & Automation

### Manual Testing Tools
- **Chrome DevTools**: Network, Application (IndexedDB), Console, Performance
- **Network Throttling**: Offline, Slow 3G, Fast 3G
- **Lighthouse**: PWA audit, performance metrics
- **React DevTools**: (If using React components)

### Automated Testing (Future)
```bash
# E2E Tests (Playwright)
npm run test:e2e

# WebSocket Load Test (Artillery)
artillery run websocket-load-test.yml

# Performance Tests
npm run test:performance
```

### Playwright E2E Example
```javascript
// tests/e2e/task-menu.spec.ts
test('Task edit propagates across tabs', async ({ context }) => {
  const page1 = await context.newPage();
  const page2 = await context.newPage();
  
  await page1.goto('/tasks');
  await page2.goto('/tasks');
  
  // Edit in page1
  await page1.click('[data-task-id="123"] .task-menu-trigger');
  await page1.click('text=Edit');
  await page1.fill('.task-title-edit-input', 'Updated Title');
  await page1.press('.task-title-edit-input', 'Enter');
  
  // Verify in page2
  await expect(page2.locator('[data-task-id="123"] .task-title-text'))
    .toHaveText('Updated Title', { timeout: 500 });
});
```

### Artillery WebSocket Load Test
```yaml
# websocket-load-test.yml
config:
  target: 'wss://your-app.com'
  phases:
    - duration: 60
      arrivalRate: 50  # 50 users/sec
  processor: "./websocket-processor.js"

scenarios:
  - name: "Task Updates"
    engine: ws
    flow:
      - send:
          channel: "/tasks"
          data:
            type: "task:update"
            task_id: "{{ $randomNumber(1, 1000) }}"
            updates: { priority: "high" }
      - think: 2
      - send:
          channel: "/tasks"
          data:
            type: "task:create"
            task: { title: "Load Test Task {{ $randomString() }}" }
```

---

## 📊 Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| Cache Hit Ratio | 80-95% | IndexedDB access logs |
| Sync Latency | <300ms | WebSocket event timestamp delta |
| TTI (Time to Interactive) | <200ms | Lighthouse audit |
| Offline Queue Success | 100% | No data loss after reconnect |
| Multi-tab Sync | <300ms | Cross-tab event propagation |
| Rollback Success | 100% | All failed operations revert cleanly |
| WER (Word Error Rate) | <5% | (For transcript features) |

---

## 🐛 Known Issues & Edge Cases

1. **Race Conditions**: Multiple rapid edits to same field
2. **Temp ID Collision**: Unlikely but possible with ULID generation
3. **WebSocket Disconnect**: Graceful degradation to polling fallback
4. **IndexedDB Quota**: Browser storage limits (~50MB typical)
5. **Service Worker Cache**: Stale assets after deployment (version bumping required)

---

## 🚀 Pre-Production Checklist

- [ ] All 13 menu actions work end-to-end
- [ ] Multi-tab sync tested across Chrome, Firefox, Safari
- [ ] Offline queue tested with >10 pending operations
- [ ] Cache hit ratio >80% after warm-up
- [ ] Sync latency <300ms under normal conditions
- [ ] Error toasts display clear, actionable messages
- [ ] Rollback mechanisms tested for all failure scenarios
- [ ] WebSocket reconnection tested (close connection manually)
- [ ] IndexedDB migration tested (schema changes)
- [ ] Dashboard metrics update in real-time
- [ ] Archive filter tab functional with restore
- [ ] Undo functionality tested (15s window)
- [ ] Performance tested with 100+ tasks
- [ ] Mobile responsive (touch interactions)
- [ ] Accessibility (keyboard navigation, screen readers)

---

## 📚 References

- [Linear Sync Engine](https://linear.app/blog/scaling-the-linear-sync-engine)
- [Reverse Engineering Linear](https://marknotfound.com/posts/reverse-engineering-linears-sync-magic/)
- [Optimistic UI Best Practices](https://www.builder.io/blog/optimistic-ui)
- [WebSocket Testing Guide](https://apidog.com/blog/websocket-testing-tools/)
- [IndexedDB Performance](https://web.dev/indexeddb-best-practices/)

---

**Last Updated**: 2025-11-21  
**Version**: 1.0  
**Owner**: Engineering Team
