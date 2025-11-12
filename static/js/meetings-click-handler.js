/**
 * Mina Meetings Click Handler v2.2
 * Safely attaches click listeners to meeting cards in a CSP-compliant way.
 * Author: Mina AI (Chinyemba)
 */

(() => {
  const logPrefix = "[MeetingsClickHandler]";
  let isBound = false;

  // Utility: safe logging wrapper
  const log = (...args) => console.log(`${logPrefix}`, ...args);
  const warn = (...args) => console.warn(`${logPrefix}`, ...args);

  // Utility: send telemetry event if CROWN+ telemetry is available
  const track = (name, payload = {}) => {
    if (window.CROWNTelemetry?.record) {
      window.CROWNTelemetry.record(name, payload);
      log("📡 Telemetry event sent:", name, payload);
    } else {
      log("⚙️ Telemetry skipped (not available)", name);
    }
  };

  // Utility: redirect with graceful delay
  const navigateToSession = (sessionId) => {
    if (!sessionId) {
      window.showToast?.("Meeting is still being processed.", "info");
      warn("⚠️ No sessionId provided. Navigation skipped.");
      return;
    }

    // Use smooth navigation if available
    if (window.smoothNavigation?.goTo) {
      log("✨ Smooth navigation to /sessions/" + sessionId);
      window.smoothNavigation.goTo(`/sessions/${sessionId}`);
    } else {
      log("🔁 Direct navigation to /sessions/" + sessionId);
      window.location.href = `/sessions/${sessionId}`;
    }
  };

  // Core binding logic
  const bindMeetingClicks = () => {
    if (isBound) {
      log("⏭️ Click handler already bound — skipping duplicate bind");
      return;
    }

    const container = document.getElementById("active-meetings");
    if (!container) {
      warn("❌ active-meetings container not found — retrying in 1s");
      setTimeout(bindMeetingClicks, 1000);
      return;
    }

    container.addEventListener("click", (e) => {
      const card = e.target.closest(".meeting-card");
      if (!card || e.target.closest(".meeting-actions")) return;

      const { meetingId, sessionId, meetingTitle } = card.dataset;
      log("🟢 Card clicked:", { meetingId, sessionId, meetingTitle });

      // Prevent ghost clicks if missing data
      if (!meetingId) {
        warn("⚠️ Clicked card missing meetingId");
        return;
      }

      // Use global dashboard handler if it exists
      if (typeof window.handleCardClick === "function") {
        log("➡️ Using global handleCardClick");
        window.handleCardClick({
          currentTarget: card,
          stopPropagation() {},
          preventDefault() {},
        });
      } else {
        // Local fallback: direct navigation
        navigateToSession(sessionId);
      }

      // Optional telemetry
      track("meeting_card_clicked", { meetingId, sessionId });
    });

    isBound = true;
    log("✅ Meeting click handler bound successfully");
  };

  // Ensure we only bind once DOM + JS fully ready
  window.addEventListener("load", bindMeetingClicks);

  // Safety: handle async re-renders (e.g. via WebSocket updates)
  const observer = new MutationObserver((mutations) => {
    const added = mutations.some((m) => m.addedNodes.length);
    if (added && !isBound) {
      log("🔄 DOM changed — rebinding click listeners");
      bindMeetingClicks();
    }
  });

  observer.observe(document.body, {
    childList: true,
    subtree: true,
  });
})();
