# CROWN 4.6 Testing Strategy & Execution Guide

## Overview

This directory contains comprehensive test suites validating 100% alignment with the CROWN 4.6 specification for the Mina Tasks page.

## Test Suites

### 1. Performance Validation (`test_crown46_performance_validation.py`)
**What it tests:**
- ✅ First paint <200ms (cache-first bootstrap)
- ✅ Optimistic UI updates <150ms (p95)
- ✅ Semantic search <100ms
- ✅ Scroll performance 60 FPS
- ✅ Completion UX animation timing
- ✅ Event reconciliation latency

**How to run:**
```bash
# Run performance tests
pytest tests/e2e/test_crown46_performance_validation.py -v -s

# Run with HTML report
pytest tests/e2e/test_crown46_performance_validation.py --html=tests/results/crown46_perf_report.html

# Run specific test
pytest tests/e2e/test_crown46_performance_validation.py::TestCROWN46Performance::test_01_first_paint_under_200ms -v
```

**Success criteria:**
- All metrics must meet or exceed thresholds
- Performance report saved to `tests/results/crown46_performance_*.json`
- Zero failed assertions

---

### 2. Event Sequencing Validation (`test_event_sequencing_validation.py`)
**What it tests:**
- ✅ All 20 event matrix scenarios
- ✅ Vector clock ordering
- ✅ Idempotency guarantees
- ✅ Offline queue replay (FIFO)
- ✅ Event deduplication (origin_hash)

**How to run:**
```bash
# Run event sequencing tests
pytest tests/crown46/test_event_sequencing_validation.py -v -s

# Test specific event
pytest tests/crown46/test_event_sequencing_validation.py::TestCROWN46EventSequencing::test_03_offline_queue_replay_idempotency -v
```

**Success criteria:**
- All events fire in correct chronological order
- No event ordering violations
- Offline queue replays successfully
- Idempotency verified (replay = same result)

---

### 3. AI/Semantic Intelligence Validation (Coming Next)
**What it will test:**
- Semantic search accuracy (≥0.8 cosine similarity)
- Meeting Intelligence Mode grouping (≥95% accuracy)
- Predictive engine suggestions
- Impact Score integration
- AI learning from user corrections

---

### 4. Offline/Sync Resilience Tests (Coming Next)
**What it will test:**
- Multi-tab BroadcastChannel sync
- Offline queue FIFO replay
- Conflict resolution (vector clocks)
- Zero data loss guarantee
- Checksum validation

---

### 5. Emotional Design & UX Validation (Coming Next)
**What it will test:**
- Animation timing (<150ms frames)
- Completion burst visual regression
- Undo functionality
- Calm score calculation (±2% accuracy)
- Emotional cue appropriateness

---

## Test Execution Matrix

| Requirement Category | Test Suite | Status | Command |
|---------------------|------------|--------|---------|
| Performance (<200ms) | `test_crown46_performance_validation.py` | ✅ Ready | `pytest tests/e2e/test_crown46_performance_validation.py` |
| Event Sequencing | `test_event_sequencing_validation.py` | ✅ Ready | `pytest tests/crown46/test_event_sequencing_validation.py` |
| AI/Semantic Search | TBD | 🚧 Pending | - |
| Offline/Sync | TBD | 🚧 Pending | - |
| Emotional Design | TBD | 🚧 Pending | - |
| Mobile Experience | TBD | 🚧 Pending | - |
| Meeting Integration | TBD | 🚧 Pending | - |

---

## Continuous Integration

### GitHub Actions Workflow (Recommended)

```yaml
name: CROWN 4.6 Validation

on: [push, pull_request]

jobs:
  performance:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r tests/setup/requirements.txt
      - run: playwright install chromium
      - run: pytest tests/e2e/test_crown46_performance_validation.py --html=report.html
      - uses: actions/upload-artifact@v3
        with:
          name: performance-report
          path: report.html
          
  event-sequencing:
    runs-on: ubuntu-latest  
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r tests/setup/requirements.txt
      - run: playwright install chromium
      - run: pytest tests/crown46/test_event_sequencing_validation.py --html=report.html
```

---

## Performance Budgets

Enforce these thresholds in CI to catch regressions:

```python
PERFORMANCE_BUDGETS = {
    'first_paint_ms': 200,        # Target: <200ms
    'cache_bootstrap_ms': 50,     # Target: <50ms
    'semantic_search_ms': 100,    # Target: <100ms
    'optimistic_update_ms': 150,  # Target: <150ms (p95)
    'event_latency_ms': 300,      # Target: <300ms
    'scroll_fps': 60,             # Target: 60 FPS
    'reconciliation_ms': 150      # Target: <150ms (optimistic→truth)
}
```

**CI Failure Condition:** ANY metric exceeds its budget by >10%

---

## Coverage Requirements

- **Unit Tests:** >90% line coverage for critical modules
  - `semantic-search.js`
  - `predictive-engine.js`
  - `task-store.js`
  - `event-sequencer.py`

- **Integration Tests:** >80% statement coverage for Flask services
  - `services/event_sequencer.py`
  - `services/task_extraction_service.py`
  - `routes/api_tasks.py`

- **E2E Tests:** 100% coverage of user-facing features
  - All 20 event matrix scenarios
  - All CROWN 4.6 performance requirements
  - All emotional design elements

---

## Debugging Failed Tests

### Performance test failures

```bash
# Run with detailed timing
pytest tests/e2e/test_crown46_performance_validation.py -v -s --capture=no

# Check performance report
cat tests/results/crown46_performance_*.json | jq '.metrics'

# Profile specific operation
pytest tests/e2e/test_crown46_performance_validation.py::TestCROWN46Performance::test_01_first_paint_under_200ms -v -s
```

### Event sequencing failures

```bash
# Run with event logging
pytest tests/crown46/test_event_sequencing_validation.py -v -s --log-cli-level=DEBUG

# Check event order violations
grep "violation" tests/results/*.log
```

---

## Visual Regression Testing

Use Percy or Playwright's built-in screenshot comparison:

```bash
# Capture baselines
pytest tests/visual/test_task_animations.py --update-snapshots

# Run visual regression
pytest tests/visual/test_task_animations.py
```

---

## Load Testing

K6 scenarios for concurrent user simulation:

```bash
# Run load test (100 concurrent users)
k6 run tests/k6/scenarios/04-slo-verification.js --vus 100 --duration 60s

# Check SLO compliance
cat results.json | jq '.metrics.http_req_duration'
```

---

## Test Results & Reporting

All test runs generate artifacts:

- **Performance Reports:** `tests/results/crown46_performance_*.json`
- **Event Logs:** `tests/results/crown46_events_*.json`
- **HTML Reports:** `tests/results/html-report/index.html`
- **Coverage Data:** `.coverage` (use `coverage html` to view)

---

## Manual Testing Checklist

Some aspects require human validation:

### Emotional Design Heuristics
- [ ] Animations feel smooth (no jank)
- [ ] Completion burst is satisfying
- [ ] Calm UI principles evident
- [ ] No overwhelming motion
- [ ] Emotional cues appropriate for meeting type

### Mobile Experience  
- [ ] Touch targets ≥48px
- [ ] Swipe gestures responsive (<120ms)
- [ ] Thumb-reachable controls
- [ ] 90-120Hz animation smoothness
- [ ] No layout shift on interaction

### Accessibility
- [ ] Keyboard navigation complete
- [ ] Screen reader friendly
- [ ] WCAG AA contrast ratios
- [ ] Focus indicators visible
- [ ] ARIA labels present

---

## Next Steps

1. ✅ **Task 1 Complete:** Performance validation framework built
2. ✅ **Task 2 Complete:** Event sequencing tests implemented
3. 🚧 **Task 3:** Build AI/semantic intelligence validation
4. 🚧 **Task 4:** Implement offline/sync resilience tests
5. 🚧 **Task 5:** Create emotional design validation suite
6. 🚧 **Task 6:** Mobile experience framework
7. 🚧 **Task 7:** Meeting integration tests
8. 🚧 **Task 8:** Wire into CI/CD pipeline

---

## Contact & Support

For questions about the testing strategy:
- Review CROWN 4.6 specification in project root
- Check `/tests/e2e/test_strategy.md` for overall approach
- See `/docs/` for architecture documentation

**Testing Philosophy:** Validate behavior, not implementation. Tests should verify the CROWN 4.6 guarantees from a user's perspective.
