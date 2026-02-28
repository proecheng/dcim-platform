# 删除确认对话框使用指南

## 组件位置
`frontend/src/components/common/DeleteConfirmDialog.vue`

## 功能说明
通用的设备删除确认对话框，支持：
- 自动获取删除影响分析
- 分类展示影响（阻断原因、级联删除、解绑操作、软引用）
- 阻断原因时禁用删除按钮
- 完整的加载和错误处理

## 使用方法

### 1. 在页面中导入组件

```vue
<script setup lang="ts">
import DeleteConfirmDialog from '@/components/common/DeleteConfirmDialog.vue'
import { ref } from 'vue'

const showDeleteDialog = ref(false)
const selectedDeviceId = ref(0)
const selectedDeviceName = ref('')

const handleDelete = (device: any) => {
  selectedDeviceId.value = device.id
  selectedDeviceName.value = device.device_name
  showDeleteDialog.value = true
}

const handleDeleted = () => {
  // 删除成功后的回调，例如刷新列表
  fetchDeviceList()
}
</script>
```

### 2. 在模板中使用

```vue
<template>
  <!-- 设备列表 -->
  <el-table :data="deviceList">
    <el-table-column label="操作">
      <template #default="{ row }">
        <el-button
          type="danger"
          size="small"
          @click="handleDelete(row)"
        >
          删除
        </el-button>
      </template>
    </el-table-column>
  </el-table>

  <!-- 删除确认对话框 -->
  <DeleteConfirmDialog
    v-model="showDeleteDialog"
    :device-id="selectedDeviceId"
    :device-name="selectedDeviceName"
    @deleted="handleDeleted"
  />
</template>
```

## Props

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| modelValue | boolean | 是 | 对话框显示状态（支持 v-model） |
| deviceId | number | 是 | 要删除的设备 ID |
| deviceName | string | 是 | 设备名称（用于显示） |

## Events

| 事件名 | 参数 | 说明 |
|--------|------|------|
| update:modelValue | value: boolean | 对话框状态变化时触发 |
| deleted | - | 删除成功后触发 |

## 集成示例

### 设备管理页面 (views/device-manage/index.vue)

```vue
<script setup lang="ts">
import DeleteConfirmDialog from '@/components/common/DeleteConfirmDialog.vue'

// ... 现有代码 ...

const showDeleteDialog = ref(false)
const deleteDeviceId = ref(0)
const deleteDeviceName = ref('')

const handleDeleteDevice = (row: any) => {
  deleteDeviceId.value = row.id
  deleteDeviceName.value = row.device_name
  showDeleteDialog.value = true
}

const handleDeviceDeleted = () => {
  ElMessage.success('设备删除成功')
  fetchDeviceList() // 刷新列表
}
</script>

<template>
  <!-- 在操作列添加删除按钮 -->
  <el-table-column label="操作" width="200">
    <template #default="{ row }">
      <el-button type="danger" size="small" @click="handleDeleteDevice(row)">
        删除
      </el-button>
    </template>
  </el-table-column>

  <!-- 添加对话框 -->
  <DeleteConfirmDialog
    v-model="showDeleteDialog"
    :device-id="deleteDeviceId"
    :device-name="deleteDeviceName"
    @deleted="handleDeviceDeleted"
  />
</template>
```

### 能源管理页面 (views/energy/monitor.vue)

```vue
<script setup lang="ts">
import DeleteConfirmDialog from '@/components/common/DeleteConfirmDialog.vue'

// ... 现有代码 ...

const showDeleteDialog = ref(false)
const deleteDeviceId = ref(0)
const deleteDeviceName = ref('')

const handleDeletePowerDevice = (device: any) => {
  deleteDeviceId.value = device.id
  deleteDeviceName.value = device.device_name
  showDeleteDialog.value = true
}

const handlePowerDeviceDeleted = () => {
  ElMessage.success('用电设备删除成功')
  fetchPowerDevices() // 刷新设备列表
}
</script>

<template>
  <!-- 在设备卡片或表格中添加删除按钮 -->
  <el-button
    type="danger"
    size="small"
    @click="handleDeletePowerDevice(device)"
  >
    删除
  </el-button>

  <!-- 添加对话框 -->
  <DeleteConfirmDialog
    v-model="showDeleteDialog"
    :device-id="deleteDeviceId"
    :device-name="deleteDeviceName"
    @deleted="handlePowerDeviceDeleted"
  />
</template>
```

## 后端 API

组件使用以下 API：
- `DELETE /api/v1/energy/devices/{id}?force=false` - 获取删除影响分析
- `DELETE /api/v1/energy/devices/{id}?force=true` - 执行删除

## 影响分析数据结构

```typescript
interface DeleteImpact {
  can_delete: boolean
  blocking_reasons: string[]  // 阻断原因
  cascade_deletes: {          // 级联删除
    [table_name: string]: number
  }
  unbind_operations: {        // 解绑操作
    [table_name: string]: number
  }
  soft_references: {          // 软引用
    [table_name: string]: number
  }
}
```

## 注意事项

1. **阻断原因**：当存在阻断原因时（如有子设备），删除按钮会被禁用
2. **级联删除**：会永久删除关联数据，用户需要明确确认
3. **错误处理**：组件内部已处理所有错误情况，会显示友好的错误提示
4. **权限控制**：确保用户有删除权限，否则 API 会返回 403 错误
