"""
E2E数据一致性测试 - DCIM算力中心智能监控系统

测试目标：
1. 节能方案API返回数据与前端展示是否一致
2. RL优化端点数据流
3. 效果监测数据闭环

测试框架: Playwright (Python)
"""

import json
import time
import requests
from playwright.sync_api import sync_playwright, Page, expect

# 配置
FRONTEND_URL = "http://localhost:3000"
BACKEND_URL = "http://localhost:8080"
API_BASE = f"{BACKEND_URL}/api/v1"

# 测试凭据
TEST_USER = "admin"
TEST_PASS = "admin123"


def login(page: Page) -> str:
    """登录系统并返回token"""
    page.goto(f"{FRONTEND_URL}/login")
    page.wait_for_load_state("networkidle")

    # 填写登录表单
    page.fill('input[placeholder="用户名"]', TEST_USER)
    page.fill('input[placeholder="密码"]', TEST_PASS)
    page.click('button:has-text("登 录")')

    # 等待登录成功并跳转
    page.wait_for_url(f"{FRONTEND_URL}/", timeout=10000)

    # 从localStorage获取token
    token = page.evaluate("() => localStorage.getItem('token')")
    print(f"✓ 登录成功, token: {token[:20]}...")
    return token


def get_api_data(endpoint: str, token: str) -> dict:
    """直接调用后端API获取数据"""
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{API_BASE}{endpoint}", headers=headers)
    return response.json()


def post_api_data(endpoint: str, token: str, data: dict = None) -> dict:
    """直接调用后端API提交数据"""
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    response = requests.post(f"{API_BASE}{endpoint}", headers=headers, json=data or {})
    return response.json()


class TestDataConsistency:
    """E2E数据一致性测试类"""

    def __init__(self, page: Page, token: str):
        self.page = page
        self.token = token
        self.results = []

    def log_result(self, test_name: str, passed: bool, details: str = ""):
        """记录测试结果"""
        status = "✓ PASS" if passed else "✗ FAIL"
        self.results.append({
            "test": test_name,
            "passed": passed,
            "details": details
        })
        print(f"{status}: {test_name}")
        if details:
            print(f"   {details}")

    def test_saving_potential_consistency(self):
        """测试1: 节能潜力卡片数据一致性"""
        print("\n" + "="*60)
        print("测试1: 节能潜力卡片数据一致性")
        print("="*60)

        # 1. 获取后端API数据
        api_data = get_api_data("/proposals/saving-potential", self.token)
        if api_data.get("code") != 0:
            self.log_result("API调用", False, f"API返回错误: {api_data}")
            return

        backend_data = api_data.get("data", {})
        print(f"后端数据: {json.dumps(backend_data, indent=2, ensure_ascii=False)}")

        # 2. 导航到节能建议页面
        self.page.goto(f"{FRONTEND_URL}/energy/suggestions")
        self.page.wait_for_load_state("networkidle")
        time.sleep(2)  # 等待数据加载

        # 3. 获取前端显示的数据
        try:
            # 潜在节能 (kWh/月)
            potential_saving_text = self.page.locator('.potential-card:has-text("潜在节能") .value').text_content()
            potential_saving_frontend = float(potential_saving_text.replace(",", ""))

            # 预计节省 (元/月)
            cost_saving_text = self.page.locator('.potential-card:has-text("预计节省") .value').text_content()
            cost_saving_frontend = float(cost_saving_text.replace(",", ""))

            # 已完成建议
            completed_text = self.page.locator('.potential-card:has-text("已完成") .value').text_content()
            completed_frontend = int(completed_text)

            print(f"前端数据: 潜在节能={potential_saving_frontend}, 预计节省={cost_saving_frontend}, 已完成={completed_frontend}")

            # 4. 比较数据
            backend_potential = backend_data.get("total_potential_saving", 0)
            backend_cost = backend_data.get("total_cost_saving", 0)
            backend_completed = backend_data.get("completed_count", 0)

            # 验证潜在节能
            potential_match = abs(potential_saving_frontend - backend_potential) < 1
            self.log_result(
                "潜在节能数据一致性",
                potential_match,
                f"前端={potential_saving_frontend}, 后端={backend_potential}"
            )

            # 验证预计节省
            cost_match = abs(cost_saving_frontend - backend_cost) < 1
            self.log_result(
                "预计节省数据一致性",
                cost_match,
                f"前端={cost_saving_frontend}, 后端={backend_cost}"
            )

            # 验证已完成数量
            completed_match = completed_frontend == backend_completed
            self.log_result(
                "已完成数量一致性",
                completed_match,
                f"前端={completed_frontend}, 后端={backend_completed}"
            )

        except Exception as e:
            self.log_result("前端数据提取", False, f"错误: {str(e)}")

    def test_suggestions_list_consistency(self):
        """测试2: 节能建议列表数据一致性"""
        print("\n" + "="*60)
        print("测试2: 节能建议列表数据一致性")
        print("="*60)

        # 1. 获取后端API数据
        api_data = get_api_data("/proposals/as-suggestions", self.token)
        if api_data.get("code") != 0:
            self.log_result("API调用", False, f"API返回错误: {api_data}")
            return

        backend_suggestions = api_data.get("data", [])
        print(f"后端返回 {len(backend_suggestions)} 条建议")

        # 2. 确保在建议页面
        if "/energy/suggestions" not in self.page.url:
            self.page.goto(f"{FRONTEND_URL}/energy/suggestions")
            self.page.wait_for_load_state("networkidle")
            time.sleep(2)

        # 3. 获取前端显示的建议数量
        try:
            suggestion_items = self.page.locator('.suggestion-item')
            frontend_count = suggestion_items.count()

            # 验证数量一致
            count_match = frontend_count == len(backend_suggestions)
            self.log_result(
                "建议数量一致性",
                count_match,
                f"前端={frontend_count}, 后端={len(backend_suggestions)}"
            )

            # 验证第一条建议的内容
            if frontend_count > 0 and len(backend_suggestions) > 0:
                first_backend = backend_suggestions[0]
                first_rule_name = self.page.locator('.suggestion-item:first-child .rule-name').text_content()

                backend_rule_name = first_backend.get("rule_name") or first_backend.get("rule_id")
                name_match = first_rule_name == backend_rule_name
                self.log_result(
                    "首条建议名称一致性",
                    name_match,
                    f"前端='{first_rule_name}', 后端='{backend_rule_name}'"
                )

        except Exception as e:
            self.log_result("建议列表验证", False, f"错误: {str(e)}")

    def test_rl_optimization_data_flow(self):
        """测试3: RL优化端点数据流"""
        print("\n" + "="*60)
        print("测试3: RL优化端点数据流")
        print("="*60)

        # 1. 获取RL模型信息
        model_info = get_api_data("/proposals/rl/model-info", self.token)
        print(f"RL模型信息: {json.dumps(model_info, indent=2, ensure_ascii=False)}")

        model_available = model_info.get("model_loaded", False) or model_info.get("available", False)
        self.log_result(
            "RL模型状态获取",
            "error" not in str(model_info).lower(),
            f"模型加载={model_available}"
        )

        # 2. 获取方案列表以进行RL优化测试
        proposals = get_api_data("/proposals/as-suggestions", self.token)
        if proposals.get("code") != 0 or not proposals.get("data"):
            # 触发智能分析生成方案
            print("没有方案，触发智能分析...")
            analyze_result = post_api_data("/proposals/analyze", self.token)
            print(f"分析结果: {analyze_result}")
            proposals = get_api_data("/proposals/as-suggestions", self.token)

        if proposals.get("data") and len(proposals["data"]) > 0:
            proposal_id = proposals["data"][0]["id"]
            print(f"使用方案ID: {proposal_id}")

            # 3. 执行RL优化
            rl_result = post_api_data(f"/proposals/{proposal_id}/rl/optimize", self.token, {})
            print(f"RL优化结果: {json.dumps(rl_result, indent=2, ensure_ascii=False)}")

            # 验证RL优化响应结构
            if isinstance(rl_result, dict):
                has_success = "success" in rl_result
                has_adjustments = "adjustments" in rl_result

                self.log_result(
                    "RL优化响应格式",
                    has_success and has_adjustments,
                    f"success字段={has_success}, adjustments字段={has_adjustments}"
                )

                if rl_result.get("success"):
                    self.log_result(
                        "RL优化执行成功",
                        True,
                        f"探索率={rl_result.get('exploration_rate', 'N/A')}, 置信度={rl_result.get('confidence', 'N/A')}"
                    )
                else:
                    self.log_result(
                        "RL优化执行",
                        False,
                        f"错误: {rl_result.get('detail', rl_result.get('error', 'Unknown'))}"
                    )
            else:
                self.log_result("RL优化响应格式", False, f"返回非字典类型: {type(rl_result)}")
        else:
            self.log_result("RL优化测试", False, "没有可用的方案进行测试")

    def test_effect_monitoring_closed_loop(self):
        """测试4: 效果监测数据闭环"""
        print("\n" + "="*60)
        print("测试4: 效果监测数据闭环")
        print("="*60)

        # 1. 获取方案列表
        proposals = get_api_data("/proposals/as-suggestions", self.token)
        if not proposals.get("data") or len(proposals["data"]) == 0:
            self.log_result("效果监测测试", False, "没有可用的方案")
            return

        proposal_id = proposals["data"][0]["id"]
        print(f"测试方案ID: {proposal_id}")

        # 2. 获取监测状态
        monitoring_status = get_api_data(f"/proposals/{proposal_id}/monitoring/status", self.token)
        print(f"监测状态: {json.dumps(monitoring_status, indent=2, ensure_ascii=False)}")

        self.log_result(
            "监测状态API",
            monitoring_status.get("code") == 0,
            f"返回码={monitoring_status.get('code')}"
        )

        # 3. 获取效果汇总
        effect_summary = get_api_data(f"/proposals/{proposal_id}/effect-summary", self.token)
        print(f"效果汇总: {json.dumps(effect_summary, indent=2, ensure_ascii=False)}")

        self.log_result(
            "效果汇总API",
            effect_summary.get("code") == 0,
            f"返回码={effect_summary.get('code')}"
        )

        # 4. 测试RL反馈闭环 (S4e → S5)
        rl_feedback = post_api_data(f"/proposals/{proposal_id}/rl-feedback", self.token)
        print(f"RL反馈结果: {json.dumps(rl_feedback, indent=2, ensure_ascii=False)}")

        self.log_result(
            "RL反馈闭环",
            rl_feedback.get("code") == 0,
            f"报告ID={rl_feedback.get('data', {}).get('report_id', 'N/A')}"
        )

    def test_proposal_enhanced_detail(self):
        """测试5: 方案增强详情数据完整性"""
        print("\n" + "="*60)
        print("测试5: 方案增强详情数据完整性")
        print("="*60)

        # 1. 获取方案列表
        proposals = get_api_data("/proposals/as-suggestions", self.token)
        if not proposals.get("data") or len(proposals["data"]) == 0:
            self.log_result("增强详情测试", False, "没有可用的方案")
            return

        proposal_id = proposals["data"][0]["id"]

        # 2. 获取增强详情
        enhanced = get_api_data(f"/proposals/{proposal_id}/enhanced", self.token)
        print(f"增强详情结构: {list(enhanced.get('data', {}).keys()) if enhanced.get('data') else 'N/A'}")

        if enhanced.get("code") == 0:
            data = enhanced.get("data", {})

            # 验证必要字段
            required_fields = ["id", "rule_name", "parameters", "current_pricing", "time_periods"]
            missing_fields = [f for f in required_fields if f not in data]

            self.log_result(
                "增强详情必要字段",
                len(missing_fields) == 0,
                f"缺失字段: {missing_fields}" if missing_fields else "所有字段存在"
            )

            # 验证参数结构
            params = data.get("parameters", {})
            param_fields = ["sharp_price", "peak_price", "valley_price", "devices", "calculation_formula"]
            missing_params = [f for f in param_fields if f not in params]

            self.log_result(
                "参数结构完整性",
                len(missing_params) == 0,
                f"缺失参数: {missing_params}" if missing_params else "参数完整"
            )

            # 验证电价数据
            if "sharp_price" in params and "valley_price" in params:
                price_diff = params.get("sharp_price", 0) - params.get("valley_price", 0)
                self.log_result(
                    "峰谷电价差计算",
                    price_diff == params.get("price_diff", -1),
                    f"计算值={price_diff}, API值={params.get('price_diff')}"
                )
        else:
            self.log_result("增强详情API", False, f"返回错误: {enhanced}")

    def generate_report(self):
        """生成测试报告"""
        print("\n" + "="*60)
        print("E2E数据一致性测试报告")
        print("="*60)

        total = len(self.results)
        passed = sum(1 for r in self.results if r["passed"])
        failed = total - passed

        print(f"\n总测试数: {total}")
        print(f"通过: {passed}")
        print(f"失败: {failed}")
        print(f"通过率: {passed/total*100:.1f}%\n")

        if failed > 0:
            print("失败的测试:")
            for r in self.results:
                if not r["passed"]:
                    print(f"  - {r['test']}: {r['details']}")

        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "rate": passed/total*100 if total > 0 else 0,
            "details": self.results
        }


def main():
    """主测试函数"""
    print("="*60)
    print("DCIM系统 E2E数据一致性测试")
    print("="*60)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        try:
            # 登录
            token = login(page)

            # 创建测试实例
            tester = TestDataConsistency(page, token)

            # 执行测试
            tester.test_saving_potential_consistency()
            tester.test_suggestions_list_consistency()
            tester.test_rl_optimization_data_flow()
            tester.test_effect_monitoring_closed_loop()
            tester.test_proposal_enhanced_detail()

            # 生成报告
            report = tester.generate_report()

            # 保存报告
            with open("e2e_test_report.json", "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)

            print(f"\n报告已保存到: e2e_test_report.json")

        except Exception as e:
            print(f"\n测试过程中发生错误: {str(e)}")
            import traceback
            traceback.print_exc()
        finally:
            browser.close()


if __name__ == "__main__":
    main()
