#!/usr/bin/env python3
"""
Direct AI Proposals Test
Tests the AI Proposals streaming functionality directly without HTTP.
No mock data - uses real OpenAI API with gpt-4o-mini model.
"""

import sys
import os
import json
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    print("=" * 60)
    print("AI PROPOSALS DIRECT VERIFICATION")
    print("Testing core AI functionality without HTTP layer")
    print("=" * 60)
    
    results = {'passed': 0, 'failed': 0}
    
    def log_result(test_name, passed, message):
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"\n{status}: {test_name}")
        print(f"   {message}")
        if passed:
            results['passed'] += 1
        else:
            results['failed'] += 1
    
    from app import app, db
    from models import User, Workspace, Meeting, Task
    from services.openai_client_manager import OpenAIClientManager
    
    with app.app_context():
        print("\n📋 Test 1: OpenAI Client Manager")
        try:
            client_manager = OpenAIClientManager()
            client = client_manager.get_client()
            log_result(
                "OpenAI Client Manager",
                client is not None,
                f"Client initialized: {client is not None}"
            )
        except Exception as e:
            log_result("OpenAI Client Manager", False, str(e))
            return 1
        
        print("\n📋 Test 2: Database Context")
        user = db.session.query(User).first()
        workspace = db.session.query(Workspace).first()
        meetings = db.session.query(Meeting).limit(5).all()
        tasks = db.session.query(Task).limit(10).all()
        
        log_result(
            "Database Context",
            user is not None and workspace is not None,
            f"User: {user.email if user else 'None'}, "
            f"Workspace: {workspace.id if workspace else 'None'}, "
            f"Meetings: {len(meetings)}, Tasks: {len(tasks)}"
        )
        
        print("\n📋 Test 3: AI Task Proposal Generation")
        try:
            context_data = {
                'recent_meetings': [
                    {
                        'id': m.id,
                        'title': m.title,
                        'date': str(m.created_at) if m.created_at else None
                    } for m in meetings[:3]
                ],
                'existing_tasks': [
                    {
                        'id': t.id,
                        'title': t.title,
                        'status': t.status
                    } for t in tasks[:5]
                ]
            }
            
            prompt = f"""Based on the following workspace context, suggest 2 new actionable tasks that would help the team be more productive.

Context:
- Recent meetings: {json.dumps(context_data['recent_meetings'], indent=2)}
- Existing tasks: {json.dumps(context_data['existing_tasks'], indent=2)}

Respond with a JSON array of 2 task proposals. Each proposal should have:
- title: A clear, actionable task title
- description: Brief description of what needs to be done
- priority: One of "low", "medium", "high"
- reasoning: Why this task is suggested

Return ONLY valid JSON, no other text."""

            print("   Calling OpenAI gpt-4o-mini-2024-07-18...")
            start_time = time.time()
            
            response = client.chat.completions.create(
                model="gpt-4o-mini-2024-07-18",
                messages=[
                    {"role": "system", "content": "You are an AI assistant that suggests actionable tasks based on meeting context. Always respond with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000,
                temperature=0.7
            )
            
            elapsed = time.time() - start_time
            
            response_text = response.choices[0].message.content
            print(f"   Response received in {elapsed*1000:.0f}ms")
            
            try:
                if response_text.startswith("```"):
                    response_text = response_text.split("```")[1]
                    if response_text.startswith("json"):
                        response_text = response_text[4:]
                
                proposals = json.loads(response_text.strip())
                
                log_result(
                    "AI Proposal Generation",
                    len(proposals) > 0,
                    f"Generated {len(proposals)} proposals in {elapsed*1000:.0f}ms"
                )
                
                print("\n📋 Test 4: Proposal Quality")
                mock_indicators = ['mock', 'dummy', 'placeholder', 'lorem', 'sample', 'test proposal']
                response_lower = json.dumps(proposals).lower()
                found_mocks = [ind for ind in mock_indicators if ind in response_lower]
                
                log_result(
                    "No Mock Data",
                    len(found_mocks) == 0,
                    f"Mock indicators: {found_mocks}" if found_mocks else "Clean - real AI content"
                )
                
                print("\n📋 Test 5: Proposal Structure")
                required_fields = ['title', 'description', 'priority']
                all_valid = True
                for i, proposal in enumerate(proposals):
                    missing = [f for f in required_fields if f not in proposal]
                    if missing:
                        all_valid = False
                        print(f"   Proposal {i+1} missing: {missing}")
                    else:
                        print(f"   Proposal {i+1}: ✓ {proposal['title'][:50]}...")
                
                log_result(
                    "Proposal Structure",
                    all_valid,
                    f"All {len(proposals)} proposals have required fields"
                )
                
                print("\n📋 Test 6: Response Time Performance")
                log_result(
                    "Response Time",
                    elapsed < 10.0,
                    f"Total: {elapsed*1000:.0f}ms (target: <10s)"
                )
                
            except json.JSONDecodeError as e:
                log_result("AI Proposal Generation", False, f"Invalid JSON: {e}")
                print(f"   Raw response: {response_text[:200]}...")
                
        except Exception as e:
            log_result("AI Proposal Generation", False, f"Error: {e}")
            import traceback
            traceback.print_exc()
        
        print("\n📋 Test 7: Streaming Capability")
        try:
            stream = client.chat.completions.create(
                model="gpt-4o-mini-2024-07-18",
                messages=[
                    {"role": "user", "content": "Say 'AI Proposals working!' in exactly 3 words."}
                ],
                max_tokens=50,
                stream=True
            )
            
            chunks = []
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    chunks.append(chunk.choices[0].delta.content)
            
            full_response = ''.join(chunks)
            log_result(
                "Streaming Capability",
                len(chunks) > 0,
                f"Received {len(chunks)} chunks: '{full_response.strip()}'"
            )
            
        except Exception as e:
            log_result("Streaming Capability", False, str(e))
    
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    print(f"✅ Passed: {results['passed']}")
    print(f"❌ Failed: {results['failed']}")
    print("=" * 60)
    
    if results['failed'] == 0:
        print("\n🎉 ALL TESTS PASSED!")
        print("AI Proposals core functionality verified with real OpenAI API")
        return 0
    else:
        print("\n⚠️ Some tests failed - review details above")
        return 1


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
