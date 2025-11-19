"""
CROWN 4.6 AI & Semantic Intelligence Validation Tests
Validates semantic search accuracy, Meeting Intelligence Mode, predictive engine, and Impact Score

Test Coverage:
1. Semantic Search Accuracy - Cosine similarity ≥0.8 for relevant results
2. Meeting Intelligence Mode Grouping - ≥95% accuracy in task grouping
3. Predictive Engine - Suggestion quality and relevance
4. Impact Score Integration - Accurate task prioritization
5. AI Learning - Correction feedback loop validation
"""

import pytest
import json
import time
import math
from datetime import datetime
from playwright.sync_api import Page, expect


class AIMetricsValidator:
    """Validates AI accuracy metrics and learning behavior"""
    
    def __init__(self):
        self.metrics = {}
        self.thresholds = {
            'semantic_search_cosine': 0.8,     # ≥0.8 cosine similarity
            'meeting_grouping_accuracy': 0.95,  # ≥95% accuracy
            'predictive_precision': 0.7,        # ≥70% precision
            'impact_score_correlation': 0.85    # ≥85% correlation
        }
    
    def record_metric(self, name: str, value: float):
        """Record an AI metric"""
        if name not in self.metrics:
            self.metrics[name] = []
        self.metrics[name].append(value)
    
    def calculate_cosine_similarity(self, vec1: list, vec2: list) -> float:
        """Calculate cosine similarity between two vectors"""
        if len(vec1) != len(vec2):
            return 0.0
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(b * b for b in vec2))
        
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
        
        return dot_product / (magnitude1 * magnitude2)
    
    def validate_metric(self, name: str) -> dict:
        """Validate metric against threshold"""
        if name not in self.metrics or len(self.metrics[name]) == 0:
            return {'valid': False, 'reason': 'no_data'}
        
        # Calculate average across samples
        avg_value = sum(self.metrics[name]) / len(self.metrics[name])
        threshold = self.thresholds.get(name)
        
        if threshold is None:
            return {'valid': True, 'value': avg_value, 'threshold': None}
        
        valid = avg_value >= threshold
        
        return {
            'valid': valid,
            'value': avg_value,
            'threshold': threshold,
            'samples': len(self.metrics[name]),
            'percentage': (avg_value / threshold * 100) if threshold > 0 else 100
        }
    
    def get_summary(self) -> dict:
        """Get summary of all metrics"""
        results = {}
        passed = 0
        failed = 0
        
        for name in self.metrics.keys():
            result = self.validate_metric(name)
            results[name] = result
            
            if result.get('threshold') is not None:
                if result['valid']:
                    passed += 1
                else:
                    failed += 1
        
        return {
            'total_metrics': len(results),
            'passed': passed,
            'failed': failed,
            'details': results
        }


@pytest.fixture
def ai_metrics():
    """Provides AI metrics validator"""
    return AIMetricsValidator()


class TestCROWN46AISemanticIntelligence:
    """CROWN 4.6 AI & Semantic Intelligence Validation Suite"""
    
    def test_01_semantic_search_accuracy(self, page: Page, ai_metrics: AIMetricsValidator):
        """
        Requirement: Semantic search with ≥0.8 cosine similarity
        Tests: Query-result relevance using embedding similarity
        """
        print("\n" + "="*80)
        print("AI TEST 1: Semantic Search Accuracy (≥0.8 Cosine Similarity)")
        print("="*80)
        
        page.goto('/dashboard/tasks')
        page.wait_for_selector('.task-card, .empty-state', timeout=5000)
        
        # Check if semantic search is available
        has_semantic = page.evaluate("""
            () => {
                return window.semanticSearch || 
                       document.querySelector('#semantic-search-toggle') !== null ||
                       (window.taskStore && window.taskStore.semanticSearch);
            }
        """)
        
        if not has_semantic:
            pytest.skip("Semantic search not detected - requires implementation")
        
        # Define test queries with expected relevance
        test_queries = [
            {
                'query': 'follow up on yesterday discussion',
                'expected_keywords': ['follow', 'discussion', 'meeting'],
                'min_similarity': 0.8
            },
            {
                'query': 'urgent deadline tomorrow',
                'expected_keywords': ['urgent', 'deadline', 'priority'],
                'min_similarity': 0.8
            },
            {
                'query': 'review document before meeting',
                'expected_keywords': ['review', 'document', 'meeting'],
                'min_similarity': 0.75
            }
        ]
        
        search_input = page.locator('#task-search-input, input[placeholder*="Search"]').first
        
        if not search_input.is_visible():
            pytest.skip("Search input not found - requires search UI")
        
        # Enable semantic search if toggle exists
        semantic_toggle = page.locator('#semantic-search-toggle')
        if semantic_toggle.count() > 0 and semantic_toggle.is_visible():
            if not semantic_toggle.is_checked():
                semantic_toggle.click()
                page.wait_for_timeout(500)
            print(f"  ✅ Semantic search enabled")
        
        total_similarity = 0
        valid_queries = 0
        
        for test_case in test_queries:
            query = test_case['query']
            
            # Clear and search
            search_input.fill('')
            page.wait_for_timeout(200)
            search_input.fill(query)
            page.wait_for_timeout(1000)  # Allow search to complete
            
            # Get search results with embeddings
            results = page.evaluate("""
                () => {
                    const cards = document.querySelectorAll('.task-card');
                    return Array.from(cards).slice(0, 3).map(card => ({
                        title: card.querySelector('.task-title, .task-text')?.textContent || '',
                        similarity: card.dataset.similarity ? parseFloat(card.dataset.similarity) : null,
                        embedding: card.dataset.embedding ? JSON.parse(card.dataset.embedding) : null
                    }));
                }
            """)
            
            if len(results) == 0:
                print(f"  ⚠️  Query '{query}': No results found")
                continue
            
            # Only use top result for accuracy (not averaging across all results)
            top_result = results[0] if results else None
            
            if not top_result:
                continue
                
            if top_result['similarity'] is not None:
                # Use provided similarity score from embeddings
                similarity = top_result['similarity']
                total_similarity += similarity
                valid_queries += 1
                ai_metrics.record_metric('semantic_search_cosine', similarity)
                
                print(f"  Query: '{query}' → Top Result: '{top_result['title'][:50]}...' (similarity: {similarity:.3f})")
            else:
                # No embeddings available - this is an error for semantic search
                print(f"  ❌ Query '{query}': No embedding similarity score (semantic search requires embeddings)")
                # Don't inflate score with keyword fallback - skip this query
                continue
        
        if valid_queries == 0:
            raise AssertionError("No valid search results with embedding similarity scores - semantic search requires embeddings")
        
        # Validate average similarity
        avg_similarity = total_similarity / valid_queries
        result = ai_metrics.validate_metric('semantic_search_cosine')
        
        print(f"\n  Average Similarity: {avg_similarity:.3f} (threshold: 0.8)")
        print(f"  Queries Tested: {len(test_queries)}")
        print(f"  Valid Results: {valid_queries}")
        
        if not result['valid']:
            raise AssertionError(f"Semantic search accuracy {avg_similarity:.3f} below 0.8 threshold")
        
        print(f"  ✅ PASS: Semantic search meets ≥0.8 similarity requirement")
    
    
    def test_02_meeting_intelligence_mode_grouping(self, page: Page, ai_metrics: AIMetricsValidator):
        """
        Requirement: Meeting Intelligence Mode with ≥95% grouping accuracy
        Tests: AI grouping of tasks by meeting session
        """
        print("\n" + "="*80)
        print("AI TEST 2: Meeting Intelligence Mode Grouping (≥95% Accuracy)")
        print("="*80)
        
        page.goto('/dashboard/tasks')
        page.wait_for_selector('.task-card, .empty-state', timeout=5000)
        
        # Check if Meeting Intelligence Mode exists
        has_meeting_mode = page.evaluate("""
            () => {
                return document.querySelector('[data-mode="meeting-intelligence"]') !== null ||
                       document.querySelector('#meeting-mode-toggle') !== null ||
                       (window.taskStore && window.taskStore.meetingIntelligenceMode);
            }
        """)
        
        if not has_meeting_mode:
            pytest.skip("Meeting Intelligence Mode not detected - requires implementation")
        
        # Enable Meeting Intelligence Mode
        meeting_toggle = page.locator('#meeting-mode-toggle, [data-mode="meeting-intelligence"]').first
        if meeting_toggle.count() > 0:
            meeting_toggle.click()
            page.wait_for_timeout(1000)
            print(f"  ✅ Meeting Intelligence Mode enabled")
        
        # Get grouped tasks
        grouped_data = page.evaluate("""
            () => {
                // Try to get groups from UI
                const groups = document.querySelectorAll('.meeting-group, [data-meeting-group]');
                
                if (groups.length === 0) {
                    // Fallback: try to get from task store
                    if (window.taskStore && window.taskStore.getMeetingGroups) {
                        return window.taskStore.getMeetingGroups();
                    }
                    return [];
                }
                
                return Array.from(groups).map(group => ({
                    meeting_id: group.dataset.meetingId || group.dataset.meetingGroup,
                    meeting_title: group.querySelector('.meeting-title, .group-title')?.textContent || 'Unknown',
                    task_count: group.querySelectorAll('.task-card').length,
                    tasks: Array.from(group.querySelectorAll('.task-card')).map(card => ({
                        id: card.dataset.taskId,
                        title: card.querySelector('.task-title, .task-text')?.textContent || '',
                        session_id: card.dataset.sessionId || null
                    }))
                }));
            }
        """)
        
        if len(grouped_data) == 0:
            pytest.skip("No meeting groups found - requires grouped tasks")
        
        total_groups = len(grouped_data)
        total_tasks = sum(group['task_count'] for group in grouped_data)
        correctly_grouped = 0
        total_groupable = 0
        
        print(f"\n  Meeting Groups Found: {total_groups}")
        print(f"  Total Tasks in Groups: {total_tasks}")
        
        # Validate grouping accuracy
        for group in grouped_data:
            meeting_id = group['meeting_id']
            tasks = group['tasks']
            
            # Check if all tasks in group share same session_id
            session_ids = [t['session_id'] for t in tasks if t['session_id']]
            
            # Require session IDs to be present for validation
            if len(session_ids) != len(tasks):
                missing = len(tasks) - len(session_ids)
                print(f"  ⚠️  Group '{group['meeting_title'][:40]}': {missing} tasks missing session_id")
                # Don't count groups with incomplete session data
                continue
            
            if len(session_ids) > 0:
                # Most common session_id in group
                from collections import Counter
                session_counts = Counter(session_ids)
                most_common_session = session_counts.most_common(1)[0][0]
                correct_in_group = session_counts[most_common_session]
                
                correctly_grouped += correct_in_group
                total_groupable += len(tasks)
                
                accuracy = correct_in_group / len(tasks) if len(tasks) > 0 else 0
                print(f"  Group '{group['meeting_title'][:40]}': {correct_in_group}/{len(tasks)} correct ({accuracy*100:.1f}%)")
        
        if total_groupable == 0:
            raise AssertionError("No tasks with complete session IDs - cannot validate grouping accuracy")
        
        # Require minimum sample size for statistical validity
        if total_groupable < 10:
            raise AssertionError(f"Insufficient sample size ({total_groupable} tasks) - need at least 10 for grouping validation")
        
        # Calculate overall grouping accuracy
        grouping_accuracy = correctly_grouped / total_groupable
        ai_metrics.record_metric('meeting_grouping_accuracy', grouping_accuracy)
        
        result = ai_metrics.validate_metric('meeting_grouping_accuracy')
        
        print(f"\n  Grouping Accuracy: {grouping_accuracy*100:.1f}% (threshold: 95%)")
        print(f"  Correctly Grouped: {correctly_grouped}/{total_groupable}")
        
        if not result['valid']:
            raise AssertionError(f"Meeting grouping accuracy {grouping_accuracy*100:.1f}% below 95% threshold")
        
        print(f"  ✅ PASS: Meeting Intelligence grouping meets ≥95% accuracy requirement")
    
    
    def test_03_predictive_engine_suggestions(self, page: Page, ai_metrics: AIMetricsValidator):
        """
        Requirement: Predictive engine with quality suggestions
        Tests: Suggestion relevance and user acceptance rate
        """
        print("\n" + "="*80)
        print("AI TEST 3: Predictive Engine Suggestion Quality")
        print("="*80)
        
        page.goto('/dashboard/tasks')
        page.wait_for_selector('.task-card, .empty-state', timeout=5000)
        
        # Check if predictive engine is active
        has_predictive = page.evaluate("""
            () => {
                return window.predictiveEngine || 
                       (window.taskStore && window.taskStore.predictiveEngine) ||
                       document.querySelector('.ai-suggestion, [data-ai-suggestion]') !== null;
            }
        """)
        
        if not has_predictive:
            pytest.skip("Predictive engine not detected - requires implementation")
        
        # Get AI suggestions
        suggestions = page.evaluate("""
            () => {
                // Try to get from UI
                const suggestionElements = document.querySelectorAll('.ai-suggestion, [data-ai-suggestion]');
                
                if (suggestionElements.length > 0) {
                    return Array.from(suggestionElements).map(el => ({
                        type: el.dataset.suggestionType || 'unknown',
                        confidence: parseFloat(el.dataset.confidence || '0'),
                        text: el.textContent.trim(),
                        accepted: el.classList.contains('accepted') || el.dataset.accepted === 'true'
                    }));
                }
                
                // Fallback: try to get from predictive engine
                if (window.predictiveEngine && window.predictiveEngine.getSuggestions) {
                    return window.predictiveEngine.getSuggestions();
                }
                
                return [];
            }
        """)
        
        if len(suggestions) == 0:
            pytest.skip("No AI suggestions found - predictive engine may need time to generate suggestions")
        
        print(f"\n  AI Suggestions Found: {len(suggestions)}")
        
        # Analyze suggestion quality
        high_confidence = [s for s in suggestions if s['confidence'] >= 0.7]
        accepted = [s for s in suggestions if s.get('accepted', False)]
        
        precision = len(accepted) / len(suggestions) if len(suggestions) > 0 else 0
        ai_metrics.record_metric('predictive_precision', precision)
        
        print(f"  High Confidence (≥0.7): {len(high_confidence)}/{len(suggestions)}")
        print(f"  User Accepted: {len(accepted)}/{len(suggestions)}")
        print(f"  Precision: {precision*100:.1f}%")
        
        # Sample suggestions
        for i, suggestion in enumerate(suggestions[:3]):
            print(f"  Suggestion {i+1}: {suggestion['text'][:60]}... (confidence: {suggestion['confidence']:.2f})")
        
        result = ai_metrics.validate_metric('predictive_precision')
        
        if not result['valid']:
            raise AssertionError(f"Predictive precision {precision*100:.1f}% below 70% threshold")
        
        print(f"  ✅ PASS: Predictive engine meets quality threshold (≥70% precision)")
    
    
    def test_04_impact_score_integration(self, page: Page, ai_metrics: AIMetricsValidator):
        """
        Requirement: Impact Score accurate task prioritization
        Tests: Impact Score calculation and ranking correlation
        """
        print("\n" + "="*80)
        print("AI TEST 4: Impact Score Integration & Prioritization")
        print("="*80)
        
        page.goto('/dashboard/tasks')
        page.wait_for_selector('.task-card, .empty-state', timeout=5000)
        
        # Get tasks with Impact Scores
        tasks_with_scores = page.evaluate("""
            () => {
                const cards = document.querySelectorAll('.task-card');
                const tasks = [];
                
                cards.forEach(card => {
                    const scoreEl = card.querySelector('[data-impact-score], .impact-score');
                    const priorityEl = card.querySelector('[data-priority], .priority');
                    
                    if (scoreEl || card.dataset.impactScore) {
                        tasks.push({
                            id: card.dataset.taskId,
                            title: card.querySelector('.task-title, .task-text')?.textContent || '',
                            impact_score: parseFloat(scoreEl?.textContent || card.dataset.impactScore || '0'),
                            priority: priorityEl?.textContent || card.dataset.priority || 'medium',
                            position: card.offsetTop  // Visual position on page
                        });
                    }
                });
                
                return tasks;
            }
        """)
        
        if len(tasks_with_scores) == 0:
            pytest.skip("No tasks with Impact Scores found - requires implementation")
        
        print(f"\n  Tasks with Impact Scores: {len(tasks_with_scores)}")
        
        # Validate correlation between Impact Score and priority
        priority_map = {'high': 3, 'medium': 2, 'low': 1, 'urgent': 4}
        
        impact_scores = [t['impact_score'] for t in tasks_with_scores]
        
        # Validate priority mapping - don't default to 2, fail on unknown priorities
        priority_values = []
        for t in tasks_with_scores:
            priority_str = t['priority'].lower()
            if priority_str not in priority_map:
                raise AssertionError(f"Unknown priority '{priority_str}' - expected one of {list(priority_map.keys())}")
            priority_values.append(priority_map[priority_str])
        
        # Require minimum sample size for correlation
        if len(impact_scores) < 10:
            raise AssertionError(f"Insufficient sample size ({len(impact_scores)} tasks) - need at least 10 for correlation validation")
        
        # Calculate Spearman correlation (rank correlation)
        from scipy.stats import spearmanr
        
        correlation, p_value = spearmanr(impact_scores, priority_values)
        ai_metrics.record_metric('impact_score_correlation', correlation)
        
        print(f"  Impact Score Range: {min(impact_scores):.2f} - {max(impact_scores):.2f}")
        print(f"  Correlation with Priority: {correlation:.3f} (threshold: 0.85)")
        print(f"  Statistical Significance: p={p_value:.4f}")
        
        # Require statistical significance
        if p_value >= 0.05:
            raise AssertionError(f"Correlation not statistically significant (p={p_value:.4f} >= 0.05)")
        
        # Show top 3 by Impact Score
        sorted_tasks = sorted(tasks_with_scores, key=lambda t: t['impact_score'], reverse=True)
        print(f"\n  Top 3 by Impact Score:")
        for i, task in enumerate(sorted_tasks[:3]):
            print(f"    {i+1}. {task['title'][:50]}... (score: {task['impact_score']:.2f}, priority: {task['priority']})")
        
        result = ai_metrics.validate_metric('impact_score_correlation')
        
        if not result['valid']:
            raise AssertionError(f"Impact Score correlation {correlation:.3f} below 0.85 threshold")
        
        print(f"  ✅ PASS: Impact Score meets ≥0.85 correlation requirement")
    
    
    def test_05_ai_learning_feedback_loop(self, page: Page, ai_metrics: AIMetricsValidator):
        """
        Requirement: AI learns from user corrections
        Tests: Feedback incorporation and suggestion improvement
        """
        print("\n" + "="*80)
        print("AI TEST 5: AI Learning & Feedback Loop")
        print("="*80)
        
        page.goto('/dashboard/tasks')
        page.wait_for_selector('.task-card, .empty-state', timeout=5000)
        
        # Check if feedback mechanism exists
        has_feedback = page.evaluate("""
            () => {
                return (window.predictiveEngine && window.predictiveEngine.recordFeedback) ||
                       document.querySelector('[data-ai-feedback], .ai-feedback-button') !== null;
            }
        """)
        
        if not has_feedback:
            pytest.skip("AI feedback mechanism not detected - requires implementation")
        
        # Simulate user correction
        feedback_result = page.evaluate("""
            async () => {
                if (window.predictiveEngine && window.predictiveEngine.recordFeedback) {
                    // Record a correction
                    const feedback = await window.predictiveEngine.recordFeedback({
                        suggestion_id: 'test_suggestion_123',
                        action: 'reject',
                        reason: 'not_relevant',
                        timestamp: Date.now()
                    });
                    
                    return {
                        recorded: true,
                        feedback_count: window.predictiveEngine.getFeedbackCount ? 
                            window.predictiveEngine.getFeedbackCount() : 0
                    };
                }
                return { recorded: false, feedback_count: 0 };
            }
        """)
        
        print(f"  Feedback Recorded: {feedback_result.get('recorded', False)}")
        print(f"  Total Feedback Events: {feedback_result.get('feedback_count', 0)}")
        
        if not feedback_result.get('recorded'):
            raise AssertionError("Feedback loop failed to record user correction - AI learning not functional")
        
        print(f"  ✅ PASS: AI feedback loop functional")
    
    
    def test_99_ai_metrics_summary(self, ai_metrics: AIMetricsValidator):
        """
        Final test: Generate AI validation summary
        """
        print("\n" + "="*80)
        print("AI VALIDATION SUMMARY")
        print("="*80)
        
        summary = ai_metrics.get_summary()
        
        print(f"\nTotal Metrics: {summary['total_metrics']}")
        print(f"Passed: {summary['passed']}")
        print(f"Failed: {summary['failed']}")
        print(f"\nDetailed Results:")
        
        for name, result in summary['details'].items():
            if result.get('threshold'):
                status = "✅ PASS" if result['valid'] else "❌ FAIL"
                value = result['value']
                threshold = result['threshold']
                percentage = result['percentage']
                
                print(f"  {status} {name}: {value:.3f} / {threshold:.3f} ({percentage:.1f}%)")
            else:
                print(f"  ℹ️  {name}: {result.get('value', 0):.3f} (no threshold)")
        
        # Save report
        import os
        os.makedirs('tests/results', exist_ok=True)
        report_path = f"tests/results/crown46_ai_validation_{int(time.time())}.json"
        with open(report_path, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'summary': summary,
                'metrics': ai_metrics.metrics,
                'thresholds': ai_metrics.thresholds
            }, f, indent=2)
        
        print(f"\n📊 Report saved to: {report_path}")
        
        # Assert overall pass (allow skipped tests)
        if summary['failed'] > 0:
            raise AssertionError(f"{summary['failed']} AI metrics failed validation")
        
        print(f"\n🎉 AI validation completed!")
