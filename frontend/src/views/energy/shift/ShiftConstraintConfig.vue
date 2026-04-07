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
          确保三相负载平衡，不平衡度建议 &lt;10%。超过此值可能导致设备损坏或效率降低。
        </el-descriptions-item>
        <el-descriptions-item label="温度约束">
          限制设备温度和温升速率，防止过热导致设备损坏。
        </el-descriptions-item>
        <el-descriptions-item label="设备寿命">
          限制设备启停次数和运行间隔，减少频繁启停对设备寿命的影响（15-25% 寿命损失）。
        </el-descriptions-item>
        <el-descriptions-item label="算力中心负载占比">
          约束 IT 负载占比区间，并按制冷/其他可转移系数计算最大可转移功率，避免超出算力中心可调节空间。
        </el-descriptions-item>
        <el-descriptions-item label="UPS容量约束">
          校验转移后峰值功率不超过 UPS 容量上限（容量×安全系数），超限时可自动降功率或拒绝执行。
        </el-descriptions-item>
      </el-descriptions>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import ConstraintEditor from '@/components/energy/shift/ConstraintEditor.vue'
import {
  getShiftConstraints,
  createShiftConstraint,
  updateShiftConstraint,
  deleteShiftConstraint,
  getShiftableDevices,
} from '@/api/modules/shift'

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
const availableDevices = ref<Array<{ id: number; name: string; rated_power?: number }>>([])

const fetchConstraints = async () => {
  loading.value = true
  try {
    const res = await getShiftConstraints()
    const list = res?.data?.data || res?.data || []
    constraints.value = list.map((item: any) => ({
      id: item.id,
      type: item.type,
      name: item.name,
      description: item.description || '',
      params: item.constraint_config || item.params || {},
      priority: toPriorityLabel(item.priority),
      enabled: Boolean(item.enabled),
      created_at: item.created_at,
    }))
  } catch (error: any) {
    ElMessage.error(error.message || '获取约束列表失败')
  } finally {
    loading.value = false
  }
}

const fetchDevices = async () => {
  try {
    const res = await getShiftableDevices()
    const list = res?.data?.data || res?.data || []
    availableDevices.value = (Array.isArray(list) ? list : list.items || []).map((d: any) => ({
      id: d.id,
      name: d.device_name || d.name || `设备-${d.id}`,
      rated_power: Number(d.rated_power || 0),
    }))
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
    const payload = {
      name: constraint.name,
      type: constraint.type,
      description: constraint.description,
      constraint_config: constraint.params || {},
      priority: toPriorityNumber(constraint.priority),
      enabled: constraint.enabled,
    }

    if (constraint.id) {
      await updateShiftConstraint(constraint.id, payload)
    } else {
      await createShiftConstraint(payload)
    }
    
    ElMessage.success('保存成功')
    dialogVisible.value = false
    await fetchConstraints()
  } catch (error: any) {
    ElMessage.error(error.message || '保存失败')
  }
}

const handleToggle = async (row: Constraint) => {
  try {
    if (!row.id) return
    await updateShiftConstraint(row.id, { enabled: row.enabled })
    
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
    
    if (!row.id) return
    await deleteShiftConstraint(row.id)
    
    ElMessage.success('删除成功')
    await fetchConstraints()
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || '删除失败')
    }
  }
}

type TagType = 'primary' | 'success' | 'warning' | 'info' | 'danger'

const getTypeColor = (type: string): TagType => {
  const map: Record<string, TagType> = {
    device: 'primary',
    time: 'success',
    power: 'warning',
    phase_balance: 'danger',
    temperature: 'info',
    device_lifetime: 'info',
    datacenter_load: 'success',
    ups_capacity: 'danger',
  }
  return map[type] || 'info'
}

const getTypeLabel = (type: string) => {
  const map: Record<string, string> = {
    device: '设备约束',
    time: '时间约束',
    power: '功率约束',
    phase_balance: '三相平衡',
    temperature: '温度约束',
    device_lifetime: '设备寿命',
    datacenter_load: '算力中心负载占比',
    ups_capacity: 'UPS容量约束',
  }
  return map[type] || type
}

const getPriorityColor = (priority: string): TagType => {
  const p = toPriorityLabel(priority)
  const map: Record<string, TagType> = {
    high: 'danger',
    medium: 'warning',
    low: 'info'
  }
  return map[p] || 'info'
}

const getPriorityLabel = (priority: string) => {
  const p = toPriorityLabel(priority)
  const map: Record<string, string> = {
    high: '高',
    medium: '中',
    low: '低'
  }
  return map[p] || p
}

const toPriorityLabel = (priority: string | number | undefined) => {
  if (typeof priority === 'number') {
    if (priority <= 3) return 'high'
    if (priority <= 6) return 'medium'
    return 'low'
  }
  return priority || 'medium'
}

const toPriorityNumber = (priority: string | number) => {
  if (typeof priority === 'number') return priority
  if (priority === 'high') return 1
  if (priority === 'low') return 9
  return 5
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
