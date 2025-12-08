// ========================================
// Session Refined View - Tab Switching & Interactive Features
// ========================================

(function() {
  'use strict';

  // Wait for DOM to be fully loaded
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeTabs);
  } else {
    initializeTabs();
  }

  function initializeTabs() {
    console.log('[Tabs] Initializing tab switching functionality...');
    
    const tabButtons = document.querySelectorAll('.tab-button');
    const tabContents = document.querySelectorAll('.tab-content');
    
    console.log(`[Tabs] Found ${tabButtons.length} tab buttons and ${tabContents.length} tab contents`);
    
    if (tabButtons.length === 0) {
      console.error('[Tabs] No tab buttons found! Check HTML structure.');
      return;
    }
    
    // Tab switching function with optional scroll behavior
    function switchTab(tabId, shouldScroll = false) {
      console.log(`[Tabs] Switching to tab: ${tabId}, scroll: ${shouldScroll}`);
      
      // Remove active from all buttons
      tabButtons.forEach(btn => {
        btn.classList.remove('active');
        btn.setAttribute('aria-selected', 'false');
      });
      
      // Remove active from all content
      tabContents.forEach(content => {
        content.classList.remove('active');
      });
      
      // Add active to clicked button
      const activeButton = document.querySelector(`[data-tab="${tabId}"]`);
      if (activeButton) {
        activeButton.classList.add('active');
        activeButton.setAttribute('aria-selected', 'true');
        console.log(`[Tabs] Activated button: ${tabId}`);
      }
      
      // Add active to corresponding content
      const activeContent = document.getElementById(`${tabId}-tab`);
      if (activeContent) {
        activeContent.classList.add('active');
        console.log(`[Tabs] Activated content: ${tabId}-tab`);
        
        // Scroll to content if requested (e.g., from hash navigation)
        if (shouldScroll) {
          requestAnimationFrame(() => {
            activeContent.scrollIntoView({ behavior: 'smooth', block: 'start' });
          });
        }
      } else {
        console.error(`[Tabs] Content panel not found: ${tabId}-tab`);
      }
    }
    
    // Add click listeners to all tab buttons
    tabButtons.forEach(button => {
      button.addEventListener('click', function() {
        const tabId = this.getAttribute('data-tab');
        if (tabId) {
          switchTab(tabId);
          // Update URL hash without triggering scroll
          history.replaceState(null, '', `#${tabId}`);
        } else {
          console.error('[Tabs] Button missing data-tab attribute:', this);
        }
      });
    });
    
    // CROWN⁴.6: Hash-aware initialization for "Jump to transcript" navigation
    // Run immediately and also after a short delay to catch late-arriving hashes
    handleHashNavigation();
    setTimeout(handleHashNavigation, 150);
    
    // Listen for hash changes (e.g., user clicks browser back/forward)
    window.addEventListener('hashchange', handleHashNavigation);
    
    function handleHashNavigation() {
      const hash = window.location.hash.replace('#', '');
      console.log(`[Tabs] Checking hash navigation, hash="${hash}", URL="${window.location.href}"`);
      
      if (hash) {
        // Map common hash values to tab IDs
        const tabMap = {
          'transcript': 'transcript',
          'highlights': 'highlights',
          'analytics': 'analytics',
          'tasks': 'tasks'
        };
        
        const tabId = tabMap[hash];
        if (tabId) {
          console.log(`[Tabs] Hash navigation detected: #${hash} -> switching to ${tabId} tab`);
          // Switch tab and scroll to it
          switchTab(tabId, true);
        } else {
          console.log(`[Tabs] Unknown hash: ${hash}`);
        }
      }
    }
    
    console.log('[Tabs] Tab switching initialized successfully!');
    
    // ========================================
    // Task Checkbox Handling
    // ========================================
    initializeTaskCheckboxes();
    
    // ========================================
    // WebSocket Event Listeners
    // ========================================
    initializeWebSocketListeners();
  }

  function initializeTaskCheckboxes() {
    const taskCheckboxes = document.querySelectorAll('.task-checkbox');
    console.log(`[Tasks] Found ${taskCheckboxes.length} task checkboxes`);
    
    taskCheckboxes.forEach(checkbox => {
      checkbox.addEventListener('change', function(e) {
        const taskId = e.target.getAttribute('data-task-id');
        const taskItem = e.target.closest('.task-item');
        
        if (!taskItem) return;
        
        if (e.target.checked) {
          taskItem.style.opacity = '0.6';
          const taskText = taskItem.querySelector('.task-text');
          if (taskText) {
            taskText.style.textDecoration = 'line-through';
          }
          
          console.log(`[Tasks] Task ${taskId} marked as complete`);
          
          // Emit task_complete event via WebSocket if available
          if (window.socket) {
            const sessionId = document.body.getAttribute('data-session-id');
            window.socket.emit('task_complete', {
              session_id: sessionId,
              task_id: taskId
            });
          }
        } else {
          taskItem.style.opacity = '1';
          const taskText = taskItem.querySelector('.task-text');
          if (taskText) {
            taskText.style.textDecoration = 'none';
          }
        }
      });
    });
  }

  function initializeWebSocketListeners() {
    if (window.socket) {
      console.log('[WebSocket] Listening for real-time updates...');
      
      window.socket.on('insights_generate', function(data) {
        console.log('[WebSocket] Insights update received:', data);
        if (data.status === 'completed') {
          console.log('[WebSocket] Insights completed, reloading page...');
          setTimeout(() => location.reload(), 1000);
        }
      });
      
      window.socket.on('insights_progress', function(data) {
        console.log('[WebSocket] Insights progress:', data.progress_percent + '%', data.message);
      });
      
      window.socket.on('analytics_update', function(data) {
        console.log('[WebSocket] Analytics update received:', data);
      });
    }
  }
})();
