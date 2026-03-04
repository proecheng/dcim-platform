# 负荷转移系统 Phase 2 开发指南

**文档版本**: v1.0  
**创建日期**: 2026-03-03  
**当前状态**: Phase 1 已完成，Phase 2 待开发

---

## 📋 Phase 2 待完成任务清单

### 高优先级（6个任务）

#### 1. 执行监控增强
- ✅ **执行记录列表页面** (已完成)
  - 文件: `frontend/src/views/energy/shift/ShiftExecutionList.vue`
  - 功能: 状态筛选、日期范围查询、成功率展示
  
- ⏳ **执行详情页面** (待开发)
  - 文件: `frontend/src/views/energy/shift/ShiftExecutionDetail.vue`
  - 功能: 执行过程详情、设备执行状态、制冷联动数据
  
- ⏳ **实时监控页面** (待开发)
  - 文件: `frontend/src/views/energy/shift/ShiftExecutionMonitor.vue`
  - 功能: 实时执行状态、WebSocket推送、进度可视化

#### 2. 制冷联动机制
- ⏳ **配置页面** (待开发)
  - 文件: `frontend/src/views/energy/shift/CoolingLinkageConfig.vue`
  - 功能: 制冷滞后时间配置、目标COP设置、温度阈值配置
  
- ⏳ **状态监控** (待开发)
  - 文件: `frontend/src/views/energy/shift/CoolingLinkageMonitor.vue`
  - 功能: 实时制冷功率、COP监控、供回水温度展示

### 中优先级（4个任务）

#### 3. 约束管理
- ⏳ **约束配置页面** (待开发)
  - 文件: `frontend/src/views/energy/shift/ShiftConstraintConfig.vue`
  - 功能: 约束列表、CRUD操作、启用/禁用
  
- ⏳ **约束编辑器组件** (待开发)
  - 文件: `frontend/src/views/energy/shift/components/ConstraintEditor.vue`
  - 功能: 约束类型选择、参数配置、优先级设置

#### 4. 收益报表
- ⏳ **月度/年度报表页面** (待开发)
  - 文件: `frontend/src/views/energy/shift/ShiftReports.vue`
  - 功能: 月度统计、年度汇总、趋势图表
  
- ⏳ **Excel/PDF导出功能** (待开发)
  - 后端: `backend/app/services/load_shift/shift_report_service.py`
  - 功能: 报表生成、Excel导出、PDF导出

---

## 🔧 开发准备

### 后端API端点（已存在但未实现）

```python
# 执行记录API
GET  /api/v1/energy/shift/executions              # 执行记录列表
GET  /api/v1/energy/shift/executions/{exec_id}    # 执行详情
GET  /api/v1/energy/shift/executions/statistics   # 执行统计

# 制冷联动API
GET  /api/v1/energy/shift/cooling/config          # 获取配置
PUT  /api/v1/energy/shift/cooling/config          # 更新配置
GET  /api/v1/energy/shift/cooling/status          # 制冷状态
GET  /api/v1/energy/shift/cooling/records         # 联动记录

# 约束管理API
GET    /api/v1/energy/shift/constraints           # 约束列表
POST   /api/v1/energy/shift/constraints           # 创建约束
PUT    /api/v1/energy/shift/constraints/{id}      # 更新约束
DELETE /api/v1/energy/shift/constraints/{id}      # 删除约束

# 报表API
GET /api/v1/energy/shift/reports/savings          # 收益报表
GET /api/v1/energy/shift/reports/monthly          # 月度报表
GET /api/v1/energy/shift/reports/yearly           # 年度报表
GET /api/v1/energy/shift/reports/export/excel     # Excel导出
GET /api/v1/energy/shift/reports/export/pdf       # PDF导出
```

### 前端API客户端（需添加）

在 `frontend/src/api/modules/shift.ts` 中添加：

```typescript
// 执行记录接口
export function getExecutions(params?: any) {
  return request.get('/v1/energy/shift/executions', { params })
}

export function getExecutionDetail(id: number) {
  return request.get(`/v1/energy/shift/executions/${id}`)
}

// 制冷联动接口
export function getCoolingConfig() {
  return request.get('/v1/energy/shift/cooling/config')
}

export function updateCoolingConfig(data: any) {
  return request.put('/v1/energy/shift/cooling/config', data)
}

// 约束管理接口
export function getConstraints(params?: any) {
  return request.get('/v1/energy/shift/constraints', { params })
}

export function createConstraint(data: any) {
  return request.post('/v1/energy/shift/constraints', data)
}

// 报表接口
export function getMonthlyReport(year: number, month: number) {
  return request.get('/v1/energy/shift/reports/monthly', { params: { year, month } })
}

export function exportExcel(params: any) {
  return request.get('/v1/energy/shift/reports/export/excel', { 
    params, 
    responseType: 'blob' 
  })
}
```

---

## 📝 开发步骤建议

### Step 1: 执行监控增强（优先）

**1.1 执行详情页面**
```bash
# 创建文件
frontend/src/views/energy/shift/ShiftExecutionDetail.vue

# 功能要点
- 基本信息展示（执行编号、计划名称、时间）
- 执行过程时间线
- 设备执行状态表格
- 制冷联动数据图表
- 实际收益对比
```

**1.2 实时监控页面**
```bash
# 创建文件
frontend/src/views/energy/shift/ShiftExecutionMonitor.vue

# 功能要点
- WebSocket连接实时数据
- 执行进度条
- 设备状态实时更新
- 功率曲线实时图表
- 异常告警提示
```

**1.3 添加路由**
```typescript
// frontend/src/router/index.ts
{
  path: 'executions',
  name: 'ShiftExecutionList',
  component: () => import('@/views/energy/shift/ShiftExecutionList.vue'),
  meta: { title: '执行记录', icon: 'List' }
},
{
  path: 'execution/:id',
  name: 'ShiftExecutionDetail',
  component: () => import('@/views/energy/shift/ShiftExecutionDetail.vue'),
  meta: { title: '执行详情', icon: 'View', hidden: true }
},
{
  path: 'monitor',
  name: 'ShiftExecutionMonitor',
  component: () => import('@/views/energy/shift/ShiftExecutionMonitor.vue'),
  meta: { title: '实时监控', icon: 'Monitor' }
}
```

### Step 2: 制冷联动机制

**2.1 后端服务实现**
```python
# backend/app/services/load_shift/cooling_linkage_service.py

class CoolingLinkageService:
    @staticmethod
    async def get_config(db: AsyncSession):
        # 获取制冷联动配置
        pass
    
    @staticmethod
    async def update_config(db: AsyncSession, config_data: dict):
        # 更新配置
        pass
    
    @staticmethod
    async def get_cooling_status(db: AsyncSession):
        # 获取实时制冷状态
        pass
```

**2.2 前端配置页面**
```vue
<!-- CoolingLinkageConfig.vue -->
<template>
  <el-form :model="configForm">
    <el-form-item label="制冷滞后时间">
      <el-input-number v-model="configForm.cooling_lag_minutes" :min="15" :max="30" />
      <span class="tip">分钟</span>
    </el-form-item>
    <el-form-item label="目标COP">
      <el-input-number v-model="configForm.target_cop" :min="2.5" :max="4.0" :step="0.1" />
    </el-form-item>
    <!-- 更多配置项 -->
  </el-form>
</template>
```

### Step 3: 约束管理

**3.1 约束配置页面**
- 约束列表表格
- 新建/编辑对话框
- 启用/禁用开关
- 优先级排序

**3.2 约束编辑器组件**
- 约束类型选择（功率/时间/设备/制冷/安全/电气）
- 动态参数表单
- 验证规则配置

### Step 4: 收益报表

**4.1 报表页面**
```vue
<!-- ShiftReports.vue -->
<template>
  <el-tabs v-model="activeTab">
    <el-tab-pane label="月度报表" name="monthly">
      <!-- 月度统计图表 -->
    </el-tab-pane>
    <el-tab-pane label="年度报表" name="yearly">
      <!-- 年度汇总图表 -->
    </el-tab-pane>
  </el-tabs>
  
  <el-button @click="exportExcel">导出Excel</el-button>
  <el-button @click="exportPDF">导出PDF</el-button>
</template>
```

**4.2 导出功能**
```python
# backend/app/services/load_shift/shift_report_service.py

class ShiftReportService:
    @staticmethod
    async def export_excel(db: AsyncSession, params: dict) -> BytesIO:
        # 使用 openpyxl 生成Excel
        pass
    
    @staticmethod
    async def export_pdf(db: AsyncSession, params: dict) -> BytesIO:
        # 使用 reportlab 生成PDF
        pass
```

---

## 🧪 测试建议

### 单元测试
```bash
# 后端测试
cd backend
pytest tests/services/test_cooling_linkage_service.py
pytest tests/services/test_shift_report_service.py

# 前端测试
cd frontend
npm run test:unit
```

### 集成测试
```bash
# API测试
curl -X GET "http://localhost:8888/api/v1/energy/shift/executions"
curl -X GET "http://localhost:8888/api/v1/energy/shift/cooling/config"
```

---

## 📚 参考文档

- **技术文档**: `docs/负荷转移系统技术文档.md`
- **API设计**: `docs/load_shift_api_design.md`
- **验证报告**: `docs/负荷转移系统端到端验证报告.md`

---

## 🚀 快速开始

### 继续开发
```bash
# 1. 确保服务运行
# 后端: http://localhost:8888
# 前端: http://localhost:3000

# 2. 创建新分支
git checkout -b feature/phase2-execution-monitor

# 3. 开始开发执行详情页面
# 参考已完成的 ShiftExecutionList.vue

# 4. 测试验证
npm run build
pytest tests/
```

---

## ✅ 完成标准

每个功能完成需满足：
1. ✅ 前端页面正常渲染
2. ✅ API接口正常响应
3. ✅ 数据正确展示
4. ✅ 交互功能正常
5. ✅ 无TypeScript类型错误
6. ✅ 无控制台错误

---

**Phase 2 开发预计工作量**: 3-5天  
**建议开发顺序**: 执行监控 → 制冷联动 → 约束管理 → 收益报表

*文档维护者: AI Assistant*  
*最后更新: 2026-03-03*
