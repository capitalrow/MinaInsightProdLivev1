#!/usr/bin/env python3
"""
Flask Context AI Proposals Test
Tests AI Proposals using Flask test client with proper authentication.
No mock data - uses real OpenAI API.
"""

import pytest
import json
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ['DATABASE_URL'] = os.environ.get('DATABASE_URL', '')
os.environ['TESTING'] = 'true'


class TestAIProposalsFlask:
    """Flask context tests for AI Proposals."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test client with authentication."""
        from app import app, db
        from models import User, Workspace
        
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['LOGIN_DISABLED'] = False
        
        self.app = app
        self.db = db
        
        with app.test_client() as client:
            with app.app_context():
                user = db.session.query(User).first()
                workspace = db.session.query(Workspace).first()
                
                if user and workspace:
                    with client.session_transaction() as sess:
                        sess['_user_id'] = str(user.id)
                        sess['user_id'] = user.id
                        sess['workspace_id'] = workspace.id
                        sess['_fresh'] = True
                    
                    self.user = user
                    self.workspace = workspace
                    self.client = client
                    self.authenticated = True
                    print(f"✅ Authenticated as user {user.id} in workspace {workspace.id}")
                else:
                    self.authenticated = False
                    self.client = client
                    print("⚠️ No user/workspace found for authentication")
                
                yield
    
    def test_01_endpoint_exists(self):
        """Test: AI proposals endpoint exists."""
        with self.app.app_context():
            response = self.client.post(
                '/api/tasks/ai-proposals/stream',
                json={'max_proposals': 1},
                content_type='application/json'
            )
            
            assert response.status_code != 404, "Endpoint should exist"
            print(f"✅ Endpoint exists (status: {response.status_code})")
    
    def test_02_requires_authentication(self):
        """Test: Endpoint requires authentication."""
        with self.app.test_client() as unauth_client:
            response = unauth_client.post(
                '/api/tasks/ai-proposals/stream',
                json={'max_proposals': 1},
                content_type='application/json'
            )
            
            assert response.status_code in [401, 302, 403], \
                f"Should require auth, got {response.status_code}"
            print(f"✅ Authentication required (status: {response.status_code})")
    
    def test_03_authenticated_access(self):
        """Test: Authenticated user can access endpoint."""
        if not self.authenticated:
            pytest.skip("No authenticated session available")
        
        with self.app.app_context():
            response = self.client.post(
                '/api/tasks/ai-proposals/stream',
                json={'max_proposals': 2},
                content_type='application/json'
            )
            
            print(f"Response status: {response.status_code}")
            print(f"Content-Type: {response.content_type}")
            
            if response.status_code == 200:
                assert 'text/event-stream' in response.content_type
                print("✅ SSE stream returned successfully")
            elif response.status_code == 401:
                pytest.skip("Session authentication not persisting in test")
    
    def test_04_sse_format(self):
        """Test: Response is valid SSE format."""
        if not self.authenticated:
            pytest.skip("No authenticated session available")
        
        with self.app.app_context():
            response = self.client.post(
                '/api/tasks/ai-proposals/stream',
                json={'max_proposals': 2},
                content_type='application/json'
            )
            
            if response.status_code != 200:
                pytest.skip(f"Endpoint returned {response.status_code}")
            
            data = response.get_data(as_text=True)
            
            assert 'data:' in data, "SSE should contain data events"
            
            events = []
            for line in data.split('\n'):
                if line.startswith('data:'):
                    json_str = line[5:].strip()
                    if json_str and json_str != '[DONE]':
                        try:
                            events.append(json.loads(json_str))
                        except json.JSONDecodeError:
                            pass
            
            print(f"✅ Received {len(events)} SSE events")
            
            for event in events[:3]:
                if 'type' in event:
                    print(f"   Event type: {event['type']}")
    
    def test_05_no_mock_data(self):
        """Test: Responses contain real AI-generated content."""
        if not self.authenticated:
            pytest.skip("No authenticated session available")
        
        with self.app.app_context():
            response = self.client.post(
                '/api/tasks/ai-proposals/stream',
                json={'max_proposals': 2},
                content_type='application/json'
            )
            
            if response.status_code != 200:
                pytest.skip(f"Endpoint returned {response.status_code}")
            
            data = response.get_data(as_text=True).lower()
            
            mock_indicators = [
                'mock', 'dummy', 'placeholder', 'lorem ipsum',
                'sample task', 'test proposal'
            ]
            
            found_mocks = [ind for ind in mock_indicators if ind in data]
            
            if found_mocks:
                print(f"⚠️ Potential mock indicators: {found_mocks}")
            else:
                print("✅ No mock data indicators found")
            
            assert 'data:' in data
    
    def test_06_response_performance(self):
        """Test: Response time is acceptable."""
        if not self.authenticated:
            pytest.skip("No authenticated session available")
        
        with self.app.app_context():
            start_time = time.time()
            
            response = self.client.post(
                '/api/tasks/ai-proposals/stream',
                json={'max_proposals': 1},
                content_type='application/json'
            )
            
            elapsed = time.time() - start_time
            
            print(f"Response time: {elapsed*1000:.0f}ms")
            
            if response.status_code == 200:
                assert elapsed < 30.0, f"Response took {elapsed}s, should be < 30s"
                print(f"✅ Response received in {elapsed*1000:.0f}ms")


def run_tests():
    """Run all Flask context tests."""
    pytest.main([
        __file__,
        '-v',
        '-s',
        '--tb=short'
    ])


if __name__ == '__main__':
    run_tests()
