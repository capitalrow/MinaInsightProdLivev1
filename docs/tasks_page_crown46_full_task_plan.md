# Tasks Page CROWN¹⁴.⁶ Alignment Task List

Status: gaps remain. This list enumerates the concrete work required to bring the Tasks surface to the CROWN¹⁴.⁶ spec (meeting-native, emotionally calm, deterministic, offline-resilient).

## A. Arrival & Boot (instant paint <200 ms)
- Add IndexedDB/LocalStorage bootstrap of cached tasks + checksum validation; paint skeleton + counters within 200 ms.
- Subscribe to tasks WebSocket with last_event_id replay; reconcile drift via checksum + diff.
- Prefetch next 50 tasks at 70% scroll; guard with stable cursor + seen_ids.
- Add QuietStateManager caps for concurrent animations (<=3) to keep calm UX.

## B. Capture & Creation
- Inline composer: focus, Enter=save, Esc=cancel; generate provisional IDs for optimistic insert.
- AI proposals: render confidence-graded glow; accept/decline flows keep origin_hash; throttle spam per session.
- Manual create + NLP accept flows enqueue to offline FIFO with vector clocks; retry with backoff.

## C. Editing, Completion, Undo
- Inline title edit with 250 ms debounce + optimistic tick; field-level diff patch.
- Priority/due/assignee/labels chips: one-tap selectors; optimistic reorder + shimmer.
- Status toggle: burst animation + slide; maintain Undo toast with rollback queue.
- Snooze: slide-to-snoozed with calm fade; support swipe gestures (mobile) and keyboard shortcuts.
- Kebab menu: actionable options only; guard against duplicate listeners; include delete, restore, jump-to-span, link meeting.

## D. Meeting Intelligence & Provenance
- Memory heatmap: highlight tasks by recency/importance of originating meeting.
- Transcript context: hover/long-press preview bubble (5-10s snippet, speaker, intent summary); tap/hover to jump-to-span with morph transition.
- Agenda/section tagging for tasks derived from meeting summaries; display provenance badge (meeting, who said it, confidence).
- Group Similar / Meeting Intelligence Mode: group by meeting, topic clusters, decision vs follow-up vs risk, spoken urgency.
- Impact-aware ranking: lift tasks from high-Impact Score meetings; explain reorder reason.

## E. Search, Filter, Organize
- Semantic + keyword search (<100 ms) with spoken-context awareness; debounce + cancel in-flight queries; show transcript-linked results.
- Filters/tabs: status-driven tabs with counter pulse; persistent TaskViewState in store + IndexedDB.
- Sort: local first then reconcile server ordering; spring reorder animations.
- Bulk multi-select: batch patch with chunking; group animation for mass changes.

## F. Offline, Consistency, Sync
- Offline detection UI (gentle cloud icon); queue mutations in durable FIFO with vector clocks.
- Idle sync (30 s) checksum compare + delta pull; BroadcastChannel multi-tab alignment.
- Conflict handling: merge by updated_at + actor_rank; reconciliation indicator for resolved conflicts.
- Deduper on origin_hash to prevent NLP duplicates; merge badge for merged tasks.
- Ledger compaction for stored mutations; retry policy with bounded backoff.

## G. Performance, Animations, Accessibility
- Target metrics: first paint <=200 ms, mutation apply <=50 ms, reconcile <=150 ms p95, WS propagation <=300 ms, scroll 60 FPS.
- Unified animation timing; limit concurrent animations; support high-refresh (90-120hz) mobile gestures (swipe complete/snooze, swipe-up hold for transcript context).
- Virtualize lists >50 items; adaptive prefetch to keep CPU overhead <=5%.
- Accessibility: focus order, keyboard shortcuts (N, Cmd/Ctrl+K, Cmd/Ctrl+Enter, S), ARIA labels, reduced-motion mode.

## H. Observability & Telemetry
- Emit structured events with trace_id, latency_ms, optimistic_to_truth_ms, confidence_level, emotion_cue, session_id.
- Measure cache hit rate, offline replay success, predictive accuracy drift, Calm Score (latency x animation x error rate).
- Alerting for WS drops, checksum drift, replay backlogs; dashboards for latency p95 and optimistic reconciliation times.

## I. Security & Privacy
- Redacted ledger storing references not transcript content; per-event key rotation; short-lived JWT row-level auth.
- Cascade deletion for linked sessions/tasks; opaque trace IDs for cross-linking; audit-friendly ledger.

## J. Delivery & QA
- Implement EventSequencer validation + TaskStore delta merge before UI commit.
- Add automated Playwright flows for arrival, capture, edit, complete, search, provenance hover, offline replay.
- Add regression tests for optimistic/rollback, dedupe, group-similar clustering, jump-to-transcript routing, and vector-clock replay.
- Validate mobile gestures via emulator/screenshot; ensure swipe actions + context reveal.

## K. Open Gaps vs Current State (high-level)
- No semantic/spoken-context search or sub-100 ms response path.
- No meeting-aware provenance surfaces (heatmap, transcript bubble, agenda tags) or impact-based ordering.
- No offline FIFO, vector clocks, BroadcastChannel sync, or checksum reconciliation.
- No emotional cues/animation system tied to event/emotion map; no unified timing constraints.
- No telemetry for optimistic-to-truth, Calm Score, cache hit rate, or predictive accuracy drift.
- No grouped intelligence mode (by meeting/topic/decision/follow-up/risk) or clustering.
- No swipe/mobile gesture support; limited accessibility and keyboard coverage.
