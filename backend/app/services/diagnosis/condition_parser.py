"""
条件表达式解析器
Story 25.6: 动态告警阈值

支持的运算符: >, <, ==, !=, >=, <=, AND, OR
支持括号分组
"""

import logging
from typing import Any, Dict
from enum import Enum

logger = logging.getLogger(__name__)


class TokenType(Enum):
    """Token 类型"""

    NUMBER = "NUMBER"
    STRING = "STRING"
    IDENTIFIER = "IDENTIFIER"
    OPERATOR = "OPERATOR"
    AND = "AND"
    OR = "OR"
    LPAREN = "LPAREN"
    RPAREN = "RPAREN"
    EOF = "EOF"


class Token:
    """Token 对象"""

    def __init__(self, type_: TokenType, value: Any):
        self.type = type_
        self.value = value

    def __repr__(self):
        return f"Token({self.type}, {self.value})"


class Lexer:
    """词法分析器"""

    def __init__(self, text: str):
        self.text = text
        self.pos = 0
        self.current_char = self.text[self.pos] if self.text else None

    def advance(self):
        """移动到下一个字符"""
        self.pos += 1
        if self.pos < len(self.text):
            self.current_char = self.text[self.pos]
        else:
            self.current_char = None

    def skip_whitespace(self):
        """跳过空白字符"""
        while self.current_char is not None and self.current_char.isspace():
            self.advance()

    def read_number(self) -> float:
        """读取数字"""
        num_str = ""
        while self.current_char is not None and (self.current_char.isdigit() or self.current_char == "."):
            num_str += self.current_char
            self.advance()
        return float(num_str)

    def read_string(self) -> str:
        """读取字符串（单引号或双引号）"""
        quote = self.current_char
        self.advance()  # 跳过开始引号
        string = ""
        while self.current_char is not None and self.current_char != quote:
            string += self.current_char
            self.advance()
        self.advance()  # 跳过结束引号
        return string

    def read_identifier(self) -> str:
        """读取标识符（限制为字母、数字、下划线）"""
        identifier = ""
        while self.current_char is not None and (self.current_char.isalnum() or self.current_char == "_"):
            identifier += self.current_char
            self.advance()

        # 安全检查: 变量名只能包含字母、数字、下划线
        if not identifier or not all(c.isalnum() or c == "_" for c in identifier):
            raise ValueError(f"Invalid identifier: {identifier}")

        return identifier

    def get_next_token(self) -> Token:
        """获取下一个 token"""
        while self.current_char is not None:
            if self.current_char.isspace():
                self.skip_whitespace()
                continue

            if self.current_char.isdigit():
                return Token(TokenType.NUMBER, self.read_number())

            if self.current_char in ('"', "'"):
                return Token(TokenType.STRING, self.read_string())

            if self.current_char.isalpha() or self.current_char == "_":
                identifier = self.read_identifier()
                if identifier.upper() == "AND":
                    return Token(TokenType.AND, "AND")
                elif identifier.upper() == "OR":
                    return Token(TokenType.OR, "OR")
                else:
                    return Token(TokenType.IDENTIFIER, identifier)

            if self.current_char == "(":
                self.advance()
                return Token(TokenType.LPAREN, "(")

            if self.current_char == ")":
                self.advance()
                return Token(TokenType.RPAREN, ")")

            # 运算符
            if self.current_char in (">", "<", "=", "!"):
                op = self.current_char
                self.advance()
                if self.current_char == "=":
                    op += self.current_char
                    self.advance()
                return Token(TokenType.OPERATOR, op)

            raise ValueError(f"Invalid character: {self.current_char}")

        return Token(TokenType.EOF, None)


class Parser:
    """语法分析器"""

    MAX_RECURSION_DEPTH = 20  # P1-1 修复: 最大递归深度

    def __init__(self, lexer: Lexer):
        self.lexer = lexer
        self.current_token = self.lexer.get_next_token()
        self._recursion_depth = 0  # P1-1 修复: 递归深度计数器

    def _check_recursion_depth(self):
        """P1-1 修复: 检查递归深度"""
        if self._recursion_depth >= self.MAX_RECURSION_DEPTH:
            raise ValueError(f"表达式嵌套过深 (最大 {self.MAX_RECURSION_DEPTH} 层)")

    def eat(self, token_type: TokenType):
        """消费当前 token"""
        if self.current_token.type == token_type:
            self.current_token = self.lexer.get_next_token()
        else:
            raise ValueError(f"Expected {token_type}, got {self.current_token.type}")

    def parse(self) -> Any:
        """解析表达式"""
        return self.or_expr()

    def or_expr(self):
        """OR 表达式"""
        self._recursion_depth += 1  # P1-1 修复
        self._check_recursion_depth()  # P1-1 修复
        try:
            node = self.and_expr()

            while self.current_token.type == TokenType.OR:
                self.eat(TokenType.OR)
                node = ("OR", node, self.and_expr())

            return node
        finally:
            self._recursion_depth -= 1  # P1-1 修复

    def and_expr(self):
        """AND 表达式"""
        self._recursion_depth += 1  # P1-1 修复
        self._check_recursion_depth()  # P1-1 修复
        try:
            node = self.comparison()

            while self.current_token.type == TokenType.AND:
                self.eat(TokenType.AND)
                node = ("AND", node, self.comparison())

            return node
        finally:
            self._recursion_depth -= 1  # P1-1 修复

    def comparison(self):
        """比较表达式"""
        self._recursion_depth += 1  # P1-1 修复
        self._check_recursion_depth()  # P1-1 修复
        try:
            if self.current_token.type == TokenType.LPAREN:
                self.eat(TokenType.LPAREN)
                node = self.or_expr()
                self.eat(TokenType.RPAREN)
                return node

            left = self.current_token
            if left.type == TokenType.IDENTIFIER:
                self.eat(TokenType.IDENTIFIER)
            else:
                raise ValueError(f"Expected IDENTIFIER, got {left.type}")

            op = self.current_token
            if op.type == TokenType.OPERATOR:
                self.eat(TokenType.OPERATOR)
            else:
                raise ValueError(f"Expected OPERATOR, got {op.type}")

            right = self.current_token
            if right.type in (TokenType.NUMBER, TokenType.STRING, TokenType.IDENTIFIER):
                self.eat(right.type)
            else:
                raise ValueError(f"Expected NUMBER/STRING/IDENTIFIER, got {right.type}")

            return ("CMP", left.value, op.value, right.value, right.type)
        finally:
            self._recursion_depth -= 1  # P1-1 修复


class ConditionEvaluator:
    """条件求值器"""

    def __init__(self, context: Dict[str, Any]):
        self.context = context

    def evaluate(self, node) -> bool:
        """求值表达式树"""
        if isinstance(node, tuple):
            if node[0] == "OR":
                return self.evaluate(node[1]) or self.evaluate(node[2])
            elif node[0] == "AND":
                return self.evaluate(node[1]) and self.evaluate(node[2])
            elif node[0] == "CMP":
                right_type = node[4] if len(node) > 4 else None
                return self.evaluate_comparison(node[1], node[2], node[3], right_type)
        return False

    def evaluate_comparison(self, left: str, op: str, right: Any, right_type=None) -> bool:
        """求值比较表达式"""
        # 获取左值
        left_value = self.context.get(left)
        if left_value is None:
            return False

        # 获取右值：仅当右操作数为 IDENTIFIER 类型时才从上下文解析变量
        if right_type == TokenType.IDENTIFIER and isinstance(right, str) and right in self.context:
            right_value = self.context[right]
        else:
            right_value = right

        # 执行比较
        try:
            if op == ">":
                return left_value > right_value
            elif op == "<":
                return left_value < right_value
            elif op == ">=":
                return left_value >= right_value
            elif op == "<=":
                return left_value <= right_value
            elif op == "==":
                return left_value == right_value
            elif op == "!=":
                return left_value != right_value
            else:
                return False
        except (TypeError, ValueError):
            return False


def parse_and_evaluate(condition: str, context: Dict[str, Any]) -> bool:
    """
    解析并求值条件表达式

    Args:
        condition: 条件表达式字符串
        context: 上下文变量字典

    Returns:
        bool: 条件是否满足

    Examples:
        >>> parse_and_evaluate("outdoor_temp >= 35", {"outdoor_temp": 36})
        True
        >>> parse_and_evaluate("it_load_percent > 80 AND season == 'summer'",
        ...                    {"it_load_percent": 85, "season": "summer"})
        True
    """
    try:
        # 安全检查: 限制表达式长度 < 200 字符
        if len(condition) >= 200:
            logger.warning(f"条件表达式过长 ({len(condition)} 字符): {condition[:50]}...")
            return False

        lexer = Lexer(condition)
        parser = Parser(lexer)
        ast = parser.parse()
        evaluator = ConditionEvaluator(context)
        return evaluator.evaluate(ast)
    except Exception as e:
        logger.warning(f"条件表达式解析失败: {condition} - {e}")
        return False
