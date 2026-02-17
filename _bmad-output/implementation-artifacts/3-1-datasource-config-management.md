# Story 3.1: 数据源配置管理

Status: done

## Story

As a 集成工程师,
I want 在前端页面配置和管理数据源,
So that 我可以通过界面完成设备协议对接而不需要编辑配置文件。

## Acceptance Criteria (验收标准)

1. **AC-1: 数据源列表页面** — 在前端新增数据源管理页面（`/datasources`），展示数据源列表，包含名称、协议类型、网关、连接状态、最后通信时间、操作列
2. **AC-2: 数据源 CRUD** — 支持创建、编辑、删除数据源，创建/编辑使用对话框表单
3. **AC-3: 协议动态表单** — 根据协议类型动态显示配置表单：Modbus TCP（IP/端口/从站地址）、Modbus RTU（串口/波特率/数据位/校验位/停止位）、SNMP（目标地址/端口/团体名/版本）
4. **AC-4: 连接状态显示** — 每个数据源显示连接状态标签（connected=绿色、disconnected=灰色、communication_error=红色）和最后通信时间
5. **AC-5: 测试连接** — 创建/编辑表单中提供"测试连接"按钮，调用后端 `/test-connection` API 并显示结果
6. **AC-6: 筛选与分页** — 支持按协议类型、状态筛选，支持分页
7. **AC-7: 前端 API 模块** — 创建 `frontend/src/api/datasource.ts`，封装数据源相关 API 调用
8. **AC-8: 路由注册** — 在路由配置中注册数据源管理页面，放在"点位管理"之后

## Tasks / Subtasks (任务分解)

- [ ] Task 1: 前端 API 模块 (AC: #7)
  - [ ] 1.1 创建 `frontend/src/api/datasource.ts`
  - [ ] 1.2 定义 DataSource 接口类型
  - [ ] 1.3 实现 getDatasources(params), createDatasource(data), updateDatasource(id, data), deleteDatasource(id), testConnection(data), testExistingConnection(id)

- [ ] Task 2: 路由注册 (AC: #8)
  - [ ] 2.1 在 `frontend/src/router/index.ts` 中新增 `/datasources` 路由，放在 `devices` 之后

- [ ] Task 3: 数据源列表页面 (AC: #1, #4, #6)
  - [ ] 3.1 创建 `frontend/src/views/datasource/index.vue`
  - [ ] 3.2 实现数据源列表表格（名称、协议类型、网关、状态标签、最后通信时间、操作列）
  - [ ] 3.3 实现筛选栏（协议类型下拉、状态下拉、关键词搜索）
  - [ ] 3.4 实现分页组件
  - [ ] 3.5 状态标签颜色：connected=success, disconnected=info, communication_error=danger

- [ ] Task 4: 创建/编辑对话框 (AC: #2, #3, #5)
  - [ ] 4.1 实现创建/编辑对话框，包含基础字段（名称、协议类型、网关、采集周期、启用状态）
  - [ ] 4.2 实现协议动态表单：选择协议类型后动态渲染对应配置字段
  - [ ] 4.3 Modbus TCP 配置：host(IP), port(端口), slave_id(从站地址)
  - [ ] 4.4 Modbus RTU 配置：serial_port(串口), baudrate(波特率), data_bits(数据位), parity(校验位), stop_bits(停止位)
  - [ ] 4.5 SNMP 配置：host(目标地址), port(端口), community(团体名), version(版本)
  - [ ] 4.6 实现"测试连接"按钮，调用 API 并显示结果（成功/失败 + 延迟）

- [ ] Task 5: 删除确认 (AC: #2)
  - [ ] 5.1 删除操作使用 el-popconfirm 确认

- [ ] Task 6: 后端增强（可选）
  - [ ] 6.1 在 list_datasources API 中增加 keyword 搜索支持（按名称模糊匹配）

## Dev Notes (开发指南)

### 1. 文件位置

```
frontend/src/api/datasource.ts              # 新建 — 数据源 API
frontend/src/views/datasource/index.vue     # 新建 — 数据源管理页面
frontend/src/router/index.ts               # 修改 — 新增路由
backend/app/api/v1/datasources.py          # 修改 — 增加 keyword 搜索（可选）
```

### 2. 前端 API 模块

```typescript
// frontend/src/api/datasource.ts
import request from '@/utils/request'

export interface DataSource {
  id: number
  name: string
  protocol_type: string
  gateway_id: number | null
  connection_config: Record<string, any>
  collection_interval: number
  write_enabled: boolean
  status: string
  last_communication: string | null
  consecutive_failures: number
  retry_base_delay: number
  retry_max_delay: number
  retry_max_failures: number
  site_id: number
  is_enabled: boolean
  created_at: string
  updated_at: string
}

export interface ConnectionTestResult {
  success: boolean
  message: string
  latency_ms: number | null
  sample_data: Record<string, any> | null
}

export function getDatasources(params?: any) {
  return request.get('/v1/datasources', { params })
}

export function getDatasource(id: number) {
  return request.get(`/v1/datasources/${id}`)
}

export function createDatasource(data: Partial<DataSource>) {
  return request.post('/v1/datasources', data)
}

export function updateDatasource(id: number, data: Partial<DataSource>) {
  return request.put(`/v1/datasources/${id}`, data)
}

export function deleteDatasource(id: number) {
  return request.delete(`/v1/datasources/${id}`)
}

export function testConnection(data: { protocol_type: string; connection_config: Record<string, any> }) {
  return request.post<ConnectionTestResult>('/v1/datasources/test-connection', data)
}

export function testExistingConnection(id: number) {
  return request.post<ConnectionTestResult>(`/v1/datasources/${id}/test-connection`)
}
```

### 3. 路由注册

在 `frontend/src/router/index.ts` 的 children 中，`devices` 路由之后新增：

```typescript
{
  path: 'datasources',
  name: 'Datasources',
  component: () => import('@/views/datasource/index.vue'),
  meta: { title: '数据源管理', icon: 'Connection' }
},
```

### 4. 数据源管理页面

页面结构严格参照 `views/device/index.vue` 的模式：
- el-card 包裹，header 含标题 + 新增按钮
- 筛选栏：协议类型下拉、状态下拉、关键词搜索
- 分页信息栏 + el-pagination
- el-table 数据表格
- el-dialog 创建/编辑对话框

#### 4.1 协议动态表单

根据 `form.protocol_type` 的值，使用 `v-if` 动态渲染不同的配置字段区域：

```vue
<!-- Modbus TCP -->
<template v-if="form.protocol_type === 'modbus_tcp'">
  <el-form-item label="IP 地址" prop="connection_config.host">
    <el-input v-model="form.connection_config.host" placeholder="192.168.1.100" />
  </el-form-item>
  <el-form-item label="端口" prop="connection_config.port">
    <el-input-number v-model="form.connection_config.port" :min="1" :max="65535" />
  </el-form-item>
  <el-form-item label="从站地址" prop="connection_config.slave_id">
    <el-input-number v-model="form.connection_config.slave_id" :min="1" :max="247" />
  </el-form-item>
</template>

<!-- Modbus RTU -->
<template v-if="form.protocol_type === 'modbus_rtu'">
  <el-form-item label="串口">
    <el-input v-model="form.connection_config.serial_port" placeholder="COM1 或 /dev/ttyUSB0" />
  </el-form-item>
  <el-form-item label="波特率">
    <el-select v-model="form.connection_config.baudrate">
      <el-option v-for="r in [9600, 19200, 38400, 57600, 115200]" :key="r" :label="r" :value="r" />
    </el-select>
  </el-form-item>
  <el-form-item label="数据位">
    <el-select v-model="form.connection_config.data_bits">
      <el-option v-for="b in [7, 8]" :key="b" :label="b" :value="b" />
    </el-select>
  </el-form-item>
  <el-form-item label="校验位">
    <el-select v-model="form.connection_config.parity">
      <el-option label="无" value="N" />
      <el-option label="奇校验" value="O" />
      <el-option label="偶校验" value="E" />
    </el-select>
  </el-form-item>
  <el-form-item label="停止位">
    <el-select v-model="form.connection_config.stop_bits">
      <el-option v-for="s in [1, 2]" :key="s" :label="s" :value="s" />
    </el-select>
  </el-form-item>
</template>

<!-- SNMP -->
<template v-if="form.protocol_type === 'snmp_v2c' || form.protocol_type === 'snmp_v3'">
  <el-form-item label="目标地址">
    <el-input v-model="form.connection_config.host" placeholder="192.168.1.100" />
  </el-form-item>
  <el-form-item label="端口">
    <el-input-number v-model="form.connection_config.port" :min="1" :max="65535" />
  </el-form-item>
  <el-form-item label="团体名">
    <el-input v-model="form.connection_config.community" placeholder="public" />
  </el-form-item>
</template>
```

#### 4.2 状态标签

```vue
<el-table-column prop="status" label="连接状态" width="120">
  <template #default="{ row }">
    <el-tag :type="getStatusType(row.status)" size="small">
      {{ getStatusLabel(row.status) }}
    </el-tag>
  </template>
</el-table-column>
```

```typescript
function getStatusType(status: string) {
  const map: Record<string, string> = {
    connected: 'success',
    disconnected: 'info',
    communication_error: 'danger',
  }
  return map[status] || 'info'
}

function getStatusLabel(status: string) {
  const map: Record<string, string> = {
    connected: '已连接',
    disconnected: '未连接',
    communication_error: '通信中断',
  }
  return map[status] || status
}
```

#### 4.3 测试连接按钮

在对话框 footer 中，"确定"按钮左侧增加"测试连接"按钮：

```vue
<template #footer>
  <div style="display: flex; justify-content: space-between;">
    <el-button :loading="testing" @click="handleTestConnection">
      测试连接
    </el-button>
    <div>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" @click="handleSubmit">确定</el-button>
    </div>
  </div>
</template>
```

#### 4.4 协议类型选项

```typescript
const protocolOptions = [
  { label: 'Modbus TCP', value: 'modbus_tcp' },
  { label: 'Modbus RTU', value: 'modbus_rtu' },
  { label: 'SNMP v2c', value: 'snmp_v2c' },
  { label: 'SNMP v3', value: 'snmp_v3' },
]
```

#### 4.5 协议默认配置

切换协议类型时，重置 connection_config 为对应默认值：

```typescript
function getDefaultConfig(protocolType: string): Record<string, any> {
  switch (protocolType) {
    case 'modbus_tcp':
      return { host: '', port: 502, slave_id: 1 }
    case 'modbus_rtu':
      return { serial_port: '', baudrate: 9600, data_bits: 8, parity: 'N', stop_bits: 1 }
    case 'snmp_v2c':
    case 'snmp_v3':
      return { host: '', port: 161, community: 'public' }
    default:
      return {}
  }
}
```

### 5. 后端 keyword 搜索增强（可选）

在 `backend/app/api/v1/datasources.py` 的 `list_datasources` 中增加 keyword 参数：

```python
keyword: Optional[str] = Query(None, description="名称关键词"),

# 在 query 构建中
if keyword:
    query = query.where(DataSource.name.contains(keyword))
```

### 6. 关键约束

- **严格参照 device/index.vue 的代码风格**：el-card 包裹、筛选栏、分页栏、表格、对话框的结构和样式完全一致
- **API 路径**: 使用 `/v1/datasources`（与后端一致）
- **协议类型**: modbus_tcp, modbus_rtu, snmp_v2c, snmp_v3（与后端 KNOWN_PROTOCOL_TYPES 一致）
- **connection_config**: 是一个 JSON 对象，不同协议有不同字段
- **不需要后端测试**: 本 Story 主要是前端页面，后端 API 已在 Epic 1 Story 1.5 中实现
- **不需要修改后端模型**: DataSource 模型已完整
- **前端构建验证**: 完成后运行 `cd frontend && npm run build` 确保无编译错误

### Project Structure Notes

- `frontend/src/api/datasource.ts` — 新建
- `frontend/src/views/datasource/index.vue` — 新建
- `frontend/src/router/index.ts` — 修改（新增路由）
- `backend/app/api/v1/datasources.py` — 可选修改（keyword 搜索）

### References

- [Source: views/device/index.vue] 点位管理页面 — UI 风格参照
- [Source: api/point.ts] 点位 API — API 模块风格参照
- [Source: router/index.ts] 路由配置 — 路由注册位置
- [Source: schemas/gateway.py] DataSourceCreate/Update/Response — 后端 Schema
- [Source: api/v1/datasources.py] 后端数据源 API — 已有端点
- [Source: epics.md#Story 3.1] Acceptance Criteria

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

