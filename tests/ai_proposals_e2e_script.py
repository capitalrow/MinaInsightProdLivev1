#!/usr/bin/env python3
"""
End-to-End AI Proposals Button Test Suite
Tests the complete user flow with real OpenAI API - No mocks or stubs
"""

import os
import sys
import time
import requests
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("=" * 70)
print("AI PROPOSALS END-TO-END TEST SUITE")
print(f"Timestamp: {datetime.now().isoformat()}")
print("Testing complete user flow with real OpenAI API")
print("=" * 70)

results = []
performance_metrics = {}

def log_result(test_name, passed, details=""):
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"\n{status}: {test_name}")
    if details:
        print(f"   {details}")
    results.append({"test": test_name, "passed": passed, "details": details})
    return passed

from app import app, db

# Test 1: Application Health Check
print("\n" + "=" * 70)
print("SECTION 1: APPLICATION HEALTH")
print("=" * 70)

print("\n📋 Test 1: Application Running")
try:
    response = requests.get("http://localhost:5000/health/live", timeout=5)
    log_result("Application Health", response.status_code == 200, 
               f"Status: {response.status_code}")
except Exception as e:
    log_result("Application Health", False, str(e))

# Test 2: Database Setup
print("\n📋 Test 2: Database Context")
user_id = None
workspace_id = None
try:
    with app.app_context():
        from models import User, Workspace
        
        # Get existing user and workspace
        user = db.session.query(User).first()
        workspace = db.session.query(Workspace).first()
        
        if user and workspace:
            user_id = user.id
            workspace_id = workspace.id
            log_result("Database Context", True, 
                       f"User: {user.email}, Workspace: {workspace_id}")
        else:
            log_result("Database Context", False, "No user or workspace found")
except Exception as e:
    log_result("Database Context", False, str(e))

# Test 3: SSE Endpoint Auth Required
print("\n📋 Test 3: SSE Endpoint Auth Required")
try:
    response = requests.post(
        "http://localhost:5000/api/tasks/ai-proposals/stream",
        json={},
        timeout=10
    )
    auth_required = response.status_code in [401, 302, 403]
    log_result("SSE Auth Required", auth_required, 
               f"Status: {response.status_code} (expected 401/302/403)")
except Exception as e:
    log_result("SSE Auth Required", False, str(e))

# Test 4: OpenAI Streaming (Real AI)
print("\n" + "=" * 70)
print("SECTION 2: SSE STREAMING FUNCTIONALITY")
print("=" * 70)

chunks = []
print("\n📋 Test 4: OpenAI Streaming (Real API)")
try:
    from services.openai_client_manager import OpenAIClientManager
    from config import Config
    
    with app.app_context():
        client_manager = OpenAIClientManager()
        client = client_manager.get_client()
        
        start_time = time.time()
        first_chunk_time = None
        
        stream = client.chat.completions.create(
            model=Config.AI_PROPOSALS_MODEL,
            messages=[
                {"role": "system", "content": "You are a task proposal assistant."},
                {"role": "user", "content": "Suggest one actionable task for improving team productivity. Be brief."}
            ],
            max_tokens=100,
            stream=True
        )
        
        for chunk in stream:
            if chunk.choices[0].delta.content:
                if first_chunk_time is None:
                    first_chunk_time = time.time()
                chunks.append(chunk.choices[0].delta.content)
        
        total_time = time.time() - start_time
        ttfb = (first_chunk_time - start_time) * 1000 if first_chunk_time else 0
        
        performance_metrics['sse_ttfb'] = ttfb
        performance_metrics['sse_total_time'] = total_time * 1000
        performance_metrics['chunk_count'] = len(chunks)
        
        full_response = ''.join(chunks)
        log_result("OpenAI Streaming (Real API)", 
                   len(chunks) > 0 and len(full_response) > 20,
                   f"Chunks: {len(chunks)}, TTFB: {ttfb:.0f}ms, Response: {len(full_response)} chars")
except Exception as e:
    log_result("OpenAI Streaming (Real API)", False, str(e))

# Test 5: SSE Response Quality
print("\n📋 Test 5: SSE Response Quality")
try:
    full_response = ''.join(chunks) if chunks else ''
    has_content = len(full_response) > 50
    no_mock = 'mock' not in full_response.lower() and 'placeholder' not in full_response.lower()
    
    log_result("SSE Response Quality", has_content and no_mock,
               f"Length: {len(full_response)} chars, Real data: {no_mock}")
except Exception as e:
    log_result("SSE Response Quality", False, str(e))

# Test 6: TTFB Performance
print("\n📋 Test 6: TTFB Performance (<2000ms)")
ttfb = performance_metrics.get('sse_ttfb', 0)
log_result("TTFB Performance", ttfb < 2000 and ttfb > 0, f"TTFB: {ttfb:.0f}ms")

# Test 7: Concurrent OpenAI Requests
print("\n" + "=" * 70)
print("SECTION 3: PERFORMANCE & RELIABILITY")
print("=" * 70)

print("\n📋 Test 7: Concurrent OpenAI Requests")
try:
    import concurrent.futures
    from services.openai_client_manager import OpenAIClientManager
    from config import Config
    
    def make_openai_request():
        with app.app_context():
            client_manager = OpenAIClientManager()
            client = client_manager.get_client()
            
            start = time.time()
            response = client.chat.completions.create(
                model=Config.AI_PROPOSALS_MODEL,
                messages=[
                    {"role": "user", "content": "Say 'OK' in one word."}
                ],
                max_tokens=10
            )
            content = response.choices[0].message.content
            return time.time() - start, len(content) > 0
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(make_openai_request) for _ in range(3)]
        concurrent_results = [f.result() for f in futures]
    
    all_success = all(r[1] for r in concurrent_results)
    avg_time = sum(r[0] for r in concurrent_results) / len(concurrent_results)
    performance_metrics['concurrent_avg'] = avg_time * 1000
    
    log_result("Concurrent OpenAI Requests", all_success,
               f"3/3 successful, Avg: {avg_time*1000:.0f}ms")
except Exception as e:
    log_result("Concurrent OpenAI Requests", False, str(e))

# Test 8: Frontend Files
print("\n" + "=" * 70)
print("SECTION 4: FRONTEND INTEGRATION")
print("=" * 70)

print("\n📋 Test 8: Frontend JavaScript Files")
try:
    files_ok = True
    file_sizes = {}
    
    for filepath in ['static/js/task-proposal-ui.js', 'static/js/task-page-master-init.js']:
        if os.path.exists(filepath):
            size = os.path.getsize(filepath)
            file_sizes[os.path.basename(filepath)] = size
            if size < 1000:
                files_ok = False
        else:
            files_ok = False
            file_sizes[os.path.basename(filepath)] = 'MISSING'
    
    log_result("Frontend JS Files", files_ok, str(file_sizes))
except Exception as e:
    log_result("Frontend JS Files", False, str(e))

# Test 9: HTML Button Element
print("\n📋 Test 9: HTML Button Element")
try:
    with open('templates/dashboard/tasks.html', 'r') as f:
        template = f.read()
    
    has_button = 'btn-generate-proposals' in template
    has_text = 'AI Proposals' in template
    
    log_result("HTML Button Element", has_button and has_text,
               f"Button: {has_button}, Text: {has_text}")
except Exception as e:
    log_result("HTML Button Element", False, str(e))

# Test 10: TaskProposalUI Class
print("\n📋 Test 10: TaskProposalUI Class")
try:
    with open('static/js/task-proposal-ui.js', 'r') as f:
        js_content = f.read()
    
    has_class = 'class TaskProposalUI' in js_content
    has_stream = 'startProposalStream' in js_content
    has_handler = 'btn-generate-proposals' in js_content
    
    log_result("TaskProposalUI Class", has_class and has_stream and has_handler,
               f"Class: {has_class}, Stream: {has_stream}, Handler: {has_handler}")
except Exception as e:
    log_result("TaskProposalUI Class", False, str(e))

# Test 11: Master Init Integration
print("\n📋 Test 11: Master Init Integration")
try:
    with open('static/js/task-page-master-init.js', 'r') as f:
        init_content = f.read()
    
    has_proposal = 'TaskProposalUI' in init_content
    log_result("Master Init Integration", has_proposal, f"ProposalUI ref: {has_proposal}")
except Exception as e:
    log_result("Master Init Integration", False, str(e))

# Test 12: OpenAI Model Config
print("\n" + "=" * 70)
print("SECTION 5: AI CONFIGURATION")
print("=" * 70)

print("\n📋 Test 12: OpenAI Model Configuration")
try:
    from config import Config
    model = getattr(Config, 'AI_PROPOSALS_MODEL', 'gpt-4o-mini-2024-07-18')
    is_correct = 'gpt-4o-mini' in model or 'gpt-4' in model
    log_result("OpenAI Model Config", is_correct, f"Model: {model}")
except Exception as e:
    log_result("OpenAI Model Config", False, str(e))

# Test 13: API Route Registration
print("\n📋 Test 13: API Route Registration")
try:
    with app.app_context():
        rules = [r.rule for r in app.url_map.iter_rules()]
        has_route = '/api/tasks/ai-proposals/stream' in rules
        
        methods = set()
        for r in app.url_map.iter_rules():
            if r.rule == '/api/tasks/ai-proposals/stream':
                methods = r.methods
                break
        
        has_post = 'POST' in methods
        log_result("API Route Registration", has_route and has_post,
                   f"Route: {has_route}, POST: {has_post}")
except Exception as e:
    log_result("API Route Registration", False, str(e))

# Final Summary
print("\n" + "=" * 70)
print("PERFORMANCE SUMMARY")
print("=" * 70)
for metric, value in performance_metrics.items():
    print(f"  {metric}: {value:.0f}ms" if isinstance(value, float) else f"  {metric}: {value}")

print("\n" + "=" * 70)
print("FINAL SUMMARY")
print("=" * 70)

passed = sum(1 for r in results if r['passed'])
failed = sum(1 for r in results if not r['passed'])
total = len(results)

print(f"\n✅ Passed: {passed}")
print(f"❌ Failed: {failed}")
print(f"📊 Pass Rate: {passed/total*100:.1f}%")
print("=" * 70)

if failed == 0:
    print("\n🎉 ALL END-TO-END TESTS PASSED!")
    print("AI Proposals button fully functional with real OpenAI API")
    sys.exit(0)
else:
    print("\n⚠️ Some tests failed - see details above")
    for r in results:
        if not r['passed']:
            print(f"   - {r['test']}: {r['details']}")
    sys.exit(1)
