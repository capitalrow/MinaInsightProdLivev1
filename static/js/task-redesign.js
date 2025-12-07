/**
 * MINA Task Page Redesign - JavaScript Interactions
 * Handles:
 * - Mobile tap expansion (progressive disclosure)
 * - View toggle functionality
 * - Task card interactions
 * - Real-time count updates
 */

(function() {
  'use strict';

  // ========================================
  // TASK CARD EXPANSION (3-TIER PROGRESSIVE DISCLOSURE)
  // ========================================
  
  function initTaskCardExpansion() {
    const isTouchDevice = 'ontouchstart' in window || navigator.maxTouchPoints > 0;
    
    function toggleExpand(taskCard, collapseOthers) {
      if (collapseOthers) {
        document.querySelectorAll('.task-card.expanded').forEach(card => {
          if (card !== taskCard) {
            card.classList.remove('expanded');
          }
        });
      }
      taskCard.classList.toggle('expanded');
      
      // Update aria-expanded for accessibility
      const isExpanded = taskCard.classList.contains('expanded');
      taskCard.setAttribute('aria-expanded', isExpanded ? 'true' : 'false');
      
      // Update expand trigger icon rotation
      const expandTrigger = taskCard.querySelector('.task-expand-trigger');
      if (expandTrigger) {
        expandTrigger.setAttribute('aria-expanded', isExpanded ? 'true' : 'false');
        expandTrigger.setAttribute('title', isExpanded ? 'Hide details' : 'Show details');
      }
    }
    
    function isInteractiveElement(target) {
      return target.closest('.task-checkbox') || 
             target.closest('.task-menu-trigger') ||
             target.closest('.task-expand-trigger') ||
             target.closest('button') ||
             target.closest('a') ||
             target.closest('input') ||
             target.closest('select');
    }
    
    // Handle expand trigger button click (desktop + mobile)
    document.addEventListener('click', function(e) {
      const expandTrigger = e.target.closest('.task-expand-trigger');
      if (expandTrigger) {
        e.preventDefault();
        e.stopPropagation();
        const taskCard = expandTrigger.closest('.task-card');
        if (taskCard) {
          toggleExpand(taskCard, true);
        }
        return;
      }
    });
    
    // Mobile: tap anywhere on card to expand (except interactive elements)
    if (isTouchDevice) {
      document.addEventListener('click', function(e) {
        const taskCard = e.target.closest('.task-card');
        
        if (!taskCard) {
          document.querySelectorAll('.task-card.expanded').forEach(card => {
            card.classList.remove('expanded');
          });
          return;
        }
        
        if (isInteractiveElement(e.target)) return;
        
        toggleExpand(taskCard, true);
      });
    }
    
    document.addEventListener('keydown', function(e) {
      if (e.key !== 'Enter' && e.key !== ' ') return;
      
      const taskCard = e.target.closest('.task-card');
      if (!taskCard) return;
      
      if (isInteractiveElement(e.target)) return;
      
      if (e.target === taskCard || e.target.classList.contains('task-content') ||
          e.target.classList.contains('task-title') || e.target.classList.contains('task-primary-row')) {
        e.preventDefault();
        toggleExpand(taskCard, false);
      }
    });
    
    document.querySelectorAll('.task-card').forEach(card => {
      if (!card.hasAttribute('tabindex')) {
        card.setAttribute('tabindex', '0');
      }
      card.setAttribute('role', 'article');
      card.setAttribute('aria-expanded', card.classList.contains('expanded') ? 'true' : 'false');
    });
    
    const observer = new MutationObserver(function(mutations) {
      mutations.forEach(function(mutation) {
        if (mutation.attributeName === 'class') {
          const card = mutation.target;
          if (card.classList.contains('task-card')) {
            card.setAttribute('aria-expanded', card.classList.contains('expanded') ? 'true' : 'false');
          }
        }
        if (mutation.addedNodes.length) {
          mutation.addedNodes.forEach(node => {
            if (node.classList && node.classList.contains('task-card')) {
              if (!node.hasAttribute('tabindex')) {
                node.setAttribute('tabindex', '0');
              }
              node.setAttribute('role', 'article');
              node.setAttribute('aria-expanded', 'false');
            }
          });
        }
      });
    });
    
    const listContainer = document.querySelector('.tasks-list-container, #tasks-list-container');
    if (listContainer) {
      observer.observe(listContainer, { childList: true, subtree: true, attributes: true, attributeFilter: ['class'] });
    }
    
    console.log('[TaskRedesign] Mobile tap expansion + keyboard accessibility initialized');
  }

  // ========================================
  // VIEW TOGGLE FUNCTIONALITY
  // ========================================
  
  const VIEW_STORAGE_KEY = 'mina_task_view_preference';
  
  function getViewPreference() {
    try {
      return localStorage.getItem(VIEW_STORAGE_KEY) || 'list';
    } catch (e) {
      return 'list';
    }
  }
  
  function setViewPreference(view) {
    try {
      localStorage.setItem(VIEW_STORAGE_KEY, view);
    } catch (e) {
      console.warn('[TaskRedesign] Could not save view preference');
    }
  }
  
  function applyView(view) {
    const container = document.querySelector('.tasks-list-container, #tasks-list-container');
    if (!container) return;
    
    container.classList.remove('view-list', 'view-grid', 'view-bar');
    container.classList.add('view-' + view);
    
    // CROWN⁴.8 FIX: Only update buttons INSIDE .view-toggle-group
    const viewToggleGroup = document.querySelector('.view-toggle-group');
    if (viewToggleGroup) {
      viewToggleGroup.querySelectorAll('.view-toggle-btn[data-view]').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.view === view);
      });
    }
    
    console.log('[TaskRedesign] Applied view:', view);
  }
  
  function initViewToggles() {
    // CROWN⁴.8 FIX: Only use the official .view-toggle-btn buttons in .view-toggle-group
    // Do NOT create additional toggles from stray SVGs - this was causing duplicates!
    const viewToggleGroup = document.querySelector('.view-toggle-group');
    if (!viewToggleGroup) {
      console.warn('[TaskRedesign] No .view-toggle-group found');
      return;
    }
    
    // Only listen to clicks on official toggle buttons
    viewToggleGroup.addEventListener('click', function(e) {
      const viewBtn = e.target.closest('.view-toggle-btn[data-view]');
      if (!viewBtn) return;
      
      e.preventDefault();
      e.stopPropagation();
      
      const view = viewBtn.dataset.view;
      if (view) {
        setViewPreference(view);
        applyView(view);
      }
    });
    
    const savedView = getViewPreference();
    applyView(savedView);
    
    console.log('[TaskRedesign] View toggles initialized (official group only), current view:', savedView);
  }

  // ========================================
  // TASK COUNT UPDATES (ACCURATE: completed + cancelled = archived)
  // ========================================
  
  function updateTaskCounts() {
    const allTasks = document.querySelectorAll('.task-card');
    
    let activeCount = 0;
    let archivedCount = 0;
    
    allTasks.forEach(task => {
      const status = task.dataset.status || '';
      const isCompleted = task.classList.contains('completed');
      const isArchived = status === 'completed' || status === 'cancelled' || isCompleted;
      
      if (isArchived) {
        archivedCount++;
      } else {
        activeCount++;
      }
    });
    
    const allCount = allTasks.length;
    
    const allCounter = document.querySelector('[data-counter="all"], .filter-counter-all');
    const activeCounter = document.querySelector('[data-counter="active"], .filter-counter-active');
    const archivedCounter = document.querySelector('[data-counter="archived"], .filter-counter-archived');
    
    if (allCounter) allCounter.textContent = allCount;
    if (activeCounter) activeCounter.textContent = activeCount;
    if (archivedCounter) archivedCounter.textContent = archivedCount;
    
    const visibleCount = document.getElementById('visible-task-count');
    const totalCount = document.getElementById('total-task-count');
    
    if (visibleCount) {
      const visibleTasks = document.querySelectorAll('.task-card:not([style*="display: none"])');
      visibleCount.textContent = visibleTasks.length;
    }
    if (totalCount) totalCount.textContent = allCount;
  }

  // ========================================
  // TASK CHECKBOX HANDLER
  // ========================================
  
  function initCheckboxHandlers() {
    document.addEventListener('change', function(e) {
      if (!e.target.classList.contains('task-checkbox')) return;
      
      const checkbox = e.target;
      const taskCard = checkbox.closest('.task-card');
      const taskId = checkbox.dataset.taskId || taskCard?.dataset.taskId;
      
      if (!taskCard || !taskId) return;
      
      const isCompleted = checkbox.checked;
      taskCard.classList.toggle('completed', isCompleted);
      taskCard.dataset.status = isCompleted ? 'completed' : 'todo';
      
      updateTaskCounts();
      
      if (typeof window.TaskAPI !== 'undefined' && window.TaskAPI.updateTask) {
        window.TaskAPI.updateTask(taskId, { 
          status: isCompleted ? 'completed' : 'todo' 
        }).catch(err => {
          console.error('[TaskRedesign] Failed to update task:', err);
          checkbox.checked = !isCompleted;
          taskCard.classList.toggle('completed', !isCompleted);
          updateTaskCounts();
        });
      }
    });
    
    console.log('[TaskRedesign] Checkbox handlers initialized');
  }

  // ========================================
  // FILTER TAB HANDLERS
  // ========================================
  
  function initFilterTabs() {
    document.addEventListener('click', function(e) {
      const filterTab = e.target.closest('.filter-tab');
      if (!filterTab) return;
      
      e.preventDefault();
      
      // CROWN⁴.12: Set user action lock to prevent background state restores
      if (window.taskSearchSort?._setUserActionLock) {
          window.taskSearchSort._setUserActionLock();
      }
      
      document.querySelectorAll('.filter-tab').forEach(tab => {
        tab.classList.remove('active');
      });
      filterTab.classList.add('active');
      
      const filter = filterTab.dataset.filter;
      applyFilter(filter);
    });
    
    console.log('[TaskRedesign] Filter tabs initialized');
  }
  
  function applyFilter(filter) {
    const tasks = document.querySelectorAll('.task-card');
    
    tasks.forEach(task => {
      const isCompleted = task.classList.contains('completed') || 
                          task.dataset.status === 'completed' ||
                          task.dataset.status === 'cancelled';
      
      let shouldShow = true;
      
      switch (filter) {
        case 'active':
          shouldShow = !isCompleted;
          break;
        case 'archived':
          shouldShow = isCompleted;
          break;
        case 'all':
        default:
          shouldShow = true;
      }
      
      task.style.display = shouldShow ? '' : 'none';
    });
    
    updateTaskCounts();
    updateEmptyStates(filter);
  }
  
  function updateEmptyStates(filter) {
    const visibleTasks = document.querySelectorAll('.task-card:not([style*="display: none"])');
    const emptyState = document.getElementById('tasks-empty-state');
    const allDoneState = document.getElementById('tasks-all-done-state');
    const noResultsState = document.getElementById('tasks-no-results-state');
    const archivedEmptyState = document.getElementById('tasks-archived-empty-state');
    const listContainer = document.getElementById('tasks-list-container');
    
    const hasVisibleTasks = visibleTasks.length > 0;
    const allTasks = document.querySelectorAll('.task-card');
    const hasAnyTasks = allTasks.length > 0;
    const completedTasks = document.querySelectorAll('.task-card[data-status="completed"], .task-card[data-status="cancelled"], .task-card.completed');
    const hasCompletedTasks = completedTasks.length > 0;
    
    if (emptyState) {
      const showMainEmpty = !hasAnyTasks;
      emptyState.classList.toggle('hidden', !showMainEmpty);
    }
    if (allDoneState) {
      const showAllDone = !hasVisibleTasks && filter === 'active' && hasCompletedTasks && hasAnyTasks;
      allDoneState.classList.toggle('hidden', !showAllDone);
    }
    if (archivedEmptyState) {
      const showArchivedEmpty = !hasVisibleTasks && filter === 'archived' && !hasCompletedTasks && hasAnyTasks;
      archivedEmptyState.classList.toggle('hidden', !showArchivedEmpty);
    }
    if (listContainer) listContainer.style.display = hasVisibleTasks ? '' : 'none';
  }

  // ========================================
  // INITIALIZATION
  // ========================================
  
  // ========================================
  // MOBILE FAB (Floating Action Button)
  // ========================================
  
  function initMobileFAB() {
    const fab = document.getElementById('mobile-fab');
    const newTaskBtn = document.getElementById('new-task-btn');
    
    if (!fab) return;
    
    fab.addEventListener('click', function(e) {
      e.preventDefault();
      fab.classList.add('fab-pressed');
      setTimeout(() => fab.classList.remove('fab-pressed'), 300);
      
      // Trigger the same action as the "New" button
      if (newTaskBtn) {
        newTaskBtn.click();
      } else if (window.TaskModalManager && typeof window.TaskModalManager.openCreateModal === 'function') {
        window.TaskModalManager.openCreateModal();
      } else {
        // Fallback: dispatch custom event
        document.dispatchEvent(new CustomEvent('task:create-new'));
      }
    });
    
    console.log('[TaskRedesign] Mobile FAB initialized');
  }
  
  function initFilterResetButtons() {
    document.querySelectorAll('.filter-reset-btn').forEach(btn => {
      btn.addEventListener('click', function(e) {
        e.preventDefault();
        const targetFilter = btn.dataset.filter || 'active';
        
        // Update filter tabs
        document.querySelectorAll('.filter-tab').forEach(tab => {
          tab.classList.toggle('active', tab.dataset.filter === targetFilter);
          tab.setAttribute('aria-selected', tab.dataset.filter === targetFilter ? 'true' : 'false');
        });
        
        // Apply filter
        applyFilter(targetFilter);
        
        // Also trigger TaskSearchSort if available
        if (window.taskSearchSort && typeof window.taskSearchSort.setFilter === 'function') {
          window.taskSearchSort.setFilter(targetFilter);
        }
      });
    });
    
    console.log('[TaskRedesign] Filter reset buttons initialized');
  }
  
  function init() {
    console.log('[TaskRedesign] Initializing...');
    
    initTaskCardExpansion();
    initViewToggles();
    initCheckboxHandlers();
    initMobileFAB();
    initFilterResetButtons();
    // CROWN⁴.12: Removed initFilterTabs() - now handled by task-page-master-init.js + TaskSearchSort
    // initFilterTabs();
    updateTaskCounts();
    
    const observer = new MutationObserver(function(mutations) {
      let shouldUpdate = false;
      mutations.forEach(function(mutation) {
        if (mutation.addedNodes.length || mutation.removedNodes.length) {
          mutation.addedNodes.forEach(node => {
            if (node.classList && node.classList.contains('task-card')) {
              shouldUpdate = true;
            }
          });
          mutation.removedNodes.forEach(node => {
            if (node.classList && node.classList.contains('task-card')) {
              shouldUpdate = true;
            }
          });
        }
      });
      if (shouldUpdate) {
        updateTaskCounts();
      }
    });
    
    const listContainer = document.querySelector('.tasks-list-container, #tasks-list-container');
    if (listContainer) {
      observer.observe(listContainer, { childList: true, subtree: true });
    }
    
    console.log('[TaskRedesign] Initialization complete');
  }
  
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
  
  window.TaskRedesign = {
    updateCounts: updateTaskCounts,
    applyFilter: applyFilter,
    applyView: applyView,
    getViewPreference: getViewPreference
  };
  
})();
