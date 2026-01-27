"""
测试模板生成器服务
验证6种模板的生成功能
"""
import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.services.template_generator import TemplateGenerator
from app.models.energy import (
    EnergySavingProposal,
    ProposalMeasure,
    EnergyDaily,
    DemandHistory,
    MeterPoint,
    PowerDevice,
    DeviceShiftConfig
)


class TestTemplateGenerator:
    """模板生成器测试类"""

    @pytest.fixture
    def generator(self, db_session: Session):
        """创建模板生成器实例"""
        return TemplateGenerator(db_session)

    @pytest.fixture
    def setup_basic_data(self, db_session: Session):
        """设置基础测试数据"""
        # 创建计量点
        meter_point = MeterPoint(
            meter_code="M001",
            meter_name="总表",
            declared_demand=5000,
            is_enabled=True
        )
        db_session.add(meter_point)
        db_session.flush()

        # 创建能耗数据
        today = datetime.now().date()
        for i in range(30):
            date = today - timedelta(days=i)
            energy_daily = EnergyDaily(
                device_id=1,
                stat_date=date,
                total_energy=50000,
                peak_energy=20000,
                normal_energy=18000,
                valley_energy=12000,
                max_power=3000,
                avg_power=2083
            )
            db_session.add(energy_daily)

        # 创建需量历史
        current_year = datetime.now().year
        current_month = datetime.now().month
        demand_history = DemandHistory(
            meter_point_id=meter_point.id,
            stat_year=current_year,
            stat_month=current_month,
            declared_demand=5000,
            max_demand=4200,
            avg_demand=3500,
            demand_95th=4000
        )
        db_session.add(demand_history)

        # 创建设备
        device1 = PowerDevice(
            device_code="DEV001",
            device_name="空压机1",
            device_type="PUMP",
            rated_power=160,
            efficiency=92,
            is_enabled=True
        )
        db_session.add(device1)
        db_session.flush()

        # 创建设备转移配置
        shift_config = DeviceShiftConfig(
            device_id=device1.id,
            is_shiftable=True,
            shiftable_power_ratio=0.5,
            shift_notice_time=10
        )
        db_session.add(shift_config)

        db_session.commit()
        return meter_point.id

    def test_template_configs(self, generator: TemplateGenerator):
        """测试模板配置"""
        assert "A1" in generator.TEMPLATE_CONFIGS
        assert "A2" in generator.TEMPLATE_CONFIGS
        assert "A3" in generator.TEMPLATE_CONFIGS
        assert "A4" in generator.TEMPLATE_CONFIGS
        assert "A5" in generator.TEMPLATE_CONFIGS
        assert "B1" in generator.TEMPLATE_CONFIGS

        # 验证A类型模板
        assert generator.TEMPLATE_CONFIGS["A1"]["type"] == "A"
        assert generator.TEMPLATE_CONFIGS["A2"]["type"] == "A"

        # 验证B类型模板
        assert generator.TEMPLATE_CONFIGS["B1"]["type"] == "B"

    def test_invalid_template_id(self, generator: TemplateGenerator):
        """测试无效的模板ID"""
        with pytest.raises(ValueError, match="无效的模板ID"):
            generator.generate_proposal("INVALID_ID", 30)

    def test_generate_a1_peak_valley_proposal(
        self,
        generator: TemplateGenerator,
        db_session: Session,
        setup_basic_data
    ):
        """测试A1-峰谷套利优化方案生成"""
        proposal = generator.generate_proposal("A1", analysis_days=30)

        # 验证方案基本信息
        assert proposal.proposal_type == "A"
        assert proposal.template_id == "A1"
        assert proposal.template_name == "峰谷套利优化方案"
        assert proposal.proposal_code.startswith("A1-")
        assert proposal.total_investment == Decimal("0")

        # 验证措施数量
        assert len(proposal.measures) == 3

        # 验证措施1: 热处理预热工序调整
        measure1 = proposal.measures[0]
        assert "M001" in measure1.measure_code
        assert "热处理" in measure1.regulation_object
        assert measure1.annual_benefit > 0
        assert measure1.investment == Decimal("0")

        # 验证措施2: 辅助设备错峰运行
        measure2 = proposal.measures[1]
        assert "M002" in measure2.measure_code
        assert "辅助" in measure2.regulation_object

        # 验证措施3: 空压机储气罐优化
        measure3 = proposal.measures[2]
        assert "M003" in measure3.measure_code
        assert "空压机" in measure3.regulation_object

        # 验证总收益
        expected_total = sum(m.annual_benefit for m in proposal.measures)
        assert proposal.total_benefit == expected_total

        # 验证当前状况数据
        assert "尖峰电量" in proposal.current_situation
        assert "总电量" in proposal.current_situation

    def test_generate_a2_demand_control_proposal(
        self,
        generator: TemplateGenerator,
        db_session: Session,
        setup_basic_data
    ):
        """测试A2-需量控制方案生成"""
        proposal = generator.generate_proposal("A2", analysis_days=30)

        # 验证方案基本信息
        assert proposal.proposal_type == "A"
        assert proposal.template_id == "A2"
        assert proposal.template_name == "需量控制方案"

        # 验证措施数量
        assert len(proposal.measures) == 3

        # 验证措施类型
        measure_objects = [m.regulation_object for m in proposal.measures]
        assert any("申报需量" in obj for obj in measure_objects)
        assert any("监控" in obj for obj in measure_objects)
        assert any("负荷" in obj for obj in measure_objects)

        # 验证所有措施都是A类型（无需投资）
        for measure in proposal.measures:
            assert measure.investment == Decimal("0")

    def test_generate_a3_equipment_optimization_proposal(
        self,
        generator: TemplateGenerator,
        db_session: Session,
        setup_basic_data
    ):
        """测试A3-设备运行优化方案生成"""
        proposal = generator.generate_proposal("A3", analysis_days=30)

        # 验证方案基本信息
        assert proposal.proposal_type == "A"
        assert proposal.template_id == "A3"
        assert proposal.template_name == "设备运行优化方案"

        # 验证措施数量
        assert len(proposal.measures) == 3

        # 验证措施针对不同设备类型
        measure_objects = [m.regulation_object for m in proposal.measures]
        assert any("空压机" in obj for obj in measure_objects)
        assert any("水泵" in obj for obj in measure_objects)
        assert any("照明" in obj for obj in measure_objects)

    def test_generate_a4_vpp_response_proposal(
        self,
        generator: TemplateGenerator,
        db_session: Session,
        setup_basic_data
    ):
        """测试A4-VPP需求响应方案生成"""
        proposal = generator.generate_proposal("A4", analysis_days=30)

        # 验证方案基本信息
        assert proposal.proposal_type == "A"
        assert proposal.template_id == "A4"
        assert proposal.template_name == "VPP需求响应方案"

        # 验证措施数量
        assert len(proposal.measures) == 3

        # 验证措施分级
        measure_objects = [m.regulation_object for m in proposal.measures]
        assert any("Ⅰ级" in obj for obj in measure_objects)
        assert any("Ⅱ级" in obj for obj in measure_objects)
        assert any("Ⅲ级" in obj for obj in measure_objects)

        # 验证当前状况包含VPP数据
        assert "总容量" in proposal.current_situation

    def test_generate_a5_load_scheduling_proposal(
        self,
        generator: TemplateGenerator,
        db_session: Session,
        setup_basic_data
    ):
        """测试A5-负荷调度优化方案生成"""
        proposal = generator.generate_proposal("A5", analysis_days=30)

        # 验证方案基本信息
        assert proposal.proposal_type == "A"
        assert proposal.template_id == "A5"
        assert proposal.template_name == "负荷调度优化方案"

        # 验证措施数量
        assert len(proposal.measures) == 3

        # 验证措施类型
        measure_objects = [m.regulation_object for m in proposal.measures]
        assert any("生产" in obj for obj in measure_objects)
        assert any("启停" in obj for obj in measure_objects)
        assert any("负荷曲线" in obj for obj in measure_objects)

    def test_generate_b1_equipment_upgrade_proposal(
        self,
        generator: TemplateGenerator,
        db_session: Session,
        setup_basic_data
    ):
        """测试B1-设备改造升级方案生成"""
        proposal = generator.generate_proposal("B1", analysis_days=30)

        # 验证方案基本信息
        assert proposal.proposal_type == "B"
        assert proposal.template_id == "B1"
        assert proposal.template_name == "设备改造升级方案"

        # 验证措施数量
        assert len(proposal.measures) == 3

        # 验证B类型方案需要投资
        assert proposal.total_investment > 0

        # 验证每个措施都有投资
        for measure in proposal.measures:
            assert measure.investment > 0

        # 验证措施类型
        measure_objects = [m.regulation_object for m in proposal.measures]
        assert any("空压机" in obj for obj in measure_objects)
        assert any("水泵" in obj for obj in measure_objects)
        assert any("照明" in obj for obj in measure_objects)

        # 验证投资回收期信息在公式中
        for measure in proposal.measures:
            assert "投资回收期" in measure.calculation_formula

    def test_proposal_code_generation(
        self,
        generator: TemplateGenerator,
        db_session: Session,
        setup_basic_data
    ):
        """测试方案编号生成"""
        # 生成第一个方案
        proposal1 = generator.generate_proposal("A1", 30)
        code1 = proposal1.proposal_code

        # 保存到数据库
        db_session.add(proposal1)
        db_session.commit()

        # 生成第二个方案
        proposal2 = generator.generate_proposal("A1", 30)
        code2 = proposal2.proposal_code

        # 验证编号格式
        assert code1.startswith("A1-")
        assert code2.startswith("A1-")

        # 验证编号不同（序号递增）
        assert code1 != code2

        # 验证序号部分递增
        seq1 = int(code1.split("-")[-1])
        seq2 = int(code2.split("-")[-1])
        assert seq2 == seq1 + 1

    def test_measure_structure(
        self,
        generator: TemplateGenerator,
        db_session: Session,
        setup_basic_data
    ):
        """测试措施结构完整性"""
        proposal = generator.generate_proposal("A1", 30)

        for measure in proposal.measures:
            # 验证必填字段
            assert measure.measure_code is not None
            assert measure.regulation_object is not None
            assert measure.regulation_description is not None

            # 验证状态数据是字典
            assert isinstance(measure.current_state, dict)
            assert isinstance(measure.target_state, dict)

            # 验证公式和依据
            assert measure.calculation_formula is not None
            assert measure.calculation_basis is not None

            # 验证收益和投资
            assert measure.annual_benefit is not None
            assert measure.investment is not None

            # 验证收益大于等于0
            assert measure.annual_benefit >= 0

    def test_proposal_current_situation(
        self,
        generator: TemplateGenerator,
        db_session: Session,
        setup_basic_data
    ):
        """测试方案当前状况数据"""
        # A1方案应包含峰谷数据
        a1_proposal = generator.generate_proposal("A1", 30)
        assert "尖峰电量" in a1_proposal.current_situation
        assert "总电量" in a1_proposal.current_situation

        # A2方案应包含需量数据
        a2_proposal = generator.generate_proposal("A2", 30)
        assert "当前申报需量" in a2_proposal.current_situation

        # A4方案应包含VPP容量数据
        a4_proposal = generator.generate_proposal("A4", 30)
        assert "总容量" in a4_proposal.current_situation

        # A5方案应包含负荷曲线数据
        a5_proposal = generator.generate_proposal("A5", 30)
        assert "负荷率" in a5_proposal.current_situation

    def test_analysis_dates(
        self,
        generator: TemplateGenerator,
        db_session: Session,
        setup_basic_data
    ):
        """测试分析日期设置"""
        analysis_days = 60
        proposal = generator.generate_proposal("A1", analysis_days)

        # 验证分析日期
        assert proposal.analysis_start_date is not None
        assert proposal.analysis_end_date is not None

        # 验证日期间隔
        date_diff = (proposal.analysis_end_date - proposal.analysis_start_date).days
        assert date_diff >= analysis_days - 1  # 允许1天误差

    def test_all_templates_generate_successfully(
        self,
        generator: TemplateGenerator,
        db_session: Session,
        setup_basic_data
    ):
        """测试所有6种模板都能成功生成"""
        template_ids = ["A1", "A2", "A3", "A4", "A5", "B1"]

        for template_id in template_ids:
            proposal = generator.generate_proposal(template_id, 30)

            # 验证基本信息
            assert proposal.template_id == template_id
            assert proposal.proposal_code is not None
            assert proposal.template_name is not None

            # 验证措施
            assert len(proposal.measures) > 0

            # 验证收益
            assert proposal.total_benefit >= 0

            # 验证A类型无投资，B类型有投资
            if template_id.startswith("A"):
                assert proposal.total_investment == Decimal("0")
            else:
                assert proposal.total_investment > 0


class TestMeasureGeneration:
    """测试各措施生成方法"""

    @pytest.fixture
    def generator(self, db_session: Session):
        """创建模板生成器实例"""
        return TemplateGenerator(db_session)

    @pytest.fixture
    def mock_proposal(self, db_session: Session):
        """创建模拟方案对象"""
        proposal = EnergySavingProposal(
            proposal_code="TEST-20260125-001",
            proposal_type="A",
            template_id="A1",
            template_name="测试方案",
            analysis_start_date=datetime.now().date(),
            analysis_end_date=datetime.now().date()
        )
        return proposal

    def test_heat_treatment_shift_measure(
        self,
        generator: TemplateGenerator,
        mock_proposal: EnergySavingProposal
    ):
        """测试热处理工序转移措施"""
        measure = generator._generate_measure_heat_treatment_shift(mock_proposal, 30)

        assert "热处理" in measure.regulation_object
        assert "尖峰" in measure.regulation_description
        assert measure.annual_benefit > 0
        assert "计算步骤" in measure.calculation_formula

    def test_demand_reduction_measure(
        self,
        generator: TemplateGenerator,
        mock_proposal: EnergySavingProposal,
        db_session: Session
    ):
        """测试需量降低措施"""
        # 创建需量数据
        meter_point = MeterPoint(
            meter_code="M001",
            meter_name="测试表",
            declared_demand=5000,
            is_enabled=True
        )
        db_session.add(meter_point)
        db_session.flush()

        demand_history = DemandHistory(
            meter_point_id=meter_point.id,
            stat_year=datetime.now().year,
            stat_month=datetime.now().month,
            demand_95th=4000
        )
        db_session.add(demand_history)
        db_session.commit()

        demand_data = generator.calculator.calc_demand_control_data()
        measure = generator._generate_measure_demand_reduction(mock_proposal, demand_data)

        assert "申报需量" in measure.regulation_object
        assert measure.investment == Decimal("0")

    def test_led_retrofit_measure(
        self,
        generator: TemplateGenerator,
        mock_proposal: EnergySavingProposal
    ):
        """测试LED改造措施"""
        mock_proposal.proposal_type = "B"
        measure = generator._generate_measure_led_retrofit(mock_proposal)

        assert "照明" in measure.regulation_object
        assert "LED" in measure.regulation_description
        assert measure.investment > 0
        assert measure.annual_benefit > 0
        assert "投资回收期" in measure.calculation_formula


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
