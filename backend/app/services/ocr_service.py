"""
电费单 OCR 识别服务

MVP 实现策略:
- 尝试导入 PaddleOCR，如果不可用则降级为 mock 模式
- mock 模式返回国家电网标准五时段电价示例数据
- 生产环境后续集成 PaddleOCR 或云 OCR API
"""

import logging
from typing import Optional
from datetime import date

logger = logging.getLogger(__name__)

# 尝试导入 PaddleOCR
_paddle_available = False
try:
    import importlib.util
    _paddle_available = importlib.util.find_spec("paddleocr") is not None
    if _paddle_available:
        logger.info("PaddleOCR 可用，使用本地 OCR 引擎")
    else:
        logger.info("PaddleOCR 未安装，使用 mock 模式")
except Exception:
    logger.info("PaddleOCR 检测失败，使用 mock 模式")


class OcrBillItem:
    """OCR 识别的单条电价数据"""

    def __init__(
        self,
        pricing_name: str,
        period_type: str,
        start_time: str,
        end_time: str,
        price: float,
        confidence: float,
        effective_date: str,
    ):
        self.pricing_name = pricing_name
        self.period_type = period_type
        self.start_time = start_time
        self.end_time = end_time
        self.price = price
        self.confidence = confidence
        self.effective_date = effective_date


class OcrBillResult:
    """OCR 识别结果"""

    def __init__(
        self,
        success: bool,
        confidence: float,
        provider: str,
        items: list[OcrBillItem],
        raw_text: Optional[str] = None,
        error_message: Optional[str] = None,
    ):
        self.success = success
        self.confidence = confidence
        self.provider = provider
        self.items = items
        self.raw_text = raw_text
        self.error_message = error_message


def _get_mock_result() -> OcrBillResult:
    """返回国家电网标准五时段电价 mock 数据"""
    today = date.today().isoformat()
    items = [
        OcrBillItem(
            pricing_name="尖峰时段",
            period_type="sharp",
            start_time="10:00",
            end_time="12:00",
            price=1.4052,
            confidence=92.0,
            effective_date=today,
        ),
        OcrBillItem(
            pricing_name="高峰时段",
            period_type="peak",
            start_time="08:00",
            end_time="10:00",
            price=1.0549,
            confidence=88.0,
            effective_date=today,
        ),
        OcrBillItem(
            pricing_name="平段时段",
            period_type="flat",
            start_time="12:00",
            end_time="17:00",
            price=0.6838,
            confidence=90.0,
            effective_date=today,
        ),
        OcrBillItem(
            pricing_name="低谷时段",
            period_type="valley",
            start_time="23:00",
            end_time="07:00",
            price=0.3620,
            confidence=85.0,
            effective_date=today,
        ),
        OcrBillItem(
            pricing_name="深谷时段",
            period_type="deep_valley",
            start_time="01:00",
            end_time="05:00",
            price=0.2215,
            confidence=78.0,
            effective_date=today,
        ),
    ]
    return OcrBillResult(
        success=True,
        confidence=85.0,
        provider="国家电网",
        items=items,
        raw_text="[mock] 国家电网标准五时段电价示例数据",
    )


async def recognize_bill(file_bytes: bytes, filename: str) -> OcrBillResult:
    """
    识别电费单图片，提取电价信息

    Args:
        file_bytes: 图片文件字节
        filename: 文件名

    Returns:
        OcrBillResult: 识别结果
    """
    # 校验文件类型
    lower_name = filename.lower()
    valid_extensions = (".jpg", ".jpeg", ".png", ".pdf")
    if not any(lower_name.endswith(ext) for ext in valid_extensions):
        return OcrBillResult(
            success=False,
            confidence=0,
            provider="unknown",
            items=[],
            error_message="不支持的文件格式，请上传 JPG/PNG/PDF 文件",
        )

    # 校验文件大小 (10MB)
    max_size = 10 * 1024 * 1024
    if len(file_bytes) > max_size:
        return OcrBillResult(
            success=False,
            confidence=0,
            provider="unknown",
            items=[],
            error_message="文件大小不能超过10MB",
        )

    if _paddle_available:
        return await _recognize_with_paddle(file_bytes, filename)

    # PaddleOCR 不可用，使用 mock 模式
    logger.info("使用 mock 模式返回示例电价数据 (PaddleOCR 未安装)")
    return _get_mock_result()


async def _recognize_with_paddle(file_bytes: bytes, filename: str) -> OcrBillResult:
    """
    使用 PaddleOCR 识别电费单

    TODO: 集成真实 PaddleOCR 识别逻辑
    - 初始化 PaddleOCR 实例
    - 将 file_bytes 转为图片
    - 调用 ocr.ocr() 获取文本
    - 使用正则/模板匹配提取电价信息
    - 根据模板判断是国家电网还是南方电网
    """
    # TODO: 实现真实 PaddleOCR 识别
    # 当前即使 PaddleOCR 可用也先返回 mock 数据，待模板匹配逻辑完善后替换
    logger.info("PaddleOCR 已安装，但模板匹配逻辑待完善，暂用 mock 数据")
    return _get_mock_result()
