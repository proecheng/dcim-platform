<template>
  <div class="linkage-policy-page">
    <!-- 顶部筛选栏 -->
    <el-card shadow="hover" class="filter-card">
      <el-form :inline="true" class="filter-form">
        <el-form-item label="策略名称">
          <el-input v-model="filters.name" placeholder="搜索策略名称" clearable @keyup.enter="handleSearch" />
        </el-form-item>
        <el-form-item label="触发类型">
          <el-select v-model="filters.trigger_type" placeholder="全部" clearable>
            <el-option label="告警触发" value="alarm.triggered" />
            <el-option label="告警恢复" value="alarm.resolved" />
            <el-option label="设备离线" value="device.offline" />
            <el-option label="手动触发" value="manual" />
          </el-select>
        </el-form-item>
        <el-form-item label="启用状态">
          <el-select v-model="filters.is_enabled" placeholder="全部" clearable>
            <el-option label="启用" :value="true" />
            <el-option label="禁用" :value="false" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
        <el-form-item style="float: right">
          <el-button type="primary" @click="handleAdd">新建策略</el-button>
          <el-button type="warning" @click="handleReloadFireProtection">重载消防策略</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 策略列表 -->
    <el-card shadow="hover" class="table-card">
      <el-table :data="policies" stripe border v-loading="loading">
        <el-table-column prop="name" label="策略名称" min-width="150" show-overflow-tooltip />
        <el-table-column prop="trigger_type" label="触发类型" width="120" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="triggerTypeTag(row.trigger_type)">
              {{ triggerTypeText(row.trigger_type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="priority" label="优先级" width="100" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="priorityTag(row.priority)">
              {{ priorityText(row.priority) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="is_enabled" label="启用状态" width="100" align="center">
          <template #default="{ row }">
            <el-switch
              :model-value="row.is_enabled"
              :before-change="() => handleToggle(row)"
            />
          </template>
        </el-table-column>
        <el-table-column prop="is_system" label="类型" width="140" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.is_system" type="danger" size="small">系统</el-tag>
            <el-tag v-else type="success" size="small">自定义</el-tag>
            <el-tag
              v-if="getFireLevel(row) === 'warning'"
              type="warning"
              size="small"
              style="margin-left: 4px"
            >预警</el-tag>
            <el-tag
              v-if="getFireLevel(row) === 'linkage'"
              type="danger"
              size="small"
              style="margin-left: 4px"
            >联动</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="动作数量" width="100" align="center">
          <template #default="{ row }">
            {{ row.actions ? row.actions.length : 0 }}
          </template>
        </el-table-column>
        <el-table-column prop="updated_at" label="更新时间" width="180" show-overflow-tooltip />
        <el-table-column label="操作" width="200" fixed="right" align="center">
          <template #default="{ row }">
            <el-button type="primary" link @click="handleEdit(row)">编辑</el-button>
            <el-button type="warning" link @click="handleTest(row)">测试</el-button>
            <el-button
              type="danger"
              link
              :disabled="row.is_system"
              @click="handleDelete(row.id)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        class="pagination"
        @size-change="loadPolicies"
        @current-change="loadPolicies"
      />
    </el-card>

    <!-- 新建/编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑联动策略' : '新建联动策略'"
      width="720px"
      
    >
      <el-form ref="formRef" :model="form" :rules="formRules" label-width="100px">
        <el-form-item label="策略名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入策略名称" />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input v-model="form.description" type="textarea" :rows="2" placeholder="请输入描述（可选）" />
        </el-form-item>
        <el-form-item label="触发类型" prop="trigger_type">
          <el-select v-model="form.trigger_type" placeholder="请选择触发类型" :disabled="isEdit && isSystemPolicy">
            <el-option label="告警触发" value="alarm.triggered" />
            <el-option label="告警恢复" value="alarm.resolved" />
            <el-option label="设备离线" value="device.offline" />
            <el-option label="手动触发" value="manual" />
          </el-select>
        </el-form-item>
        <el-form-item label="触发条件" prop="trigger_condition">
          <el-input
            v-model="form.trigger_condition_str"
            type="textarea"
            :rows="3"
            placeholder='JSON 格式，如 {"alarm_level": "critical"}'
            :disabled="isEdit && isSystemPolicy"
          />
        </el-form-item>
        <el-form-item label="优先级" prop="priority">
          <el-select v-model="form.priority" placeholder="请选择优先级">
            <el-option label="消防信号" value="fire_signal" />
            <el-option label="紧急" value="critical" />
            <el-option label="普通" value="normal" />
          </el-select>
        </el-form-item>

        <!-- 动作列表 -->
        <el-divider content-position="left">联动动作</el-divider>
        <div v-for="(action, index) in form.actions" :key="index" class="action-item">
          <el-row :gutter="12" align="middle">
            <el-col :span="6">
              <el-form-item
                :label="'动作 ' + (index + 1)"
                :prop="'actions.' + index + '.action_type'"
                :rules="[{ required: true, message: '请选择动作类型', trigger: 'change' }]"
                label-width="70px"
              >
                <el-select v-model="action.action_type" placeholder="动作类型">
                  <el-option
                    v-for="at in actionTypes"
                    :key="at.action_type"
                    :label="at.description"
                    :value="at.action_type"
                    :disabled="!at.is_implemented"
                  />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="配置" label-width="50px">
                <el-input
                  v-model="action.action_config_str"
                  type="textarea"
                  :rows="2"
                  placeholder='JSON 配置'
                />
              </el-form-item>
            </el-col>
            <el-col :span="4">
              <el-form-item label="超时(秒)" label-width="70px">
                <el-input-number v-model="action.timeout_seconds" :min="1" :max="3600" size="small" />
              </el-form-item>
            </el-col>
            <el-col :span="3">
              <el-form-item label="重试" label-width="50px">
                <el-input-number v-model="action.retry_count" :min="0" :max="10" size="small" />
              </el-form-item>
            </el-col>
            <el-col :span="3">
              <div class="action-btns">
                <el-button
                  :icon="ArrowUp"
                  circle
                  size="small"
                  :disabled="index === 0"
                  @click="moveAction(index, -1)"
                />
                <el-button
                  :icon="ArrowDown"
                  circle
                  size="small"
                  :disabled="index === form.actions.length - 1"
                  @click="moveAction(index, 1)"
                />
                <el-button
                  :icon="Delete"
                  circle
                  size="small"
                  type="danger"
                  @click="removeAction(index)"
                />
              </div>
            </el-col>
          </el-row>
        </div>
        <el-button type="primary" plain @click="addAction" style="margin-left: 100px">
          添加动作
        </el-button>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitForm">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ArrowUp, ArrowDown, Delete } from '@element-plus/icons-vue'
import {
  getLinkagePolicies,
  createLinkagePolicy,
  updateLinkagePolicy,
  deleteLinkagePolicy,
  toggleLinkagePolicy,
  testLinkagePolicy,
  getActionTypes as fetchActionTypes,
  reloadFireProtection,
  type LinkagePolicy,
  type LinkagePolicyCreate,
  type ActionTypeInfo
} from '@/api/modules/linkage'

// ==================== 列表数据 ====================
const loading = ref(false)
const policies = ref<LinkagePolicy[]>([])
const pagination = reactive({ page: 1, pageSize: 20, total: 0 })
const filters = reactive({
  name: '',
  trigger_type: '',
  is_enabled: undefined as boolean | undefined
})

// ==================== 动作类型 ====================
const actionTypes = ref<ActionTypeInfo[]>([])

async function loadActionTypes() {
  try {
    const res = await fetchActionTypes()
    actionTypes.value = Array.isArray(res) ? res : []
  } catch {
    actionTypes.value = []
  }
}

// ==================== 加载策略列表 ====================
async function loadPolicies() {
  loading.value = true
  try {
    const params: Record<string, string | number | boolean> = {
      page: pagination.page,
      page_size: pagination.pageSize
    }
    if (filters.name) params.name = filters.name
    if (filters.trigger_type) params.trigger_type = filters.trigger_type
    if (typeof filters.is_enabled === 'boolean') params.is_enabled = filters.is_enabled
    const result = await getLinkagePolicies(params)
    policies.value = result.items || []
    pagination.total = result.total || 0
  } catch {
    ElMessage.error('加载联动策略失败')
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  pagination.page = 1
  loadPolicies()
}

function resetFilters() {
  filters.name = ''
  filters.trigger_type = ''
  filters.is_enabled = undefined
  pagination.page = 1
  loadPolicies()
}

// ==================== 启用/禁用 ====================
async function handleToggle(row: LinkagePolicy): Promise<boolean> {
  try {
    await toggleLinkagePolicy(row.id)
    ElMessage.success(row.is_enabled ? '已禁用' : '已启用')
    loadPolicies()
    return true
  } catch {
    ElMessage.error('操作失败')
    return false
  }
}

// ==================== 测试 ====================
async function handleTest(row: LinkagePolicy) {
  try {
    const res = await testLinkagePolicy(row.id)
    ElMessage.success(res.message || '测试执行成功')
  } catch {
    ElMessage.error('测试执行失败')
  }
}

// ==================== 删除 ====================
async function handleDelete(id: number) {
  try {
    await ElMessageBox.confirm('确认删除该联动策略？删除后不可恢复。', '提示', { type: 'warning' })
    await deleteLinkagePolicy(id)
    ElMessage.success('删除成功')
    loadPolicies()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

// ==================== 表单 ====================
interface ActionFormItem {
  action_type: string
  action_config_str: string
  timeout_seconds: number
  retry_count: number
}

const dialogVisible = ref(false)
const isEdit = ref(false)
const currentId = ref<number | null>(null)
const formRef = ref()
const submitting = ref(false)

const form = reactive({
  name: '',
  description: '',
  trigger_type: '',
  trigger_condition_str: '',
    priority: 'normal',
  actions: [] as ActionFormItem[]
})

const formRules = {
  name: [
    { required: true, message: '请输入策略名称', trigger: 'blur' },
    { min: 2, max: 100, message: '长度在 2 到 100 个字符', trigger: 'blur' }
  ],
  trigger_type: [
    { required: true, message: '请选择触发类型', trigger: 'change' }
  ],
  trigger_condition: [
    { required: true, message: '请输入触发条件', trigger: 'blur' }
  ],
  priority: [
    { required: true, message: '请选择优先级', trigger: 'change' }
  ]
}

function handleAdd() {
  isEdit.value = false
  currentId.value = null
  isSystemPolicy.value = false
  form.name = ''
  form.description = ''
  form.trigger_type = ''
  form.trigger_condition_str = ''
  form.priority = 'medium'
  form.actions = []
  dialogVisible.value = true
}

function handleEdit(row: LinkagePolicy) {
  isEdit.value = true
  currentId.value = row.id
  isSystemPolicy.value = row.is_system
  form.name = row.name
  form.description = row.description || ''
  form.trigger_type = row.trigger_type
  form.trigger_condition_str = JSON.stringify(row.trigger_condition, null, 2)
  form.priority = row.priority
  form.actions = (row.actions || []).map(a => ({
    action_type: a.action_type,
    action_config_str: JSON.stringify(a.action_config, null, 2),
    timeout_seconds: a.timeout_seconds || 30,
    retry_count: a.retry_count || 0
  }))
  dialogVisible.value = true
}

function addAction() {
  form.actions.push({
    action_type: '',
    action_config_str: '{}',
    timeout_seconds: 30,
    retry_count: 0
  })
}

function removeAction(index: number) {
  form.actions.splice(index, 1)
}

function moveAction(index: number, direction: number) {
  const target = index + direction
  if (target < 0 || target >= form.actions.length) return
  const temp = form.actions[index]
  form.actions[index] = form.actions[target]
  form.actions[target] = temp
}

async function submitForm() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  // 解析触发条件 JSON
  let triggerCondition: Record<string, unknown>
  try {
    triggerCondition = JSON.parse(form.trigger_condition_str || '{}')
  } catch {
    ElMessage.error('触发条件 JSON 格式不正确')
    return
  }

  // 解析动作配置 JSON
  const actions = form.actions.map((a, i) => {
    let config: Record<string, unknown>
    try {
      config = JSON.parse(a.action_config_str || '{}')
    } catch {
      throw new Error(`动作 ${i + 1} 的配置 JSON 格式不正确`)
    }
    return {
      action_type: a.action_type,
      action_config: config,
      sort_order: i,
      timeout_seconds: a.timeout_seconds,
      retry_count: a.retry_count
    }
  })

  const data: LinkagePolicyCreate = {
    name: form.name,
    description: form.description || undefined,
    trigger_type: form.trigger_type,
    trigger_condition: triggerCondition,
    priority: form.priority,
    actions
  }

  submitting.value = true
  try {
    if (isEdit.value && currentId.value) {
      await updateLinkagePolicy(currentId.value, data)
      ElMessage.success('更新成功')
    } else {
      await createLinkagePolicy(data)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    loadPolicies()
  } catch (e) {
    if (e instanceof Error) {
      ElMessage.error(e.message)
    } else {
      ElMessage.error('保存失败')
    }
  } finally {
    submitting.value = false
  }
}

// ==================== 消防策略辅助 ====================
function getFireLevel(row: LinkagePolicy): string | null {
  const condition = row.trigger_condition
  if (condition && typeof condition === 'object' && 'fire_level' in condition) {
    return condition.fire_level as string
  }
  return null
}

const isSystemPolicy = ref(false)

async function handleReloadFireProtection() {
  try {
    await ElMessageBox.confirm('确认重载消防策略？将从 YAML 文件重新加载系统消防策略。', '提示', { type: 'warning' })
    const res = await reloadFireProtection()
    ElMessage.success(res.message || '重载成功')
    loadPolicies()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('重载失败')
    }
  }
}

// ==================== 辅助函数 ====================
function triggerTypeText(type: string): string {
  const map: Record<string, string> = { 'alarm.triggered': '告警触发', 'alarm.resolved': '告警恢复', 'device.offline': '设备离线', manual: '手动触发' }
  return map[type] || type
}

function triggerTypeTag(type: string): 'success' | 'warning' | 'info' | 'danger' {
  const map: Record<string, 'success' | 'warning' | 'info' | 'danger'> = { 'alarm.triggered': 'danger', 'alarm.resolved': 'success', 'device.offline': 'warning', manual: 'info' }
  return map[type] || 'info'
}

function priorityText(p: string): string {
  const map: Record<string, string> = { fire_signal: '消防信号', critical: '紧急', normal: '普通' }
  return map[p] || p
}

function priorityTag(p: string): 'success'|'warning'|'info'|'danger' {
  const map: Record<string, 'success'|'warning'|'info'|'danger'> = { fire_signal: 'danger', critical: 'warning', normal: 'info' }
  return map[p] || 'info'
}

// ==================== 生命周期 ====================
onMounted(() => {
  loadPolicies()
  loadActionTypes()
})
</script>

<style lang="scss" scoped>
@use '@/styles/_mixins-25d' as *;

.linkage-policy-page {
  height: 100%;
  padding: 16px;
  overflow-y: auto;
  @include page-list;
}

.filter-card {
  margin-bottom: 16px;
}

.filter-form {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
}

.table-card {
  margin-bottom: 16px;
}

.pagination {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.action-item {
  background: var(--el-fill-color-lighter);
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 12px;
  margin-left: 100px;
}

.action-btns {
  display: flex;
  gap: 4px;
  align-items: center;
  justify-content: center;
}
</style>
