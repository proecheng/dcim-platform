# -*- coding: utf-8 -*-
from playwright.sync_api import sync_playwright
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = context.new_page()
        page.set_default_timeout(60000)
        
        try:
            print("Inspecting login page...")
            page.goto('http://localhost:3000', wait_until='networkidle')
            
            # Save screenshot
            page.screenshot(path='login_page.png')
            print("Screenshot saved: login_page.png")
            
            # Get all buttons
            buttons = page.locator('button').all()
            print(f"\nFound {len(buttons)} buttons:")
            for i, btn in enumerate(buttons):
                text = btn.inner_text()
                print(f"  Button {i+1}: '{text}'")
            
            # Get all inputs
            inputs = page.locator('input').all()
            print(f"\nFound {len(inputs)} inputs:")
            for i, inp in enumerate(inputs):
                input_type = inp.get_attribute('type')
                placeholder = inp.get_attribute('placeholder')
                print(f"  Input {i+1}: type='{input_type}', placeholder='{placeholder}'")
            
            # Get page HTML
            html = page.content()
            with open('login_page.html', 'w', encoding='utf-8') as f:
                f.write(html)
            print("\nHTML saved: login_page.html")
            
        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            browser.close()

if __name__ == '__main__':
    main()
