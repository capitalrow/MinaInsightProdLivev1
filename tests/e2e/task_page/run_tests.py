#!/usr/bin/env python3
"""
Task Page E2E Test Runner
Runs the comprehensive 400% coverage test suite

Usage:
    python tests/e2e/task_page/run_tests.py [options]

Options:
    --functional    Run functional tests only
    --performance   Run performance tests only
    --security      Run security tests only
    --accessibility Run accessibility tests only
    --all           Run all tests (default)
    --parallel      Run tests in parallel
    --headed        Run with browser visible
    --report        Generate HTML report
"""
import subprocess
import sys
import os
import argparse
from pathlib import Path

TEST_DIR = Path(__file__).parent
PROJECT_ROOT = TEST_DIR.parent.parent.parent


def run_tests(test_files=None, parallel=False, headed=False, report=True):
    """Run pytest with specified options"""
    
    cmd = ['python', '-m', 'pytest']
    
    if test_files:
        cmd.extend([str(TEST_DIR / f) for f in test_files])
    else:
        cmd.append(str(TEST_DIR))
    
    cmd.extend(['-v', '--tb=short'])
    
    if parallel:
        cmd.extend(['-n', 'auto'])
    
    if headed:
        cmd.extend(['--headed'])
    
    if report:
        cmd.extend([
            '--html=tests/results/task_page_e2e_report.html',
            '--self-contained-html'
        ])
    
    cmd.extend(['--ignore=tests/e2e/task_page/run_tests.py'])
    
    print(f"Running: {' '.join(cmd)}")
    
    result = subprocess.run(cmd, cwd=PROJECT_ROOT)
    return result.returncode


def main():
    parser = argparse.ArgumentParser(description='Task Page E2E Test Runner')
    
    parser.add_argument('--functional', action='store_true', help='Run functional tests only')
    parser.add_argument('--performance', action='store_true', help='Run performance tests only')
    parser.add_argument('--security', action='store_true', help='Run security tests only')
    parser.add_argument('--accessibility', action='store_true', help='Run accessibility tests only')
    parser.add_argument('--offline', action='store_true', help='Run offline sync tests only')
    parser.add_argument('--sync', action='store_true', help='Run multi-tab sync tests only')
    parser.add_argument('--all', action='store_true', help='Run all tests')
    parser.add_argument('--parallel', action='store_true', help='Run tests in parallel')
    parser.add_argument('--headed', action='store_true', help='Run with browser visible')
    parser.add_argument('--no-report', action='store_true', help='Skip HTML report generation')
    
    args = parser.parse_args()
    
    test_files = []
    
    if args.functional:
        test_files.extend([
            'test_01_task_crud.py',
            'test_02_ai_proposals.py',
            'test_03_filter_sort_search.py',
            'test_04_bulk_actions.py',
            'test_05_modals_overlays.py',
        ])
    
    if args.performance:
        test_files.append('test_06_performance.py')
    
    if args.offline:
        test_files.append('test_07_offline_sync.py')
    
    if args.sync:
        test_files.append('test_08_multi_tab_sync.py')
    
    if args.accessibility:
        test_files.append('test_09_accessibility.py')
    
    if args.security:
        test_files.append('test_10_visual_security.py')
    
    if args.all or not test_files:
        test_files = None
    
    return run_tests(
        test_files=test_files,
        parallel=args.parallel,
        headed=args.headed,
        report=not args.no_report
    )


if __name__ == '__main__':
    sys.exit(main())
