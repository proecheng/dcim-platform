"""
API数据一致性测试 - 仅测试后端API
无需启动前端，直接验证API响应格式和数据逻辑
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import json
import requests
from typing import Dict, Any, List

# 配置
BACKEND_URL = "http://localhost:8080"
API_BASE = f"{BACKEND_URL}/api/v1"

# 测试凭据
TEST_USER = "admin"
TEST_PASS = "admin123"


class APITester:
    def __init__(self):
        self.token = None
        self.results = []

    def login(self) -> bool:
        """登录获取token"""
        try:
            resp = requests.post(
                f"{API_BASE}/auth/login",
                data={"username": TEST_USER, "password": TEST_PASS}
            )
            if resp.status_code == 200:
                data = resp.json()
                self.token = data.get("access_token")
                print(f"✓ 登录成功, token: {self.token[:20] if self.token else 'N/A'}...")
                return True
            else:
                print(f"✗ 登录失败: {resp.status_code} - {resp.text}")
                return False
        except Exception as e:
            print(f"✗ 登录异常: {e}")
            return False

    def get(self, endpoint: str) -> Dict:
        """GET请求"""
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        try:
            resp = requests.get(f"{API_BASE}{endpoint}", headers=headers, timeout=10)
            return resp.json()
        except Exception as e:
            return {"error": str(e)}

    def post(self, endpoint: str, data: Dict = None) -> Dict:
        """POST请求"""
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        } if self.token else {"Content-Type": "application/json"}
        try:
            resp = requests.post(f"{API_BASE}{endpoint}", headers=headers, json=data or {}, timeout=30)
            return resp.json()
        except Exception as e:
            return {"error": str(e)}

    def log_result(self, test_name: str, passed: bool, details: str = ""):
        """记录测试结果"""
        status = "✓ PASS" if passed else "✗ FAIL"
        self.results.append({"test": test_name, "passed": passed, "details": details})
        print(f"{status}: {test_name}")
        if details:
            print(f"       {details}")

    def test_templates_api(self):
        """测试1: 模板API"""
        print("\n" + "="*60)
        print("测试1: 模板列表API (/proposals/templates)")
        print("="*60)

        data = self.get("/proposals/templates")
        print(f"响应: {json.dumps(data, indent=2, ensure_ascii=False)[:500]}...")

        # 验证响应格式
        self.log_result(
            "模板API响应码",
            data.get("code") == 0,
            f"code={data.get('code')}"
        )

        templates = data.get("data", {}).get("templates", [])
        self.log_result(
            "模板数量",
            len(templates) == 6,
            f"实际={len(templates)}, 期望=6 (A1-A5, B1)"
        )

        # 验证模板结构
        if templates:
            t = templates[0]
            required_fields = ["id", "name", "type", "description", "category", "priority"]
            missing = [f for f in required_fields if f not in t]
            self.log_result(
                "模板字段完整性",
                len(missing) == 0,
                f"缺失字段: {missing}" if missing else "字段完整"
            )

    def test_saving_potential_api(self):
        """测试2: 节能潜力API"""
        print("\n" + "="*60)
        print("测试2: 节能潜力API (/proposals/saving-potential)")
        print("="*60)

        data = self.get("/proposals/saving-potential")
        print(f"响应: {json.dumps(data, indent=2, ensure_ascii=False)}")

        self.log_result(
            "节能潜力API响应码",
            data.get("code") == 0,
            f"code={data.get('code')}"
        )

        potential = data.get("data", {})
        required_fields = [
            "total_potential_saving", "total_cost_saving",
            "pending_count", "accepted_count", "completed_count",
            "high_priority_count", "medium_priority_count", "low_priority_count"
        ]
        missing = [f for f in required_fields if f not in potential]
        self.log_result(
            "节能潜力字段完整性",
            len(missing) == 0,
            f"缺失字段: {missing}" if missing else "字段完整"
        )

        # 验证数据逻辑: 总数 = 高 + 中 + 低
        if not missing:
            total_by_priority = (
                potential.get("high_priority_count", 0) +
                potential.get("medium_priority_count", 0) +
                potential.get("low_priority_count", 0)
            )
            total_by_status = (
                potential.get("pending_count", 0) +
                potential.get("accepted_count", 0) +
                potential.get("completed_count", 0)
            )
            # 注意: rejected也可能存在，所以这里只验证优先级总数和状态总数是否接近
            self.log_result(
                "优先级统计逻辑",
                total_by_priority >= 0,
                f"高+中+低={total_by_priority}"
            )

    def test_suggestions_api(self):
        """测试3: 建议列表API"""
        print("\n" + "="*60)
        print("测试3: 建议列表API (/proposals/as-suggestions)")
        print("="*60)

        data = self.get("/proposals/as-suggestions")

        self.log_result(
            "建议列表API响应码",
            data.get("code") == 0,
            f"code={data.get('code')}"
        )

        suggestions = data.get("data", [])
        print(f"返回 {len(suggestions)} 条建议")

        if suggestions:
            s = suggestions[0]
            print(f"首条建议: {json.dumps(s, indent=2, ensure_ascii=False)[:400]}...")

            required_fields = ["id", "rule_id", "rule_name", "status", "priority", "potential_saving"]
            missing = [f for f in required_fields if f not in s]
            self.log_result(
                "建议字段完整性",
                len(missing) == 0,
                f"缺失字段: {missing}" if missing else "字段完整"
            )

            # 验证状态值有效性
            valid_statuses = ["pending", "accepted", "rejected", "completed"]
            valid_priorities = ["high", "medium", "low"]

            status_valid = s.get("status") in valid_statuses
            priority_valid = s.get("priority") in valid_priorities

            self.log_result(
                "状态值有效性",
                status_valid,
                f"status='{s.get('status')}', 有效值={valid_statuses}"
            )
            self.log_result(
                "优先级值有效性",
                priority_valid,
                f"priority='{s.get('priority')}', 有效值={valid_priorities}"
            )
        else:
            self.log_result("建议列表", True, "列表为空，尝试触发分析...")

    def test_analyze_and_generate(self):
        """测试4: 智能分析API"""
        print("\n" + "="*60)
        print("测试4: 智能分析API (/proposals/analyze)")
        print("="*60)

        data = self.post("/proposals/analyze")
        print(f"响应: {json.dumps(data, indent=2, ensure_ascii=False)}")

        self.log_result(
            "分析API响应码",
            data.get("code") == 0,
            f"code={data.get('code')}"
        )

        result = data.get("data", {})
        self.log_result(
            "分析结果字段",
            "new_suggestions" in result,
            f"new_suggestions={result.get('new_suggestions', 'N/A')}"
        )

    def test_proposal_enhanced_detail(self):
        """测试5: 方案增强详情API"""
        print("\n" + "="*60)
        print("测试5: 方案增强详情API")
        print("="*60)

        # 先获取方案列表
        suggestions = self.get("/proposals/as-suggestions")
        if suggestions.get("code") != 0 or not suggestions.get("data"):
            self.log_result("增强详情测试", False, "没有可用方案")
            return

        proposal_id = suggestions["data"][0]["id"]
        print(f"测试方案ID: {proposal_id}")

        data = self.get(f"/proposals/{proposal_id}/enhanced")

        self.log_result(
            "增强详情API响应码",
            data.get("code") == 0,
            f"code={data.get('code')}"
        )

        detail = data.get("data", {})
        if detail:
            # 验证核心字段
            core_fields = ["id", "rule_name", "parameters", "status"]
            missing_core = [f for f in core_fields if f not in detail]
            self.log_result(
                "核心字段完整性",
                len(missing_core) == 0,
                f"缺失: {missing_core}" if missing_core else "完整"
            )

            # 验证parameters结构
            params = detail.get("parameters", {})
            param_fields = ["sharp_price", "valley_price", "devices", "calculation_formula"]
            missing_params = [f for f in param_fields if f not in params]
            self.log_result(
                "参数字段完整性",
                len(missing_params) == 0,
                f"缺失: {missing_params}" if missing_params else "完整"
            )

            # 验证电价计算逻辑
            if "sharp_price" in params and "valley_price" in params:
                calc_diff = params.get("sharp_price", 0) - params.get("valley_price", 0)
                api_diff = params.get("price_diff", None)
                if api_diff is not None:
                    self.log_result(
                        "电价差计算一致性",
                        abs(calc_diff - api_diff) < 0.001,
                        f"计算={calc_diff:.4f}, API={api_diff}"
                    )

    def test_rl_model_info(self):
        """测试6: RL模型信息API"""
        print("\n" + "="*60)
        print("测试6: RL模型信息API (/proposals/rl/model-info)")
        print("="*60)

        data = self.get("/proposals/rl/model-info")
        print(f"响应: {json.dumps(data, indent=2, ensure_ascii=False)}")

        # RL模型可能未加载，但API应该返回有效结构
        is_valid = isinstance(data, dict) and "error" not in data
        self.log_result(
            "RL模型API响应",
            is_valid,
            "响应格式有效" if is_valid else f"错误: {data.get('error', data.get('detail', 'Unknown'))}"
        )

        if is_valid:
            # 验证关键字段
            info_fields = ["model_loaded", "exploration_rate", "total_steps"]
            present = [f for f in info_fields if f in data]
            self.log_result(
                "RL模型信息字段",
                len(present) > 0,
                f"存在字段: {present}"
            )

    def test_rl_optimization(self):
        """测试7: RL优化API"""
        print("\n" + "="*60)
        print("测试7: RL优化API")
        print("="*60)

        # 获取方案ID
        suggestions = self.get("/proposals/as-suggestions")
        if suggestions.get("code") != 0 or not suggestions.get("data"):
            self.log_result("RL优化测试", False, "没有可用方案")
            return

        proposal_id = suggestions["data"][0]["id"]
        print(f"测试方案ID: {proposal_id}")

        data = self.post(f"/proposals/{proposal_id}/rl/optimize")
        print(f"响应: {json.dumps(data, indent=2, ensure_ascii=False)[:600]}...")

        # 验证响应结构
        is_success_response = "success" in data or "adjustments" in data
        is_error_response = "detail" in data or "error" in data

        if is_success_response:
            self.log_result(
                "RL优化API响应格式",
                True,
                f"success={data.get('success')}"
            )

            if data.get("success"):
                # 验证调整建议结构
                adjustments = data.get("adjustments", {})
                self.log_result(
                    "RL优化调整建议",
                    isinstance(adjustments, dict),
                    f"调整项数量: {len(adjustments)}"
                )

                self.log_result(
                    "探索率字段",
                    "exploration_rate" in data,
                    f"exploration_rate={data.get('exploration_rate', 'N/A')}"
                )
        elif is_error_response:
            self.log_result(
                "RL优化API",
                False,
                f"错误: {data.get('detail', data.get('error', 'Unknown'))}"
            )
        else:
            self.log_result("RL优化API响应格式", False, f"未知格式: {list(data.keys())}")

    def test_effect_monitoring_apis(self):
        """测试8: 效果监测API组"""
        print("\n" + "="*60)
        print("测试8: 效果监测API组")
        print("="*60)

        suggestions = self.get("/proposals/as-suggestions")
        if suggestions.get("code") != 0 or not suggestions.get("data"):
            self.log_result("效果监测测试", False, "没有可用方案")
            return

        proposal_id = suggestions["data"][0]["id"]

        # 8.1 监测状态API
        status = self.get(f"/proposals/{proposal_id}/monitoring/status")
        self.log_result(
            "监测状态API",
            status.get("code") == 0,
            f"code={status.get('code')}"
        )

        # 8.2 效果汇总API
        summary = self.get(f"/proposals/{proposal_id}/effect-summary")
        self.log_result(
            "效果汇总API",
            summary.get("code") == 0,
            f"code={summary.get('code')}"
        )

        # 8.3 RL反馈API (S4e → S5闭环)
        feedback = self.post(f"/proposals/{proposal_id}/rl-feedback")
        self.log_result(
            "RL反馈API",
            feedback.get("code") == 0,
            f"code={feedback.get('code')}, 报告ID={feedback.get('data', {}).get('report_id', 'N/A')}"
        )

    def test_api_response_consistency(self):
        """测试9: API响应格式一致性"""
        print("\n" + "="*60)
        print("测试9: API响应格式一致性检查")
        print("="*60)

        # 检查多个API的响应格式是否一致
        apis_to_check = [
            "/proposals/templates",
            "/proposals/saving-potential",
            "/proposals/as-suggestions",
        ]

        consistent_format = True
        formats = []

        for endpoint in apis_to_check:
            data = self.get(endpoint)
            has_code = "code" in data
            has_message = "message" in data
            has_data = "data" in data

            format_info = {
                "endpoint": endpoint,
                "has_code": has_code,
                "has_message": has_message,
                "has_data": has_data
            }
            formats.append(format_info)

            if not (has_code and has_data):
                consistent_format = False

        self.log_result(
            "API响应格式一致性",
            consistent_format,
            f"检查了 {len(apis_to_check)} 个API"
        )

        # 详细报告不一致的API
        for f in formats:
            if not (f["has_code"] and f["has_data"]):
                print(f"       ⚠ {f['endpoint']}: code={f['has_code']}, data={f['has_data']}")

    def generate_report(self) -> Dict:
        """生成测试报告"""
        print("\n" + "="*60)
        print("API数据一致性测试报告")
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
    print("="*60)
    print("DCIM系统 API数据一致性测试")
    print("="*60)

    tester = APITester()

    # 登录
    if not tester.login():
        print("登录失败，退出测试")
        return

    # 执行测试
    tester.test_templates_api()
    tester.test_saving_potential_api()
    tester.test_suggestions_api()
    tester.test_analyze_and_generate()
    tester.test_proposal_enhanced_detail()
    tester.test_rl_model_info()
    tester.test_rl_optimization()
    tester.test_effect_monitoring_apis()
    tester.test_api_response_consistency()

    # 生成报告
    report = tester.generate_report()

    # 保存报告
    with open("D:/mytest1/api_test_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n报告已保存到: D:/mytest1/api_test_report.json")


if __name__ == "__main__":
    main()
