<template>
  <div class="workorder-page">
    <!-- 统计卡片 -->
    <el-row :gutter="20" class="stat-cards">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card stat-card-total">
          <div class="stat-icon icon-total">
            <el-icon :size="28"><Tickets /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ statistics.total_workorders || 0 }}</div>
            <div class="stat-label">全部工单</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card stat-card-pending">
          <div class="stat-icon icon-pending">
            <el-icon :size="28"><Clock /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ statistics.pending_workorders || 0 }}</div>
            <div class="stat-label">待处理</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card stat-card-processing">
          <div class="stat-icon icon-processing">
            <el-icon :size="28"><Loading /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ statistics.processing_workorders || 0 }}</div>
            <div class="stat-label">处理中</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card stat-card-completed">
          <div class="stat-icon icon-completed">
            <el-icon :size="28"><CircleCheck /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ statistics.completed_workorders || 0 }}</div>
            <div class="stat-label">已完成</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 主内容区域 -->
    <el-card shadow="hover" class="main-card">
      <!-- 工具栏 -->
      <div class="toolbar">
        <div class="toolbar-left">
          <el-select v-model="filterStatus" placeholder="工单状态" clearable style="width: 140px;">
            <el-option label="待处理" value="pending" />
            <el-option label="已分配" value="assigned" />
            <el-option label="处理中" value="processing" />
            <el-option label="已完成" value="completed" />
            <el-option label="已关闭" value="closed" />
            <el-option label="已取消" value="cancelled" />
          </el-select>
          <el-select v-model="filterPriority" placeholder="优先级" clearable style="width: 120px;">
            <el-option label="紧急" value="critical" />
            <el-option label="高" value="high" />
            <el-option label="中" value="medium" />
            <el-option label="低" value="low" />
          </el-select>
          <el-input
            v-model="filterKeyword"
            placeholder="搜索工单..."
            clearable
            style="width: 200px;"
            @keyup.enter="handleSearch"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
          <el-button type="primary" @click="handleSearch">搜索</el-button>
        </div>
        <div class="toolbar-right">
          <el-button type="primary" :icon="Plus" @click="showCreateDialog">新建工单</el-button>
        </div>
      </div>

      <!-- 数据表格 -->
      <el-table :data="workOrderList" stripe border v-loading="loading">
        <el-table-column prop="order_no" label="工单编号" width="140" />
        <el-table-column prop="title" label="标题" min-width="180" show-overflow-tooltip />
        <el-table-column prop="order_type" label="类型" width="100">
          <template #default="{ row }">
            {{ getOrderTypeLabel(row.order_type) }}
          </template>
        </el-table-column>
        <el-table-column prop="priority" label="优先级" width="100">
          <template #default="{ row }">
            <el-tag :type="getPriorityType(row.priority)" size="small">
              {{ getPriorityLabel(row.priority) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ getStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="assignee" label="处理人" width="100">
          <template #default="{ row }">
            {{ row.assignee || '--' }}
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="170">
          <template #default="{ row }">
            {{ formatDateTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="showDetailDialog(row)">详情</el-button>
            <el-button
              v-if="row.status === 'pending' || row.status === 'assigned'"
              type="success"
              link
              @click="handleProcess(row)"
            >
              处理
            </el-button>
            <el-button
              v-if="row.status === 'processing'"
              type="warning"
              link
              @click="showCompleteDialog(row)"
            >
              完成
            </el-button>
            <el-button type="danger" link @click="confirmDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="loadWorkOrders"
          @current-change="loadWorkOrders"
        />
      </div>
    </el-card>

    <!-- 新建/编辑工单对话框 -->
    <el-dialog
      v-model="createDialogVisible"
      :title="isEdit ? '编辑工单' : '新建工单'"
      width="600px"
      destroy-on-close
    >
      <el-form
        ref="createFormRef"
        :model="createForm"
        :rules="createRules"
        label-width="100px"
      >
        <el-form-item label="标题" prop="title">
          <el-input v-model="createForm.title" placeholder="请输入工单标题" />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input
            v-model="createForm.description"
            type="textarea"
            :rows="4"
            placeholder="请输入工单描述"
          />
        </el-form-item>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="工单类型" prop="order_type">
              <el-select v-model="createForm.order_type" placeholder="请选择类型" style="width: 100%;">
                <el-option label="故障" value="fault" />
                <el-option label="维护" value="maintenance" />
                <el-option label="巡检" value="inspection" />
                <el-option label="变更" value="change" />
                <el-option label="其他" value="other" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="优先级" prop="priority">
              <el-select v-model="createForm.priority" placeholder="请选择优先级" style="width: 100%;">
                <el-option label="紧急" value="critical" />
                <el-option label="高" value="high" />
                <el-option label="中" value="medium" />
                <el-option label="低" value="low" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="设备名称" prop="device_name">
              <el-input v-model="createForm.device_name" placeholder="请输入设备名称" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="位置" prop="location">
              <el-input v-model="createForm.location" placeholder="请输入位置" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="报修人" prop="reporter">
              <el-input v-model="createForm.reporter" placeholder="请输入报修人" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="联系电话" prop="reporter_phone">
              <el-input v-model="createForm.reporter_phone" placeholder="请输入联系电话" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitCreateForm" :loading="submitting">确定</el-button>
      </template>
    </el-dialog>

    <!-- 工单详情对话框 -->
    <el-dialog
      v-model="detailDialogVisible"
      title="工单详情"
      width="700px"
      destroy-on-close
    >
      <el-descriptions :column="2" border>
        <el-descriptions-item label="工单编号">{{ currentOrder?.order_no }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="getStatusType(currentOrder?.status)" size="small">
            {{ getStatusLabel(currentOrder?.status) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="标题" :span="2">{{ currentOrder?.title }}</el-descriptions-item>
        <el-descriptions-item label="描述" :span="2">{{ currentOrder?.description || '--' }}</el-descriptions-item>
        <el-descriptions-item label="工单类型">{{ getOrderTypeLabel(currentOrder?.order_type) }}</el-descriptions-item>
        <el-descriptions-item label="优先级">
          <el-tag :type="getPriorityType(currentOrder?.priority)" size="small">
            {{ getPriorityLabel(currentOrder?.priority) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="设备名称">{{ currentOrder?.device_name || '--' }}</el-descriptions-item>
        <el-descriptions-item label="位置">{{ currentOrder?.location || '--' }}</el-descriptions-item>
        <el-descriptions-item label="报修人">{{ currentOrder?.reporter || '--' }}</el-descriptions-item>
        <el-descriptions-item label="联系电话">{{ currentOrder?.reporter_phone || '--' }}</el-descriptions-item>
        <el-descriptions-item label="处理人">{{ currentOrder?.assignee || '--' }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ formatDateTime(currentOrder?.created_at) }}</el-descriptions-item>
        <el-descriptions-item label="分配时间">{{ formatDateTime(currentOrder?.assigned_at) }}</el-descriptions-item>
        <el-descriptions-item label="开始时间">{{ formatDateTime(currentOrder?.started_at) }}</el-descriptions-item>
        <el-descriptions-item label="完成时间">{{ formatDateTime(currentOrder?.completed_at) }}</el-descriptions-item>
        <el-descriptions-item label="解决方案" :span="2">{{ currentOrder?.solution || '--' }}</el-descriptions-item>
        <el-descriptions-item label="根因分析" :span="2">{{ currentOrder?.root_cause || '--' }}</el-descriptions-item>
      </el-descriptions>

      <!-- 工单日志 -->
      <div class="log-section">
        <div class="log-header">
          <span class="log-title">工单日志</span>
          <el-button type="primary" size="small" @click="showAddLogDialog">添加日志</el-button>
        </div>
        <el-timeline v-if="orderLogs.length > 0">
          <el-timeline-item
            v-for="log in orderLogs"
            :key="log.id"
            :timestamp="formatDateTime(log.created_at)"
            placement="top"
          >
            <el-card shadow="never" class="log-card">
              <div class="log-action">{{ log.action }}</div>
              <div class="log-content">{{ log.content }}</div>
              <div class="log-operator" v-if="log.operator">操作人: {{ log.operator }}</div>
            </el-card>
          </el-timeline-item>
        </el-timeline>
        <el-empty v-else description="暂无日志" :image-size="60" />
      </div>

      <template #footer>
        <el-button @click="detailDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 添加日志对话框 -->
    <el-dialog
      v-model="addLogDialogVisible"
      title="添加日志"
      width="500px"
      destroy-on-close
    >
      <el-form
        ref="logFormRef"
        :model="logForm"
        :rules="logRules"
        label-width="80px"
      >
        <el-form-item label="操作类型" prop="action">
          <el-select v-model="logForm.action" placeholder="请选择操作类型" style="width: 100%;">
            <el-option label="跟进" value="跟进" />
            <el-option label="处理" value="处理" />
            <el-option label="备注" value="备注" />
            <el-option label="转交" value="转交" />
            <el-option label="其他" value="其他" />
          </el-select>
        </el-form-item>
        <el-form-item label="内容" prop="content">
          <el-input
            v-model="logForm.content"
            type="textarea"
            :rows="4"
            placeholder="请输入日志内容"
          />
        </el-form-item>
        <el-form-item label="操作人" prop="operator">
          <el-input v-model="logForm.operator" placeholder="请输入操作人" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addLogDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitAddLog" :loading="submitting">确定</el-button>
      </template>
    </el-dialog>

    <!-- 完成工单对话框 -->
    <el-dialog
      v-model="completeDialogVisible"
      title="完成工单"
      width="500px"
      destroy-on-close
    >
      <el-form
        ref="completeFormRef"
        :model="completeForm"
        :rules="completeRules"
        label-width="80px"
      >
        <el-form-item label="解决方案" prop="solution">
          <el-input
            v-model="completeForm.solution"
            type="textarea"
            :rows="4"
            placeholder="请输入解决方案"
          />
        </el-form-item>
        <el-form-item label="根因分析" prop="root_cause">
          <el-input
            v-model="completeForm.root_cause"
            type="textarea"
            :rows="3"
            placeholder="请输入根因分析（可选）"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="completeDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitComplete" :loading="submitting">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance } from 'element-plus'
import { Tickets, Clock, Loading, CircleCheck, Plus, Search } from '@element-plus/icons-vue'
import {
  getWorkOrders,
  createWorkOrder,
  updateWorkOrder,
  deleteWorkOrder,
  startWorkOrder,
  completeWorkOrder,
  getWorkOrderLogs,
  addWorkOrderLog,
  getOperationStatistics,
  type WorkOrder,
  type WorkOrderStatus,
  type WorkOrderPriority,
  type WorkOrderType,
  type WorkOrderLog,
  type OperationStatistics
} from '@/api/modules/operation'

// 类型定义
type TagType = 'success' | 'warning' | 'danger' | 'info' | 'primary'

// 数据状态
const loading = ref(false)
const submitting = ref(false)
const workOrderList = ref<WorkOrder[]>([])
const statistics = ref<Partial<OperationStatistics>>({})

// 分页
const currentPage = ref(1)
const pageSize = ref(10)
const total = ref(0)

// 筛选条件
const filterStatus = ref<WorkOrderStatus | ''>('')
const filterPriority = ref<WorkOrderPriority | ''>('')
const filterKeyword = ref('')

// 对话框状态
const isEdit = ref(false)
const currentId = ref<number | null>(null)
const currentOrder = ref<WorkOrder | null>(null)
const orderLogs = ref<WorkOrderLog[]>([])

// 新建/编辑对话框
const createDialogVisible = ref(false)
const createFormRef = ref<FormInstance>()
const createForm = reactive({
  title: '',
  description: '',
  order_type: 'fault' as WorkOrderType,
  priority: 'medium' as WorkOrderPriority,
  device_name: '',
  location: '',
  reporter: '',
  reporter_phone: ''
})

const createRules = {
  title: [{ required: true, message: '请输入工单标题', trigger: 'blur' }],
  order_type: [{ required: true, message: '请选择工单类型', trigger: 'change' }],
  priority: [{ required: true, message: '请选择优先级', trigger: 'change' }]
}

// 详情对话框
const detailDialogVisible = ref(false)

// 添加日志对话框
const addLogDialogVisible = ref(false)
const logFormRef = ref<FormInstance>()
const logForm = reactive({
  action: '',
  content: '',
  operator: ''
})

const logRules = {
  action: [{ required: true, message: '请选择操作类型', trigger: 'change' }],
  content: [{ required: true, message: '请输入日志内容', trigger: 'blur' }]
}

// 完成工单对话框
const completeDialogVisible = ref(false)
const completeFormRef = ref<FormInstance>()
const completeForm = reactive({
  solution: '',
  root_cause: ''
})

const completeRules = {
  solution: [{ required: true, message: '请输入解决方案', trigger: 'blur' }]
}

// 初始化加载
onMounted(() => {
  loadStatistics()
  loadWorkOrders()
})

// 加载统计数据
async function loadStatistics() {
  try {
    const res = await getOperationStatistics()
    if (res.data) {
      statistics.value = res.data
    }
  } catch (e) {
    console.error('加载统计数据失败', e)
  }
}

// 加载工单列表
async function loadWorkOrders() {
  loading.value = true
  try {
    const res = await getWorkOrders({
      page: currentPage.value,
      page_size: pageSize.value,
      status: filterStatus.value || undefined,
      priority: filterPriority.value || undefined,
      keyword: filterKeyword.value || undefined
    })
    if (res.data) {
      const data = res.data as any
      workOrderList.value = Array.isArray(data) ? data : data.items || []
      total.value = data.total || workOrderList.value.length
    }
  } catch (e) {
    console.error('加载工单列表失败', e)
    ElMessage.error('加载工单列表失败')
  } finally {
    loading.value = false
  }
}

// 搜索
function handleSearch() {
  currentPage.value = 1
  loadWorkOrders()
}

// 显示新建对话框
function showCreateDialog() {
  isEdit.value = false
  currentId.value = null
  Object.assign(createForm, {
    title: '',
    description: '',
    order_type: 'fault',
    priority: 'medium',
    device_name: '',
    location: '',
    reporter: '',
    reporter_phone: ''
  })
  createDialogVisible.value = true
}

// 提交新建/编辑表单
async function submitCreateForm() {
  const valid = await createFormRef.value?.validate()
  if (!valid) return

  submitting.value = true
  try {
    const data = {
      title: createForm.title,
      description: createForm.description || undefined,
      order_type: createForm.order_type,
      priority: createForm.priority,
      location: createForm.location || undefined,
      reporter: createForm.reporter || undefined,
      reporter_phone: createForm.reporter_phone || undefined
    }

    if (isEdit.value && currentId.value) {
      await updateWorkOrder(currentId.value, data)
      ElMessage.success('更新成功')
    } else {
      await createWorkOrder(data)
      ElMessage.success('创建成功')
    }
    createDialogVisible.value = false
    loadWorkOrders()
    loadStatistics()
  } catch (e) {
    console.error('操作失败', e)
    ElMessage.error('操作失败')
  } finally {
    submitting.value = false
  }
}

// 显示详情对话框
async function showDetailDialog(row: WorkOrder) {
  currentOrder.value = row
  detailDialogVisible.value = true

  // 加载工单日志
  try {
    const res = await getWorkOrderLogs(row.id)
    if (res.data) {
      orderLogs.value = Array.isArray(res.data) ? res.data : (res.data as any).items || []
    }
  } catch (e) {
    console.error('加载工单日志失败', e)
    orderLogs.value = []
  }
}

// 显示添加日志对话框
function showAddLogDialog() {
  Object.assign(logForm, {
    action: '',
    content: '',
    operator: ''
  })
  addLogDialogVisible.value = true
}

// 提交添加日志
async function submitAddLog() {
  const valid = await logFormRef.value?.validate()
  if (!valid) return

  if (!currentOrder.value) return

  submitting.value = true
  try {
    await addWorkOrderLog(currentOrder.value.id, logForm.action, logForm.content, logForm.operator || undefined)
    ElMessage.success('添加日志成功')
    addLogDialogVisible.value = false

    // 重新加载日志
    const res = await getWorkOrderLogs(currentOrder.value.id)
    if (res.data) {
      orderLogs.value = Array.isArray(res.data) ? res.data : (res.data as any).items || []
    }
  } catch (e) {
    console.error('添加日志失败', e)
    ElMessage.error('添加日志失败')
  } finally {
    submitting.value = false
  }
}

// 处理工单
async function handleProcess(row: WorkOrder) {
  try {
    await startWorkOrder(row.id)
    ElMessage.success('开始处理工单')
    loadWorkOrders()
    loadStatistics()
  } catch (e) {
    console.error('处理工单失败', e)
    ElMessage.error('处理工单失败')
  }
}

// 显示完成对话框
function showCompleteDialog(row: WorkOrder) {
  currentId.value = row.id
  Object.assign(completeForm, {
    solution: '',
    root_cause: ''
  })
  completeDialogVisible.value = true
}

// 提交完成工单
async function submitComplete() {
  const valid = await completeFormRef.value?.validate()
  if (!valid) return

  if (!currentId.value) return

  submitting.value = true
  try {
    await completeWorkOrder(currentId.value, completeForm.solution, completeForm.root_cause || undefined)
    ElMessage.success('工单已完成')
    completeDialogVisible.value = false
    loadWorkOrders()
    loadStatistics()
  } catch (e) {
    console.error('完成工单失败', e)
    ElMessage.error('完成工单失败')
  } finally {
    submitting.value = false
  }
}

// 确认删除
function confirmDelete(row: WorkOrder) {
  ElMessageBox.confirm(
    `确定要删除工单 "${row.title}" 吗？`,
    '删除确认',
    { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
  ).then(async () => {
    try {
      await deleteWorkOrder(row.id)
      ElMessage.success('删除成功')
      loadWorkOrders()
      loadStatistics()
    } catch (e) {
      console.error('删除失败', e)
      ElMessage.error('删除失败')
    }
  }).catch(() => {})
}

// 辅助函数
function getStatusType(status?: WorkOrderStatus): TagType {
  const map: Record<WorkOrderStatus, TagType> = {
    pending: 'warning',
    assigned: 'info',
    processing: 'primary',
    completed: 'success',
    closed: 'info',
    cancelled: 'danger'
  }
  return status ? map[status] || 'info' : 'info'
}

function getStatusLabel(status?: WorkOrderStatus): string {
  const map: Record<WorkOrderStatus, string> = {
    pending: '待处理',
    assigned: '已分配',
    processing: '处理中',
    completed: '已完成',
    closed: '已关闭',
    cancelled: '已取消'
  }
  return status ? map[status] || status : '--'
}

function getPriorityType(priority?: WorkOrderPriority): TagType {
  const map: Record<WorkOrderPriority, TagType> = {
    critical: 'danger',
    high: 'warning',
    medium: 'primary',
    low: 'info'
  }
  return priority ? map[priority] || 'info' : 'info'
}

function getPriorityLabel(priority?: WorkOrderPriority): string {
  const map: Record<WorkOrderPriority, string> = {
    critical: '紧急',
    high: '高',
    medium: '中',
    low: '低'
  }
  return priority ? map[priority] || priority : '--'
}

function getOrderTypeLabel(type?: WorkOrderType): string {
  const map: Record<WorkOrderType, string> = {
    fault: '故障',
    maintenance: '维护',
    inspection: '巡检',
    change: '变更',
    other: '其他'
  }
  return type ? map[type] || type : '--'
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
.workorder-page {
  .stat-cards {
    margin-bottom: 20px;
  }

  .stat-card {
    background: var(--bg-card);
    border-color: var(--border-color);
    transition: all 0.3s ease;

    :deep(.el-card__body) {
      display: flex;
      align-items: center;
      gap: 16px;
      padding: 20px;
    }

    .stat-icon {
      width: 56px;
      height: 56px;
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      color: #fff;
      flex-shrink: 0;

      &.icon-total,
      &.icon-processing {
        background: linear-gradient(135deg, #1890ff, #40a9ff);
      }

      &.icon-pending {
        background: linear-gradient(135deg, #faad14, #ffc53d);
      }

      &.icon-completed {
        background: linear-gradient(135deg, #52c41a, #73d13d);
      }
    }

    .stat-info {
      flex: 1;

      .stat-value {
        font-size: 28px;
        font-weight: bold;
        color: var(--text-primary);
        line-height: 1.2;
      }

      .stat-label {
        font-size: 14px;
        color: var(--text-secondary);
        margin-top: 4px;
      }
    }

    &:hover {
      transform: translateY(-2px);
      border-color: var(--accent-color);
    }

    &.stat-card-total:hover {
      box-shadow: 0 0 20px rgba(64, 158, 255, 0.3);
    }

    &.stat-card-pending:hover {
      box-shadow: 0 0 20px rgba(230, 162, 60, 0.3);
    }

    &.stat-card-processing:hover {
      box-shadow: 0 0 20px rgba(64, 158, 255, 0.3);
    }

    &.stat-card-completed:hover {
      box-shadow: 0 0 20px rgba(103, 194, 58, 0.3);
    }
  }

  .main-card {
    background: var(--bg-card);
    border-color: var(--border-color);
  }

  .toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;

    .toolbar-left {
      display: flex;
      gap: 12px;
      align-items: center;
    }

    .toolbar-right {
      display: flex;
      gap: 12px;
    }
  }

  .pagination-wrapper {
    display: flex;
    justify-content: flex-end;
    margin-top: 16px;
  }

  .log-section {
    margin-top: 24px;

    .log-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 16px;

      .log-title {
        font-size: 16px;
        font-weight: bold;
        color: var(--text-primary);
      }
    }

    .log-card {
      background: rgba(255, 255, 255, 0.02);
      border-color: var(--border-color);

      .log-action {
        font-weight: bold;
        color: var(--text-primary);
        margin-bottom: 8px;
      }

      .log-content {
        color: var(--text-secondary);
        margin-bottom: 8px;
      }

      .log-operator {
        font-size: 12px;
        color: var(--text-secondary);
      }
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

  :deep(.el-timeline-item__timestamp) {
    color: var(--text-secondary);
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
}
</style>
