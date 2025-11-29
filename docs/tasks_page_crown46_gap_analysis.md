# Tasks Page vs CROWN⁴.6 Requirements – Gap Analysis

## Summary
The current Tasks page wiring remains **far short** of the CROWN⁴.6 “I Want…” specification. It only covers baseline DOM event binding (filters, new task modal trigger, checkboxes, delete/restore, and menu hooks) and a simple client-side search/sort. There is **no implementation** of the experience-critical items in the spec: sub-200 ms contextual load with memory heatmap, meeting-aware emotional cues, semantic/AI search, meeting-provenance overlays, contextual grouping, tactile completion animations, inline cognitive tooltips, or the transcript-linked previews that differentiate Mina.

## Evidence from current code
- The master initializer only sets up basic controls (filter tabs, new task buttons, checkbox toggles, restore/delete, menu hooks) and waits for optimistic UI; it does not include memory heatmaps, emotional cues, semantic grouping, transcript previews, or animation logic.
  - `static/js/task-page-master-init.js` lines 17–190 show the initialization map and handlers for filters, new task buttons, checkboxes, restore, and delete with fallback to direct API calls but no contextual UI or animation hooks.
- Search and sort are implemented as plain string matching on title/assignee/labels with simple DOM filtering and sort routines; there is no semantic search, transcript awareness, or sub-100 ms AI relevance layer described in the spec.
  - `static/js/task-search-sort.js` lines 6–146 filter tasks by `includes()` on text content and toggle visibility/order in the DOM.
- No code path provides meeting-informed emotional cues, calming/energising animations, or contextual “spoken provenance” overlays; the initializer and search/sort modules focus purely on DOM updates without the adaptive cues or transcript span previews mandated by CROWN⁴.6.

## Conclusion
Given the current implementation, the Tasks page does **not** satisfy the CROWN⁴.6 requirements. Achieving compliance will require new features for meeting-aware context (memory heatmap, transcript previews, agenda tagging), semantic/AI search and grouping, tactile completion/undo flows with animations, emotional cue orchestration, offline-first replay with UX cues, and full provenance display per task.
