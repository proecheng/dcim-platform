# -*- coding: utf-8 -*-
from playwright.sync_api import sync_playwright
import time
import sys
import io

# Set UTF-8 encoding for output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = context.new_page()
        page.set_default_timeout(60000)
        
        console_logs = []
        page.on('console', lambda msg: console_logs.append(f"[{msg.type}] {msg.text}"))
        
        try:
            print("=" * 60)
            print("Cabinet Drawer Issue Reproduction")
            print("=" * 60)
            
            print("\n[1/8] Visit login page")
            page.goto('http://localhost:3000', wait_until='networkidle')
            print("OK - Login page loaded")
            
            print("\n[2/8] Enter credentials")
            username_input = page.locator('input[type="text"]').first
            password_input = page.locator('input[type="password"]').first
            username_input.fill('admin')
            password_input.fill('admin123')
            print("OK - Credentials entered")
            
            print("\n[3/8] Click login button")
            login_button = page.locator('button:has-text("登录")').first
            login_button.click()
            page.wait_for_load_state('networkidle')
            time.sleep(2)
            print("OK - Login successful")
            
            print("\n[4/8] Navigate to Power-Cabinet page")
            power_menu = page.locator('text=供配电监控').first
            power_menu.click()
            time.sleep(0.5)
            
            cabinet_menu = page.locator('text=配电柜').first
            cabinet_menu.click()
            page.wait_for_load_state('networkidle')
            time.sleep(2)
            print("OK - Cabinet page loaded")
            
            print("\n[5/8] Check table data")
            table = page.locator('.el-table__body')
            table.wait_for()
            
            rows = page.locator('.el-table__body tr').all()
            row_count = len(rows)
            print(f"OK - Table has {row_count} rows")
            
            if row_count == 0:
                print("ERROR - No data in table")
                return
            
            print("\nTable preview:")
            for i in range(min(3, row_count)):
                row_text = rows[i].inner_text().replace('\n', ' | ')
                print(f"  Row {i+1}: {row_text}")
            if row_count > 3:
                print(f"  ... ({row_count - 4} rows omitted)")
                last_row_text = rows[-1].inner_text().replace('\n', ' | ')
                print(f"  Row {row_count} (last): {last_row_text}")
            
            print("\n[6/8] Click last row")
            last_row = rows[-1]
            last_row.click()
            time.sleep(1.5)
            print("OK - Last row clicked")
            
            print("\n[7/8] Check drawer")
            drawer = page.locator('.el-drawer')
            
            if drawer.count() == 0:
                print("ERROR - Drawer not opened")
                page.screenshot(path='error_no_drawer.png')
                return
            
            print("OK - Drawer opened")
            
            drawer_title_elem = page.locator('.el-drawer__header')
            if drawer_title_elem.count() > 0:
                drawer_title = drawer_title_elem.inner_text()
                print(f"\nDrawer title: '{drawer_title}'")
            else:
                print("\nWARNING - No drawer title element found")
            
            drawer_body = page.locator('.el-drawer__body')
            drawer_content = drawer_body.inner_text()
            
            print(f"\nDrawer content length: {len(drawer_content)} chars")
            
            branches_table = drawer_body.locator('.el-table')
            
            if branches_table.count() == 0:
                print("\nERROR - No branches table found")
                print(f"Drawer content preview:\n{drawer_content[:300]}")
            else:
                print("\nOK - Branches table found")
                
                headers = branches_table.locator('th').all()
                header_texts = [h.inner_text().strip() for h in headers if h.inner_text().strip()]
                print(f"\nTable columns ({len(header_texts)}): {header_texts}")
                
                table_rows = branches_table.locator('.el-table__body tr').all()
                print(f"Table rows: {len(table_rows)}")
                
                if len(table_rows) > 0:
                    print("\nTable data:")
                    for i, row in enumerate(table_rows[:3]):
                        row_text = row.inner_text().replace('\n', ' | ')
                        print(f"  Row {i+1}: {row_text}")
                    if len(table_rows) > 3:
                        print(f"  ... (total {len(table_rows)} rows)")
                else:
                    print("\nWARNING - No data in table")
                
                table_wrapper = branches_table.locator('.el-table__body-wrapper').first
                if table_wrapper.count() > 0:
                    scroll_height = table_wrapper.evaluate('el => el.scrollHeight')
                    client_height = table_wrapper.evaluate('el => el.clientHeight')
                    print(f"\nScroll info:")
                    print(f"  scrollHeight: {scroll_height}px")
                    print(f"  clientHeight: {client_height}px")
                    if scroll_height > client_height:
                        print(f"  WARNING - Content exceeds viewport by {scroll_height - client_height}px")
            
            print("\n[8/8] Check for issues")
            
            issues = []
            if '未定义' in drawer_content:
                issues.append("Contains '未定义' text")
            if 'undefined' in drawer_content.lower():
                issues.append("Contains 'undefined' text")
            if 'null' in drawer_content.lower():
                issues.append("Contains 'null' text")
            
            if issues:
                print(f"\nWARNING - Data mapping issues: {', '.join(issues)}")
            else:
                print("\nOK - No obvious data mapping issues")
            
            drawer_height = drawer.evaluate('el => el.offsetHeight')
            body_height = drawer_body.evaluate('el => el.scrollHeight')
            print(f"\nDrawer dimensions:")
            print(f"  Drawer height: {drawer_height}px")
            print(f"  Content height: {body_height}px")
            if body_height > drawer_height:
                print(f"  WARNING - Content exceeds drawer by {body_height - drawer_height}px")
            
            print("\nSaving screenshot...")
            page.screenshot(path='cabinet_drawer_final.png', full_page=True)
            print("OK - Screenshot saved: cabinet_drawer_final.png")
            
            if console_logs:
                print(f"\nConsole logs (last 10):")
                for log in console_logs[-10:]:
                    print(f"  {log}")
            
            print("\n" + "=" * 60)
            print("Test completed")
            print("=" * 60)
            
        except Exception as e:
            print(f"\nERROR - Exception occurred: {e}")
            import traceback
            traceback.print_exc()
            try:
                page.screenshot(path='error_screenshot.png')
                print("Error screenshot saved: error_screenshot.png")
            except:
                pass
        
        finally:
            browser.close()

if __name__ == '__main__':
    main()
