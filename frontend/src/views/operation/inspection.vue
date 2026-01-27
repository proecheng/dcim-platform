<template>
  <div class="inspection-page">
    <!-- 主内容区域 -->
    <el-card shadow="hover" class="main-card">
      <el-tabs v-model="activeTab" @tab-change="handleTabChange">
        <!-- 巡检计划标签页 -->
        <el-tab-pane label="巡检计划" name="plan">
          <div class="tab-toolbar">
            <el-button type="primary" :icon="Plus" @click="showPlanDialog()">新建计划</el-button>
          </div>
          <el-table :data="planList" stripe border v-loading="planLoading">
            <el-table-column prop="plan_name" label="计划名称" min-width="150" show-overflow-tooltip />
            <el-table-column prop="frequency" label="频率" width="120">
              <template #default="{ row }">
                {{ getFrequencyLabel(row.frequency) }}
              </template>
            </el-table-column>
            <el-table-column label="位置" min-width="150">
              <template #default="{ row }">
                {{ row.locations?.join(', ') || '--' }}
              </template>
            </el-table-column>
            <el-table-column prop="inspector" label="巡检人" width="100">
              <template #default="{ row }">
                {{ row.inspector || '--' }}
              </template>
            </el-table-column>
            <el-table-column prop="is_active" label="启用状态" width="100">
              <template #default="{ row }">
                <el-switch
                  v-model="row.is_active"
                  @change="handleToggleActive(row)"
                />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="150" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" link @click="showPlanDialog(row)">编辑</el-button>
                <el-button type="danger" link @click="confirmDeletePlan(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- 巡检任务标签页 -->
        <el-tab-pane label="巡检任务" name="task">
          <div class="tab-toolbar">
            <el-button type="primary" :icon="Plus" @click="showTaskDialog()">创建任务</el-button>
          </div>
          <el-table :data="taskList" stripe border v-loading="taskLoading">
            <el-table-column prop="task_no" label="任务编号" width="140" />
            <el-table-column prop="plan_name" label="计划名称" min-width="150" show-overflow-tooltip>
              <template #default="{ row }">
                {{ row.plan_name || '--' }}
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="getTaskStatusType(row.status)" size="small">
                  {{ getTaskStatusLabel(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="inspector" label="巡检人" width="100">
              <template #default="{ row }">
                {{ row.inspector || '--' }}
              </template>
            </el-table-column>
            <el-table-column prop="scheduled_time" label="计划时间" width="170">
              <template #default="{ row }">
                {{ formatDateTime(row.scheduled_time) }}
              </template>
            </el-table-column>
            <el-table-column label="异常数量" width="100">
              <template #default="{ row }">
                <el-tag v-if="row.results?.abnormal_count > 0" type="danger" size="small">
                  {{ row.results?.abnormal_count || 0 }}
                </el-tag>
                <span v-else>{{ row.results?.abnormal_count || 0 }}</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="180" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" link @click="showTaskDetailDialog(row)">详情</el-button>
                <el-button
                  v-if="row.status === 'pending'"
                  type="success"
                  link
                  @click="handleStartTask(row)"
                >
                  开始
                </el-button>
                <el-button
                  v-if="row.status === 'in_progress'"
                  type="warning"
                  link
                  @click="showCompleteTaskDialog(row)"
                >
                  完成
                </el-button>
                <el-button type="danger" link @click="confirmDeleteTask(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 新建/编辑计划对话框 -->
    <el-dialog
      v-model="planDialogVisible"
      :title="isEditPlan ? '编辑巡检计划' : '新建巡检计划'"
      width="600px"
      destroy-on-close
    >
      <el-form
        ref="planFormRef"
        :model="planForm"
        :rules="planRules"
        label-width="100px"
      >
        <el-form-item label="计划名称" prop="plan_name">
          <el-input v-model="planForm.plan_name" placeholder="请输入计划名称" />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input
            v-model="planForm.description"
            type="textarea"
            :rows="3"
            placeholder="请输入计划描述"
          />
        </el-form-item>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="频率" prop="frequency">
              <el-select v-model="planForm.frequency" placeholder="请选择频率" style="width: 100%;">
                <el-option label="每日" value="daily" />
                <el-option label="每周" value="weekly" />
                <el-option label="每月" value="monthly" />
                <el-option label="每季度" value="quarterly" />
                <el-option label="每年" value="yearly" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="巡检人" prop="inspector">
              <el-input v-model="planForm.inspector" placeholder="请输入巡检人" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="位置" prop="location">
          <el-input v-model="planForm.location" placeholder="请输入位置（多个用逗号分隔）" />
        </el-form-item>
        <el-form-item label="检查项目" prop="check_items">
          <el-input
            v-model="planForm.check_items"
            type="textarea"
            :rows="4"
            placeholder="请输入检查项目（每行一项）"
          />
        </el-form-item>
        <el-form-item label="启用状态" prop="is_active">
          <el-switch v-model="planForm.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="planDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitPlanForm" :loading="submitting">确定</el-button>
      </template>
    </el-dialog>

    <!-- 创建任务对话框 -->
    <el-dialog
      v-model="taskDialogVisible"
      title="创建巡检任务"
      width="500px"
      destroy-on-close
    >
      <el-form
        ref="taskFormRef"
        :model="taskForm"
        :rules="taskRules"
        label-width="100px"
      >
        <el-form-item label="巡检计划" prop="plan_id">
          <el-select v-model="taskForm.plan_id" placeholder="请选择巡检计划" style="width: 100%;">
            <el-option
              v-for="plan in activePlanList"
              :key="plan.id"
              :label="plan.plan_name"
              :value="plan.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="巡检人" prop="inspector">
          <el-input v-model="taskForm.inspector" placeholder="请输入巡检人" />
        </el-form-item>
        <el-form-item label="计划时间" prop="scheduled_time">
          <el-date-picker
            v-model="taskForm.scheduled_time"
            type="datetime"
            placeholder="请选择计划时间"
            style="width: 100%;"
            format="YYYY-MM-DD HH:mm"
            value-format="YYYY-MM-DDTHH:mm:ss"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="taskDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitTaskForm" :loading="submitting">确定</el-button>
      </template>
    </el-dialog>

    <!-- 任务详情对话框 -->
    <el-dialog
      v-model="taskDetailDialogVisible"
      title="任务详情"
      width="600px"
      destroy-on-close
    >
      <el-descriptions :column="2" border>
        <el-descriptions-item label="任务编号">{{ currentTask?.task_no }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="getTaskStatusType(currentTask?.status)" size="small">
            {{ getTaskStatusLabel(currentTask?.status) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="计划名称">{{ currentTask?.plan_name || '--' }}</el-descriptions-item>
        <el-descriptions-item label="巡检人">{{ currentTask?.inspector || '--' }}</el-descriptions-item>
        <el-descriptions-item label="计划时间">{{ formatDateTime(currentTask?.scheduled_time) }}</el-descriptions-item>
        <el-descriptions-item label="开始时间">{{ formatDateTime(currentTask?.started_at) }}</el-descriptions-item>
        <el-descriptions-item label="完成时间">{{ formatDateTime(currentTask?.completed_at) }}</el-descriptions-item>
        <el-descriptions-item label="异常数量">
          <el-tag v-if="(currentTask?.results?.abnormal_count || 0) > 0" type="danger" size="small">
            {{ currentTask?.results?.abnormal_count || 0 }}
          </el-tag>
          <span v-else>{{ currentTask?.results?.abnormal_count || 0 }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="备注" :span="2">{{ currentTask?.remarks || '--' }}</el-descriptions-item>
      </el-descriptions>

      <!-- 检查项目列表 -->
      <div class="checklist-section" v-if="currentTask?.checklist?.length">
        <div class="section-title">检查项目</div>
        <el-table :data="currentTask.checklist" stripe border size="small">
          <el-table-column type="index" label="序号" width="60" />
          <el-table-column label="检查项">
            <template #default="{ row }">
              {{ row }}
            </template>
          </el-table-column>
          <el-table-column label="结果" width="100">
            <template #default="{ $index }">
              <el-tag
                v-if="currentTask?.results?.items?.[$index]"
                :type="currentTask.results.items[$index] === 'normal' ? 'success' : 'danger'"
                size="small"
              >
                {{ currentTask.results.items[$index] === 'normal' ? '正常' : '异常' }}
              </el-tag>
              <span v-else>--</span>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <template #footer>
        <el-button @click="taskDetailDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 完成任务对话框 -->
    <el-dialog
      v-model="completeTaskDialogVisible"
      title="完成巡检任务"
      width="600px"
      destroy-on-close
    >
      <div class="complete-task-content">
        <div class="section-title">检查项目结果</div>
        <el-table :data="checklistItems" stripe border size="small">
          <el-table-column type="index" label="序号" width="60" />
          <el-table-column prop="item" label="检查项" />
          <el-table-column label="结果" width="150">
            <template #default="{ row }">
              <el-radio-group v-model="row.result">
                <el-radio value="normal">正常</el-radio>
                <el-radio value="abnormal">异常</el-radio>
              </el-radio-group>
            </template>
          </el-table-column>
        </el-table>

        <el-form
          ref="completeTaskFormRef"
          :model="completeTaskForm"
          label-width="80px"
          style="margin-top: 20px;"
        >
          <el-form-item label="备注">
            <el-input
              v-model="completeTaskForm.remarks"
              type="textarea"
              :rows="3"
              placeholder="请输入备注（可选）"
            />
          </el-form-item>
        </el-form>
      </div>
      <template #footer>
        <el-button @click="completeTaskDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitCompleteTask" :loading="submitting">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import {
  getInspectionPlans,
  createInspectionPlan,
  updateInspectionPlan,
  deleteInspectionPlan,
  getInspectionTasks,
  createInspectionTask,
  deleteInspectionTask,
  startInspectionTask,
  completeInspectionTask,
  type InspectionPlan,
  type InspectionTask,
  type InspectionStatus
} from '@/api/modules/operation'

// 类型定义
type TagType = 'success' | 'warning' | 'danger' | 'info' | 'primary'

interface ChecklistItem {
  item: string
  result: 'normal' | 'abnormal'
}

// 数据状态
const planLoading = ref(false)
const taskLoading = ref(false)
const submitting = ref(false)
const activeTab = ref('plan')

// 列表数据
const planList = ref<InspectionPlan[]>([])
const taskList = ref<InspectionTask[]>([])

// 计算活跃计划列表
const activePlanList = computed(() => planList.value.filter(p => p.is_active))

// 对话框状态
const isEditPlan = ref(false)
const currentPlanId = ref<number | null>(null)
const currentTask = ref<InspectionTask | null>(null)

// 巡检计划对话框
const planDialogVisible = ref(false)
const planFormRef = ref<FormInstance>()
const planForm = reactive({
  plan_name: '',
  description: '',
  frequency: 'daily',
  location: '',
  check_items: '',
  inspector: '',
  is_active: true
})

const planRules = {
  plan_name: [{ required: true, message: '请输入计划名称', trigger: 'blur' }],
  frequency: [{ required: true, message: '请选择频率', trigger: 'change' }]
}

// 创建任务对话框
const taskDialogVisible = ref(false)
const taskFormRef = ref<FormInstance>()
const taskForm = reactive({
  plan_id: null as number | null,
  inspector: '',
  scheduled_time: ''
})

const taskRules = {
  plan_id: [{ required: true, message: '请选择巡检计划', trigger: 'change' }],
  scheduled_time: [{ required: true, message: '请选择计划时间', trigger: 'change' }]
}

// 任务详情对话框
const taskDetailDialogVisible = ref(false)

// 完成任务对话框
const completeTaskDialogVisible = ref(false)
const checklistItems = ref<ChecklistItem[]>([])
const completeTaskForm = reactive({
  remarks: ''
})

// 初始化加载
onMounted(() => {
  loadPlanList()
})

// 标签页切换
function handleTabChange(tab: string) {
  if (tab === 'plan') {
    loadPlanList()
  } else if (tab === 'task') {
    loadTaskList()
  }
}

// ==================== 巡检计划 ====================

// 加载计划列表
async function loadPlanList() {
  planLoading.value = true
  try {
    const res = await getInspectionPlans()
    if (res.data) {
      const data = res.data as any
      planList.value = Array.isArray(data) ? data : data.items || []
    }
  } catch (e) {
    console.error('加载巡检计划列表失败', e)
    ElMessage.error('加载巡检计划列表失败')
  } finally {
    planLoading.value = false
  }
}

// 显示计划对话框
function showPlanDialog(row?: InspectionPlan) {
  isEditPlan.value = !!row
  currentPlanId.value = row?.id || null
  if (row) {
    Object.assign(planForm, {
      plan_name: row.plan_name,
      description: row.description || '',
      frequency: row.frequency,
      location: row.locations?.join(', ') || '',
      check_items: row.checklist?.join('\n') || '',
      inspector: row.inspector || '',
      is_active: row.is_active
    })
  } else {
    Object.assign(planForm, {
      plan_name: '',
      description: '',
      frequency: 'daily',
      location: '',
      check_items: '',
      inspector: '',
      is_active: true
    })
  }
  planDialogVisible.value = true
}

// 提交计划表单
async function submitPlanForm() {
  const valid = await planFormRef.value?.validate()
  if (!valid) return

  submitting.value = true
  try {
    const locations = planForm.location ? planForm.location.split(/[,，]/).map(s => s.trim()).filter(Boolean) : []
    const checklist = planForm.check_items ? planForm.check_items.split('\n').map(s => s.trim()).filter(Boolean) : []

    const data = {
      plan_name: planForm.plan_name,
      description: planForm.description || undefined,
      plan_type: 'routine',
      frequency: planForm.frequency,
      start_date: new Date().toISOString().split('T')[0],
      locations: locations.length > 0 ? locations : undefined,
      checklist: checklist.length > 0 ? checklist : undefined,
      inspector: planForm.inspector || undefined,
      is_active: planForm.is_active
    }

    if (isEditPlan.value && currentPlanId.value) {
      await updateInspectionPlan(currentPlanId.value, data)
      ElMessage.success('更新成功')
    } else {
      await createInspectionPlan(data)
      ElMessage.success('创建成功')
    }
    planDialogVisible.value = false
    loadPlanList()
  } catch (e) {
    console.error('操作失败', e)
    ElMessage.error('操作失败')
  } finally {
    submitting.value = false
  }
}

// 切换启用状态
async function handleToggleActive(row: InspectionPlan) {
  try {
    await updateInspectionPlan(row.id, { is_active: row.is_active })
    ElMessage.success(row.is_active ? '已启用' : '已禁用')
  } catch (e) {
    console.error('更新状态失败', e)
    ElMessage.error('更新状态失败')
    row.is_active = !row.is_active
  }
}

// 确认删除计划
function confirmDeletePlan(row: InspectionPlan) {
  ElMessageBox.confirm(
    `确定要删除巡检计划 "${row.plan_name}" 吗？`,
    '删除确认',
    { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
  ).then(async () => {
    try {
      await deleteInspectionPlan(row.id)
      ElMessage.success('删除成功')
      loadPlanList()
    } catch (e) {
      console.error('删除失败', e)
      ElMessage.error('删除失败')
    }
  }).catch(() => {})
}

// ==================== 巡检任务 ====================

// 加载任务列表
async function loadTaskList() {
  taskLoading.value = true
  try {
    const res = await getInspectionTasks()
    if (res.data) {
      const data = res.data as any
      taskList.value = Array.isArray(data) ? data : data.items || []
    }
  } catch (e) {
    console.error('加载巡检任务列表失败', e)
    ElMessage.error('加载巡检任务列表失败')
  } finally {
    taskLoading.value = false
  }
}

// 显示创建任务对话框
function showTaskDialog() {
  // 先确保已加载计划列表
  if (planList.value.length === 0) {
    loadPlanList()
  }
  Object.assign(taskForm, {
    plan_id: null,
    inspector: '',
    scheduled_time: ''
  })
  taskDialogVisible.value = true
}

// 提交创建任务表单
async function submitTaskForm() {
  const valid = await taskFormRef.value?.validate()
  if (!valid) return

  if (!taskForm.plan_id) return

  submitting.value = true
  try {
    const data = {
      plan_id: taskForm.plan_id,
      inspector: taskForm.inspector || undefined,
      scheduled_time: taskForm.scheduled_time
    }

    await createInspectionTask(data)
    ElMessage.success('创建成功')
    taskDialogVisible.value = false
    loadTaskList()
  } catch (e) {
    console.error('创建任务失败', e)
    ElMessage.error('创建任务失败')
  } finally {
    submitting.value = false
  }
}

// 显示任务详情对话框
function showTaskDetailDialog(row: InspectionTask) {
  currentTask.value = row
  taskDetailDialogVisible.value = true
}

// 开始任务
async function handleStartTask(row: InspectionTask) {
  try {
    await startInspectionTask(row.id)
    ElMessage.success('任务已开始')
    loadTaskList()
  } catch (e) {
    console.error('开始任务失败', e)
    ElMessage.error('开始任务失败')
  }
}

// 显示完成任务对话框
function showCompleteTaskDialog(row: InspectionTask) {
  currentTask.value = row
  checklistItems.value = (row.checklist || []).map(item => ({
    item,
    result: 'normal' as const
  }))
  completeTaskForm.remarks = ''
  completeTaskDialogVisible.value = true
}

// 提交完成任务
async function submitCompleteTask() {
  if (!currentTask.value) return

  submitting.value = true
  try {
    const abnormalCount = checklistItems.value.filter(item => item.result === 'abnormal').length
    const results = {
      items: checklistItems.value.map(item => item.result),
      abnormal_count: abnormalCount
    }

    await completeInspectionTask(currentTask.value.id, results, completeTaskForm.remarks || undefined)
    ElMessage.success('任务已完成')
    completeTaskDialogVisible.value = false
    loadTaskList()
  } catch (e) {
    console.error('完成任务失败', e)
    ElMessage.error('完成任务失败')
  } finally {
    submitting.value = false
  }
}

// 确认删除任务
function confirmDeleteTask(row: InspectionTask) {
  ElMessageBox.confirm(
    `确定要删除巡检任务 "${row.task_no}" 吗？`,
    '删除确认',
    { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
  ).then(async () => {
    try {
      await deleteInspectionTask(row.id)
      ElMessage.success('删除成功')
      loadTaskList()
    } catch (e) {
      console.error('删除失败', e)
      ElMessage.error('删除失败')
    }
  }).catch(() => {})
}

// ==================== 辅助函数 ====================

function getFrequencyLabel(frequency: string): string {
  const map: Record<string, string> = {
    daily: '每日',
    weekly: '每周',
    monthly: '每月',
    quarterly: '每季度',
    yearly: '每年'
  }
  return map[frequency] || frequency
}

function getTaskStatusType(status?: InspectionStatus): TagType {
  const map: Record<InspectionStatus, TagType> = {
    pending: 'warning',
    in_progress: 'primary',
    completed: 'success',
    overdue: 'danger'
  }
  return status ? map[status] || 'info' : 'info'
}

function getTaskStatusLabel(status?: InspectionStatus): string {
  const map: Record<InspectionStatus, string> = {
    pending: '待执行',
    in_progress: '执行中',
    completed: '已完成',
    overdue: '已超期'
  }
  return status ? map[status] || status : '--'
}

function formatDateTime(dateStr?: string): string {
  if (!dateStr) return '--'
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}
</script>

<style scoped lang="scss">
.inspection-page {
  .main-card {
    background: var(--bg-card-solid);
    border-color: var(--border-color);

    :deep(.el-card__body) {
      background-color: var(--bg-card-solid);
    }

    :deep(.el-tabs__header) {
      margin-bottom: 20px;
      background-color: var(--bg-tertiary);
      border-bottom: 1px solid var(--border-color);
      padding: 0 16px;
    }

    :deep(.el-tabs__nav-wrap::after) {
      background-color: transparent;
    }

    :deep(.el-tabs__item) {
      color: var(--text-secondary);
      font-weight: 400;
      height: 48px;
      line-height: 48px;

      &.is-active {
        color: var(--accent-color);
        font-weight: 500;
      }

      &:hover {
        color: var(--text-primary);
      }
    }

    :deep(.el-tabs__active-bar) {
      background-color: var(--accent-color);
    }

    :deep(.el-tabs__content) {
      background-color: var(--bg-card-solid);
      padding: 0 16px 16px;
    }
  }

  .tab-toolbar {
    margin-bottom: 16px;
    display: flex;
    justify-content: flex-start;
    gap: 12px;
  }

  .section-title {
    font-size: 16px;
    font-weight: bold;
    color: var(--text-primary);
    margin-bottom: 12px;
    margin-top: 20px;
  }

  .checklist-section {
    margin-top: 20px;
  }

  .complete-task-content {
    .section-title {
      margin-top: 0;
    }
  }

  :deep(.el-table) {
    background: transparent;

    th.el-table__cell {
      background: var(--bg-card);
      color: var(--text-primary);
      border-color: var(--border-color);
    }

    td.el-table__cell {
      border-color: var(--border-color);
    }

    tr {
      background: var(--bg-card);

      &:hover > td.el-table__cell {
        background: rgba(255, 255, 255, 0.05);
      }
    }

    .el-table__body tr.el-table__row--striped td.el-table__cell {
      background: rgba(255, 255, 255, 0.02);
    }
  }

  :deep(.el-dialog) {
    background: var(--bg-card);
    border: 1px solid var(--border-color);

    .el-dialog__header {
      border-bottom: 1px solid var(--border-color);
    }

    .el-dialog__title {
      color: var(--text-primary);
    }

    .el-dialog__footer {
      border-top: 1px solid var(--border-color);
    }
  }

  :deep(.el-descriptions) {
    .el-descriptions__label {
      background: rgba(255, 255, 255, 0.02);
      color: var(--text-secondary);
    }

    .el-descriptions__content {
      background: var(--bg-card);
      color: var(--text-primary);
    }

    .el-descriptions__cell {
      border-color: var(--border-color);
    }
  }

  :deep(.el-form-item__label) {
    color: var(--text-secondary);
  }

  :deep(.el-input__wrapper),
  :deep(.el-textarea__inner),
  :deep(.el-select .el-input__wrapper) {
    background: rgba(255, 255, 255, 0.05);
    border-color: var(--border-color);

    &:hover {
      border-color: var(--accent-color);
    }
  }

  :deep(.el-input__inner),
  :deep(.el-textarea__inner) {
    color: var(--text-primary);

    &::placeholder {
      color: var(--text-secondary);
    }
  }

  :deep(.el-switch) {
    --el-switch-on-color: var(--accent-color);
  }

  :deep(.el-radio__label) {
    color: var(--text-primary);
  }
}
</style>
