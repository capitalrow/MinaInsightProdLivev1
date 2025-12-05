"""
Accessibility Testing Configuration
Provides fixtures and utilities for axe-core accessibility testing.
"""
import pytest
from playwright.sync_api import Page
import json
from pathlib import Path
from typing import Optional, List

@pytest.fixture
def axe_builder(page: Page):
    """Create an AxeBuilder instance for accessibility testing."""
    
    def run_axe_scan(context=None, options=None):
        """Run axe accessibility scan on the current page."""
        axe_options = options or {}
        axe_context = context or {"include": [["html"]]}
        
        page.add_script_tag(url="https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.8.2/axe.min.js")
        page.wait_for_function("typeof axe !== 'undefined'", timeout=10000)
        
        results = page.evaluate("""
            async (params) => {
                return await axe.run(params.context, params.options);
            }
        """, {"context": axe_context, "options": axe_options})
        
        return results
    
    return run_axe_scan

@pytest.fixture
def accessibility_results_dir():
    """Create directory for accessibility test results."""
    results_dir = Path("tests/results/accessibility")
    results_dir.mkdir(parents=True, exist_ok=True)
    return results_dir

@pytest.fixture
def save_accessibility_report(accessibility_results_dir):
    """Save accessibility test results to file."""
    def save_report(test_name: str, results: dict):
        report_path = accessibility_results_dir / f"{test_name}_a11y_report.json"
        with open(report_path, 'w') as f:
            json.dump(results, f, indent=2)
        return report_path
    
    return save_report

def format_violations(violations: list) -> str:
    """Format accessibility violations for readable output."""
    if not violations:
        return "✓ No accessibility violations found"
    
    output = [f"\n{'='*60}"]
    output.append(f"Found {len(violations)} accessibility violation(s):")
    output.append('='*60)
    
    for i, violation in enumerate(violations, 1):
        output.append(f"\n{i}. {violation['id']}")
        impact = violation.get('impact', 'unknown')
        output.append(f"   Impact: {impact.upper() if impact else 'UNKNOWN'}")
        output.append(f"   Description: {violation['description']}")
        output.append(f"   Help: {violation['help']}")
        output.append(f"   Affected elements: {len(violation['nodes'])}")
        
        # Show first 3 affected elements
        for node in violation['nodes'][:3]:
            if 'html' in node:
                output.append(f"   - {node['html'][:100]}...")
    
    output.append('='*60 + '\n')
    return '\n'.join(output)

@pytest.fixture
def assert_no_violations():
    """Assert that there are no accessibility violations."""
    def _assert(results: dict, allowed_rules: Optional[List[str]] = None):
        violations = results.get('violations', [])
        
        # Filter out allowed violations if specified
        if allowed_rules is not None:
            violations = [v for v in violations if v['id'] not in allowed_rules]
        
        if violations:
            message = format_violations(violations)
            pytest.fail(message)
    
    return _assert
