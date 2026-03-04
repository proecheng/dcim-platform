const { chromium } = require('@playwright/test');

(async () => {
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext();
  const page = await context.newPage();

  console.log('=== 性能测试开始 ===\n');

  // 1. 登录
  console.log('1. 登录...');
  await page.goto('http://localhost:3000/login');
  await page.fill('input[placeholder="用户名"]', 'admin');
  await page.fill('input[placeholder="密码"]', 'admin123');
  await page.click('button.login-btn');
  await page.waitForFunction(() => window.location.pathname !== '/login', { timeout: 10000 });
  await page.waitForTimeout(2000);
  console.log('   登录成功\n');

  // 2. 直接访问供配电总览页面
  console.log('2. 访问供配电总览页面...');
  const overviewStart = Date.now();
  await page.goto('http://localhost:3000/power/overview');
  await page.waitForLoadState('networkidle');
  await page.waitForSelector('.stat-card', { timeout: 10000 });
  const overviewLoadTime = Date.now() - overviewStart;
  console.log(`   供配电总览页面加载时间: ${overviewLoadTime}ms\n`);

  // 3. 测试页面交互
  console.log('3. 测试页面交互...');
  const cardClickStart = Date.now();
  await page.locator('.stat-card').first().click();
  await page.waitForTimeout(300);
  const cardClickTime = Date.now() - cardClickStart;
  console.log(`   卡片点击响应: ${cardClickTime}ms\n`);

  // 4. 测试窗口 resize
  console.log('4. 测试窗口 resize...');
  const resizeStart = Date.now();
  await page.setViewportSize({ width: 1200, height: 800 });
  await page.waitForTimeout(300);
  await page.setViewportSize({ width: 1920, height: 1080 });
  await page.waitForTimeout(300);
  const resizeTime = Date.now() - resizeStart;
  console.log(`   窗口 resize 响应: ${resizeTime}ms\n`);

  // 5. 访问 UPS 监控页面
  console.log('5. 访问 UPS 监控页面...');
  const upsStart = Date.now();
  await page.goto('http://localhost:3000/power/ups');
  await page.waitForLoadState('networkidle');
  const upsLoadTime = Date.now() - upsStart;
  console.log(`   UPS 监控页面加载时间: ${upsLoadTime}ms\n`);

  // 总结
  console.log('=== 性能测试完成 ===');
  console.log(`\n关键指标:`);
  console.log(`  - 供配电总览加载: ${overviewLoadTime}ms ${overviewLoadTime < 1000 ? '✅ 优秀' : overviewLoadTime < 2000 ? '⚠️ 一般' : '❌ 需优化'}`);
  console.log(`  - 页面交互响应: ${cardClickTime}ms ${cardClickTime < 500 ? '✅ 流畅' : '⚠️ 一般'}`);
  console.log(`  - 窗口 resize: ${resizeTime}ms ${resizeTime < 1000 ? '✅ 流畅' : '⚠️ 一般'}`);
  console.log(`  - UPS 页面加载: ${upsLoadTime}ms ${upsLoadTime < 1000 ? '✅ 优秀' : '⚠️ 一般'}`);
  
  console.log('\n浏览器将在 5 秒后关闭...');
  await page.waitForTimeout(5000);

  await browser.close();
})();
