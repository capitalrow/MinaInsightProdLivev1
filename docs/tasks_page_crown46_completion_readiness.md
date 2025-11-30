# Tasks Page CROWN⁴.6 Completion Readiness Checklist

This checklist clarifies what must be built before the Tasks page can be declared compliant with the CROWN⁴.6 specification. It is scoped to the web client and assumes matching backend capabilities (event ledger, semantic search, provenance retrieval, offline queues).

## Functional gaps to close
- **Semantic, transcript-aware search (<100 ms target):** AI-backed search across task text + transcript spans with meeting/topic/intent filters; preload indexes for mobile.
- **Meeting intelligence & grouping:** "Group Similar" mode that clusters by meeting, topic, intent type (decision/follow-up/risk), urgency tone, and renders a memory heatmap for recent meetings.
- **Spoken provenance overlays:** Each card shows originating meeting, speaker, utterance snippet, confidence, and jump-to-transcript span; hover/long-press preview bubble.
- **Predictive task intelligence:** Suggestions for due date/priority/owner/labels tied to Impact Score and meeting context; gentle AI nudges and low-confidence tuck-away state.
- **Completion UX + undo:** Burst animation, glide-to-completed, always-on undo with soft delete window and ledgered restores.
- **Inline editing ergonomics:** Instant title edit, one-tap priority/assign/labels with lightweight selectors, cognitive tooltip for auto-clean training.
- **Mobile gestures & reachability:** Swipe complete/snooze and swipe-up transcript reveal; thumb-friendly layout tuning for 90–120 Hz devices.
- **Offline + multi-tab truth:** IndexedDB cache with vector-clock replay, offline cloud indicator, preload of next 50 tasks, BroadcastChannel sync, checksum reconciliation.
- **Adaptive ordering & navigation:** Contextual reordering with explanations, collapsible groups, calm motion limits (QuietStateManager).
- **Telemetry & sequencing:** EventSequencer tokens, checksum validation, Observability 2.0 payloads, predictive accuracy drift tracking, and animation calm score metrics.

## Required engineering assets
- **Services:** Event ledger + vector clocks, semantic search endpoint, provenance resolver (meeting → transcript span), predictive engine for due/priority/owner/labels.
- **Clients:** WebSocket subscriber with deterministic replay, abortable fetches for filters/sorts, offline FIFO queue, IndexedDB cache mirror, BroadcastChannel sync.
- **UI modules:** Memory heatmap renderer, grouping toggles, provenance bubble, AI proposal surface with confidence tiers, gesture handlers, animation controller.
- **QA harness:** Performance probes (first paint, search latency), offline replay tests, multi-tab consistency tests, gesture e2e tests, semantic search relevancy checks, and provenance jump-to-span verification.

## Exit criteria to claim CROWN⁴.6 readiness
1. First paint ≤200 ms on cold start with cache pre-paint; search responses <100 ms p95 (desktop + mobile profiles).
2. Semantic search returns transcript-linked tasks with provenance bubble and jump-to-span navigation.
3. Group Similar mode clusters by meeting/topic/intent/urgency and renders memory heatmap with collapse/expand.
4. Completion provides burst + glide + undo; soft-deleted items restorable for 7 days with ledger audit.
5. Inline edits, priority/assign/labels selectors, and cognitive tooltip operate inline without modal pauses.
6. Offline mode retains edits with vector-clock replay; reconnect shows “Synced” toast and no duplicates across tabs.
7. Mobile gestures (complete/snooze, swipe-up transcript reveal) pass e2e tests on 90–120 Hz profiles.
8. Telemetry emits Observability 2.0 payloads for core events with calm-score and predictive accuracy metrics.

## Current status
Current JavaScript initializers only wire basic filters, new-task triggers, checkbox toggles, delete/restore, and proposal hooks. None of the above exit criteria are implemented yet; the Tasks page is **not CROWN⁴.6-complete** until each gap is delivered and verified.
