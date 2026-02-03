# Task Plan: shiftable_power_ratio 智能推荐功能

## Goal
基于设备历史运行数据，智能计算推荐的 shiftable_power_ratio，并在配电配置页面新增"转移配置"选项卡，让用户查看、调整、批量接受推荐值。

## Current Phase
✅ **已完成所有工作（开发 + 测试验证）**

## Phases

### Phase 1: 后端 - Schema + 服务 + API ✅
- [x] 在 schemas/energy.py 添加 RatioRecommendation, BatchUpdateRatioRequest 等类型
- [x] 在 device_regulation_service.py 添加推荐值计算方法
- [x] 在 api/v1/energy.py 添加4个API端点
- **Status:** completed
- **文件:**
  - `backend/app/schemas/energy.py` - 新增4个Schema类
  - `backend/app/services/device_regulation_service.py` - 新增5个方法
  - `backend/app/api/v1/energy.py` - 新增4个API端点

### Phase 2: 前端 - API 和类型定义 ✅
- [x] 在 api/modules/energy.ts 添加 TypeScript 类型
- [x] 在 api/modules/energy.ts 添加 API 调用函数
- **Status:** completed
- **文件:** `frontend/src/api/modules/energy.ts`

### Phase 3: 前端 - 配电配置页面新增选项卡 ✅
- [x] 在 config.vue 添加"转移配置"选项卡
- [x] 添加设备列表表格（当前值/推荐值/操作）
- [x] 添加调整对话框（滑块+推荐值按钮）
- [x] 添加"全部接受推荐值"按钮
- [x] 添加统计汇总卡片
- **Status:** completed
- **文件:** `frontend/src/views/energy/config.vue`

### Phase 4: 测试与验证 ✅
- [x] 启动后端服务验证 API
- [x] 启动前端验证 UI
- [x] 查看设备推荐列表（28台设备）
- [x] 调整对话框（滑块 + 使用推荐值 + 保存）
- [x] 单个设备接受推荐值
- [x] 全部接受推荐值（批量27台）
- [x] 底部统计汇总实时更新
- **Status:** completed

## 新增代码清单

### 后端新增

**schemas/energy.py** (4个新类型):
- `RatioRecommendation` - 单个设备推荐值
- `RatioRecommendationResponse` - 推荐值列表响应
- `BatchUpdateRatioRequest` - 批量更新请求
- `UpdateSingleRatioRequest` - 单个更新请求

**device_regulation_service.py** (5个新方法):
- `get_ratio_recommendations()` - 获取所有推荐值
- `_get_hourly_stats()` - 获取小时级功率统计
- `_get_daily_stats()` - 获取日级峰谷统计
- `_calculate_recommendation()` - 计算单个设备推荐
- `update_device_ratio()` - 更新单个设备
- `batch_update_ratios()` - 批量更新
- `accept_all_recommendations()` - 全部接受推荐

**api/v1/energy.py** (4个新端点):
- `GET /devices/shift-ratio/recommendations` - 获取推荐值
- `PUT /devices/{device_id}/shift-ratio` - 更新单个
- `POST /devices/shift-ratio/batch-update` - 批量更新
- `POST /devices/shift-ratio/accept-all` - 全部接受

### 前端新增

**api/modules/energy.ts**:
- 4个新类型定义
- 4个新API函数

**views/energy/config.vue**:
- "转移配置"选项卡 (含表格、汇总卡片)
- 调整对话框 (含滑块、使用推荐值按钮)
- 相关数据和方法

## 推荐算法公式
```
recommended_ratio = min(
    1 - min_power/rated_power,           # 最低功率约束
    (max_power - avg_power)/rated_power, # 负荷波动空间
    peak_ratio × flexibility_factor,     # 峰时可转移比例
    type_max_ratio                       # 设备类型上限
) × 0.85 (安全系数)
```

## 验证步骤

1. 启动后端: `cd backend && python run.py`
2. 启动前端: `cd frontend && npm run dev`
3. 访问: 配电配置 → 转移配置 选项卡
4. 验证功能:
   - 查看设备推荐列表
   - 点击"调整"修改单个设备
   - 点击"接受"应用单个推荐
   - 点击"全部接受推荐值"批量应用
