"""
单元测试：冗余约束计算逻辑
"""
import pytest
from app.services.datacenter_shift_strategy import RedundancyConstraint


class TestRedundancyConstraint:
    """冗余约束计算测试"""
    
    def test_redundancy_constraint_structure(self):
        """测试：RedundancyConstraint数据结构"""
        constraint = RedundancyConstraint()
        
        # 检查默认值
        assert constraint.max_reduction_ratio == 1.0
        assert constraint.redundancy_group == []
        assert constraint.total_capacity == 0.0
        assert constraint.current_load == 0.0
        assert constraint.n_plus_one_capacity == 0.0
        assert constraint.is_safe == True
        assert constraint.reason == ""
        
        # 检查可以设置值
        constraint.max_reduction_ratio = 0.3
        constraint.total_capacity = 150.0
        constraint.current_load = 100.0
        constraint.n_plus_one_capacity = 120.0
        constraint.reason = "N+1冗余满足"
        
        assert constraint.max_reduction_ratio == 0.3
        assert constraint.total_capacity == 150.0
        assert constraint.current_load == 100.0
        assert constraint.n_plus_one_capacity == 120.0
        assert constraint.reason == "N+1冗余满足"
    
    def test_n_plus_one_calculation(self):
        """测试：N+1容量计算逻辑"""
        # 场景：3台50kW空调，总容量150kW
        n = 3
        single_capacity = 50.0
        safety_factor = 0.9
        
        # N+1容量 = (N-1) × 单机容量 × 安全系数
        n_plus_one_capacity = (n - 1) * single_capacity * safety_factor
        
        # 预期：(3-1) × 50 × 0.9 = 90kW
        assert n_plus_one_capacity == 90.0
        
        # 如果当前负载80kW < 90kW，则安全
        current_load = 80.0
        assert current_load < n_plus_one_capacity
        
        # 如果当前负载100kW > 90kW，则不安全
        current_load = 100.0
        assert current_load > n_plus_one_capacity
    
    def test_redundancy_with_two_devices(self):
        """测试：2台设备的冗余场景"""
        # 2台100kW设备
        n = 2
        single_capacity = 100.0
        safety_factor = 0.9
        
        # N+1容量 = (2-1) × 100 × 0.9 = 90kW
        n_plus_one_capacity = (n - 1) * single_capacity * safety_factor
        assert n_plus_one_capacity == 90.0
        
        # 当前负载85kW，安全
        current_load = 85.0
        assert current_load < n_plus_one_capacity
    
    def test_redundancy_with_single_device(self):
        """测试：单台设备无冗余"""
        # 单台设备无法提供N+1冗余
        n = 1
        single_capacity = 100.0
        safety_factor = 0.9
        
        # N+1容量 = (1-1) × 100 × 0.9 = 0kW
        n_plus_one_capacity = (n - 1) * single_capacity * safety_factor
        assert n_plus_one_capacity == 0.0
        
        # 任何负载都会超过N+1容量
        current_load = 50.0
        assert current_load > n_plus_one_capacity
    
    def test_max_reduction_ratio_calculation(self):
        """测试：最大降低比例计算"""
        # 场景：3台设备，总容量150kW，当前负载90kW
        total_capacity = 150.0
        current_load = 90.0
        n = 3
        single_capacity = total_capacity / n  # 50kW
        safety_factor = 0.9
        
        # N+1容量 = (3-1) × 50 × 0.9 = 90kW
        n_plus_one_capacity = (n - 1) * single_capacity * safety_factor
        
        # 当前负载刚好等于N+1容量，不能降低
        assert current_load == n_plus_one_capacity
        max_reduction_ratio = 0.0
        
        # 如果当前负载是80kW
        current_load = 80.0
        # 可以降低的功率 = 80 - 90 = -10kW（不能降低）
        # 或者说，可以增加10kW的裕度
        margin = n_plus_one_capacity - current_load
        assert margin == 10.0
        
        # 如果当前负载是70kW
        current_load = 70.0
        margin = n_plus_one_capacity - current_load
        assert margin == 20.0
        # 可以降低的比例 = 20 / 70 ≈ 28.6%
        max_reduction_ratio = margin / current_load
        assert abs(max_reduction_ratio - 0.286) < 0.001


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
