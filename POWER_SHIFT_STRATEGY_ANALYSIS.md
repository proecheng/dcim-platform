# 功率转移策略系统 - 问题分析与改进方案

## 一、当前问题诊断

### 1.1 数据显示问题

**问题现象：**
- 抽屉显示"暂无历史数据"和"模拟数据"标签
- 用户误以为系统没有真实数据

**根本原因：**
```
数据模拟器 → PointHistory 表 (✅ 1,232,640 条记录)
                ↓
         (❌ 缺少聚合任务)
                ↓
         EnergyHourly 表 (❌ 0 条记录)
                ↓
    典型日曲线 API 查询 EnergyHourly
                ↓
         has_real_data = False
                ↓
      显示"模拟数据"标签
```

**代码位置：**
- `backend/app/services/device_regulation_service.py:497`
  ```python
  has_real_data = len(hourly_map) > 0  # hourly_map 来自 EnergyHourly 表
  ```

### 1.2 数据聚合缺失

**问题：**
- `PointHistory` 表有大量原始数据
- 但没有定时任务将其聚合到 `EnergyHourly` 和 `EnergyDaily` 表
- 导致所有依赖聚合数据的功能都显示"模拟数据"

**影响范围：**
1. 设备典型日功率曲线
2. 转移比例推荐算法
3. 能效分析报表
4. 峰谷用电统计

### 1.3 功率曲线问题

**当前实现：**
- 只有一个 24 小时典型日曲线
- 虽然前端有 30 天/90 天切换按钮，但后端只是改变查询时间范围
- 最终仍然聚合为 24 小时曲线，无法看到趋势变化

**用户期望：**
- 30 天模式：显示 30 天的每日功率曲线（30 个数据点）
- 90 天模式：显示 90 天的每日功率曲线（90 个数据点）
- 能够看到功率随时间的变化趋势

---

## 二、功率转移策略对抗性审查

### 2.1 当前策略分析

**算法核心（`device_regulation_service.py:684-893`）：**

```python
# 四个约束条件取最小值
constraints = [
    min_power_constraint,    # 最低功率约束
    load_variation_space,    # 负荷波动空间
    peak_shift_potential,    # 峰时可转移潜力
    type_max_ratio          # 设备类型上限
]
recommended_ratio = min(constraints)
```

**约束条件详解：**

1. **最低功率约束**
   ```python
   min_power_constraint = (rated_power - min_power) / rated_power
   ```
   - 假设：设备必须维持最低运行功率
   - 问题：未考虑设备可以完全关闭的情况

2. **负荷波动空间**
   ```python
   load_variation_space = (max_power - avg_power) / rated_power
   ```
   - 假设：历史最大功率与平均功率之差代表可调节空间
   - 问题：未考虑负荷波动的时间分布

3. **峰时可转移潜力**
   ```python
   peak_shift_potential = peak_ratio * flexibility_factor
   ```
   - 假设：峰时用电占比越高，转移潜力越大
   - 问题：未考虑谷时是否有容量接纳

4. **设备类型上限**
   ```python
   type_max_ratio = FLEXIBILITY_FACTORS[device_type]  # 固定值
   ```
   - 假设：不同设备类型有固定的安全上限
   - 问题：未考虑设备个体差异

### 2.2 策略不足分析

#### 2.2.1 缺少的关键约束

**❌ 1. 设备启停特性**
- 当前：假设设备可以连续调节功率
- 现实：很多设备只能开/关，不能调功率
- 影响：空调、水泵等设备的转移策略不准确

**❌ 2. 负荷预测不确定性**
- 当前：基于历史数据直接推荐
- 现实：未来负荷可能与历史不同
- 影响：可能导致实际转移时容量不足

**❌ 3. 电价时段影响**
- 当前：只考虑峰谷比例，未考虑电价差异
- 现实：应优先转移高电价时段的负荷
- 影响：经济效益不是最优

**❌ 4. 设备间耦合关系**
- 当前：每个设备独立计算
- 现实：冷机和水泵、空调和新风机组等有耦合
- 影响：可能导致系统不协调

**❌ 5. 用户舒适度约束**
- 当前：未考虑用户体验
- 现实：空调转移会影响室温，照明转移影响工作
- 影响：实际可转移容量被高估

**❌ 6. 设备寿命影响**
- 当前：未考虑频繁启停对设备的损害
- 现实：频繁调节会缩短设备寿命
- 影响：长期运维成本增加

**❌ 7. 需量管理约束**
- 当前：未与需量管理联动
- 现实：转移后可能导致其他时段超需量
- 影响：可能增加需量电费

**❌ 8. 电网约束**
- 当前：未考虑变压器容量限制
- 现实：转移后可能导致某时段过载
- 影响：可能触发保护装置

#### 2.2.2 算法简化问题

**问题 1：线性假设**
```python
recommended_ratio = min(constraints)  # 简单取最小值
```
- 现实：约束之间可能有交互作用
- 改进：应使用优化算法求解多约束问题

**问题 2：静态参数**
```python
FLEXIBILITY_FACTORS = {
    "PUMP": 0.7,
    "AC": 0.5,
    ...
}
```
- 现实：柔性系数应该是动态的，取决于运行状态
- 改进：基于实时数据动态调整

**问题 3：缺少验证**
- 当前：推荐后没有验证是否可行
- 改进：应模拟转移后的负荷曲线，验证是否满足所有约束

---

## 三、改进方案

### 3.1 短期修复（立即实施）

#### 3.1.1 修复数据聚合

**方案 A：直接查询 PointHistory（快速修复）**

修改 `device_regulation_service.py:get_device_typical_profile`：

```python
async def get_device_typical_profile(self, device_id: int, days: int = 30):
    # 查找设备对应的点位
    device_result = await self.db.execute(
        select(PowerDevice).where(PowerDevice.id == device_id)
    )
    device = device_result.scalar_one_or_none()
    if not device:
        return None
    
    # 查找设备关联的功率点位
    point_result = await self.db.execute(
        select(Point)
        .join(DevicePoint, Point.id == DevicePoint.point_id)
        .where(
            DevicePoint.device_id == device_id,
            Point.point_name.like('%功率%')  # 或其他识别功率点位的逻辑
        )
    )
    power_point = point_result.scalar_one_or_none()
    
    if not power_point:
        # 回退到模拟数据
        return self._generate_simulated_profile(device, days)
    
    # 直接从 PointHistory 查询并聚合
    cutoff_date = datetime.now() - timedelta(days=days)
    
    result = await self.db.execute(
        select(
            extract("hour", PointHistory.recorded_at).label("hour"),
            func.avg(PointHistory.value).label("avg_power"),
            func.max(PointHistory.value).label("max_power"),
            func.min(PointHistory.value).label("min_power"),
            func.count(PointHistory.id).label("record_count"),
        )
        .where(
            and_(
                PointHistory.point_id == power_point.id,
                PointHistory.recorded_at >= cutoff_date,
            )
        )
        .group_by(extract("hour", PointHistory.recorded_at))
        .order_by(extract("hour", PointHistory.recorded_at))
    )
    
    rows = result.all()
    has_real_data = len(rows) > 0  # 现在会是 True
    
    # ... 后续处理逻辑
```

**优点：**
- 立即可用，不需要等待数据聚合
- 使用真实的历史数据
- `has_real_data` 会正确显示为 True

**缺点：**
- 查询性能较差（需要扫描大量原始数据）
- 需要建立 PowerDevice 到 Point 的映射关系

**方案 B：添加数据聚合任务（长期方案）**

创建定时任务，每小时聚合一次：

```python
# backend/app/tasks/energy_aggregation.py

async def aggregate_energy_hourly():
    """
    将 PointHistory 数据聚合到 EnergyHourly 表
    每小时运行一次
    """
    async with async_session() as db:
        # 获取所有功率点位
        power_points = await db.execute(
            select(Point, DevicePoint)
            .join(DevicePoint, Point.id == DevicePoint.point_id)
            .where(Point.point_name.like('%功率%'))
        )
        
        # 聚合上一小时的数据
        last_hour = datetime.now().replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
        next_hour = last_hour + timedelta(hours=1)
        
        for point, device_point in power_points.all():
            # 查询该小时的数据
            result = await db.execute(
                select(
                    func.avg(PointHistory.value).label("avg_power"),
                    func.max(PointHistory.value).label("max_power"),
                    func.min(PointHistory.value).label("min_power"),
                    func.count(PointHistory.id).label("record_count"),
                )
                .where(
                    and_(
                        PointHistory.point_id == point.id,
                        PointHistory.recorded_at >= last_hour,
                        PointHistory.recorded_at < next_hour,
                    )
                )
            )
            
            row = result.first()
            if row and row.record_count > 0:
                # 插入或更新 EnergyHourly
                energy_hourly = EnergyHourly(
                    device_id=device_point.device_id,
                    stat_time=last_hour,
                    avg_power=float(row.avg_power),
                    max_power=float(row.max_power),
                    min_power=float(row.min_power),
                )
                
                # 使用 merge 或 upsert
                await db.merge(energy_hourly)
        
        await db.commit()
```

#### 3.1.2 改进功率曲线显示

**添加趋势曲线 API：**

```python
@router.get(
    "/devices/{device_id}/power-trend",
    response_model=ResponseModel,
    summary="获取设备功率趋势曲线"
)
async def get_device_power_trend(
    device_id: int,
    days: int = Query(30, ge=7, le=90),
    granularity: str = Query("daily", regex="^(hourly|daily)$"),
    db: AsyncSession = Depends(get_db),
):
    """
    获取设备功率趋势曲线
    
    - granularity="daily": 返回每日平均功率（适合 30/90 天视图）
    - granularity="hourly": 返回每小时平均功率（适合 7 天视图）
    """
    # 实现逻辑...
```

**前端修改：**

```vue
<el-radio-group v-model="viewMode" size="small" @change="reloadProfile">
  <el-radio-button value="typical">典型日</el-radio-button>
  <el-radio-button value="trend-30">30天趋势</el-radio-button>
  <el-radio-button value="trend-90">90天趋势</el-radio-button>
</el-radio-group>
```

### 3.2 中期改进（1-2 周）

#### 3.2.1 增强约束条件

**添加舒适度约束：**

```python
def _calculate_comfort_constraint(self, device: PowerDevice, hourly_stats: Dict) -> float:
    """
    计算舒适度约束
    
    对于空调、照明等影响用户体验的设备，限制转移比例
    """
    device_type = device.device_type.upper()
    
    if device_type == "AC":
        # 空调：根据室外温度和设定温度差异
        # 温差越大，可转移比例越小
        return 0.3  # 示例值
    elif device_type == "LIGHTING":
        # 照明：工作时间不可转移
        current_hour = datetime.now().hour
        if 8 <= current_hour <= 18:
            return 0  # 工作时间不可转移
        return 0.5
    else:
        return 1.0  # 不受舒适度约束
```

**添加需量管理约束：**

```python
async def _calculate_demand_constraint(self, device: PowerDevice, shift_ratio: float) -> float:
    """
    计算需量管理约束
    
    确保转移后不会导致其他时段超需量
    """
    # 查询设备所属计量点的申报需量
    meter_point = await self._get_device_meter_point(device.id)
    if not meter_point or not meter_point.declared_demand:
        return 1.0
    
    # 模拟转移后的需量曲线
    # 检查是否会超过申报需量
    # ...
    
    return constraint_ratio
```

#### 3.2.2 改进推荐算法

**使用优化算法：**

```python
from scipy.optimize import minimize

def _optimize_shift_ratio(self, device: PowerDevice, constraints: Dict) -> float:
    """
    使用优化算法求解最优转移比例
    
    目标函数：最大化经济效益
    约束条件：所有技术约束
    """
    def objective(ratio):
        # 目标：最大化电费节省
        return -self._calculate_cost_saving(device, ratio[0])
    
    def constraint_func(ratio):
        # 所有约束条件
        return [
            ratio[0] - constraints['min_power_constraint'],  # >= 0
            constraints['load_variation'] - ratio[0],         # >= 0
            constraints['comfort'] - ratio[0],                # >= 0
            # ... 其他约束
        ]
    
    result = minimize(
        objective,
        x0=[0.5],  # 初始值
        bounds=[(0, 1)],
        constraints={'type': 'ineq', 'fun': constraint_func}
    )
    
    return result.x[0]
```

### 3.3 长期改进（1-2 月）

#### 3.3.1 机器学习预测

**负荷预测模型：**

```python
class LoadForecastModel:
    """
    基于历史数据预测未来负荷
    
    特征：
    - 时间特征（小时、星期、月份）
    - 天气特征（温度、湿度）
    - 历史负荷
    - 节假日标识
    """
    
    def predict_next_day(self, device_id: int) -> np.ndarray:
        """预测未来 24 小时负荷"""
        # 使用 LSTM 或 XGBoost
        pass
```

**不确定性量化：**

```python
def _calculate_uncertainty_margin(self, forecast: np.ndarray) -> float:
    """
    计算预测不确定性，调整转移比例
    
    预测越不确定，转移比例越保守
    """
    std = np.std(forecast)
    mean = np.mean(forecast)
    cv = std / mean  # 变异系数
    
    # 变异系数越大，裕度越大
    margin = 1 - min(cv * 2, 0.3)
    return margin
```

#### 3.3.2 多设备协同优化

**全局优化框架：**

```python
class GlobalShiftOptimizer:
    """
    全局负荷转移优化
    
    考虑：
    - 所有设备的耦合关系
    - 变压器容量约束
    - 总需量约束
    - 电价时段
    """
    
    async def optimize(self, devices: List[PowerDevice]) -> Dict[int, float]:
        """
        返回每个设备的最优转移比例
        
        使用混合整数规划（MIP）求解
        """
        # 构建优化模型
        # ...
        
        return optimal_ratios
```

---

## 四、实施优先级

### P0 - 立即修复（本周）

1. ✅ **修复数据显示问题**
   - 实施方案 A：直接查询 PointHistory
   - 移除"模拟数据"标签的误导性显示
   - 预计工作量：4 小时

2. ✅ **添加功率趋势曲线**
   - 实现 30 天/90 天趋势视图
   - 预计工作量：8 小时

### P1 - 短期改进（2 周内）

3. ⚠️ **实施数据聚合任务**
   - 创建定时任务聚合 PointHistory 到 EnergyHourly
   - 预计工作量：16 小时

4. ⚠️ **增强约束条件**
   - 添加舒适度约束
   - 添加需量管理约束
   - 预计工作量：24 小时

### P2 - 中期改进（1 月内）

5. 📋 **改进推荐算法**
   - 使用优化算法替代简单取最小值
   - 预计工作量：40 小时

6. 📋 **添加验证机制**
   - 模拟转移后的负荷曲线
   - 验证是否满足所有约束
   - 预计工作量：24 小时

### P3 - 长期规划（2-3 月）

7. 💡 **机器学习预测**
   - 实现负荷预测模型
   - 不确定性量化
   - 预计工作量：80 小时

8. 💡 **全局协同优化**
   - 多设备协同优化框架
   - 预计工作量：120 小时

---

## 五、风险评估

### 技术风险

1. **性能风险**
   - 直接查询 PointHistory 可能较慢
   - 缓解：添加索引，限制查询范围

2. **数据一致性风险**
   - PowerDevice 到 Point 的映射可能不准确
   - 缓解：添加数据验证和人工审核

3. **算法复杂度风险**
   - 优化算法可能求解失败
   - 缓解：保留简单算法作为回退方案

### 业务风险

1. **用户接受度风险**
   - 新策略可能与用户经验不符
   - 缓解：提供手动调整和覆盖功能

2. **经济效益风险**
   - 优化后的策略可能实际效果不佳
   - 缓解：小范围试点，逐步推广

---

## 六、总结

当前功率转移策略系统存在两大核心问题：

1. **数据问题**：缺少数据聚合导致显示"模拟数据"
2. **策略问题**：约束条件不全面，算法过于简化

建议优先实施 P0 级修复，快速解决用户体验问题，然后逐步完善策略算法。

长期目标是建立一个基于机器学习预测和全局优化的智能负荷转移系统。
