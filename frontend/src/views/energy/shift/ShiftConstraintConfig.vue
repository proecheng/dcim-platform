<template>
  <div class="shift-constraint-config">
    <el-page-header @back="$router.back()" title="返回">
      <template #content>
        <span>约束管理</span>
      </template>
    </el-page-header>

    <el-card shadow="hover" style="margin-top: 20px">
      <template #header>
        <div class="card-header">
          <span>约束规则列表</span>
          <el-button type="primary" @click="handleAdd">新增约束</el-button>
        </div>
      </template>

      <el-table :data="constraints" border v-loading="loading">
        <el-table-column type="index" label="#" width="60" />
        <el-table-column prop="name" label="约束名称" min-width="180" />
        <el-table-column prop="type" label="约束类型" width="120">
          <template #default="{ row }">
            <el-tag :type="getTypeColor(row.type)">{{ getTypeLabel(row.type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="约束描述" min-width="200" />
        <el-table-column prop="priority" label="优先级" width="100">
          <template #default="{ row }">
            <el-tag :type="getPriorityColor(row.priority)">{{ getPriorityLabel(row.priority) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="enabled" label="状态" width="100">
          <template #default="{ row }">
            <el-switch v-model="row.enabled" @change="handleToggle(row)" />
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="160" />
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" size="small" @click="handleEdit(row)">编辑</el-button>
            <el-button type="danger" size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="800px"
      :close-on-click-modal="false"
    >
      <ConstraintEditor
        v-model="currentConstraint"
        :available-devices="availableDevices"
        @save="handleSaveConstraint"
        @cancel="dialogVisible = false"
      />
    </el-dialog>

    <el-card shadow="hover" style="margin-top: 20px">
      <template #header>
        <span>约束说明</span>
      </template>
      <el-descriptions :column="1" border>
        <el-descriptions-item label="设备约束">
          限制特定设备的转移行为，如不可同时转移、必须同时转移、转移顺序限制等。
        </el-descriptions-item>
        <el-descriptions-item label="时间约束">
          限制负荷转移的时间范围，如只能在特定时间段或特定星期执行。
        </el-descriptions-item>
        <el-descriptions-item label="功率约束">
          限制转移功率的范围和变化率，防止功率变化过快导致系统不稳定。
        </el-descriptions-item>
        <el-descriptions-item label="三相平衡">
          确保三相负载平衡，不平衡度建议 <10%。超过此值可能导致设备损坏或效率降低。
        </el-descriptions-item>
        <el-descriptions-item label="温度约束">
          限制设备温度和温升速率，防止过热导致设备损坏。
        </el-descriptions-item>
        <el-descriptions-item label="设备寿命">
          限制设备启停次数和运行间隔，减少频繁启停对设备寿命的影响（15-25% 寿命损失）。
        </el-descriptions-item>
      </el-descriptions>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import ConstraintEditor from '@/components/energy/shift/ConstraintEditor.vue'

interface Constraint {
  id?: number
  type: string
  name: string
  description: string
  params: Record<string, any>
  priority: string
  enabled: boolean
  created_at?: string
}

const loading = ref(false)
const constraints = ref<Constraint[]>([])
const dialogVisible = ref(false)
const dialogTitle = ref('')
const currentConstraint = ref<Constraint>({
  type: '',
  name: '',
  description: '',
  params: {},
  priority: 'medium',
  enabled: true
})
const availableDevices = ref<Array<{ id: number; name: string }>>([])

const fetchConstraints = async () => {
  loading.value = true
  try {
    // TODO: 调用 API 获取约束列表
    // const res = await getShiftConstraints()
    // constraints.value = res.data
    
    // 模拟数据
    constraints.value = [
      {
        id: 1,
        type: 'phase_balance',
        name: '三相平衡约束',
        description: '确保配电系统三相负载平衡，不平衡度不超过 10%',
        params: { max_imbalance: 10, check_scope: 'entire_system' },
        priority: 'high',
        enabled: true,
        created_at: '2026-03-01 10:00:00'
      },
      {
        id: 2,
        type: 'device_lifetime',
        name: '设备寿命保护',
        description: '限制设备每天启停次数不超过 5 次',
        params: { max_start_stop_count: 5, min_run_interval: 30, lifetime_loss_factor: 0.2 },
        priority: 'high',
        enabled: true,
        created_at: '2026-03-01 10:05:00'
      },
      {
        id: 3,
        type: 'time',
        name: '工作日时间限制',
        description: '仅在工作日 8:00-18:00 允许负荷转移',
        params: { time_range: ['08:00', '18:00'], weekdays: [1, 2, 3, 4, 5] },
        priority: 'medium',
        enabled: true,
        created_at: '2026-03-01 10:10:00'
      }
    ]
  } catch (error: any) {
    ElMessage.error(error.message || '获取约束列表失败')
  } finally {
    loading.value = false
  }
}

const fetchDevices = async () => {
  try {
    // TODO: 调用 API 获取可转移设备列表
    // const res = await getShiftableDevices()
    // availableDevices.value = res.data
    
    // 模拟数据
    availableDevices.value = [
      { id: 1, name: 'UPS-1' },
      { id: 2, name: 'UPS-2' },
      { id: 3, name: '空调-1' },
      { id: 4, name: '空调-2' }
    ]
  } catch (error: any) {
    ElMessage.error(error.message || '获取设备列表失败')
  }
}

const handleAdd = () => {
  dialogTitle.value = '新增约束'
  currentConstraint.value = {
    type: '',
    name: '',
    description: '',
    params: {},
    priority: 'medium',
    enabled: true
  }
  dialogVisible.value = true
}

const handleEdit = (row: Constraint) => {
  dialogTitle.value = '编辑约束'
  currentConstraint.value = { ...row }
  dialogVisible.value = true
}

const handleSaveConstraint = async (constraint: Constraint) => {
  try {
    // TODO: 调用 API 保存约束
    // if (constraint.id) {
    //   await updateShiftConstraint(constraint.id, constraint)
    // } else {
    //   await createShiftConstraint(constraint)
    // }
    
    ElMessage.success('保存成功')
    dialogVisible.value = false
    await fetchConstraints()
  } catch (error: any) {
    ElMessage.error(error.message || '保存失败')
  }
}

const handleToggle = async (row: Constraint) => {
  try {
    // TODO: 调用 API 更新约束状态
    // await updateShiftConstraint(row.id, { enabled: row.enabled })
    
    ElMessage.success(row.enabled ? '已启用' : '已禁用')
  } catch (error: any) {
    ElMessage.error(error.message || '更新失败')
    row.enabled = !row.enabled
  }
}

const handleDelete = async (row: Constraint) => {
  try {
    await ElMessageBox.confirm('确定要删除该约束吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    // TODO: 调用 API 删除约束
    // await deleteShiftConstraint(row.id)
    
    ElMessage.success('删除成功')
    await fetchConstraints()
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || '删除失败')
    }
  }
}

const getTypeColor = (type: string) => {
  const map: Record<string, string> = {
    device: 'primary',
    time: 'success',
    power: 'warning',
    phase_balance: 'danger',
    temperature: 'info',
    device_lifetime: ''
  }
  return map[type] || ''
}

const getTypeLabel = (type: string) => {
  const map: Record<string, string> = {
    device: '设备约束',
    time: '时间约束',
    power: '功率约束',
    phase_balance: '三相平衡',
    temperature: '温度约束',
    device_lifetime: '设备寿命'
  }
  return map[type] || type
}

const getPriorityColor = (priority: string) => {
  const map: Record<string, string> = {
    high: 'danger',
    medium: 'warning',
    low: 'info'
  }
  return map[priority] || ''
}

const getPriorityLabel = (priority: string) => {
  const map: Record<string, string> = {
    high: '高',
    medium: '中',
    low: '低'
  }
  return map[priority] || priority
}

onMounted(() => {
  fetchConstraints()
  fetchDevices()
})
</script>

<style scoped lang="scss">
.shift-constraint-config {
  padding: 20px;

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
}
</style>
