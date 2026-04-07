"""
HMAC 签名管理器 - Story 24.4
"""

import hmac
import hashlib
from app.core.config import get_settings


class HMACManager:
    """HMAC 签名管理器"""

    @staticmethod
    def generate_signature(data: str) -> str:
        """生成 HMAC-SHA-256 签名"""
        settings = get_settings()
        if not settings.FAULT_TREE_HMAC_KEY:
            raise ValueError("HMAC 密钥未配置或为空，请设置 FAULT_TREE_HMAC_KEY")
        key = settings.FAULT_TREE_HMAC_KEY.encode()
        signature = hmac.new(key, data.encode(), hashlib.sha256).hexdigest()
        return signature

    @staticmethod
    def generate_signature_with_key(data: str, key: str) -> str:
        """使用指定密钥生成 HMAC-SHA-256 签名（用于密钥轮换）"""
        return hmac.new(key.encode(), data.encode(), hashlib.sha256).hexdigest()

    @staticmethod
    def verify_signature(data: str, signature: str) -> bool:
        """验证 HMAC 签名（支持密钥轮换）"""
        # 输入验证
        if not signature or len(signature) != 64:
            return False

        # 验证是否为有效的十六进制字符串
        try:
            int(signature, 16)
        except ValueError:
            return False

        settings = get_settings()

        # 尝试当前密钥
        current_key = settings.FAULT_TREE_HMAC_KEY.encode()
        expected_sig = hmac.new(current_key, data.encode(), hashlib.sha256).hexdigest()
        if hmac.compare_digest(expected_sig, signature):
            return True

        # 尝试旧密钥（如果配置了）
        if settings.FAULT_TREE_HMAC_KEY_PREVIOUS:
            previous_key = settings.FAULT_TREE_HMAC_KEY_PREVIOUS.encode()
            expected_sig = hmac.new(previous_key, data.encode(), hashlib.sha256).hexdigest()
            if hmac.compare_digest(expected_sig, signature):
                return True

        return False
