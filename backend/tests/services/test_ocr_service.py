"""
电费单 OCR 识别服务单元测试

覆盖:
  - _get_mock_result: mock 模式返回数据结构验证
  - recognize_bill: 文件类型校验、文件大小校验、魔数校验、mock 模式调用
  - _detect_provider: 电力公司检测
  - _extract_pricing_items: 正则提取电价信息（带时间/不带时间/表格行）
"""

import pytest
from datetime import date

from app.services.ocr_service import (
    _get_mock_result,
    _detect_provider,
    _extract_pricing_items,
    recognize_bill,
    OcrBillResult,
)

# 测试用文件魔数前缀
JPEG_HEADER = b"\xff\xd8\xff\xe0" + b"\x00" * 100
PNG_HEADER = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
PDF_HEADER = b"%PDF-1.4" + b"\x00" * 100


class TestGetMockResult:
    """mock 模式返回数据验证"""

    def test_mock_result_structure(self):
        """mock 结果应包含完整的五时段电价数据"""
        result = _get_mock_result()
        assert isinstance(result, OcrBillResult)
        assert result.success is True
        assert result.provider == "国家电网"
        assert len(result.items) == 5
        assert result.raw_text is not None

    def test_mock_result_period_types(self):
        """mock 结果应包含所有五个时段类型"""
        result = _get_mock_result()
        period_types = {item.period_type for item in result.items}
        assert period_types == {"sharp", "peak", "flat", "valley", "deep_valley"}

    def test_mock_result_prices_positive(self):
        """所有电价应为正数"""
        result = _get_mock_result()
        for item in result.items:
            assert item.price > 0

    def test_mock_result_effective_date_is_today(self):
        """生效日期应为当天"""
        result = _get_mock_result()
        today = date.today().isoformat()
        for item in result.items:
            assert item.effective_date == today


class TestDetectProvider:
    """电力公司检测"""

    def test_detect_national_grid(self):
        assert _detect_provider("国家电网电费单") == "国家电网"

    def test_detect_national_grid_short(self):
        assert _detect_provider("国网公司") == "国家电网"

    def test_detect_southern_grid(self):
        assert _detect_provider("南方电网电费单") == "南方电网"

    def test_detect_southern_grid_short(self):
        assert _detect_provider("南网公司") == "南方电网"

    def test_detect_unknown(self):
        assert _detect_provider("某某电力公司") == "未知电力公司"

    def test_detect_empty_text(self):
        assert _detect_provider("") == "未知电力公司"


class TestExtractPricingItems:
    """正则提取电价信息"""

    def test_extract_with_time_range(self):
        """带时间范围的标准格式"""
        text = "尖峰 10:00-12:00 1.4052\n高峰 08:00-10:00 1.0549"
        items = _extract_pricing_items(text, "2026-01-01")
        assert len(items) == 2
        sharp = next(i for i in items if i.period_type == "sharp")
        assert sharp.start_time == "10:00"
        assert sharp.end_time == "12:00"
        assert sharp.price == 1.4052

    def test_extract_with_tilde_separator(self):
        """使用波浪号分隔时间"""
        text = "高峰时段 08:00~10:00 1.0549元/kWh"
        items = _extract_pricing_items(text, "2026-01-01")
        assert len(items) == 1
        assert items[0].period_type == "peak"
        assert items[0].price == 1.0549

    def test_extract_price_only(self):
        """仅有价格无时间范围"""
        text = "平段 0.6838"
        items = _extract_pricing_items(text, "2026-01-01")
        assert len(items) == 1
        assert items[0].period_type == "flat"
        assert items[0].start_time == ""
        assert items[0].end_time == ""
        assert items[0].price == 0.6838

    def test_extract_no_match(self):
        """无匹配内容返回空列表"""
        text = "这是一段普通文本，没有电价信息"
        items = _extract_pricing_items(text, "2026-01-01")
        assert items == []

    def test_extract_dedup_periods(self):
        """同一时段类型不重复提取"""
        text = "尖峰 10:00-12:00 1.4052\n尖峰 1.5000"
        items = _extract_pricing_items(text, "2026-01-01")
        # 带时间的优先匹配，仅有价格的被去重
        sharp_items = [i for i in items if i.period_type == "sharp"]
        assert len(sharp_items) == 1

    def test_extract_all_five_periods(self):
        """完整五时段提取"""
        text = (
            "尖峰 10:00-12:00 1.4052\n"
            "高峰 08:00-10:00 1.0549\n"
            "平段 12:00-17:00 0.6838\n"
            "低谷 23:00-07:00 0.3620\n"
            "深谷 01:00-05:00 0.2215"
        )
        items = _extract_pricing_items(text, "2026-01-01")
        assert len(items) == 5
        types = {i.period_type for i in items}
        assert types == {"sharp", "peak", "flat", "valley", "deep_valley"}

    def test_extract_table_format(self):
        """表格行格式（竖线分隔）"""
        text = "尖峰 | 10:00-12:00 | 1.4052"
        items = _extract_pricing_items(text, "2026-01-01")
        assert len(items) == 1
        assert items[0].period_type == "sharp"
        assert items[0].price == 1.4052


class TestRecognizeBill:
    """recognize_bill 主函数测试"""

    @pytest.mark.asyncio
    async def test_invalid_file_extension(self):
        """不支持的文件格式应返回错误"""
        result = await recognize_bill(b"fake data", "test.txt")
        assert result.success is False
        assert "不支持的文件格式" in result.error_message

    @pytest.mark.asyncio
    async def test_invalid_file_extension_bmp(self):
        """BMP 格式不支持"""
        result = await recognize_bill(b"fake data", "test.bmp")
        assert result.success is False

    @pytest.mark.asyncio
    async def test_valid_extensions_accepted(self):
        """JPG/PNG/PDF 格式应被接受（进入 mock 模式）"""
        test_data = {
            ".jpg": JPEG_HEADER,
            ".jpeg": JPEG_HEADER,
            ".png": PNG_HEADER,
            ".pdf": PDF_HEADER,
        }
        for ext, data in test_data.items():
            result = await recognize_bill(data, f"test{ext}")
            # 在 mock 模式下应返回成功
            assert result.success is True

    @pytest.mark.asyncio
    async def test_file_too_large(self):
        """超过 10MB 的文件应返回错误"""
        large_data = b"x" * (10 * 1024 * 1024 + 1)
        result = await recognize_bill(large_data, "test.jpg")
        assert result.success is False
        assert "10MB" in result.error_message

    @pytest.mark.asyncio
    async def test_file_exactly_10mb(self):
        """恰好 10MB 的文件应被接受"""
        data = JPEG_HEADER + b"x" * (10 * 1024 * 1024 - len(JPEG_HEADER))
        result = await recognize_bill(data, "test.jpg")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_mock_mode_returns_valid_data(self):
        """mock 模式应返回完整的五时段数据"""
        result = await recognize_bill(JPEG_HEADER, "bill.jpg")
        assert result.success is True
        assert result.provider == "国家电网"
        assert len(result.items) == 5

    @pytest.mark.asyncio
    async def test_case_insensitive_extension(self):
        """文件扩展名大小写不敏感"""
        result = await recognize_bill(JPEG_HEADER, "bill.JPG")
        assert result.success is True

        result = await recognize_bill(PNG_HEADER, "bill.Png")
        assert result.success is True
