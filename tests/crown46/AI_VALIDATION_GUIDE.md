# AI & Semantic Intelligence Validation Guide

## Overview

This guide explains the AI validation test suite that ensures CROWN 4.6 AI features meet accuracy and quality requirements.

## Test Suite: `test_ai_semantic_validation.py`

### Architecture

The `AIMetricsValidator` class provides:
- **Metric collection** with multi-sample averaging
- **Automated threshold validation** against CROWN 4.6 requirements
- **Cosine similarity calculation** for semantic search
- **Statistical correlation** using Spearman's rank correlation
- **JSON reporting** for CI/CD integration

---

## Test 1: Semantic Search Accuracy

**Requirement:** ≥0.8 cosine similarity between query and results

### What it validates:
- Query understanding and intent matching
- Embedding quality for semantic similarity
- Result relevance to natural language queries

### How it works:
1. Enables semantic search mode (if toggle exists)
2. Executes 3 test queries with expected keyword patterns
3. Measures similarity between query and top results
4. Calculates average similarity across all results
5. Asserts ≥0.8 threshold is met

### Test queries:
```python
'follow up on yesterday discussion'      # Tests temporal + context understanding
'urgent deadline tomorrow'               # Tests priority + time awareness
'review document before meeting'         # Tests action + dependency awareness
```

### Graceful degradation:
- If semantic search not detected → SKIP with warning
- If search UI not found → SKIP with warning
- Falls back to keyword overlap if embeddings unavailable

### Expected data format:
```javascript
// Tasks should have similarity scores in dataset
<div class="task-card" data-similarity="0.85">
  <span class="task-title">Follow up on client discussion</span>
</div>
```

---

## Test 2: Meeting Intelligence Mode Grouping

**Requirement:** ≥95% accuracy in grouping tasks by meeting session

### What it validates:
- AI's ability to cluster tasks from same meeting
- Session ID consistency within groups
- Temporal and contextual grouping logic

### How it works:
1. Enables Meeting Intelligence Mode
2. Extracts meeting groups from UI or task store
3. Validates session_id consistency within each group
4. Calculates: `accuracy = correctly_grouped / total_groupable`
5. Asserts ≥95% threshold is met

### Expected data format:
```html
<div class="meeting-group" data-meeting-id="session_123">
  <h3 class="meeting-title">Standup - Nov 19, 2025</h3>
  <div class="task-card" data-session-id="session_123">...</div>
  <div class="task-card" data-session-id="session_123">...</div>
</div>
```

### Accuracy calculation:
```python
for each group:
    most_common_session = mode(session_ids)
    correct_tasks = count(tasks with most_common_session)
    accuracy = sum(correct_tasks) / sum(all_tasks)
```

---

## Test 3: Predictive Engine Suggestions

**Requirement:** ≥70% precision (user acceptance rate)

### What it validates:
- Suggestion relevance and quality
- User acceptance as a proxy for precision
- Confidence score calibration

### How it works:
1. Retrieves AI suggestions from UI or predictive engine
2. Filters high-confidence suggestions (≥0.7)
3. Counts user-accepted suggestions
4. Calculates: `precision = accepted / total_suggestions`
5. Validates ≥70% threshold

### Expected data format:
```html
<div class="ai-suggestion" 
     data-suggestion-type="task_creation"
     data-confidence="0.85"
     data-accepted="true">
  Suggestion: Schedule follow-up meeting
</div>
```

### Metrics tracked:
- Total suggestions generated
- High confidence suggestions (≥0.7)
- User-accepted suggestions
- Precision = acceptance rate

---

## Test 4: Impact Score Integration

**Requirement:** ≥0.85 Spearman correlation with task priority

### What it validates:
- Impact Score calculation accuracy
- Correlation between AI-computed score and user priorities
- Prioritization logic consistency

### How it works:
1. Extracts tasks with Impact Scores
2. Maps priority levels to numeric values (urgent=4, high=3, medium=2, low=1)
3. Calculates Spearman rank correlation coefficient
4. Asserts ≥0.85 correlation threshold
5. Reports statistical significance (p-value)

### Expected data format:
```html
<div class="task-card" 
     data-impact-score="8.5"
     data-priority="high">
  <span class="impact-score">8.5</span>
</div>
```

### Statistical validation:
```python
from scipy.stats import spearmanr

correlation, p_value = spearmanr(impact_scores, priority_values)
# correlation ≥ 0.85 required
# p_value < 0.05 for statistical significance
```

---

## Test 5: AI Learning Feedback Loop

**Requirement:** AI must incorporate user corrections

### What it validates:
- Feedback mechanism exists and is functional
- User corrections are recorded
- Feedback count accumulates over time

### How it works:
1. Simulates user rejection of a suggestion
2. Calls `predictiveEngine.recordFeedback()`
3. Verifies feedback was recorded
4. Checks feedback count increases

### Expected API:
```javascript
window.predictiveEngine.recordFeedback({
  suggestion_id: 'suggestion_123',
  action: 'reject',  // or 'accept'
  reason: 'not_relevant',
  timestamp: Date.now()
});

window.predictiveEngine.getFeedbackCount(); // Returns total feedback events
```

---

## Running the Tests

### Run all AI tests:
```bash
pytest tests/crown46/test_ai_semantic_validation.py -v -s
```

### Run specific test:
```bash
pytest tests/crown46/test_ai_semantic_validation.py::TestCROWN46AISemanticIntelligence::test_01_semantic_search_accuracy -v
```

### With HTML report:
```bash
pytest tests/crown46/test_ai_semantic_validation.py --html=tests/results/ai_report.html --self-contained-html
```

---

## Interpreting Results

### Console output example:
```
AI TEST 1: Semantic Search Accuracy (≥0.8 Cosine Similarity)
================================================================================
  ✅ Semantic search enabled
  Query: 'follow up on yesterday discussion' → Result: 'Follow up on client meeting...' (similarity: 0.87)
  Query: 'urgent deadline tomorrow' → Result: 'Complete urgent report by EOD...' (similarity: 0.82)
  
  Average Similarity: 0.845 (threshold: 0.8)
  Queries Tested: 3
  Valid Results: 6
  ✅ PASS: Semantic search meets ≥0.8 similarity requirement
```

### JSON report structure:
```json
{
  "timestamp": "2025-11-19T10:30:00",
  "summary": {
    "total_metrics": 4,
    "passed": 3,
    "failed": 1
  },
  "metrics": {
    "semantic_search_cosine": [0.87, 0.82, 0.85],
    "meeting_grouping_accuracy": [0.96],
    "predictive_precision": [0.65],
    "impact_score_correlation": [0.88]
  },
  "thresholds": {
    "semantic_search_cosine": 0.8,
    "meeting_grouping_accuracy": 0.95,
    "predictive_precision": 0.7,
    "impact_score_correlation": 0.85
  }
}
```

---

## Troubleshooting

### Test skips with "WARNING: Semantic search not detected"

**Cause:** The test cannot find semantic search UI or API

**Solutions:**
1. Ensure `#semantic-search-toggle` element exists
2. Or expose `window.semanticSearch` object
3. Or implement `window.taskStore.semanticSearch()` method

### Test skips with "WARNING: No meeting groups found"

**Cause:** Meeting Intelligence Mode not active or no grouped data

**Solutions:**
1. Add `#meeting-mode-toggle` to UI
2. Ensure tasks have `data-session-id` attributes
3. Create `.meeting-group` containers with grouped tasks

### Low semantic search accuracy (<0.8)

**Possible causes:**
- Embedding model quality issues
- Query-result mismatch
- Insufficient training data

**Debugging:**
```bash
# Run with verbose output to see individual similarities
pytest tests/crown46/test_ai_semantic_validation.py::test_01_semantic_search_accuracy -v -s
```

### Impact Score correlation below threshold

**Possible causes:**
- Impact Score not calibrated to priority
- Priority values inconsistent
- Sample size too small

**Check:**
- Verify Impact Score calculation logic
- Ensure priority field is populated
- Review task dataset diversity

---

## CI/CD Integration

### GitHub Actions workflow:
```yaml
ai-validation:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v3
    - uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    - run: pip install pytest playwright scipy
    - run: playwright install chromium
    - run: pytest tests/crown46/test_ai_semantic_validation.py --html=report.html
    - uses: actions/upload-artifact@v3
      if: always()
      with:
        name: ai-validation-report
        path: |
          report.html
          tests/results/crown46_ai_validation_*.json
```

### Failure alerts:
Configure CI to alert when:
- Semantic search < 0.8
- Meeting grouping < 95%
- Predictive precision < 70%
- Impact Score correlation < 0.85

---

## Development Workflow

### Adding new AI features:

1. **Implement feature** in production code
2. **Add test case** to `test_ai_semantic_validation.py`
3. **Define threshold** in `AIMetricsValidator.thresholds`
4. **Run test locally** to validate
5. **Update documentation** with expected data format
6. **Merge to CI** for continuous validation

### Example: Adding new AI feature test
```python
def test_06_new_ai_feature(self, page: Page, ai_metrics: AIMetricsValidator):
    """Test new AI feature accuracy"""
    # Check if feature exists
    has_feature = page.evaluate("() => window.newAIFeature !== undefined")
    if not has_feature:
        pytest.skip("Feature not implemented")
    
    # Test feature
    result = page.evaluate("() => window.newAIFeature.test()")
    
    # Record metric
    ai_metrics.record_metric('new_feature_accuracy', result['accuracy'])
    
    # Validate threshold
    validation = ai_metrics.validate_metric('new_feature_accuracy')
    assert validation['valid'], f"New feature below threshold"
```

---

## Best Practices

1. **Use real data** - Tests should run against realistic task datasets
2. **Multiple samples** - Collect 3-5 samples per metric for statistical validity
3. **Graceful skips** - Skip tests when features not implemented (don't fail)
4. **Clear assertions** - Always assert with descriptive error messages
5. **JSON reporting** - Save reports for trend analysis and debugging

---

## Dependencies

Required Python packages:
```
pytest>=7.0.0
playwright>=1.40.0
scipy>=1.10.0  # For Spearman correlation
```

---

## Future Enhancements

Potential additions to AI validation:
- [ ] A/B testing framework for AI model comparisons
- [ ] Embedding quality regression tests
- [ ] Training data bias detection
- [ ] Explainability validation (SHAP values)
- [ ] Multi-language semantic search testing
- [ ] Adversarial query resistance

---

## Questions & Support

For issues with AI validation tests:
1. Check console output for specific failures
2. Review JSON report for metric trends
3. Verify expected data formats are present
4. Ensure scipy is installed for correlation tests

**Philosophy:** AI features should be measurable and improvable. These tests provide objective metrics to track AI quality over time.
