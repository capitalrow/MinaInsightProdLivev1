# CROWN⁴.⁶ Execution Plan for the Tasks Page

Status: Detailed task breakdown to reach full spec parity. This is the actionable backlog to implement the CROWN⁴.⁶ “I Want…” requirements (meeting-native, semantic, emotionally calm, deterministic, offline-resilient).

## 0. Guiding Principles
- Meeting-native memory: every task keeps provenance (meeting, speaker, quote, confidence, agenda section, origin_hash).
- Instant optimism, guaranteed truth: optimistic UI first; reconcile via EventSequencer + checksum + vector clocks.
- Emotional calm: unified animation timing, ≤3 concurrent animations, contextual cues (calming vs energising).
- Deterministic continuity: multi-tab alignment, offline FIFO replay, idempotent endpoints, dedupe by origin_hash.

## 1. Arrival & Boot (≤200 ms, no spinner)
- IndexedDB/LocalStorage bootstrap: cache paint (tabs, counters, skeleton cards) within 200 ms; checksum validation + drift flag.
- WebSocket subscribe with last_event_id replay; retry with backoff; telemetry for latency + p95 reconciliation.
- Prefetch controller: preload next 50 tasks at 70% scroll; stable cursor guard (seen_ids) to avoid ghosts.
- QuietStateManager: cap animations concurrently (≤3), respect prefers-reduced-motion.

## 2. Capture & Creation
- Inline composer: focus; Enter=save, Esc=cancel; provisional IDs for optimistic insert; rollback on failure.
- AI proposals (task_nlp:proposed): confidence-graded glow; accept/decline flows keep origin_hash; throttle per session.
- NLP accept + manual create: enqueue to offline FIFO with vector clocks; retry/backoff; Undo toast.

## 3. Editing, Completion, Undo
- Inline title edit: 250 ms debounce; field-level PATCH diff; optimistic save tick; conflict badge on reconciliation.
- Chips (priority/due/assignee/labels): single-tap selectors; local reorder/spring animation; shimmer on due/priority change.
- Status toggle: burst animation + slide; Undo queue; completed tasks glide to Completed tab.
- Snooze: slide/fade; swipe-left gesture (mobile) + keyboard shortcut S; include snooze-until suggestion.
- Delete/restore: soft-delete with T+7d purge; Undo always available; confirmation fallback when modal missing.

## 4. Meeting Intelligence & Provenance
- Memory heatmap: visual emphasis based on recency/importance of originating meeting.
- Transcript context: hover/long-press bubble (5–10s snippet, speaker, intent summary); Jump-to-span morph transition.
- Agenda/section tagging for summary-derived tasks; provenance badge shows meeting, who said it, quote, confidence.
- Group Similar / Meeting Intelligence Mode: group by meeting, topic clusters, decision/follow-up/risk, spoken urgency; explain reorders (“Based on importance from Monday’s meeting”).
- Impact-aware ranking: lift tasks from high Impact Score meetings; expose “why” tooltip.

## 5. Search, Filter, Organize (semantic, <100 ms perceived)
- Dual-path search: local semantic cache + remote semantic API; cancel in-flight requests; debounce; transcript-aware results with jump links.
- Filters/tabs: status-driven tabs + counter pulse; TaskViewState persisted to store + IndexedDB; keyboard shortcuts (N, Cmd/Ctrl+K, Cmd/Ctrl+Enter, S).
- Sort: local first; reconcile server order; spring reorder animations; explain reorders when impact/urgency changes.
- Bulk multi-select: batch PATCH chunked; group animation; rollback on partial failure with inline alerts.

## 6. Offline, Consistency, Sync
- Offline indicator (gentle cloud); queue mutations in durable FIFO with vector clocks; per-action retries/backoff.
- Idle sync (30 s) checksum compare + delta pull; reconciliation indicators; BroadcastChannel multi-tab alignment.
- Conflict handling: merge by updated_at + actor_rank; mark reconciled; surface inline dot for conflicts resolved.
- Deduper on origin_hash for NLP duplicates; merge badge when collapsing duplicates.
- Ledger compaction for stored mutations; stable pagination guards.

## 7. Performance, Animations, Accessibility
- Targets: first paint ≤200 ms; mutation apply ≤50 ms; reconcile ≤150 ms p95; WS propagation ≤300 ms; scroll 60 FPS; prefetch CPU ≤5%.
- Unified animation timing table mapped to events/emotion cues; reduced-motion support; high-refresh (90–120hz) gesture tuning (right=complete, left=snooze, swipe-up hold=transcript context).
- Virtualized lists >50 items; adaptive prefetch; chunked rendering to avoid jank.
- Accessibility: focus order, ARIA labels for controls/badges, keyboard shortcuts coverage, screen-reader friendly provenance text.

## 8. Observability & Telemetry
- Emit structured events: trace_id, surface, event_name, latency_ms, optimistic_to_truth_ms, confidence_level, emotion_cue, user_focus_state, session_id, timestamp.
- Metrics: cache hit rate ≥0.9, offline replay 100%, optimistic→truth <150 ms p95, Calm Score (latency × animation × error rate), predictive accuracy drift <5%.
- Alerts: WS drop, checksum drift, replay backlog, conflict spikes; dashboards for latency, reconciliation, semantic search hit rates.

## 9. Security & Privacy
- Redacted ledger storing references not transcript content; per-event key rotation (hourly); short-lived JWT row-level auth.
- Cascade deletion for linked sessions; opaque trace IDs for cross-links; audit-ready mutation ledger.

## 10. Testing & QA Matrix
- Unit: EventSequencer ordering + vector clocks; deduper; TaskStore diff/merge; offline FIFO persistence; semantic search adapter.
- Integration/API: WS subscribe/replay; checksum reconciliation; conflict resolution; semantic search API contract; provenance payload.
- UI (Playwright): arrival paint speed; inline capture; AI proposal accept/decline; completion burst + undo; semantic search; group-similar mode; provenance hover/long-press; jump-to-span routing; swipe gestures; offline replay with sync toast.
- Performance: measure paint, mutation apply, reconciliation p95; scroll FPS; CPU overhead of prefetch/virtualization.
- Accessibility: keyboard shortcuts, focus traps, ARIA for badges/buttons, reduced-motion behavior.
- Mobile: viewport/thumb reach, swipe actions, high-refresh animation cadence, transcript context on swipe-up hold.

## 11. Delivery Milestones (suggested)
1) Foundation: cache/bootstrap, WS replay, EventSequencer + TaskStore diff, offline FIFO + vector clocks, checksum/idle sync, telemetry scaffolding.
2) UX Core: optimistic create/edit/complete/snooze/delete/undo; unified animation timing; counters/tabs; keyboard shortcuts.
3) Meeting Intelligence: memory heatmap, provenance badges, transcript bubble + jump, agenda tags, impact-aware ordering, group-similar mode.
4) Semantic Search & Organize: semantic search dual-path, cluster/grouping, bulk edit, explainable reorders, filters/sort persistence.
5) Mobile & Accessibility: gesture tuning, reachability, ARIA/reduced motion, screen-reader provenance.
6) Observability & Hardening: Calm Score, predictive accuracy drift, alerts; ledger compaction; regression/perf suites.
