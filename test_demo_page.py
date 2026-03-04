# -*- coding: utf-8 -*-
from playwright.sync_api import sync_playwright
import time

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        
        console_messages = []
        page.on("console", lambda msg: console_messages.append(f"[{msg.type}] {msg.text}"))
        
        failed_requests = []
        page.on("requestfailed", lambda req: failed_requests.append(f"{req.method} {req.url}"))
        
        try:
            print("1. Visiting login page...")
            page.goto('http://localhost:3000', wait_until='networkidle')
            page.screenshot(path='screenshot_login.png', full_page=True)
            print("   Login page loaded")
            
            print("2. Entering credentials...")
            page.fill('input[type="text"]', 'admin')
            page.fill('input[type="password"]', 'admin123')
            
            print("3. Clicking login...")
            page.click('button[type="submit"]')
            page.wait_for_load_state('networkidle', timeout=10000)
            time.sleep(2)
            page.screenshot(path='screenshot_after_login.png', full_page=True)
            print("   Login successful")
            
            print("4. Looking for demo menu...")
            page_content = page.content()
            
            with open('main_page.html', 'w', encoding='utf-8') as f:
                f.write(page_content)
            
            if 'demo' in page_content.lower() or '演示' in page_content:
                print("   Found demo content")
                
                demo_elements = page.locator('text=/演示|demo/i').all()
                print(f"   Found {len(demo_elements)} elements")
                
                if demo_elements:
                    print("5. Clicking demo menu...")
                    demo_elements[0].click()
                    page.wait_for_load_state('networkidle', timeout=10000)
                    time.sleep(2)
                    page.screenshot(path='screenshot_demo_page.png', full_page=True)
                    
                    demo_content = page.content()
                    with open('demo_page.html', 'w', encoding='utf-8') as f:
                        f.write(demo_content)
                    
                    print("6. Checking issues...")
                    
                    if console_messages:
                        print(f"   Console: {len(console_messages)} messages")
                        for msg in console_messages[-5:]:
                            print(f"     {msg}")
                    
                    if failed_requests:
                        print(f"   Failed requests: {len(failed_requests)}")
                        for req in failed_requests:
                            print(f"     {req}")
                    
                    print("   HTML saved")
            else:
                print("   No demo content found")
            
        except Exception as e:
            print(f"Error: {e}")
            page.screenshot(path='screenshot_error.png', full_page=True)
            
        finally:
            browser.close()
            print("Done")

if __name__ == '__main__':
    main()
