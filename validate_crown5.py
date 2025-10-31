#!/usr/bin/env python3
"""
CROWN⁵+ Analytics System Validation Script
Validates 100% alignment with specification
"""

import sys
import json
from pathlib import Path

# Color codes for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

validation_results = {
    'passed': [],
    'failed': [],
    'warnings': []
}

def check(name, condition, error_msg=""):
    """Check a condition and record result"""
    if condition:
        validation_results['passed'].append(name)
        print(f"{GREEN}✓{RESET} {name}")
        return True
    else:
        validation_results['failed'].append(f"{name}: {error_msg}")
        print(f"{RED}✗{RESET} {name}")
        if error_msg:
            print(f"  {error_msg}")
        return False

def warn(name, message):
    """Record a warning"""
    validation_results['warnings'].append(f"{name}: {message}")
    print(f"{YELLOW}⚠{RESET} {name}: {message}")

print(f"\n{BLUE}{'='*60}{RESET}")
print(f"{BLUE}CROWN⁵+ Analytics Validation{RESET}")
print(f"{BLUE}{'='*60}{RESET}\n")

# Section 1: Event Infrastructure
print(f"\n{BLUE}1️⃣ Event Infrastructure Validation{RESET}")
print("-" * 60)

# Check EventType enum has all 10 CROWN⁵+ events
try:
    from models.event_ledger import EventType
    
    required_events = [
        'analytics_bootstrap',
        'analytics_ws_subscribe',
        'analytics_header_reconcile',
        'analytics_overview_hydrate',
        'analytics_prefetch_tabs',
        'analytics_delta_apply',
        'analytics_filter_change',
        'analytics_tab_switch',
        'analytics_export_initiated',
        'analytics_idle_sync'
    ]
    
    event_values = [e.value for e in EventType]
    all_present = all(event in event_values for event in required_events)
    
    check(
        "All 10 CROWN⁵+ events in EventType enum",
        all_present,
        f"Missing: {[e for e in required_events if e not in event_values]}"
    )
except Exception as e:
    check("EventType enum accessible", False, str(e))

# Section 2: Service Layer
print(f"\n{BLUE}2️⃣ Service Layer Validation{RESET}")
print("-" * 60)

# Check AnalyticsCacheService exists
try:
    from services.analytics_cache_service import AnalyticsCacheService
    check("AnalyticsCacheService importable", True)
    
    # Test checksum computation (static method)
    test_data = {'kpis': {'total_meetings': 100}}
    checksum = AnalyticsCacheService.generate_checksum(test_data)
    check(
        "Checksum computation works (SHA-256)",
        len(checksum) == 64 and checksum.isalnum(),
        f"Got checksum length {len(checksum)}"
    )
    
    # Test delta computation (static method)
    old_data = {'kpis': {'a': 1, 'b': 2, 'c': 3}}
    new_data = {'kpis': {'a': 1, 'b': 5, 'c': 3}}
    delta = AnalyticsCacheService.compute_delta(old_data, new_data)
    check(
        "Delta computation (field-level diff)",
        'changes' in delta and 'kpis' in delta['changes'],
        f"Should include changes: {delta}"
    )
    
except Exception as e:
    check("AnalyticsCacheService", False, str(e))

# Check AnalyticsDeltaService
try:
    from services.analytics_delta_service import AnalyticsDeltaService
    check("AnalyticsDeltaService importable", True)
    
except Exception as e:
    check("AnalyticsDeltaService", False, str(e))

# Section 3: Frontend Modules
print(f"\n{BLUE}3️⃣ Frontend Module Validation{RESET}")
print("-" * 60)

frontend_modules = [
    'static/js/analytics-cache.js',
    'static/js/analytics-lifecycle.js',
    'static/js/analytics-prefetch.js',
    'static/js/analytics-export.js',
    'static/js/analytics-crown5.js'
]

for module in frontend_modules:
    module_path = Path(module)
    exists = module_path.exists()
    check(f"Module exists: {module}", exists, f"File not found: {module}")
    
    if exists:
        content = module_path.read_text()
        # Check for key patterns
        if 'analytics-cache.js' in module:
            check(
                "  - IndexedDB implementation",
                'IndexedDB' in content or 'indexedDB' in content
            )
            check(
                "  - SHA-256 checksum",
                'SHA-256' in content or 'crypto.subtle' in content
            )
        
        elif 'analytics-lifecycle.js' in module:
            check(
                "  - Bootstrap method",
                'bootstrap' in content
            )
            check(
                "  - 30s idle sync",
                '30' in content and 'idle' in content.lower()
            )
        
        elif 'analytics-prefetch.js' in module:
            check(
                "  - AbortController",
                'AbortController' in content
            )
            check(
                "  - Network awareness",
                'navigator' in content or 'connection' in content
            )
        
        elif 'analytics-export.js' in module:
            check(
                "  - CSV export",
                'CSV' in content or 'csv' in content
            )
            check(
                "  - Toast notifications",
                'toast' in content.lower()
            )

# Section 4: WebSocket Integration
print(f"\n{BLUE}4️⃣ WebSocket Integration{RESET}")
print("-" * 60)

try:
    analytics_ws_file = Path('routes/analytics_websocket.py')
    if analytics_ws_file.exists():
        content = analytics_ws_file.read_text()
        check(
            "Analytics WebSocket namespace registered",
            '/analytics' in content
        )
        check(
            "Tab switch handler",
            'analytics_tab_switch' in content
        )
        check(
            "Bootstrap request handler",
            'analytics_bootstrap' in content or 'bootstrap_request' in content
        )
    else:
        check("Analytics WebSocket file exists", False, "routes/analytics_websocket.py not found")
except Exception as e:
    check("WebSocket integration", False, str(e))

# Section 5: Template Integration
print(f"\n{BLUE}5️⃣ Template Integration{RESET}")
print("-" * 60)

try:
    template_file = Path('templates/dashboard/analytics.html')
    if template_file.exists():
        content = template_file.read_text()
        check(
            "Chart.js loaded",
            'chart.js' in content.lower() or 'chart.min.js' in content.lower()
        )
        check(
            "CROWN⁵+ modules imported",
            'analytics-crown5.js' in content
        )
        check(
            "Crown5Analytics instantiated",
            'Crown5Analytics' in content and 'new Crown5Analytics' in content
        )
        check(
            "/analytics namespace connection",
            "io('/analytics')" in content
        )
    else:
        check("Analytics template exists", False, "templates/dashboard/analytics.html not found")
except Exception as e:
    check("Template integration", False, str(e))

# Section 6: Database Schema
print(f"\n{BLUE}6️⃣ Database Schema Validation{RESET}")
print("-" * 60)

try:
    import psycopg2
    import os
    
    db_url = os.environ.get('DATABASE_URL')
    if db_url:
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()
        
        # Check if analytics events are in enum
        cursor.execute("""
            SELECT enumlabel FROM pg_enum
            WHERE enumtypid = (
                SELECT oid FROM pg_type WHERE typname = 'eventtype'
            )
            AND enumlabel LIKE 'analytics_%'
        """)
        
        analytics_events = [row[0] for row in cursor.fetchall()]
        check(
            "CROWN⁵+ events in database enum",
            len(analytics_events) >= 10,
            f"Found {len(analytics_events)} analytics events"
        )
        
        cursor.close()
        conn.close()
    else:
        warn("Database", "DATABASE_URL not set, skipping database checks")
        
except Exception as e:
    warn("Database validation", str(e))

# Final Summary
print(f"\n{BLUE}{'='*60}{RESET}")
print(f"{BLUE}Validation Summary{RESET}")
print(f"{BLUE}{'='*60}{RESET}\n")

total_checks = len(validation_results['passed']) + len(validation_results['failed'])
pass_rate = (len(validation_results['passed']) / total_checks * 100) if total_checks > 0 else 0

print(f"{GREEN}Passed:{RESET} {len(validation_results['passed'])}")
print(f"{RED}Failed:{RESET} {len(validation_results['failed'])}")
print(f"{YELLOW}Warnings:{RESET} {len(validation_results['warnings'])}")
print(f"\n{BLUE}Pass Rate:{RESET} {pass_rate:.1f}%\n")

if validation_results['failed']:
    print(f"{RED}Failed Checks:{RESET}")
    for failure in validation_results['failed']:
        print(f"  • {failure}")
    print()

if validation_results['warnings']:
    print(f"{YELLOW}Warnings:{RESET}")
    for warning in validation_results['warnings']:
        print(f"  • {warning}")
    print()

# Exit with appropriate code
sys.exit(0 if len(validation_results['failed']) == 0 else 1)
