<template>
  <div class="inspection-page">
    <el-card shadow="hover" class="main-card">
      <el-tabs v-model="activeTab" @tab-change="handleTabChange">
        <!-- 巡检计划 -->
        <el-tab-pane label="巡检计划" name="plan">
          <div class="tab-toolbar">
            <el-input
              v-model="planSearch"
              placeholder="搜索计划名称"
              clearable
              style="width: 200px"
              @clear="loadPlanList"
              @keyup.enter="loadPlanList"
            />
            <el-select v-model="planActiveFilter" placeholder="启用状态" clearable style="width: 120px" @change="loadPlanList">
              <el-option label="全部" value="" />
              <el-option label="启用" :value="true" />
              <el-option label="停用" :value="false" />
            </el-select>
            <el-button type="primary" @click="showPlanDialog()">新建计划</el-button>
          </div>
          <el-table :data="planList" stripe border v-loading="planLoading" empty-text="暂无巡检计划数据">
            <el-table-column prop="name" label="计划名称" min-width="150" show-overflow-tooltip />
            <el-table-column label="巡检频率" width="100">
              <template #default="{ row }">
                {{ frequencyMap[row.frequency] || row.frequency || '--' }}
              </template>
            </el-table-column>
            <el-table-column label="巡检位置" min-width="140" show-overflow-tooltip>
              <template #default="{ row }">{{ row.location || '--' }}</template>
            </el-table-column>
            <el-table-column label="负责人" width="100">
              <template #default="{ row }">{{ row.assignee || '--' }}</template>
            </el-table-column>
            <el-table-column label="启用状态" width="90" align="center">
              <template #default="{ row }">
                <el-switch v-model="row.is_active" @change="handleToggleActive(row)" />
              </template>
            </el-table-column>
            <el-table-column label="创建时间" width="170">
              <template #default="{ row }">{{ formatDT(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="200" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" link @click="showPlanDialog(row)">编辑</el-button>
                <el-button type="success" link @click="handleGenerateTask(row)">生成任务</el-button>
                <el-button type="danger" link @click="confirmDeletePlan(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- 巡检任务 -->
        <el-tab-pane label="巡检任务" name="task">
          <div class="tab-toolbar">
            <el-select v-model="taskStatusFilter" placeholder="任务状态" clearable style="width: 130px" @change="loadTaskList">
              <el-option label="全部" value="" />
              <el-option label="待巡检" value="待巡检" />
              <el-option label="巡检中" value="巡检中" />
              <el-option label="已完成" value="已完成" />
              <el-option label="已逾期" value="已逾期" />
            </el-select>
            <el-select v-model="taskPlanFilter" placeholder="关联计划" clearable style="width: 180px" @change="loadTaskList">
              <el-option label="全部" value="" />
              <el-option v-for="p in planList" :key="p.id" :label="p.name" :value="p.id" />
            </el-select>
          </div>
          <el-table :data="taskList" stripe border v-loading="taskLoading" empty-text="暂无巡检任务数据">
            <el-table-column prop="task_no" label="任务编号" width="160" />
            <el-table-column label="关联计划" min-width="140" show-overflow-tooltip>
              <template #default="{ row }">{{ row.plan_name || '--' }}</template>
            </el-table-column>
            <el-table-column label="状态" width="100" align="center">
              <template #default="{ row }">
                <el-tag :type="statusTagType[row.status] || 'info'" size="small">{{ row.status }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="执行人" width="100">
              <template #default="{ row }">{{ row.assignee || '--' }}</template>
            </el-table-column>
            <el-table-column label="计划日期" width="170">
              <template #default="{ row }">{{ formatDT(row.scheduled_date) }}</template>
            </el-table-column>
            <el-table-column label="开始时间" width="170">
              <template #default="{ row }">{{ formatDT(row.started_at) }}</template>
            </el-table-column>
            <el-table-column label="完成时间" width="170">
              <template #default="{ row }">{{ formatDT(row.completed_at) }}</template>
            </el-table-column>
            <el-table-column label="异常数" width="80" align="center">
              <template #default="{ row }">
                <el-tag v-if="row.abnormal_count > 0" type="danger" size="small">{{ row.abnormal_count }}</el-tag>
                <span v-else>{{ row.abnormal_count || 0 }}</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="180" fixed="right">
              <template #default="{ row }">
                <el-button v-if="row.status === '待巡检'" type="success" link @click="handleStartTask(row)">开始巡检</el-button>
                <el-button v-if="row.status === '巡检中'" type="warning" link @click="showCompleteDialog(row)">完成巡检</el-button>
                <el-button v-if="row.status !== '已完成'" type="danger" link @click="confirmDeleteTask(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 新建/编辑计划对话框 -->
    <el-dialog append-to-body v-model="planDialogVisible" :title="editingPlan ? '编辑巡检计划' : '新建巡检计划'" width="600px">
      <el-form ref="planFormRef" :model="planForm" :rules="planRules" label-width="100px">
        <el-form-item label="计划名称" prop="name">
          <el-input v-model="planForm.name" placeholder="请输入计划名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="planForm.description" type="textarea" :rows="2" placeholder="请输入计划描述" />
        </el-form-item>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="巡检频率">
              <el-select v-model="planForm.frequency" placeholder="请选择" style="width: 100%">
                <el-option label="每日" value="daily" />
                <el-option label="每周" value="weekly" />
                <el-option label="每月" value="monthly" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="负责人">
              <el-input v-model="planForm.assignee" placeholder="请输入负责人" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="巡检位置">
          <el-input v-model="planForm.location" placeholder="请输入巡检位置" />
        </el-form-item>
        <el-form-item label="检查项目">
          <el-input v-model="planForm.check_items" type="textarea" :rows="3" placeholder="请输入检查项目（JSON格式）" />
        </el-form-item>
        <el-form-item label="启用状态">
          <el-switch v-model="planForm.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="planDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitPlanForm">确定</el-button>
      </template>
    </el-dialog>

    <!-- 完成巡检对话框 -->
    <el-dialog append-to-body v-model="completeDialogVisible" title="完成巡检任务" width="500px">
      <el-form label-width="80px">
        <el-form-item label="巡检结果">
          <el-input v-model="completeForm.result" type="textarea" :rows="4" placeholder="请输入巡检结果" />
        </el-form-item>
        <el-form-item label="异常数量">
          <el-input-number v-model="completeForm.abnormal_count" :min="0" :max="999" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="completeDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitComplete">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import {
  getInspectionPlans, createInspectionPlan, updateInspectionPlan,
  deleteInspectionPlan, generateInspectionTask,
  getInspectionTasks, startInspectionTask, completeInspectionTask,
  deleteInspectionTask
} from '@/api/modules/operation'
import type { InspectionPlan, InspectionPlanCreate, InspectionTask } from '@/api/modules/operation'

// 常量
const frequencyMap: Record<string, string> = { daily: '每日', weekly: '每周', monthly: '每月' }
type TagType = 'info' | 'warning' | 'success' | 'danger' | 'primary'
const statusTagType: Record<string, TagType> = { '待巡检': 'info', '巡检中': 'warning', '已完成': 'success', '已逾期': 'danger' }

// 状态
const activeTab = ref('plan')
const planLoading = ref(false)
const taskLoading = ref(false)
const submitting = ref(false)

// 列表
const planList = ref<InspectionPlan[]>([])
const taskList = ref<InspectionTask[]>([])

// 过滤
const planSearch = ref('')
const planActiveFilter = ref<boolean | string>('')
const taskStatusFilter = ref('')
const taskPlanFilter = ref<number | string>('')

// 计划对话框
const planDialogVisible = ref(false)
const editingPlan = ref<InspectionPlan | null>(null)
const planFormRef = ref()
const planForm = reactive<InspectionPlanCreate>({
  name: '',
  description: '',
  frequency: 'daily',
  location: '',
  check_items: '',
  assignee: '',
  is_active: true
})
const planRules = { name: [{ required: true, message: '请输入计划名称', trigger: 'blur' }] }

// 完成对话框
const completeDialogVisible = ref(false)
const completingTaskId = ref<number>(0)
const completeForm = reactive({ result: '', abnormal_count: 0 })

// 初始化
onMounted(() => { loadPlanList() })

function handleTabChange(tab: string) {
  if (tab === 'plan') loadPlanList()
  else loadTaskList()
}

// ==================== 巡检计划 ====================

async function loadPlanList() {
  planLoading.value = true
  try {
    const params: Record<string, any> = {}
    if (planSearch.value) params.name = planSearch.value
    if (planActiveFilter.value !== '') params.is_active = planActiveFilter.value
    const res = await getInspectionPlans(params)
    planList.value = Array.isArray(res.data) ? res.data : []
  } catch { ElMessage.error('加载巡检计划失败') }
  finally { planLoading.value = false }
}

function showPlanDialog(row?: InspectionPlan) {
  editingPlan.value = row || null
  if (row) {
    Object.assign(planForm, {
      name: row.name,
      description: row.description || '',
      frequency: row.frequency || 'daily',
      location: row.location || '',
      check_items: row.check_items || '',
      assignee: row.assignee || '',
      is_active: row.is_active
    })
  } else {
    Object.assign(planForm, {
      name: '', description: '', frequency: 'daily',
      location: '', check_items: '', assignee: '', is_active: true
    })
  }
  planDialogVisible.value = true
}

async function submitPlanForm() {
  const valid = await planFormRef.value?.validate()
  if (!valid) return
  submitting.value = true
  try {
    const data: InspectionPlanCreate = { ...planForm }
    if (editingPlan.value) {
      await updateInspectionPlan(editingPlan.value.id, data)
      ElMessage.success('更新成功')
    } else {
      await createInspectionPlan(data)
      ElMessage.success('创建成功')
    }
    planDialogVisible.value = false
    loadPlanList()
  } catch { ElMessage.error('操作失败') }
  finally { submitting.value = false }
}

async function handleToggleActive(row: InspectionPlan) {
  try {
    await updateInspectionPlan(row.id, { is_active: row.is_active })
    ElMessage.success(row.is_active ? '已启用' : '已停用')
  } catch {
    row.is_active = !row.is_active
    ElMessage.error('更新失败')
  }
}

async function handleGenerateTask(row: InspectionPlan) {
  try {
    await generateInspectionTask(row.id)
    ElMessage.success('已生成巡检任务')
    if (activeTab.value === 'task') loadTaskList()
  } catch { ElMessage.error('生成任务失败') }
}

function confirmDeletePlan(row: InspectionPlan) {
  ElMessageBox.confirm(`确定删除巡检计划「${row.name}」？`, '删除确认', { type: 'warning' })
    .then(async () => {
      await deleteInspectionPlan(row.id)
      ElMessage.success('删除成功')
      loadPlanList()
    }).catch(() => {})
}

// ==================== 巡检任务 ====================

async function loadTaskList() {
  taskLoading.value = true
  try {
    const params: Record<string, any> = {}
    if (taskStatusFilter.value) params.status = taskStatusFilter.value
    if (taskPlanFilter.value) params.plan_id = taskPlanFilter.value
    const res = await getInspectionTasks(params)
    taskList.value = Array.isArray(res.data) ? res.data : []
  } catch { ElMessage.error('加载巡检任务失败') }
  finally { taskLoading.value = false }
}

async function handleStartTask(row: InspectionTask) {
  try {
    await startInspectionTask(row.id)
    ElMessage.success('巡检已开始')
    loadTaskList()
  } catch { ElMessage.error('开始巡检失败') }
}

function showCompleteDialog(row: InspectionTask) {
  completingTaskId.value = row.id
  completeForm.result = ''
  completeForm.abnormal_count = 0
  completeDialogVisible.value = true
}

async function submitComplete() {
  submitting.value = true
  try {
    await completeInspectionTask(completingTaskId.value, completeForm.result || undefined, completeForm.abnormal_count)
    ElMessage.success('巡检已完成')
    completeDialogVisible.value = false
    loadTaskList()
  } catch { ElMessage.error('完成巡检失败') }
  finally { submitting.value = false }
}

function confirmDeleteTask(row: InspectionTask) {
  ElMessageBox.confirm(`确定删除巡检任务「${row.task_no}」？`, '删除确认', { type: 'warning' })
    .then(async () => {
      await deleteInspectionTask(row.id)
      ElMessage.success('删除成功')
      loadTaskList()
    }).catch(() => {})
}

// 格式化日期
function formatDT(s?: string) {
  if (!s) return '--'
  return new Date(s).toLocaleString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit'
  })
}
</script>

<style scoped lang="scss">
@use '@/styles/_mixins-25d' as *;

.inspection-page {
  @include page-list;

  .main-card {
    background: var(--bg-card-solid);
    border-color: var(--border-color);

    :deep(.el-tabs__header) {
      margin-bottom: 20px;
      background-color: var(--bg-tertiary);
      border-bottom: 1px solid var(--border-color);
      padding: 0 16px;
    }

    :deep(.el-tabs__nav-wrap::after) { background-color: transparent; }

    :deep(.el-tabs__item) {
      color: var(--text-secondary);
      height: 48px;
      line-height: 48px;
      &.is-active { color: var(--accent-color); font-weight: 500; }
      &:hover { color: var(--text-primary); }
    }

    :deep(.el-tabs__active-bar) { background-color: var(--accent-color); }
    :deep(.el-tabs__content) { padding: 0 16px 16px; }
  }

  .tab-toolbar {
    margin-bottom: 16px;
    display: flex;
    gap: 12px;
    align-items: center;
  }

  :deep(.el-table) {
    background: transparent;
    th.el-table__cell { background: var(--bg-card); color: var(--text-primary); border-color: var(--border-color); }
    td.el-table__cell { border-color: var(--border-color); }
    tr { background: var(--bg-card); &:hover > td.el-table__cell { background: rgba(255,255,255,0.05); } }
    .el-table__body tr.el-table__row--striped td.el-table__cell { background: rgba(255,255,255,0.02); }
  }

  :deep(.el-dialog) {
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    .el-dialog__header { border-bottom: 1px solid var(--border-color); }
    .el-dialog__title { color: var(--text-primary); }
    .el-dialog__footer { border-top: 1px solid var(--border-color); }
  }

  :deep(.el-form-item__label) { color: var(--text-secondary); }
  :deep(.el-input__wrapper), :deep(.el-textarea__inner) {
    background: rgba(255,255,255,0.05);
    border-color: var(--border-color);
    &:hover { border-color: var(--accent-color); }
  }
  :deep(.el-input__inner), :deep(.el-textarea__inner) {
    color: var(--text-primary);
    &::placeholder { color: var(--text-secondary); }
  }
  :deep(.el-switch) { --el-switch-on-color: var(--accent-color); }
}
</style>
