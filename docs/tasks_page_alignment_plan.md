# Tasks Page Alignment Plan for CROWN 4.6 Spec

This document outlines immediate and near-term actions to bring the Tasks page in line with the CROWN 4.6 requirements while leveraging the existing codebase (templates, static JS, and TaskStore backend). For the exhaustive backlog that enumerates every task needed for full CROWN⁴.⁶ parity (including performance, offline, semantic search, and meeting-intelligence work), see `docs/tasks_page_crown46_execution_plan.md`.

## Delivery Philosophy
- **Meeting-native first:** Every UI surface must show spoken provenance (meeting, speaker, transcript span) without friction.
- **Instant optimism, verified truth:** Optimistic UI updates within 50 ms, reconciled via WebSocket/event-sequencer confirmation within 150 ms.
- **Calm, expressive interactions:** Minimal clutter, micro-animations with controlled concurrency (max 3 simultaneous), and meeting-informed emotional cues.

## Phase 0 – Baseline Wiring (aligns with CROWN §2, §4, §5)
1. **Initialization guarantees**
   - Ensure `task-page-init.js` registers handlers for: new task, checkboxes, kebab menu, inline title edit, priority/due chips, snooze, delete, search, sort, filter tabs, AI proposals, and jump-to-transcript.
   - Blocker fix: call `initTaskPage()` on DOMContentLoaded and verify imports of `task-actions-menu.js`, `task-proposal-ui.js`, and checkbox toggle handlers.
2. **Event sequencing + optimistic UI**
   - Emit provisional IDs for manual creates and NLP accepts; render immediately with a shimmer state until confirmation (`status: pending_truth`).
   - Use the existing WebSocket channel to reconcile with `event_id` ordering; discard out-of-order updates and request a diff when gaps appear.
3. **Completion UX**
   - Attach checkbox → optimistic status toggle, micro “burst” animation, then slide completed card to the Completed tab; surface “Undo” toast with 7s window.

## Phase 1 – Perceived Performance (CROWN §1, §7, §15)
1. **<200 ms paint**
   - Preload cached tasks from IndexedDB before network; show counters with a subtle fade while checksum verification runs.
   - Abortable fetch for search/filter changes; apply local filter immediately, re-run with server truth when response arrives.
2. **Prefetch + virtualization**
   - Enable virtual list for >50 items and trigger prefetch at 70% scroll (`PrefetchController`).
   - Preload next 50 tasks in offline queue and hydrate state on reconnect.
3. **Quiet animation budget**
   - Centralize animation timing tokens (e.g., 120–160 ms easing) and prevent more than 3 concurrent animations to maintain calm motion.

## Phase 2 – Meeting Intelligence (CROWN §3, §4, §7, §14)
1. **Spoken provenance on every card**
   - Display meeting title, speaker, transcript span, and origin confidence; add “Jump to transcript” button that routes to `/transcript/<session>#<span>` with smooth morph transition.
   - Long-press/hover → show 5–10s transcript bubble with AI-summarized intent.
2. **Memory heatmap + grouping**
   - Add “Group Similar” toggle to cluster by meeting, topic, intent type (decision/follow-up/risk), and spoken urgency. Default to deterministic order; annotate any auto-reorder with a short explainer.
3. **Semantic search**
   - Client-side debounce (100 ms) to filter locally; parallel REST call for semantic results keyed by query embedding. Ensure <100 ms perceived response by rendering local results first.

## Phase 3 – Intelligent organisation & suggestions (CROWN §4, §10, §12)
1. **Predictive defaults**
   - Use Impact Score + meeting importance to lift priority; pre-fill due dates (“tomorrow morning”) and labels (“Follow-up”, “Risk”).
   - Surface low-confidence AI tasks in a “Suggested” strip; accept → convert to canonical task retaining `origin_hash`.
2. **Context-aware reorder**
   - When new meeting signals higher urgency, reorder locally with spring animation and a small tooltip (“Based on Monday’s meeting”). Maintain deterministic server order via event tokens.
3. **Relational awareness**
   - Link tasks to projects/people/insights; render connected items inline with minimal badges.

## Phase 4 – Offline, Sync, and Recovery (CROWN §8, §9)
1. **Offline-first posture**
   - Show gentle cloud icon when offline; queue mutations in durable FIFO with vector clocks. Replay on reconnect and reconcile via `updated_at` + actor rank.
2. **Multi-tab consistency**
   - Use BroadcastChannel to mirror TaskStore deltas across tabs; checksum compare every 30s idle sync.
3. **Error auto-recovery**
   - 409 conflicts → merge server truth, mark reconciled with a subtle dot; failed saves retry ×3 then mark “Needs attention”. WS drop triggers ledger diff replay.

## Phase 5 – Observability & Controls (CROWN §11, §12, §13)
1. **Telemetry envelope**
   - Emit per-event payload with latency, optimistic→truth delta, confidence, emotion cue, session_id, and Calm Score metrics.
2. **Performance guards**
   - Targets: first paint ≤200 ms, mutation apply ≤50 ms, reconcile ≤150 ms p95, WS propagation ≤300 ms. Profile scroll FPS for 60+.
3. **Security posture**
   - Keep transcript spans redacted in logs; row-level auth via short-lived JWT; cascade delete for linked sessions.

## Immediate Checklist (next PRs)
- [ ] Verify and fix `task-page-init.js` to call all initializers.
- [ ] Attach handlers for New Task, checkbox toggle, kebab menu, inline edit, priority/due chips, snooze, delete, AI proposals, jump-to-transcript.
- [ ] Implement optimistic status/due/priority updates with reconciliation path.
- [ ] Add spoken provenance UI elements (meeting, speaker, transcript span, confidence) and long-press preview bubble.
- [ ] Introduce semantic search debounce + local-first results; server-enhanced fallback.
- [ ] Wire BroadcastChannel + offline FIFO replay and checksum idle sync.
- [ ] Instrument telemetry envelope for every task event.
