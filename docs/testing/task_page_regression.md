# Task Page Regression Test Plan

## Overview
Comprehensive 34-test plan covering all Task Page functionality, bug fixes, and core features.
- **Total Tests:** 34
- **Estimated Time:** 17 minutes (Full Coverage)
- **Strategy:** Risk-Based Smoke Testing with 3-Phase Pyramid

---

## Testing Strategy: 3-Phase Pyramid

### Phase 1: GATEKEEPERS (2 min)
*Stop immediately if any fail - these prove foundational systems work*

1. **Create a task** → proves CSRF works
2. **Edit that task** → proves optimistic UI + server sync works

### Phase 2: NEW CODE (5 min)
*Highest bug probability - focus testing time here*

1. View Details → new route, new template
2. Trigger HTTP error → new rollback logic  
3. Open 2 tabs, edit in one → new WebSocket wiring

### Phase 3: REGRESSION SWEEP (10 min)
*Quick pass through remaining - confirm nothing broke*

- One test per menu action category
- One responsive breakpoint check
- One edge case (rapid clicks or long title)

---

## Section 1: View Details Action (5 tests)

| Test Case | Steps | Expected Result |
|-----------|-------|-----------------|
| Open task detail | Click task menu → "View Details" | New tab opens at `/dashboard/tasks/{id}` with task info |
| Task data displays | View the detail page | Title, status, priority, due date, assignee all show correctly |
| Back navigation | Click "Back to Tasks" | Returns to tasks list |
| Transcript link | Click "View Transcript" (if from meeting) | Navigates to session page with transcript anchor |
| 404 handling | Navigate to `/dashboard/tasks/99999` | Shows 404 error gracefully |

---

## Section 2: CSRF Token Protection (3 tests)

| Test Case | Steps | Expected Result |
|-----------|-------|-----------------|
| Create task | Click "New Task" → enter title → save | Task creates successfully (no 403 error) |
| Update task | Edit title inline | Saves without CSRF rejection |
| Delete task | Delete a task via menu | Deletes without 403 error |

---

## Section 3: HTTP Fallback & Error Rollback (3 tests)

| Test Case | Steps | Expected Result |
|-----------|-------|-----------------|
| Optimistic update | Toggle task status | UI updates immediately, then persists |
| Server rejection | Simulate network error during update | UI rolls back to original state, error toast appears |
| Offline indicator | Disconnect network | Connection banner shows offline status |

---

## Section 4: WebSocket Real-Time Sync (3 tests)

| Test Case | Steps | Expected Result |
|-----------|-------|-----------------|
| Cross-tab sync | Open tasks in 2 tabs, update in one | Change appears in other tab without refresh |
| Task creation sync | Create task in one tab | Appears in second tab |
| Task deletion sync | Delete task in one tab | Disappears from second tab |

---

## Section 5: Responsive Design (3 tests)

| Test Case | Steps | Expected Result |
|-----------|-------|-----------------|
| Desktop (>1240px) | Full width browser | Max-width container, horizontal layout |
| Tablet (768-1024px) | Resize to tablet width | Container fills width, proper padding |
| Mobile (<640px) | Resize to mobile width | Header stacks, filters wrap, touch-friendly targets |

---

## Section 6: Menu Actions (All 13)

| Action | Test Steps | Expected Result |
|--------|------------|-----------------|
| View Details | Menu → View Details | Opens detail page |
| Edit Title | Menu → Edit → type → Enter | Title updates inline |
| Set Due Date | Menu → Due Date → pick date | Date picker works, saves |
| Set Priority | Menu → Priority → select | Priority badge updates |
| Assign | Menu → Assign → select user | Assignee updates |
| Labels | Menu → Labels → add/remove | Labels update |
| Duplicate | Menu → Duplicate | Creates copy of task |
| Snooze | Menu → Snooze → pick time | Task snoozed with indicator |
| Merge | Menu → Merge → enter target ID | Tasks merged, source removed |
| Jump to Transcript | Menu → Jump to Transcript | Navigates to `/sessions/{id}#transcript` |
| Archive | Menu → Archive → confirm | Task archived/hidden |
| Delete | Menu → Delete → confirm | Task permanently removed |
| Complete/Toggle | Click checkbox | Status toggles with animation |

---

## Section 7: Edge Cases (4 tests)

| Test Case | Steps | Expected Result |
|-----------|-------|-----------------|
| Empty state | Delete all tasks | Shows "No tasks" message |
| Long title | Create task with 200+ chars | Title truncates properly |
| Rapid clicks | Click checkbox 5x quickly | Only one state persists, no race conditions |
| Browser refresh | Reload during operation | Data persists correctly |

---

## Execution Checklist

### Pre-Test Setup
- [ ] Application running on port 5000
- [ ] At least 2-3 test tasks exist
- [ ] Browser DevTools open (Console + Network tabs)
- [ ] Second browser tab ready for cross-tab tests

### Test Execution Log

| Section | Tests | Passed | Failed | Notes |
|---------|-------|--------|--------|-------|
| 1. View Details | 5 | | | |
| 2. CSRF Protection | 3 | | | |
| 3. HTTP Fallback | 3 | | | |
| 4. WebSocket Sync | 3 | | | |
| 5. Responsive | 3 | | | |
| 6. Menu Actions | 13 | | | |
| 7. Edge Cases | 4 | | | |
| **TOTAL** | **34** | | | |

---

## Known Issues to Verify Fixed

1. **Counter sync bug**: Cache renders skip `updateCounters()` - counters show stale values after cache load
2. **Pending header stale**: "X pending tasks" header not updating on cache bootstrap
3. **Dashboard WebSocket envelope**: EventBroadcaster emits simplified payload to /dashboard missing event_id/timestamp/checksum

---

## Sign-Off

- **Tested By:** _______________
- **Date:** _______________
- **Result:** PASS / FAIL
- **Notes:** _______________
