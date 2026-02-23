<template>
  <div class="compound-rule-page">
    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stat-row">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value">{{ stats.total }}</div>
          <div class="stat-label">总规则数</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value enabled">{{ stats.enabled }}</div>
          <div class="stat-label">已启用</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value disabled">{{ stats.disabled }}</div>
          <div class="stat-label">已禁用</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value types">{{ stats.andCount }}</div>
          <div class="stat-label">AND 规则</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 工具栏 -->
    <el-card shadow="hover" class="toolbar-card">
      <el-form :inline="true" class="filter-form">
        <el-form-item label="逻辑关系">
          <el-select v-model="filters.ruleType" placeholder="全部" clearable style="width: 120px">
            <el-option label="AND" value="and" />
            <el-option label="OR" value="or" />
          </el-select>
        </el-form-item>
        <el-form-item label="启用状态">
          <el-select v-model="filters.isEnabled" placeholder="全部" clearable style="width: 100px">
            <el-option label="启用" :value="true" />
            <el-option label="禁用" :value="false" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadData">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
      <div class="toolbar-actions">
        <el-button type="primary" @click="handleAdd">新增复合规则</el-button>
      </div>
    </el-card>

    <!-- 规则列表 -->
    <el-card shadow="hover" class="table-card">
      <el-table
        :data="tableData"
        stripe
        border
        v-loading="loading"
        style="width: 100%"
      >
        <el-table-column prop="rule_name" label="规则名称" min-width="160" show-overflow-tooltip />
        <el-table-column label="条件数" width="80" align="center">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ getConditionCount(row) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="逻辑关系" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.rule_type === 'and' ? 'primary' : 'warning'" size="small">
              {{ row.rule_type === 'and' ? 'AND' : 'OR' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="告警级别" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="levelTagType(row.alarm_level)" size="small">
              {{ levelLabel(row.alarm_level) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="关联点位" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">
            {{ getRelatedPoints(row) }}
          </template>
        </el-table-column>
        <el-table-column label="启用" width="80" align="center">
          <template #default="{ row }">
            <el-switch
              :model-value="row.is_enabled"
              :before-change="() => handleToggle(row)"
            />
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="170" />
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="handleEdit(row)">编辑</el-button>
            <el-button type="danger" link @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        class="pagination"
        @size-change="loadData"
        @current-change="loadData"
      />
    </el-card>

    <!-- 添加/编辑复合规则对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑复合规则' : '新增复合规则'"
      width="960px"
      destroy-on-close
      top="4vh"
    >
      <el-form ref="formRef" :model="form" :rules="formRules" label-width="90px">
        <!-- 基本信息 -->
        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="规则名称" prop="ruleName">
              <el-input v-model="form.ruleName" placeholder="请输入规则名称" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="告警级别" prop="alarmLevel">
              <el-select v-model="form.alarmLevel" style="width: 100%">
                <el-option label="紧急" value="critical" />
                <el-option label="重要" value="major" />
                <el-option label="次要" value="minor" />
                <el-option label="提示" value="info" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="告警消息">
              <el-input v-model="form.alarmMessage" placeholder="触发时的告警消息" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-divider content-position="left">条件配置</el-divider>

        <!-- 条件编辑器 -->
        <div class="condition-editor">
          <ConditionGroupEditor
            :group="form.rootGroup"
            :point-options="pointOptions"
            :depth="0"
            @update:group="(val: any) => form.rootGroup = val"
          />
        </div>

        <el-divider content-position="left">规则测试预览</el-divider>

        <!-- 规则测试 -->
        <div class="rule-test-section">
          <div class="test-header">
            <span class="test-title">输入模拟点位值，实时预览触发结果</span>
            <el-button size="small" type="primary" @click="runTest" :disabled="!hasConditions">
              执行测试
            </el-button>
          </div>
          <div v-if="testPointIds.length" class="test-inputs">
            <el-row :gutter="12">
              <el-col v-for="pid in testPointIds" :key="pid" :span="8">
                <div class="test-input-item">
                  <span class="test-point-label">{{ getPointName(pid) }}</span>
                  <el-input-number
                    v-model="testValues[pid]"
                    :precision="2"
                    size="small"
                    style="width: 100%"
                    @change="runTest"
                  />
                </div>
              </el-col>
            </el-row>
          </div>
          <div v-else class="test-empty">请先添加条件</div>
          <div v-if="testResult !== null" class="test-result" :class="{ triggered: testResult }">
            <el-icon :size="18">
              <WarningFilled v-if="testResult" />
              <CircleCheckFilled v-else />
            </el-icon>
            <span>{{ testResult ? '规则触发' : '规则未触发' }}</span>
          </div>
        </div>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm" :loading="submitting">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { WarningFilled, CircleCheckFilled } from '@element-plus/icons-vue'
import {
  getAlarmRules, createAlarmRule, updateAlarmRule, deleteAlarmRule, toggleAlarmRule,
  type AlarmRuleInfo
} from '@/api/modules/alarm'
import { getPointList, type PointInfo } from '@/api/modules/point'
import ConditionGroupEditor from './CompoundConditionGroup.vue'

// ==================== 条件树类型 ====================
interface ConditionItem {
  id: string
  type: 'condition'
  pointId: number | undefined
  pointName: string
  operator: '>' | '<' | '=' | '>=' | '<='
  threshold: number | undefined
}

interface ConditionGroup {
  id: string
  type: 'group'
  logic: 'AND' | 'OR'
  children: (ConditionItem | ConditionGroup)[]
}

interface CompoundRuleForm {
  ruleName: string
  alarmLevel: 'critical' | 'major' | 'minor' | 'info'
  alarmMessage: string
  rootGroup: ConditionGroup
}

// ==================== 状态 ====================
const loading = ref(false)
const submitting = ref(false)
const tableData = ref<AlarmRuleInfo[]>([])
const pointOptions = ref<PointInfo[]>([])

const stats = reactive({ total: 0, enabled: 0, disabled: 0, andCount: 0 })
const pagination = reactive({ page: 1, pageSize: 20, total: 0 })
const filters = reactive({
  ruleType: '' as string,
  isEnabled: undefined as boolean | undefined
})

// ==================== 初始化 ====================
onMounted(() => {
  loadPointOptions()
  loadData()
})

async function loadPointOptions() {
  try {
    const result = await getPointList({ page_size: 100 })
    pointOptions.value = result.items || []
  } catch (e) {
    console.error('加载点位失败', e)
  }
}

// ==================== 数据加载 ====================
async function loadData() {
  loading.value = true
  try {
    const params: Record<string, string | number | boolean> = {
      page: pagination.page,
      page_size: pagination.pageSize
    }
    if (filters.ruleType) params.rule_type = filters.ruleType
    if (typeof filters.isEnabled === 'boolean') params.is_enabled = filters.isEnabled

    const result = await getAlarmRules(params)
    tableData.value = result.items || []
    pagination.total = result.total || 0

    // 统计
    stats.total = result.total || 0
    stats.enabled = tableData.value.filter(r => r.is_enabled).length
    stats.disabled = tableData.value.filter(r => !r.is_enabled).length
    stats.andCount = tableData.value.filter(r => r.rule_type === 'and').length
  } catch (e) {
    console.error('加载规则失败', e)
    ElMessage.error('加载复合规则列表失败')
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  filters.ruleType = ''
  filters.isEnabled = undefined
  pagination.page = 1
  loadData()
}

// ==================== 辅助函数 ====================
function levelTagType(level: string): 'success' | 'warning' | 'danger' | 'info' {
  const map: Record<string, 'success' | 'warning' | 'danger' | 'info'> = {
    critical: 'danger', major: 'warning', minor: 'info', info: 'info'
  }
  return map[level] || 'info'
}

function levelLabel(level: string): string {
  const map: Record<string, string> = {
    critical: '紧急', major: '重要', minor: '次要', info: '提示'
  }
  return map[level] || level
}

function getConditionCount(row: AlarmRuleInfo): number {
  if (!row.condition_expr) return 0
  try {
    const root = JSON.parse(row.condition_expr) as ConditionGroup
    return countConditions(root)
  } catch {
    console.warn('条件表达式解析失败:', row.rule_name)
    return 0
  }
}

function countConditions(node: ConditionGroup | ConditionItem): number {
  if (node.type === 'condition') return 1
  return node.children.reduce((sum, child) => sum + countConditions(child), 0)
}

function getRelatedPoints(row: AlarmRuleInfo): string {
  if (!row.condition_expr) return '-'
  try {
    const root = JSON.parse(row.condition_expr) as ConditionGroup
    const names = collectPointNames(root)
    return names.length ? names.join(', ') : '-'
  } catch {
    console.warn('条件表达式解析失败:', row.rule_name)
    return '(数据异常)'
  }
}

function collectPointNames(node: ConditionGroup | ConditionItem): string[] {
  if (node.type === 'condition') {
    return node.pointName ? [node.pointName] : []
  }
  const names: string[] = []
  for (const child of node.children) {
    names.push(...collectPointNames(child))
  }
  return [...new Set(names)]
}

// ==================== 启用/禁用 ====================
async function handleToggle(row: AlarmRuleInfo): Promise<boolean> {
  try {
    await toggleAlarmRule(row.id)
    ElMessage.success(row.is_enabled ? '已禁用' : '已启用')
    loadData()
    return true
  } catch (e) {
    console.error('切换状态失败', e)
    ElMessage.error('操作失败')
    return false
  }
}

// ==================== 删除 ====================
async function handleDelete(row: AlarmRuleInfo) {
  try {
    await ElMessageBox.confirm(
      `确认删除规则「${row.rule_name}」？`,
      '删除确认',
      { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' }
    )
    await deleteAlarmRule(row.id)
    ElMessage.success('删除成功')
    loadData()
  } catch (e) {
    if (e !== 'cancel') {
      console.error('删除失败', e)
      ElMessage.error('删除失败')
    }
  }
}

// ==================== 添加/编辑对话框 ====================
const dialogVisible = ref(false)
const isEdit = ref(false)
const editingId = ref<number | null>(null)
const formRef = ref()

function createEmptyGroup(): ConditionGroup {
  return {
    id: crypto.randomUUID(),
    type: 'group',
    logic: 'AND',
    children: []
  }
}

const form = reactive<CompoundRuleForm>({
  ruleName: '',
  alarmLevel: 'major',
  alarmMessage: '',
  rootGroup: createEmptyGroup()
})

const formRules = {
  ruleName: [{ required: true, message: '请输入规则名称', trigger: 'blur' }],
  alarmLevel: [{ required: true, message: '请选择告警级别', trigger: 'change' }]
}

function handleAdd() {
  isEdit.value = false
  editingId.value = null
  form.ruleName = ''
  form.alarmLevel = 'major'
  form.alarmMessage = ''
  form.rootGroup = createEmptyGroup()
  testResult.value = null
  testValues.value = {}
  dialogVisible.value = true
}

function handleEdit(row: AlarmRuleInfo) {
  isEdit.value = true
  editingId.value = row.id
  form.ruleName = row.rule_name
  form.alarmLevel = row.alarm_level || 'major'
  form.alarmMessage = row.alarm_message || ''

  // 反序列化条件树
  if (row.condition_expr) {
    try {
      form.rootGroup = JSON.parse(row.condition_expr) as ConditionGroup
    } catch {
      ElMessage.warning('条件表达式数据异常，已重置为默认条件')
      form.rootGroup = createEmptyGroup()
    }
  } else {
    form.rootGroup = createEmptyGroup()
    form.rootGroup.logic = row.rule_type === 'or' ? 'OR' : 'AND'
  }

  testResult.value = null
  testValues.value = {}
  dialogVisible.value = true
}

async function submitForm() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    const conditionExpr = JSON.stringify(form.rootGroup)
    const data = {
      rule_name: form.ruleName,
      rule_type: form.rootGroup.logic === 'AND' ? 'and' as const : 'or' as const,
      condition_expr: conditionExpr,
      alarm_level: form.alarmLevel,
      alarm_message: form.alarmMessage,
      is_enabled: true
    }

    if (isEdit.value && editingId.value) {
      await updateAlarmRule(editingId.value, data)
      ElMessage.success('更新成功')
    } else {
      await createAlarmRule(data)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    loadData()
  } catch (e) {
    console.error('保存失败', e)
    ElMessage.error('保存失败')
  } finally {
    submitting.value = false
  }
}

// ==================== 规则测试引擎 ====================
const testValues = ref<Record<number, number>>({})
const testResult = ref<boolean | null>(null)

const testPointIds = computed<number[]>(() => {
  const ids = new Set<number>()
  collectPointIds(form.rootGroup, ids)
  return Array.from(ids)
})

const hasConditions = computed(() => testPointIds.value.length > 0)

function collectPointIds(node: ConditionGroup | ConditionItem, ids: Set<number>) {
  if (node.type === 'condition') {
    if (node.pointId != null) ids.add(node.pointId)
    return
  }
  for (const child of node.children) {
    collectPointIds(child, ids)
  }
}

function getPointName(pid: number): string {
  const p = pointOptions.value.find(pt => pt.id === pid)
  return p ? p.point_name : `点位#${pid}`
}

function runTest() {
  if (!hasConditions.value) {
    testResult.value = null
    return
  }
  testResult.value = evaluateGroup(form.rootGroup, testValues.value)
}

function evaluateGroup(group: ConditionGroup, values: Record<number, number>): boolean {
  if (!group.children.length) return false
  const results = group.children.map(child => {
    if (child.type === 'condition') return evaluateCondition(child, values)
    return evaluateGroup(child, values)
  })
  return group.logic === 'AND'
    ? results.every(Boolean)
    : results.some(Boolean)
}

function evaluateCondition(cond: ConditionItem, values: Record<number, number>): boolean {
  if (cond.pointId == null || cond.threshold == null) return false
  const val = values[cond.pointId]
  if (val == null) return false
  switch (cond.operator) {
    case '>': return val > cond.threshold
    case '<': return val < cond.threshold
    case '=': return Math.abs(val - cond.threshold) < 0.001
    case '>=': return val >= cond.threshold
    case '<=': return val <= cond.threshold
    default: return false
  }
}
</script>

<style lang="scss" scoped>
@use '@/styles/_mixins-25d' as d25;

.compound-rule-page {
  @include d25.page-list;
  padding: 16px;

  .stat-row {
    margin-bottom: 16px;
  }

  .stat-card {
    text-align: center;
    .stat-value {
      font-size: 28px;
      font-weight: 700;
      color: var(--el-text-color-primary);
      &.enabled { color: #67C23A; }
      &.disabled { color: #909399; }
      &.types { color: #409EFF; }
    }
    .stat-label {
      font-size: 13px;
      color: var(--el-text-color-secondary);
      margin-top: 4px;
    }
  }

  .toolbar-card {
    margin-bottom: 16px;
    .filter-form { margin-bottom: 8px; }
    .toolbar-actions {
      display: flex;
      gap: 8px;
    }
  }

  .table-card {
    .pagination {
      margin-top: 16px;
      justify-content: flex-end;
    }
  }
}

.condition-editor {
  padding: 12px;
  background: var(--el-fill-color-lighter);
  border-radius: 8px;
  border: 1px dashed var(--el-border-color);
  min-height: 80px;
}

.rule-test-section {
  padding: 12px;
  background: var(--el-fill-color-lighter);
  border-radius: 8px;
  border: 1px solid var(--el-border-color-lighter);

  .test-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;

    .test-title {
      font-size: 13px;
      color: var(--el-text-color-secondary);
    }
  }

  .test-inputs {
    margin-bottom: 12px;

    .test-input-item {
      margin-bottom: 8px;

      .test-point-label {
        display: block;
        font-size: 12px;
        color: var(--el-text-color-regular);
        margin-bottom: 4px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
    }
  }

  .test-empty {
    text-align: center;
    color: var(--el-text-color-placeholder);
    font-size: 13px;
    padding: 16px 0;
  }

  .test-result {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 8px 12px;
    border-radius: 6px;
    font-size: 14px;
    font-weight: 600;
    background: rgba(103, 194, 58, 0.1);
    color: #67C23A;

    &.triggered {
      background: rgba(245, 108, 108, 0.1);
      color: #F56C6C;
    }
  }
}
</style>
