#!/usr/bin/env python3
"""
CROWN⁴.5 Live Validation Suite
Tests the running application to validate CROWN⁴.5 compliance
Bypasses authentication issues by using direct API testing
"""

import requests
import json
import time
from datetime import datetime
from typing import Dict, List, Any

class CROWN45LiveValidator:
    def __init__(self, base_url='http://localhost:5000'):
        self.base_url = base_url
        self.session = requests.Session()
        self.results = {
            'events': {},
            'subsystems': {},
            'performance': {},
            'issues': []
        }
    
    def login(self, email='test@mina.ai', password='TestPassword123!'):
        """Login to get authenticated session"""
        print("🔐 Logging in...")
        try:
            response = self.session.post(
                f'{self.base_url}/login',
                data={
                    'email': email,
                    'password': password
                },
                allow_redirects=False
            )
            
            if response.status_code in [200, 302]:
                print("✅ Login successful")
                return True
            else:
                print(f"❌ Login failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Login error: {e}")
            return False
    
    def test_event_01_bootstrap(self):
        """Test Event 1: tasks_bootstrap - Cache-first paint <200ms"""
        print("\n📊 Testing Event 1: tasks_bootstrap")
        
        try:
            start = time.time()
            response = self.session.get(f'{self.base_url}/dashboard/tasks')
            latency = (time.time() - start) * 1000
            
            if response.status_code == 200:
                # Check if we got the tasks page or login redirect
                if 'login' in response.url.lower():
                    self.results['events']['bootstrap'] = {
                        'status': 'BLOCKED',
                        'reason': 'Redirected to login',
                        'latency_ms': latency
                    }
                    print(f"⚠️  Bootstrap BLOCKED - requires authentication")
                else:
                    meets_target = latency < 200
                    self.results['events']['bootstrap'] = {
                        'status': 'PASS' if meets_target else 'WARN',
                        'latency_ms': latency,
                        'target_ms': 200,
                        'has_counters': b'task-counters' in response.content,
                        'has_tabs': b'task-tabs' in response.content
                    }
                    
                    status = "✅" if meets_target else "⚠️"
                    print(f"{status} Bootstrap latency: {latency:.1f}ms (target: <200ms)")
            else:
                self.results['events']['bootstrap'] = {
                    'status': 'FAIL',
                    'http_status': response.status_code
                }
                print(f"❌ Bootstrap failed: HTTP {response.status_code}")
        
        except Exception as e:
            self.results['events']['bootstrap'] = {
                'status': 'ERROR',
                'error': str(e)
            }
            print(f"❌ Bootstrap error: {e}")
    
    def test_event_04_create_manual(self):
        """Test Event 4: task_create:manual - Manual task creation"""
        print("\n📊 Testing Event 4: task_create:manual")
        
        try:
            payload = {
                'title': f'Test Task {int(time.time())}',
                'priority': 'medium',
                'status': 'pending'
            }
            
            start = time.time()
            response = self.session.post(
                f'{self.base_url}/api/tasks',
                json=payload,
                headers={'Content-Type': 'application/json'}
            )
            latency = (time.time() - start) * 1000
            
            if response.status_code in [200, 201]:
                data = response.json()
                
                # Check for CROWN metadata
                has_event_id = '_crown_event_id' in data
                has_checksum = '_crown_checksum' in data
                has_sequence = '_crown_sequence_num' in data
                
                self.results['events']['create_manual'] = {
                    'status': 'PASS' if (has_event_id and has_checksum) else 'PARTIAL',
                    'latency_ms': latency,
                    'has_crown_event_id': has_event_id,
                    'has_crown_checksum': has_checksum,
                    'has_crown_sequence': has_sequence,
                    'task_id': data.get('id')
                }
                
                if has_event_id and has_checksum and has_sequence:
                    print(f"✅ Task created with full CROWN metadata ({latency:.1f}ms)")
                elif has_event_id or has_checksum:
                    print(f"⚠️  Task created with partial CROWN metadata ({latency:.1f}ms)")
                else:
                    print(f"❌ Task created WITHOUT CROWN metadata ({latency:.1f}ms)")
            
            elif response.status_code == 401:
                self.results['events']['create_manual'] = {
                    'status': 'BLOCKED',
                    'reason': 'Authentication required'
                }
                print(f"⚠️  Create BLOCKED - requires authentication")
            
            else:
                self.results['events']['create_manual'] = {
                    'status': 'FAIL',
                    'http_status': response.status_code,
                    'response': response.text[:200]
                }
                print(f"❌ Create failed: HTTP {response.status_code}")
        
        except Exception as e:
            self.results['events']['create_manual'] = {
                'status': 'ERROR',
                'error': str(e)
            }
            print(f"❌ Create error: {e}")
    
    def test_subsystem_event_sequencer(self):
        """Test EventSequencer subsystem"""
        print("\n📊 Testing Subsystem: EventSequencer")
        
        # Check if EventSequencer API exists
        try:
            response = self.session.get(f'{self.base_url}/api/tasks/events/status')
            
            if response.status_code == 200:
                data = response.json()
                self.results['subsystems']['event_sequencer'] = {
                    'status': 'IMPLEMENTED',
                    'data': data
                }
                print(f"✅ EventSequencer API exists")
            elif response.status_code == 404:
                self.results['subsystems']['event_sequencer'] = {
                    'status': 'NOT_FOUND',
                    'note': 'API endpoint does not exist'
                }
                print(f"⚠️  EventSequencer API not found")
            else:
                self.results['subsystems']['event_sequencer'] = {
                    'status': 'UNKNOWN',
                    'http_status': response.status_code
                }
                print(f"⚠️  EventSequencer status unknown: HTTP {response.status_code}")
        
        except Exception as e:
            self.results['subsystems']['event_sequencer'] = {
                'status': 'ERROR',
                'error': str(e)
            }
            print(f"❌ EventSequencer check error: {e}")
    
    def test_subsystem_telemetry(self):
        """Test CROWN Telemetry subsystem"""
        print("\n📊 Testing Subsystem: CROWN Telemetry")
        
        try:
            response = self.session.get(f'{self.base_url}/api/tasks/telemetry')
            
            if response.status_code == 200:
                data = response.json()
                has_batch1 = 'batch1Events' in data
                
                self.results['subsystems']['telemetry'] = {
                    'status': 'IMPLEMENTED' if has_batch1 else 'PARTIAL',
                    'has_batch1_tracking': has_batch1,
                    'data': data
                }
                
                if has_batch1:
                    print(f"✅ Telemetry API exists with batch1Events tracking")
                else:
                    print(f"⚠️  Telemetry API exists but missing batch1Events")
            
            elif response.status_code == 404:
                self.results['subsystems']['telemetry'] = {
                    'status': 'NOT_FOUND'
                }
                print(f"⚠️  Telemetry API not found")
            else:
                self.results['subsystems']['telemetry'] = {
                    'status': 'UNKNOWN',
                    'http_status': response.status_code
                }
                print(f"⚠️  Telemetry status unknown: HTTP {response.status_code}")
        
        except Exception as e:
            self.results['subsystems']['telemetry'] = {
                'status': 'ERROR',
                'error': str(e)
            }
            print(f"❌ Telemetry check error: {e}")
    
    def test_websocket_connection(self):
        """Test WebSocket /tasks namespace"""
        print("\n📊 Testing WebSocket: /tasks namespace")
        
        # We can't test WebSocket directly with requests, but we can check if SocketIO is running
        try:
            response = self.session.get(f'{self.base_url}/socket.io/')
            
            if response.status_code == 200:
                self.results['subsystems']['websocket'] = {
                    'status': 'RUNNING',
                    'note': 'Socket.IO endpoint responds'
                }
                print(f"✅ Socket.IO server is running")
            else:
                self.results['subsystems']['websocket'] = {
                    'status': 'UNKNOWN',
                    'http_status': response.status_code
                }
                print(f"⚠️  Socket.IO status unknown: HTTP {response.status_code}")
        
        except Exception as e:
            self.results['subsystems']['websocket'] = {
                'status': 'ERROR',
                'error': str(e)
            }
            print(f"❌ WebSocket check error: {e}")
    
    def run_validation(self):
        """Run complete validation suite"""
        print("=" * 60)
        print("🎯 CROWN⁴.5 Live Validation Suite")
        print("=" * 60)
        
        # Try to login
        logged_in = self.login()
        
        # Run tests
        self.test_event_01_bootstrap()
        self.test_event_04_create_manual()
        self.test_subsystem_event_sequencer()
        self.test_subsystem_telemetry()
        self.test_websocket_connection()
        
        # Generate report
        self.generate_report()
    
    def generate_report(self):
        """Generate validation report"""
        print("\n" + "=" * 60)
        print("📊 VALIDATION SUMMARY")
        print("=" * 60)
        
        # Event summary
        print("\n🎯 Events Tested:")
        for event_name, result in self.results['events'].items():
            status = result.get('status', 'UNKNOWN')
            icon = {
                'PASS': '✅',
                'PARTIAL': '⚠️',
                'FAIL': '❌',
                'BLOCKED': '🔒',
                'ERROR': '❌'
            }.get(status, '❓')
            
            print(f"  {icon} {event_name}: {status}")
            if 'latency_ms' in result:
                print(f"     Latency: {result['latency_ms']:.1f}ms")
        
        # Subsystem summary
        print("\n🔧 Subsystems Tested:")
        for subsystem_name, result in self.results['subsystems'].items():
            status = result.get('status', 'UNKNOWN')
            icon = {
                'IMPLEMENTED': '✅',
                'PARTIAL': '⚠️',
                'NOT_FOUND': '❌',
                'RUNNING': '✅',
                'ERROR': '❌'
            }.get(status, '❓')
            
            print(f"  {icon} {subsystem_name}: {status}")
        
        # Save JSON report
        report_file = f'crown45_live_validation_{int(time.time())}.json'
        with open(report_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        print(f"\n💾 Full report saved to: {report_file}")
        print("=" * 60)


if __name__ == '__main__':
    validator = CROWN45LiveValidator()
    validator.run_validation()
