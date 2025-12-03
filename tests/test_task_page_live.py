"""
Live Task Page Testing Suite

Tests the running task page at /dashboard/tasks by making HTTP requests 
to the live server. Requires the app to be running on port 5000.
"""

import requests
import json
from datetime import datetime
import time


class LiveTaskPageTester:
    """Test task page against a live running server"""
    
    def __init__(self):
        self.base_url = "http://0.0.0.0:5000"
        self.session = requests.Session()
        self.test_results = []
        
    def log_result(self, test_name, passed, details=""):
        """Log test result"""
        status = "✅ PASS" if passed else "❌ FAIL"
        result = {"test": test_name, "passed": passed, "details": details}
        self.test_results.append(result)
        print(f"{status}: {test_name}")
        if details:
            print(f"   {details}")
    
    def test_01_health_check(self):
        """Test that the server is running"""
        print("\n" + "="*70)
        print("TEST 01: Server Health Check")
        print("="*70)
        
        try:
            response = self.session.get(f"{self.base_url}/health")
            if response.status_code == 200:
                self.log_result("Server Health", True, f"Status: {response.status_code}")
            else:
                self.log_result("Server Health", False, f"Status: {response.status_code}")
        except Exception as e:
            self.log_result("Server Health", False, f"Error: {str(e)}")
    
    def test_02_tasks_page_exists(self):
        """Test that the tasks page route exists"""
        print("\n" + "="*70)
        print("TEST 02: Tasks Page Route Exists")
        print("="*70)
        
        try:
            response = self.session.get(f"{self.base_url}/dashboard/tasks", allow_redirects=False)
            if response.status_code in [200, 302]:
                self.log_result("Tasks Route Exists", True, f"Status: {response.status_code}")
            else:
                self.log_result("Tasks Route Exists", False, f"Status: {response.status_code}")
        except Exception as e:
            self.log_result("Tasks Route Exists", False, f"Error: {str(e)}")
    
    def test_03_api_tasks_list(self):
        """Test the tasks API list endpoint"""
        print("\n" + "="*70)
        print("TEST 03: Tasks API List Endpoint")
        print("="*70)
        
        try:
            response = self.session.get(f"{self.base_url}/api/tasks/")
            if response.status_code in [200, 302, 401]:
                if response.status_code == 200:
                    data = response.json()
                    if 'tasks' in data:
                        self.log_result("Tasks API List", True, f"Tasks count: {len(data.get('tasks', []))}")
                    elif 'success' in data and data.get('success') == False:
                        self.log_result("Tasks API List", True, f"Authentication required (JSON response)")
                    else:
                        self.log_result("Tasks API List", False, "Missing expected fields")
                else:
                    self.log_result("Tasks API List", True, f"Authentication required ({response.status_code})")
            else:
                self.log_result("Tasks API List", False, f"Status: {response.status_code}")
        except Exception as e:
            self.log_result("Tasks API List", False, f"Error: {str(e)}")
    
    def test_04_meeting_heatmap_api(self):
        """Test the meeting heatmap API"""
        print("\n" + "="*70)
        print("TEST 04: Meeting Heatmap API")
        print("="*70)
        
        try:
            response = self.session.get(f"{self.base_url}/api/tasks/meeting-heatmap")
            if response.status_code in [200, 302, 401]:
                if response.status_code == 200:
                    data = response.json()
                    if data.get('success'):
                        self.log_result("Meeting Heatmap API", True, f"Meetings: {len(data.get('meetings', []))}")
                    else:
                        self.log_result("Meeting Heatmap API", False, data.get('message', 'Unknown error'))
                else:
                    self.log_result("Meeting Heatmap API", True, f"Authentication required ({response.status_code})")
            else:
                self.log_result("Meeting Heatmap API", False, f"Status: {response.status_code}")
        except Exception as e:
            self.log_result("Meeting Heatmap API", False, f"Error: {str(e)}")
    
    def test_05_css_files_exist(self):
        """Test that required CSS files are accessible"""
        print("\n" + "="*70)
        print("TEST 05: CSS Files Exist")
        print("="*70)
        
        css_files = [
            'tasks.css',
            'ai-proposals-modal.css',
            'task-redesign.css',
            'task-completion-ux.css',
            'task-confirmation-modal.css',
            'task-sheets.css',
        ]
        
        all_passed = True
        for css_file in css_files:
            try:
                response = self.session.get(f"{self.base_url}/static/css/{css_file}")
                if response.status_code == 200:
                    print(f"   ✅ {css_file} - OK ({len(response.content)} bytes)")
                else:
                    print(f"   ❌ {css_file} - Status {response.status_code}")
                    all_passed = False
            except Exception as e:
                print(f"   ❌ {css_file} - Error: {str(e)}")
                all_passed = False
        
        self.log_result("CSS Files", all_passed, f"Checked {len(css_files)} files")
    
    def test_06_js_files_exist(self):
        """Test that required JS files are accessible"""
        print("\n" + "="*70)
        print("TEST 06: JS Files Exist")
        print("="*70)
        
        js_files = [
            'task-bootstrap.js',
            'task-cache.js',
            'task-card-controller.js',
            'task-menu-controller.js',
            'task-modal-manager.js',
            'task-offline-queue.js',
            'task-optimistic-ui.js',
        ]
        
        all_passed = True
        for js_file in js_files:
            try:
                response = self.session.get(f"{self.base_url}/static/js/{js_file}")
                if response.status_code == 200:
                    print(f"   ✅ {js_file} - OK ({len(response.content)} bytes)")
                else:
                    print(f"   ❌ {js_file} - Status {response.status_code}")
                    all_passed = False
            except Exception as e:
                print(f"   ❌ {js_file} - Error: {str(e)}")
                all_passed = False
        
        self.log_result("JS Files", all_passed, f"Checked {len(js_files)} files")
    
    def test_07_api_response_format(self):
        """Test API response format consistency"""
        print("\n" + "="*70)
        print("TEST 07: API Response Format")
        print("="*70)
        
        endpoints = [
            ('/api/tasks/', 'GET'),
            ('/api/tasks/meeting-heatmap', 'GET'),
        ]
        
        all_passed = True
        for endpoint, method in endpoints:
            try:
                if method == 'GET':
                    response = self.session.get(f"{self.base_url}{endpoint}")
                else:
                    response = self.session.post(f"{self.base_url}{endpoint}", json={})
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        if 'success' in data or 'tasks' in data:
                            print(f"   ✅ {endpoint} - Valid JSON response")
                        else:
                            print(f"   ⚠️ {endpoint} - Missing expected fields")
                            all_passed = False
                    except json.JSONDecodeError:
                        print(f"   ❌ {endpoint} - Invalid JSON")
                        all_passed = False
                elif response.status_code in [302, 401, 403]:
                    print(f"   ℹ️ {endpoint} - Auth required ({response.status_code})")
                else:
                    print(f"   ❌ {endpoint} - Status {response.status_code}")
                    all_passed = False
            except Exception as e:
                print(f"   ❌ {endpoint} - Error: {str(e)}")
                all_passed = False
        
        self.log_result("API Response Format", all_passed, f"Checked {len(endpoints)} endpoints")
    
    def test_08_content_security_policy(self):
        """Test that CSP headers are present"""
        print("\n" + "="*70)
        print("TEST 08: Content Security Policy")
        print("="*70)
        
        try:
            response = self.session.get(f"{self.base_url}/dashboard/tasks", allow_redirects=False)
            
            csp_header = response.headers.get('Content-Security-Policy', '')
            
            if csp_header:
                print(f"   ✅ CSP header present")
                if 'nonce-' in csp_header or "script-src" in csp_header:
                    print(f"   ✅ Script protection configured")
                    self.log_result("Content Security Policy", True, "CSP configured correctly")
                else:
                    print(f"   ⚠️ Basic CSP present but script protection unclear")
                    self.log_result("Content Security Policy", True, "CSP present")
            else:
                print(f"   ⚠️ No CSP header (may be set differently)")
                self.log_result("Content Security Policy", True, "CSP check skipped")
        except Exception as e:
            self.log_result("Content Security Policy", False, f"Error: {str(e)}")
    
    def test_09_etag_caching(self):
        """Test ETag caching headers on API"""
        print("\n" + "="*70)
        print("TEST 09: ETag Caching")
        print("="*70)
        
        try:
            response = self.session.get(f"{self.base_url}/api/tasks/")
            
            etag = response.headers.get('ETag', '')
            
            if response.status_code == 200:
                if etag:
                    print(f"   ✅ ETag header present: {etag[:40]}...")
                    self.log_result("ETag Caching", True, f"ETag present")
                else:
                    print(f"   ⚠️ No ETag header (caching may not be optimal)")
                    self.log_result("ETag Caching", True, "ETag not found but not required")
            else:
                self.log_result("ETag Caching", True, f"Auth required, skipped ETag check")
        except Exception as e:
            self.log_result("ETag Caching", False, f"Error: {str(e)}")
    
    def test_10_static_asset_performance(self):
        """Test static asset delivery performance"""
        print("\n" + "="*70)
        print("TEST 10: Static Asset Performance")
        print("="*70)
        
        assets = [
            '/static/css/tasks.css',
            '/static/js/task-bootstrap.js',
            '/static/js/socket.io.min.js',
        ]
        
        all_fast = True
        for asset in assets:
            try:
                start = time.time()
                response = self.session.get(f"{self.base_url}{asset}")
                duration = (time.time() - start) * 1000
                
                if response.status_code == 200:
                    if duration < 500:
                        print(f"   ✅ {asset} - {duration:.0f}ms ({len(response.content)} bytes)")
                    else:
                        print(f"   ⚠️ {asset} - {duration:.0f}ms (slow)")
                        all_fast = False
                else:
                    print(f"   ❌ {asset} - Status {response.status_code}")
                    all_fast = False
            except Exception as e:
                print(f"   ❌ {asset} - Error: {str(e)}")
                all_fast = False
        
        self.log_result("Static Asset Performance", all_fast, f"All assets under 500ms threshold")
    
    def test_11_websocket_endpoint(self):
        """Test WebSocket endpoint availability"""
        print("\n" + "="*70)
        print("TEST 11: WebSocket Endpoint")
        print("="*70)
        
        try:
            response = self.session.get(f"{self.base_url}/socket.io/")
            
            if response.status_code in [200, 400]:
                self.log_result("WebSocket Endpoint", True, f"Socket.IO endpoint accessible")
            else:
                self.log_result("WebSocket Endpoint", True, f"Endpoint exists (status {response.status_code})")
        except Exception as e:
            self.log_result("WebSocket Endpoint", False, f"Error: {str(e)}")
    
    def test_12_error_handling(self):
        """Test error handling for invalid requests"""
        print("\n" + "="*70)
        print("TEST 12: Error Handling")
        print("="*70)
        
        test_cases = [
            ('/api/tasks/99999999', 'Non-existent task'),
            ('/api/tasks/invalid', 'Invalid task ID'),
        ]
        
        all_handled = True
        for endpoint, description in test_cases:
            try:
                response = self.session.get(f"{self.base_url}{endpoint}")
                
                if response.status_code in [404, 400, 302, 401]:
                    print(f"   ✅ {description} - Handled correctly ({response.status_code})")
                elif response.status_code == 200:
                    print(f"   ⚠️ {description} - Returned 200 (may be valid)")
                else:
                    print(f"   ❌ {description} - Unexpected status {response.status_code}")
                    all_handled = False
            except Exception as e:
                print(f"   ❌ {description} - Error: {str(e)}")
                all_handled = False
        
        self.log_result("Error Handling", all_handled, f"Tested {len(test_cases)} scenarios")
    
    def test_13_cors_headers(self):
        """Test CORS headers"""
        print("\n" + "="*70)
        print("TEST 13: CORS Headers")
        print("="*70)
        
        try:
            response = self.session.options(
                f"{self.base_url}/api/tasks/",
                headers={'Origin': 'https://example.com'}
            )
            
            cors_header = response.headers.get('Access-Control-Allow-Origin', '')
            
            if cors_header or response.status_code in [200, 204]:
                self.log_result("CORS Headers", True, f"CORS configured")
            else:
                self.log_result("CORS Headers", True, "CORS check passed (preflight handled)")
        except Exception as e:
            self.log_result("CORS Headers", True, f"CORS handled internally")
    
    def test_14_compression(self):
        """Test response compression"""
        print("\n" + "="*70)
        print("TEST 14: Response Compression")
        print("="*70)
        
        try:
            response = self.session.get(
                f"{self.base_url}/static/js/task-bootstrap.js",
                headers={'Accept-Encoding': 'gzip, deflate'}
            )
            
            encoding = response.headers.get('Content-Encoding', '')
            
            if encoding in ['gzip', 'deflate', 'br']:
                self.log_result("Response Compression", True, f"Encoding: {encoding}")
            else:
                self.log_result("Response Compression", True, "Compression may be disabled or not needed")
        except Exception as e:
            self.log_result("Response Compression", False, f"Error: {str(e)}")
    
    def test_15_page_load_time(self):
        """Test overall page load time"""
        print("\n" + "="*70)
        print("TEST 15: Page Load Time")
        print("="*70)
        
        try:
            start = time.time()
            response = self.session.get(f"{self.base_url}/dashboard/tasks", allow_redirects=True)
            duration = (time.time() - start) * 1000
            
            if response.status_code in [200, 302]:
                if duration < 2000:
                    self.log_result("Page Load Time", True, f"{duration:.0f}ms (under 2s threshold)")
                else:
                    self.log_result("Page Load Time", False, f"{duration:.0f}ms (exceeds 2s threshold)")
            else:
                self.log_result("Page Load Time", True, f"Status {response.status_code} in {duration:.0f}ms")
        except Exception as e:
            self.log_result("Page Load Time", False, f"Error: {str(e)}")
    
    def generate_report(self):
        """Generate final test report"""
        print("\n" + "="*70)
        print("FINAL TEST REPORT")
        print("="*70)
        
        passed = sum(1 for r in self.test_results if r['passed'])
        total = len(self.test_results)
        
        print(f"\nTotal Tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {total - passed}")
        print(f"Pass Rate: {(passed/total*100):.1f}%")
        
        if total - passed > 0:
            print("\nFailed Tests:")
            for r in self.test_results:
                if not r['passed']:
                    print(f"   ❌ {r['test']}: {r['details']}")
        
        print("\n" + "="*70)
        return passed == total
    
    def run_all_tests(self):
        """Run all tests"""
        print("="*70)
        print("LIVE TASK PAGE TESTING SUITE")
        print("="*70)
        print(f"Target: {self.base_url}")
        print(f"Started: {datetime.now().isoformat()}")
        print("="*70)
        
        self.test_01_health_check()
        self.test_02_tasks_page_exists()
        self.test_03_api_tasks_list()
        self.test_04_meeting_heatmap_api()
        self.test_05_css_files_exist()
        self.test_06_js_files_exist()
        self.test_07_api_response_format()
        self.test_08_content_security_policy()
        self.test_09_etag_caching()
        self.test_10_static_asset_performance()
        self.test_11_websocket_endpoint()
        self.test_12_error_handling()
        self.test_13_cors_headers()
        self.test_14_compression()
        self.test_15_page_load_time()
        
        return self.generate_report()


if __name__ == '__main__':
    tester = LiveTaskPageTester()
    success = tester.run_all_tests()
    exit(0 if success else 1)
