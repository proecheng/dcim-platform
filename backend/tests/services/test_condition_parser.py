"""
条件表达式解析器单元测试
Story 25.6: 动态告警阈值
"""

import pytest
from app.services.diagnosis.condition_parser import parse_and_evaluate


class TestConditionParser:
    """条件解析器测试"""

    def test_simple_greater_than(self):
        """测试简单大于比较"""
        assert parse_and_evaluate("outdoor_temp > 35", {"outdoor_temp": 36}) is True
        assert parse_and_evaluate("outdoor_temp > 35", {"outdoor_temp": 35}) is False
        assert parse_and_evaluate("outdoor_temp > 35", {"outdoor_temp": 34}) is False

    def test_simple_less_than(self):
        """测试简单小于比较"""
        assert parse_and_evaluate("it_load_percent < 50", {"it_load_percent": 49}) is True
        assert parse_and_evaluate("it_load_percent < 50", {"it_load_percent": 50}) is False
        assert parse_and_evaluate("it_load_percent < 50", {"it_load_percent": 51}) is False

    def test_greater_than_or_equal(self):
        """测试大于等于比较"""
        assert parse_and_evaluate("outdoor_temp >= 35", {"outdoor_temp": 36}) is True
        assert parse_and_evaluate("outdoor_temp >= 35", {"outdoor_temp": 35}) is True
        assert parse_and_evaluate("outdoor_temp >= 35", {"outdoor_temp": 34}) is False

    def test_less_than_or_equal(self):
        """测试小于等于比较"""
        assert parse_and_evaluate("it_load_percent <= 80", {"it_load_percent": 79}) is True
        assert parse_and_evaluate("it_load_percent <= 80", {"it_load_percent": 80}) is True
        assert parse_and_evaluate("it_load_percent <= 80", {"it_load_percent": 81}) is False

    def test_equal(self):
        """测试等于比较"""
        assert parse_and_evaluate("season == 'summer'", {"season": "summer"}) is True
        assert parse_and_evaluate("season == 'summer'", {"season": "winter"}) is False
        assert parse_and_evaluate("count == 10", {"count": 10}) is True
        assert parse_and_evaluate("count == 10", {"count": 11}) is False

    def test_not_equal(self):
        """测试不等于比较"""
        assert parse_and_evaluate("season != 'winter'", {"season": "summer"}) is True
        assert parse_and_evaluate("season != 'winter'", {"season": "winter"}) is False

    def test_and_operator(self):
        """测试 AND 运算符"""
        context = {"outdoor_temp": 36, "it_load_percent": 85}
        assert parse_and_evaluate("outdoor_temp > 35 AND it_load_percent > 80", context) is True

        context = {"outdoor_temp": 34, "it_load_percent": 85}
        assert parse_and_evaluate("outdoor_temp > 35 AND it_load_percent > 80", context) is False

        context = {"outdoor_temp": 36, "it_load_percent": 75}
        assert parse_and_evaluate("outdoor_temp > 35 AND it_load_percent > 80", context) is False

    def test_or_operator(self):
        """测试 OR 运算符"""
        context = {"outdoor_temp": 36, "it_load_percent": 75}
        assert parse_and_evaluate("outdoor_temp > 35 OR it_load_percent > 80", context) is True

        context = {"outdoor_temp": 34, "it_load_percent": 85}
        assert parse_and_evaluate("outdoor_temp > 35 OR it_load_percent > 80", context) is True

        context = {"outdoor_temp": 34, "it_load_percent": 75}
        assert parse_and_evaluate("outdoor_temp > 35 OR it_load_percent > 80", context) is False

    def test_parentheses(self):
        """测试括号分组"""
        context = {"a": 10, "b": 20, "c": 30}
        assert parse_and_evaluate("(a > 5 AND b > 15) OR c > 35", context) is True
        assert parse_and_evaluate("a > 5 AND (b > 15 OR c > 35)", context) is True
        assert parse_and_evaluate("(a > 15 OR b > 15) AND c > 25", context) is True

    def test_complex_expression(self):
        """测试复杂表达式"""
        context = {
            "outdoor_temp": 36,
            "it_load_percent": 85,
            "season": "summer",
            "humidity": 60
        }
        condition = "(outdoor_temp >= 35 AND season == 'summer') OR (it_load_percent > 80 AND humidity < 70)"
        assert parse_and_evaluate(condition, context) is True

    def test_missing_variable(self):
        """测试缺失变量"""
        assert parse_and_evaluate("outdoor_temp > 35", {}) is False
        assert parse_and_evaluate("outdoor_temp > 35", {"other_var": 36}) is False

    def test_type_mismatch(self):
        """测试类型不匹配"""
        # 字符串与数字比较应返回 False
        assert parse_and_evaluate("outdoor_temp > 35", {"outdoor_temp": "high"}) is False

    def test_invalid_syntax(self):
        """测试无效语法"""
        assert parse_and_evaluate("outdoor_temp >", {"outdoor_temp": 36}) is False
        assert parse_and_evaluate("outdoor_temp 35", {"outdoor_temp": 36}) is False
        assert parse_and_evaluate("", {"outdoor_temp": 36}) is False

    def test_case_insensitive_operators(self):
        """测试运算符大小写不敏感"""
        context = {"a": 10, "b": 20}
        assert parse_and_evaluate("a > 5 and b > 15", context) is True
        assert parse_and_evaluate("a > 5 AND b > 15", context) is True
        assert parse_and_evaluate("a > 5 or b > 25", context) is True
        assert parse_and_evaluate("a > 5 OR b > 25", context) is True

    def test_string_comparison(self):
        """测试字符串比较"""
        assert parse_and_evaluate("status == 'active'", {"status": "active"}) is True
        assert parse_and_evaluate("status != 'inactive'", {"status": "active"}) is True
        assert parse_and_evaluate("name == 'test'", {"name": "test"}) is True

    def test_float_comparison(self):
        """测试浮点数比较"""
        assert parse_and_evaluate("temp > 35.5", {"temp": 36.0}) is True
        assert parse_and_evaluate("temp >= 35.5", {"temp": 35.5}) is True
        assert parse_and_evaluate("load < 80.5", {"load": 80.0}) is True
