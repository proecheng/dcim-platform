<template>
  <div class="escalation-rule-page">
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
          <div class="stat-value types">{{ stats.levelCount }}</div>
          <div class="stat-label">告警级别数</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 工具栏 -->
    <el-card shadow="hover" class="toolbar-card">
      <el-form :inline="true" class="filter-form">
        <el-form-item label="告警级别">
          <el-select v-model="filters.sourceLevel" placeholder="全部" clearable style="width: 120px">
            <el-option label="紧急" value="critical" />
            <el-option label="重要" value="major" />
            <el-option label="次要" value="minor" />
            <el-option label="提示" value="info" />
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
        <el-button type="primary" @click="handleAdd">新增升级规则</el-button>
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
        <el-table-column label="适用告警级别" width="120" align="center">
          <template #default="{ row }">
            <el-tag :type="levelTagType(row.source_level)" size="small">
              {{ levelLabel(row.source_level) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="超时时间" width="110" align="center">
          <template #default="{ row }">
            {{ row.timeout_minutes }} 分钟
          </template>
        </el-table-column>
        <el-table-column label="目标升级级别" width="120" align="center">
          <template #default="{ row }">
            <el-tag :type="levelTagType(row.target_level)" size="small">
              {{ levelLabel(row.target_level) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="升级链层数" width="100" align="center">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ getChainLength(row) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="通知人数" width="90" align="center">
          <template #default="{ row }">
            <el-tag size="small">{{ (row.notify_user_ids || []).length }}</el-tag>
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
        <el-table-column prop="updated_at" label="最后更新" width="170" show-overflow-tooltip />
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

    <!-- 添加/编辑升级规则对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑升级规则' : '新增升级规则'"
      width="860px"
      top="4vh"
    >
      <el-form ref="formRef" :model="form" :rules="formRules" label-width="100px">
        <!-- 基本信息 -->
        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="规则名称" prop="ruleName">
              <el-input v-model="form.ruleName" placeholder="请输入规则名称" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="源告警级别" prop="sourceLevel">
              <el-select v-model="form.sourceLevel" style="width: 100%">
                <el-option label="紧急" value="critical" />
                <el-option label="重要" value="major" />
                <el-option label="次要" value="minor" />
                <el-option label="提示" value="info" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="目标级别" prop="targetLevel">
              <el-select v-model="form.targetLevel" style="width: 100%">
                <el-option label="紧急" value="critical" />
                <el-option label="重要" value="major" />
                <el-option label="次要" value="minor" />
                <el-option label="提示" value="info" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-divider content-position="left">升级链配置</el-divider>

        <!-- 升级链编辑器 -->
        <div class="chain-editor">
          <div v-if="!form.chain.length" class="chain-empty">
            暂无升级节点，请点击下方按钮添加
          </div>
          <div
            v-for="(node, index) in form.chain"
            :key="node.id"
            class="chain-node"
          >
            <div class="chain-node-header">
              <span class="chain-node-index">节点 {{ index + 1 }}</span>
              <div class="chain-node-actions">
                <el-button
                  :icon="ArrowUp"
                  size="small"
                  circle
                  :disabled="index === 0"
                  @click="moveNode(index, -1)"
                />
                <el-button
                  :icon="ArrowDown"
                  size="small"
                  circle
                  :disabled="index === form.chain.length - 1"
                  @click="moveNode(index, 1)"
                />
                <el-button
                  :icon="Delete"
                  size="small"
                  circle
                  type="danger"
                  @click="removeNode(index)"
                />
              </div>
            </div>
            <el-row :gutter="12" class="chain-node-body">
              <el-col :span="5">
                <div class="chain-field-label">超时时间(分钟)</div>
                <el-input-number
                  v-model="node.timeout_minutes"
                  :min="1"
                  :max="1440"
                  style="width: 100%"
                  size="default"
                />
              </el-col>
              <el-col :span="7">
                <div class="chain-field-label">通知方式</div>
                <el-select
                  v-model="node.notify_method"
                  multiple
                  placeholder="请选择"
                  style="width: 100%"
                >
                  <el-option label="站内信" value="internal" />
                  <el-option label="邮件" value="email" />
                  <el-option label="短信" value="sms" />
                </el-select>
              </el-col>
              <el-col :span="8">
                <div class="chain-field-label">通知人</div>
                <el-select
                  v-model="node.notify_user_ids"
                  multiple
                  filterable
                  placeholder="请选择通知人"
                  style="width: 100%"
                >
                  <el-option
                    v-for="u in userOptions"
                    :key="u.id"
                    :label="u.real_name || u.username"
                    :value="u.id"
                  />
                </el-select>
              </el-col>
              <el-col :span="4">
                <div class="chain-field-label">升级告警级别</div>
                <el-switch v-model="node.upgrade_level" />
              </el-col>
            </el-row>
            <!-- 节点间连线指示 -->
            <div v-if="index < form.chain.length - 1" class="chain-connector">
              <div class="chain-connector-line" />
              <div class="chain-connector-arrow">▼</div>
            </div>
          </div>
          <el-button
            type="primary"
            plain
            class="chain-add-btn"
            @click="addNode"
          >
            + 添加升级节点
          </el-button>
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
import { ArrowUp, ArrowDown, Delete } from '@element-plus/icons-vue'
import {
  getEscalations, createEscalation, updateEscalation, deleteEscalation, toggleEscalation,
  type AlarmEscalationInfo, type AlarmEscalationCreateParams
} from '@/api/modules/alarm'
import { getUserList, type UserInfo } from '@/api/modules/user'

// ==================== 升级链节点类型 ====================
interface EscalationNode {
  id: string
  timeout_minutes: number
  notify_method: string[]
  notify_user_ids: number[]
  upgrade_level: boolean
}

// ==================== 表单类型 ====================
interface EscalationForm {
  ruleName: string
  sourceLevel: string
  targetLevel: string
  chain: EscalationNode[]
}

// ==================== 状态 ====================
const loading = ref(false)
const submitting = ref(false)
const tableData = ref<AlarmEscalationInfo[]>([])
const userOptions = ref<UserInfo[]>([])

const stats = reactive({ total: 0, enabled: 0, disabled: 0, levelCount: 0 })
const pagination = reactive({ page: 1, pageSize: 20, total: 0 })
const filters = reactive({
  sourceLevel: '' as string,
  isEnabled: undefined as boolean | undefined
})

// ==================== 初始化 ====================
onMounted(() => {
  loadUserOptions()
  loadData()
})

async function loadUserOptions() {
  try {
    const result = await getUserList({ page: 1, page_size: 100 })
    userOptions.value = result.items || []
  } catch (e) {
    console.error('加载用户列表失败', e)
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
    if (filters.sourceLevel) params.source_level = filters.sourceLevel
    if (typeof filters.isEnabled === 'boolean') params.is_enabled = filters.isEnabled

    const result = await getEscalations(params)
    const items: AlarmEscalationInfo[] = result.items || result.data?.items || []
    tableData.value = items
    pagination.total = result.total || result.data?.total || 0

    // 统计
    stats.total = pagination.total
    stats.enabled = items.filter((r: AlarmEscalationInfo) => r.is_enabled).length
    stats.disabled = items.filter((r: AlarmEscalationInfo) => !r.is_enabled).length
    const levels = new Set(items.map((r: AlarmEscalationInfo) => r.source_level))
    stats.levelCount = levels.size
  } catch (e) {
    console.error('加载升级规则失败', e)
    ElMessage.error('加载升级规则列表失败')
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  filters.sourceLevel = ''
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

/** 从 escalation_chain 字段解析升级链长度（兼容旧 description） */
function getChainLength(row: AlarmEscalationInfo): number {
  const chainStr = row.escalation_chain || row.description
  if (!chainStr) return 1
  try {
    const chain = JSON.parse(chainStr)
    if (Array.isArray(chain)) return chain.length
  } catch {
    // 不是 JSON，说明只有单节点
  }
  return 1
}

// ==================== 启用/禁用 ====================
async function handleToggle(row: AlarmEscalationInfo): Promise<boolean> {
  try {
    await toggleEscalation(row.id)
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
async function handleDelete(row: AlarmEscalationInfo) {
  try {
    await ElMessageBox.confirm(
      `确认删除升级规则「${row.rule_name}」？`,
      '删除确认',
      { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' }
    )
    await deleteEscalation(row.id)
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

const form = reactive<EscalationForm>({
  ruleName: '',
  sourceLevel: 'minor',
  targetLevel: 'major',
  chain: []
})

const formRules = {
  ruleName: [{ required: true, message: '请输入规则名称', trigger: 'blur' }],
  sourceLevel: [{ required: true, message: '请选择源告警级别', trigger: 'change' }],
  targetLevel: [{ required: true, message: '请选择目标升级级别', trigger: 'change' }]
}

function createEmptyNode(): EscalationNode {
  return {
    id: crypto.randomUUID(),
    timeout_minutes: 30,
    notify_method: ['internal'],
    notify_user_ids: [],
    upgrade_level: false
  }
}

function handleAdd() {
  isEdit.value = false
  editingId.value = null
  form.ruleName = ''
  form.sourceLevel = 'minor'
  form.targetLevel = 'major'
  form.chain = [createEmptyNode()]
  dialogVisible.value = true
}

function handleEdit(row: AlarmEscalationInfo) {
  isEdit.value = true
  editingId.value = row.id
  form.ruleName = row.rule_name
  form.sourceLevel = row.source_level
  form.targetLevel = row.target_level

  // 从 escalation_chain 反序列化升级链（兼容旧 description）
  let chain: EscalationNode[] = []
  const chainStr = row.escalation_chain || row.description
  if (chainStr) {
    try {
      const parsed = JSON.parse(chainStr)
      if (Array.isArray(parsed)) {
        chain = parsed.map((n: Record<string, unknown>) => ({
          id: (n.id as string) || crypto.randomUUID(),
          timeout_minutes: (n.timeout_minutes as number) || row.timeout_minutes,
          notify_method: (n.notify_method as string[]) || ['internal'],
          notify_user_ids: (n.notify_user_ids as number[]) || [],
          upgrade_level: (n.upgrade_level as boolean) || false
        }))
      }
    } catch {
      // 不是 JSON
    }
  }

  // 如果没有解析到链，用顶层字段构建单节点
  if (!chain.length) {
    chain = [{
      id: crypto.randomUUID(),
      timeout_minutes: row.timeout_minutes,
      notify_method: ['internal'],
      notify_user_ids: row.notify_user_ids || [],
      upgrade_level: false
    }]
  }

  form.chain = chain
  dialogVisible.value = true
}

// ==================== 升级链节点操作 ====================
function addNode() {
  form.chain.push(createEmptyNode())
}

function removeNode(index: number) {
  form.chain.splice(index, 1)
}

function moveNode(index: number, direction: number) {
  const target = index + direction
  if (target < 0 || target >= form.chain.length) return
  const temp = form.chain[index]
  form.chain[index] = form.chain[target]
  form.chain[target] = temp
}

// ==================== 提交表单 ====================
async function submitForm() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  if (!form.chain.length) {
    ElMessage.warning('请至少添加一个升级节点')
    return
  }

  submitting.value = true
  try {
    // 合并所有节点的通知人
    const allUserIds = [...new Set(form.chain.flatMap(n => n.notify_user_ids))]
    // 取第一个节点的超时时间作为顶层字段
    const firstTimeout = form.chain[0].timeout_minutes

    const data: AlarmEscalationCreateParams = {
      rule_name: form.ruleName,
      source_level: form.sourceLevel,
      timeout_minutes: firstTimeout,
      target_level: form.targetLevel,
      notify_user_ids: allUserIds,
      is_enabled: true,
      description: '',
      escalation_chain: JSON.stringify(form.chain)
    }

    if (isEdit.value && editingId.value) {
      await updateEscalation(editingId.value, data)
      ElMessage.success('更新成功')
    } else {
      await createEscalation(data)
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
</script>

<style lang="scss" scoped>
@use '@/styles/_mixins-25d' as d25;

.escalation-rule-page {
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

/* 升级链编辑器 */
.chain-editor {
  padding: 16px;
  background: var(--el-fill-color-lighter);
  border-radius: 8px;
  border: 1px dashed var(--el-border-color);
  min-height: 80px;
}

.chain-empty {
  text-align: center;
  color: var(--el-text-color-placeholder);
  font-size: 13px;
  padding: 24px 0;
}

.chain-node {
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  padding: 12px 16px;
  margin-bottom: 4px;
  transition: box-shadow 0.3s ease;

  &:hover {
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  }
}

.chain-node-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.chain-node-index {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-color-primary);
}

.chain-node-actions {
  display: flex;
  gap: 4px;
}

.chain-node-body {
  .chain-field-label {
    font-size: 12px;
    color: var(--el-text-color-secondary);
    margin-bottom: 4px;
  }
}

.chain-connector {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 2px 0;
}

.chain-connector-line {
  width: 2px;
  height: 8px;
  background: var(--el-color-primary-light-5);
}

.chain-connector-arrow {
  color: var(--el-color-primary);
  font-size: 12px;
  line-height: 1;
}

.chain-add-btn {
  width: 100%;
  margin-top: 12px;
  border-style: dashed;
}
</style>
