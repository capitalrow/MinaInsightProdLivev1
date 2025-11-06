(() => {
  const log = (...a) => console.log('[MeetingsPage]', ...a);

  function delegate(root, event, selector, handler) {
    root.addEventListener(event, (e) => {
      const el = e.target.closest(selector);
      if (el && root.contains(el)) handler(e, el);
    });
  }

  function navigate(card) {
    const sid = card.dataset.sessionId;
    if (!sid) {
      window.showToast?.('Meeting still processing.', 'info');
      return;
    }
    window.location.assign(`/sessions/${sid}`);
  }

  async function archive(meetingId) {
    log('Archiving', meetingId);
    const res = await fetch(`/api/meetings/${meetingId}/archive`, { method: 'POST' });
    if (res.ok) window.showToast?.('Archived', 'success');
    else window.showToast?.('Archive failed', 'error');
  }

  function init() {
    const container = document.getElementById('active-meetings') || document;
    log('Binding meetings handlers');

    // Card click
    delegate(container, 'click', '.meeting-card', (e, card) => {
      if (e.target.closest('.meeting-actions')) return;
      navigate(card);
    });

    // Action buttons
    delegate(container, 'click', '.meeting-actions [data-action]', (e, btn) => {
      e.preventDefault();
      e.stopPropagation();
      const { action, meetingId } = btn.dataset;
      if (action === 'archive') archive(meetingId);
      if (action === 'share') window.showToast?.('Share coming soon', 'info');
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();