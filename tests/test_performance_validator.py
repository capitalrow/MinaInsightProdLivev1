"""
CROWN⁴.6: Automated Performance Validation Test
Tests that First Paint metrics are captured correctly on the tasks page
"""
import os
import sys
import time

def test_first_paint_metric():
    """Test that First Paint metric is captured via bootstrap event"""
    try:
        from playwright.sync_api import sync_playwright
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            
            console_logs = []
            page.on('console', lambda msg: console_logs.append(msg.text))
            
            page.goto('http://localhost:5000/login')
            page.fill('input[name="email"]', 'testperformance@mina.app')
            page.fill('input[name="password"]', 'TestPassword123!')
            page.click('button[type="submit"]')
            page.wait_for_url('**/dashboard**', timeout=10000)
            
            page.goto('http://localhost:5000/dashboard/tasks')
            page.wait_for_load_state('networkidle', timeout=15000)
            
            time.sleep(7)
            
            first_paint_logs = [log for log in console_logs if 'First Paint' in log or 'FCP' in log or 'Bootstrap FCP' in log]
            performance_reports = [log for log in console_logs if 'Performance Validation Report' in log]
            
            print(f"\n=== CROWN⁴.6 Performance Validation ===")
            print(f"Total console logs: {len(console_logs)}")
            print(f"First Paint related logs: {len(first_paint_logs)}")
            print(f"Performance reports generated: {len(performance_reports)}")
            
            if first_paint_logs:
                print("\n📊 First Paint Logs:")
                for log in first_paint_logs[:5]:
                    print(f"  {log}")
            else:
                print("\n❌ No First Paint logs captured!")
            
            na_reports = [log for log in console_logs if 'N/Ams' in log]
            if na_reports:
                print(f"\n⚠️ Found N/A First Paint reports: {len(na_reports)}")
                return False
            
            fcp_success = any('FCP' in log and 'ms' in log and 'N/A' not in log for log in console_logs)
            
            browser.close()
            
            if fcp_success:
                print("\n✅ First Paint metric captured successfully!")
                return True
            else:
                print("\n❌ First Paint metric not properly captured")
                return False
                
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    result = test_first_paint_metric()
    sys.exit(0 if result else 1)
