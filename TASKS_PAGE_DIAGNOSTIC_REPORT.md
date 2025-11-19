# Tasks Page - Diagnostic Report & Fix Plan

**Generated:** November 19, 2025
**Status:** BROKEN - Most UI interactions not wired up
**Real Tasks:** 15 tasks from actual meetings (confirmed in database)

---

## Executive Summary

The Tasks page **loads and displays data correctly**, but **most interactive features are broken** because event handlers are not properly initialized.

**Infrastructure Status:** ✅ WORKING
- Page renders successfully
- 15 real tasks display
- Backend APIs functional
- CSS/JS files load
- WebSocket connects
- Cache initializes

**Interactivity Status:** ❌ BROKEN  
- "New Task" button - NO click handler
- Three-dot menu - NO click handler
- "AI Proposals" button - Handler exists but not initializing
- "Jump to Transcript" - NO navigation handler
- Task checkboxes - May not persist
- Filter tabs - May not filter
- Search bar - May not filter
- Sort dropdown - May not reorder
- Inline editing - Not wired
- Delete/Edit - No handlers

---

## Root Cause Analysis

**Problem:** JavaScript files load, but initialization functions are not being called.

**Evidence from Code Review:**

1. `templates/dashboard/tasks.html` lines 40-45:
   ```html
   <button class="btn btn-primary">
       New Task
   </button>
   ```
   ❌ NO `id`, NO `data-action`, NO onclick - Just a button with no handler

2. `static/js/task-proposal-ui.js` line 19-20:
   ```javascript
   } else if (e.target.classList.contains('btn-generate-proposals')) {
   ```
   ✅ Handler EXISTS but class needs to be in delegated event listener

3. `static/js/task-actions-menu.js`:
   ✅ Code EXISTS but needs to be initialized on page load

**The Pattern:** Code is written, but initialization is missing or not being called.

---

## Detailed Breakdown

### ❌ BROKEN: "New Task" Button

**Issue:** No click handler attached
**Location:** `templates/dashboard/tasks.html` line 40
**Fix Required:** Add event listener in initialization

### ❌ BROKEN: Three-Dot Menu

**Issue:** Menu button exists but click handler not attached
**Location:** `templates/dashboard/_task_card_macro.html` line 132
**Fix Required:** Initialize `task-actions-menu.js` on page load

### ⚠️  PARTIAL: "AI Proposals" Button  

**Issue:** Handler exists in `task-proposal-ui.js` but may not be initialized
**Location:** `static/js/task-proposal-ui.js`
**Fix Required:** Verify initialization in `task-page-init.js`

### ❌ BROKEN: Task Checkboxes

**Issue:** Checkboxes exist but toggle handler unclear
**Location:** Task cards
**Fix Required:** Wire up checkbox event with optimistic UI

### ⚠️  UNKNOWN: Filter Tabs

**Issue:** Tabs exist, unclear if filtering works
**Location:** `templates/dashboard/tasks.html` lines 58-76
**Fix Required:** Verify filter functionality

### ⚠️  UNKNOWN: Search & Sort

**Issue:** Elements exist, unclear if functional
**Location:** `templates/dashboard/tasks.html` lines 108-160
**Fix Required:** Verify search and sort handlers

### ❌ BROKEN: "Jump to Transcript"

**Issue:** Buttons exist but no navigation handler
**Location:** `templates/dashboard/_task_card_macro.html` lines 106-116
**Fix Required:** Wire up navigation to meeting transcript

---

## Test Strategy

Since Playwright E2E is complex in Replit, using hybrid approach:

1. **Browser Console Tests** - Run `/static/test/tasks-page-e2e-tests.js` in browser
2. **Manual Click Testing** - User verifies each button works
3. **Backend API Tests** - Validate APIs (authentication needed)

**To Run Browser Tests:**
1. Open `/dashboard/tasks` in browser
2. Open browser console (F12)
3. Load test file or copy/paste content
4. Run: `runAllTasksTests()`

---

## Fix Priority Order

### Phase 1: Critical Interactions (Must Fix First)
1. ✅ Wire up "New Task" button → Modal
2. ✅ Wire up three-dot menu → Show options
3. ✅ Wire up task checkboxes → Toggle completion
4. ✅ Wire up delete functionality
5. ✅ Initialize all page event handlers

### Phase 2: Filters & Search
6. ✅ Verify filter tabs work
7. ✅ Verify search filters tasks
8. ✅ Verify sort reorders tasks

### Phase 3: Meeting Features
9. ✅ Wire up "Jump to Transcript" navigation
10. ✅ Wire up "AI Proposals" button
11. ✅ Wire up context preview hover
12. ✅ Initialize meeting heatmap

---

## Expected Outcome

After fixes, browser console tests should show:
```
Total Tests: 12
✅ Passed: 12
❌ Failed: 0
📊 Pass Rate: 100%
```

Then user can manually verify all buttons click and features work with the 15 real tasks.

---

## Next Steps

1. Create master initialization file that wires up all handlers
2. Fix each broken interaction systematically
3. Test using browser console after each fix
4. Generate final validation report
