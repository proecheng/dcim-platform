"""
电费单 OCR 识别服务

实现策略:
- 尝试导入 PaddleOCR，如果不可用则降级为 mock 模式
- PaddleOCR 可用时，真实识别电费单图片并提取电价信息
- 支持国家电网（五时段）和南方电网（三/四时段）电费单模板
- mock 模式返回国家电网标准五时段电价示例数据
"""

import asyncio
import io
import logging
import re
from datetime import date
from functools import lru_cache
from typing import Optional

logger = logging.getLogger(__name__)

# 尝试导入 PaddleOCR
_paddle_available = False
_PaddleOCR = None
try:
    import importlib.util
    _paddle_available = importlib.util.find_spec("paddleocr") is not None
    if _paddle_available:
        from paddleocr import PaddleOCR as _PaddleOCR_cls
        _PaddleOCR = _PaddleOCR_cls
        logger.info("PaddleOCR 可用，使用本地 OCR 引擎")
    else:
        logger.info("PaddleOCR 未安装，使用 mock 模式")
except Exception:
    _paddle_available = False
    logger.info("PaddleOCR 检测失败，使用 mock 模式")

# 时段类型中文到英文映射
_PERIOD_TYPE_MAP: dict[str, str] = {
    "尖峰": "sharp",
    "高峰": "peak",
    "平段": "flat",
    "平": "flat",
    "低谷": "valley",
    "深谷": "deep_valley",
}

# 时段类型中文到显示名称映射
_PERIOD_NAME_MAP: dict[str, str] = {
    "尖峰": "尖峰时段",
    "高峰": "高峰时段",
    "平段": "平段时段",
    "平": "平段时段",
    "低谷": "低谷时段",
    "深谷": "深谷时段",
}


@lru_cache(maxsize=1)
def _get_paddle_ocr() -> object:
    """获取 PaddleOCR 实例（lru_cache 缓存，避免重复初始化）"""
    if _PaddleOCR is None:
        raise RuntimeError("PaddleOCR 未导入")
    return _PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)


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


def _detect_provider(raw_text: str) -> str:
    """根据 OCR 文本检测电力公司"""
    if "南方电网" in raw_text or "南网" in raw_text:
        return "南方电网"
    if "国家电网" in raw_text or "国网" in raw_text:
        return "国家电网"
    return "未知电力公司"


def _extract_pricing_items(
    raw_text: str, effective_date: str
) -> list[OcrBillItem]:
    """
    从 OCR 文本中提取电价信息

    支持的匹配模式:
    - "尖峰 10:00-12:00 1.4052"
    - "高峰时段 08:00~10:00 1.0549元/kWh"
    - "平段 0.6838"（无时间范围时留空）
    - 表格行: "尖峰 | 10:00-12:00 | 1.4052"
    """
    items: list[OcrBillItem] = []
    period_keywords = "|".join(_PERIOD_TYPE_MAP.keys())

    # 模式1: 时段名 + 时间范围 + 价格
    # 例: "尖峰 10:00-12:00 1.4052" 或 "高峰时段 08:00~10:00 1.0549元/kWh"
    pattern_with_time = re.compile(
        rf"({period_keywords})(?:时段)?\s*[|｜]?\s*"
        rf"(\d{{1,2}}:\d{{2}})\s*[-~～至到]\s*(\d{{1,2}}:\d{{2}})\s*[|｜]?\s*"
        rf"(\d+\.\d{{2,6}})\s*(?:元/?[kK][wW][hH])?",
    )

    # 模式2: 时段名 + 价格（无时间范围）
    # 例: "尖峰 1.4052" 或 "低谷时段 0.3620元/kWh"
    pattern_price_only = re.compile(
        rf"({period_keywords})(?:时段)?\s*[|｜]?\s*"
        rf"(\d+\.\d{{2,6}})\s*(?:元/?[kK][wW][hH])?",
    )

    matched_periods: set[str] = set()

    # 先尝试带时间范围的模式
    for match in pattern_with_time.finditer(raw_text):
        period_cn = match.group(1)
        start_time = match.group(2)
        end_time = match.group(3)
        price = float(match.group(4))
        period_type = _PERIOD_TYPE_MAP[period_cn]

        if period_type in matched_periods:
            continue
        matched_periods.add(period_type)

        items.append(OcrBillItem(
            pricing_name=_PERIOD_NAME_MAP[period_cn],
            period_type=period_type,
            start_time=start_time,
            end_time=end_time,
            price=price,
            confidence=0.0,  # 后续由调用方填充
            effective_date=effective_date,
        ))

    # 再尝试仅有价格的模式（补充未匹配到的时段）
    for match in pattern_price_only.finditer(raw_text):
        period_cn = match.group(1)
        price = float(match.group(2))
        period_type = _PERIOD_TYPE_MAP[period_cn]

        if period_type in matched_periods:
            continue
        matched_periods.add(period_type)

        items.append(OcrBillItem(
            pricing_name=_PERIOD_NAME_MAP[period_cn],
            period_type=period_type,
            start_time="",
            end_time="",
            price=price,
            confidence=0.0,
            effective_date=effective_date,
        ))

    return items


def _run_paddle_ocr(file_bytes: bytes) -> list[list]:
    """同步执行 PaddleOCR 识别（供 run_in_executor 调用）"""
    import numpy as np
    from PIL import Image

    ocr = _get_paddle_ocr()
    image = Image.open(io.BytesIO(file_bytes)).convert("RGB")
    img_array = np.array(image)
    result = ocr.ocr(img_array, cls=True)
    return result


async def _recognize_with_paddle(file_bytes: bytes, filename: str) -> OcrBillResult:
    """
    使用 PaddleOCR 识别电费单

    流程:
    1. 将 file_bytes 转为图片，调用 PaddleOCR 识别
    2. 拼接所有文本行为 raw_text
    3. 检测电力公司（国家电网/南方电网）
    4. 用正则提取电价时段信息
    5. 计算置信度
    """
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _run_paddle_ocr, file_bytes)
    except Exception as e:
        logger.error("PaddleOCR 识别失败: %s", e)
        return OcrBillResult(
            success=False,
            confidence=0.0,
            provider="unknown",
            items=[],
            raw_text=None,
            error_message=f"OCR 识别失败: {e}",
        )

    # 解析 PaddleOCR 返回结果，提取文本和置信度
    # PaddleOCR 返回格式: [page[ [box, (text, confidence)], ... ]]
    text_lines: list[str] = []
    confidences: list[float] = []

    if result:
        for page in result:
            if not page:
                continue
            for line in page:
                if len(line) >= 2 and isinstance(line[1], (list, tuple)):
                    text, conf = line[1][0], line[1][1]
                    text_lines.append(str(text))
                    confidences.append(float(conf))

    if not text_lines:
        return OcrBillResult(
            success=False,
            confidence=0.0,
            provider="unknown",
            items=[],
            raw_text="",
            error_message="OCR 未识别到任何文本",
        )

    raw_text = "\n".join(text_lines)
    avg_confidence = sum(confidences) / len(confidences) * 100 if confidences else 0.0

    # 检测电力公司
    provider = _detect_provider(raw_text)

    # 提取电价信息
    today = date.today().isoformat()
    items = _extract_pricing_items(raw_text, today)

    if not items:
        return OcrBillResult(
            success=False,
            confidence=avg_confidence,
            provider=provider,
            items=[],
            raw_text=raw_text,
            error_message="未能从图片中提取到电价时段信息，请确认上传的是电费单",
        )

    # 为每条识别结果填充置信度（使用 OCR 整体平均置信度）
    for item in items:
        item.confidence = round(avg_confidence, 1)

    logger.info(
        "PaddleOCR 识别完成: 供电公司=%s, 识别到 %d 个时段, 平均置信度=%.1f%%",
        provider, len(items), avg_confidence,
    )

    return OcrBillResult(
        success=True,
        confidence=round(avg_confidence, 1),
        provider=provider,
        items=items,
        raw_text=raw_text,
    )
