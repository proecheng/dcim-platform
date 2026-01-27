<template>
  <div class="energy-suggestions">
    <!-- 节能潜力卡片 -->
    <el-row :gutter="20" class="potential-cards">
      <el-col :span="6">
        <el-card shadow="hover" class="potential-card">
          <div class="card-content">
            <div class="icon-wrapper icon-wrapper--primary">
              <el-icon :size="28"><Lightning /></el-icon>
            </div>
            <div class="info">
              <div class="value">{{ potential.total_potential_saving?.toFixed(0) || 0 }}</div>
              <div class="label">潜在节能 (kWh/月)</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="potential-card">
          <div class="card-content">
            <div class="icon-wrapper icon-wrapper--success">
              <el-icon :size="28"><Money /></el-icon>
            </div>
            <div class="info">
              <div class="value">{{ potential.total_cost_saving?.toFixed(0) || 0 }}</div>
              <div class="label">预计节省 (元/月)</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="potential-card">
          <div class="card-content">
            <div class="icon-wrapper icon-wrapper--warning">
              <el-icon :size="28"><Finished /></el-icon>
            </div>
            <div class="info">
              <div class="value">{{ potential.completed_count || 0 }}</div>
              <div class="label">已完成建议</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="potential-card">
          <div class="card-content">
            <div class="icon-wrapper icon-wrapper--danger">
              <el-icon :size="28"><TrendCharts /></el-icon>
            </div>
            <div class="info">
              <div class="value">{{ potential.actual_saving_ytd?.toFixed(0) || 0 }}</div>
              <div class="label">年度实际节能 (kWh)</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20">
      <!-- 建议统计 -->
      <el-col :span="8">
        <el-card shadow="hover">
          <template #header>建议统计</template>
          <div ref="statsChartRef" class="stats-chart"></div>
          <div class="stats-summary">
            <div class="stat-item">
              <el-tag type="danger">高优先级: {{ potential.high_priority_count || 0 }}</el-tag>
            </div>
            <div class="stat-item">
              <el-tag type="warning">中优先级: {{ potential.medium_priority_count || 0 }}</el-tag>
            </div>
            <div class="stat-item">
              <el-tag type="info">低优先级: {{ potential.low_priority_count || 0 }}</el-tag>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 节能建议列表 -->
      <el-col :span="16">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>节能建议列表</span>
              <div class="header-actions">
                <el-button type="success" :loading="analyzing" @click="triggerAnalysis" size="small">
                  <el-icon><Refresh /></el-icon> 智能分析
                </el-button>
                <el-button type="primary" link @click="showTemplates = true" size="small">
                  <el-icon><Setting /></el-icon> 查看模板
                </el-button>
                <el-select v-model="filters.status" placeholder="全部状态" clearable style="width: 120px;" @change="loadSuggestions">
                  <el-option label="待处理" value="pending" />
                  <el-option label="已接受" value="accepted" />
                  <el-option label="已拒绝" value="rejected" />
                  <el-option label="已完成" value="completed" />
                </el-select>
              </div>
            </div>
          </template>

          <div class="suggestion-list" v-loading="loading">
            <div
              v-for="item in suggestions"
              :key="item.id"
              class="suggestion-item"
              :class="'priority-' + item.priority"
            >
              <div class="suggestion-header">
                <div class="priority-badge" :class="item.priority">
                  {{ priorityText[item.priority] }}
                </div>
                <div class="status-badge" :class="item.status">
                  {{ statusText[item.status] }}
                </div>
              </div>

              <div class="suggestion-content">
                <div class="rule-name">{{ item.rule_name || item.rule_id }}</div>
                <div class="suggestion-text">{{ item.suggestion }}</div>
              </div>

              <div class="suggestion-stats">
                <div class="stat">
                  <span class="label">预计节能:</span>
                  <span class="value">{{ item.potential_saving?.toFixed(0) || '-' }} kWh/月</span>
                </div>
                <div class="stat">
                  <span class="label">预计节省:</span>
                  <span class="value">{{ item.potential_cost_saving?.toFixed(0) || '-' }} 元/月</span>
                </div>
              </div>

              <div class="suggestion-actions" v-if="item.status === 'pending'">
                <el-button type="primary" size="small" @click="handleViewDetail(item)">查看详情</el-button>
                <el-button type="success" size="small" @click="handleAccept(item)">接受</el-button>
                <el-button type="danger" size="small" @click="handleReject(item)">拒绝</el-button>
              </div>

              <div class="suggestion-actions" v-else-if="item.status === 'accepted'">
                <el-button type="primary" size="small" @click="handleViewDetail(item)">查看详情</el-button>
                <el-button type="success" size="small" @click="handleComplete(item)">标记完成</el-button>
              </div>

              <div class="suggestion-actions" v-else>
                <el-button type="primary" size="small" @click="handleViewDetail(item)">查看详情</el-button>
              </div>

              <div class="suggestion-footer" v-if="item.status === 'completed'">
                <span class="completed-info">
                  完成时间: {{ item.completed_at }}
                  <template v-if="item.actual_saving">
                    | 实际节能: {{ item.actual_saving }} kWh
                  </template>
                </span>
              </div>

              <div class="suggestion-footer" v-if="item.remark">
                <span class="remark">备注: {{ item.remark }}</span>
              </div>
            </div>

            <el-empty v-if="suggestions.length === 0" description="暂无节能建议" />
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 拒绝对话框 -->
    <el-dialog v-model="rejectDialogVisible" title="拒绝建议" width="400px">
      <el-form :model="rejectForm" label-width="80px">
        <el-form-item label="拒绝原因">
          <el-input v-model="rejectForm.remark" type="textarea" :rows="3" placeholder="请输入拒绝原因" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="rejectDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitReject">确定</el-button>
      </template>
    </el-dialog>

    <!-- 完成对话框 -->
    <el-dialog v-model="completeDialogVisible" title="完成建议" width="400px">
      <el-form :model="completeForm" label-width="100px">
        <el-form-item label="实际节能">
          <el-input-number v-model="completeForm.actual_saving" :min="0" style="width: 100%;" />
          <span style="margin-left: 8px;">kWh/月</span>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="completeForm.remark" type="textarea" :rows="2" placeholder="可选备注" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="completeDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitComplete">确定</el-button>
      </template>
    </el-dialog>

    <!-- V2.3: 模板列表对话框 -->
    <el-dialog v-model="showTemplates" title="节能建议模板" width="700px">
      <el-table :data="templates" stripe border max-height="400">
        <el-table-column prop="name" label="模板名称" width="150" />
        <el-table-column prop="category" label="类别" width="100">
          <template #default="{ row }">
            <el-tag size="small">{{ categoryText[row.category] || row.category }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" show-overflow-tooltip />
        <el-table-column prop="priority" label="优先级" width="80">
          <template #default="{ row }">
            <el-tag :type="row.priority === 'high' ? 'danger' : row.priority === 'medium' ? 'warning' : 'info'" size="small">
              {{ priorityText[row.priority] }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_enabled ? 'success' : 'info'" size="small">
              {{ row.is_enabled ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="showTemplates = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- V2.4: 建议详情抽屉 -->
    <SuggestionDetailDrawer
      v-model="detailDrawerVisible"
      :suggestion="currentSuggestion"
      @accepted="handleDetailAccepted"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Lightning, Money, Finished, TrendCharts, Refresh, Setting } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import SuggestionDetailDrawer from '@/components/energy/SuggestionDetailDrawer.vue'
import {
  getSuggestions, getSavingPotential, acceptSuggestion, rejectSuggestion, completeSuggestion,
  getSuggestionTemplates, triggerSuggestionAnalysis, getSuggestionsSummary,
  type EnergySuggestion, type SavingPotential, type SuggestionTemplate, type SuggestionSummary
} from '@/api/modules/energy'

const statsChartRef = ref<HTMLElement>()
const categoryChartRef = ref<HTMLElement>()
let statsChart: echarts.ECharts | null = null
let categoryChart: echarts.ECharts | null = null

const loading = ref(false)
const analyzing = ref(false)
const suggestions = ref<EnergySuggestion[]>([])
const potential = ref<Partial<SavingPotential>>({})
const templates = ref<SuggestionTemplate[]>([])
const summary = ref<Partial<SuggestionSummary>>({})
const showTemplates = ref(false)

const filters = reactive({
  status: ''
})

const rejectDialogVisible = ref(false)
const completeDialogVisible = ref(false)
const detailDrawerVisible = ref(false)
const currentSuggestion = ref<EnergySuggestion | null>(null)

const rejectForm = reactive({
  remark: ''
})

const completeForm = reactive({
  actual_saving: 0,
  remark: ''
})

const priorityText: Record<string, string> = {
  high: '高',
  medium: '中',
  low: '低'
}

const statusText: Record<string, string> = {
  pending: '待处理',
  accepted: '已接受',
  rejected: '已拒绝',
  completed: '已完成'
}

onMounted(() => {
  initCharts()
  loadData()
})

onUnmounted(() => {
  statsChart?.dispose()
  categoryChart?.dispose()
})

function initCharts() {
  if (statsChartRef.value) {
    statsChart = echarts.init(statsChartRef.value)
  }
  if (categoryChartRef.value) {
    categoryChart = echarts.init(categoryChartRef.value)
  }
  window.addEventListener('resize', () => {
    statsChart?.resize()
    categoryChart?.resize()
  })
}

async function loadData() {
  await Promise.all([
    loadSuggestions(),
    loadPotential(),
    loadTemplates(),
    loadSummary()
  ])
}

async function loadTemplates() {
  try {
    const res = await getSuggestionTemplates()
    if (res.code === 0 && res.data) {
      templates.value = res.data.templates || []
    }
  } catch (e) {
    console.error('加载模板失败', e)
  }
}

async function loadSummary() {
  try {
    const res = await getSuggestionsSummary()
    summary.value = res.data || {}
    updateCategoryChart()
  } catch (e) {
    console.error('加载汇总失败', e)
  }
}

async function triggerAnalysis() {
  analyzing.value = true
  try {
    const res = await triggerSuggestionAnalysis()
    const count = res.data?.new_suggestions || 0
    if (count > 0) {
      ElMessage.success(`分析完成，生成了 ${count} 条新建议`)
    } else {
      ElMessage.info('分析完成，暂无新建议')
    }
    await loadData()
  } catch (e) {
    ElMessage.error('分析失败')
  } finally {
    analyzing.value = false
  }
}

function updateCategoryChart() {
  if (!categoryChart || !summary.value) return

  // Use priority counts as category data since by_category is not in the API type
  const priorityData = [
    { name: '紧急', value: summary.value.urgent_count || 0, itemStyle: { color: chartColors.error } },
    { name: '高', value: summary.value.high_count || 0, itemStyle: { color: chartColors.warning } },
    { name: '中', value: summary.value.medium_count || 0, itemStyle: { color: chartColors.primary } },
    { name: '低', value: summary.value.low_count || 0, itemStyle: { color: chartColors.text } }
  ].filter(item => item.value > 0)

  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c} 条',
      backgroundColor: chartColors.tooltipBg,
      borderColor: chartColors.border,
      textStyle: { color: 'rgba(255, 255, 255, 0.85)' }
    },
    series: [{
      type: 'pie',
      radius: '70%',
      data: priorityData,
      label: {
        formatter: '{b}\n{c}条',
        color: chartColors.text
      }
    }]
  }
  categoryChart.setOption(option)
}

const categoryText: Record<string, string> = {
  pue: 'PUE优化',
  demand: '需量管理',
  peak_valley: '峰谷优化',
  device: '设备节能',
  cooling: '制冷优化',
  other: '其他'
}

async function loadSuggestions() {
  loading.value = true
  try {
    const params: any = {}
    if (filters.status) params.status = filters.status
    const res = await getSuggestions(params)
    suggestions.value = res.data || []
  } catch (e) {
    console.error('加载建议失败', e)
  } finally {
    loading.value = false
  }
}

async function loadPotential() {
  try {
    const res = await getSavingPotential()
    potential.value = res.data || {}
    updateStatsChart()
  } catch (e) {
    console.error('加载节能潜力失败', e)
  }
}

// 图表主题色常量
const chartColors = {
  primary: '#1890ff',
  success: '#52c41a',
  warning: '#faad14',
  error: '#f5222d',
  text: 'rgba(255, 255, 255, 0.65)',
  tooltipBg: 'rgba(26, 42, 74, 0.95)',
  border: 'rgba(255, 255, 255, 0.1)'
}

function updateStatsChart() {
  if (!statsChart) return

  const data = [
    { value: potential.value.pending_count || 0, name: '待处理', itemStyle: { color: chartColors.primary } },
    { value: potential.value.accepted_count || 0, name: '已接受', itemStyle: { color: chartColors.warning } },
    { value: potential.value.completed_count || 0, name: '已完成', itemStyle: { color: chartColors.success } }
  ]

  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c} 条 ({d}%)',
      backgroundColor: chartColors.tooltipBg,
      borderColor: chartColors.border,
      textStyle: { color: 'rgba(255, 255, 255, 0.85)' }
    },
    series: [{
      type: 'pie',
      radius: ['50%', '70%'],
      avoidLabelOverlap: false,
      label: {
        show: true,
        formatter: '{b}\n{c}条',
        color: chartColors.text
      },
      data
    }]
  }
  statsChart.setOption(option)
}

function handleAccept(item: EnergySuggestion) {
  currentSuggestion.value = item
  ElMessageBox.confirm('确定接受该节能建议？', '确认', {
    type: 'info'
  }).then(async () => {
    try {
      await acceptSuggestion(item.id)
      ElMessage.success('已接受建议')
      loadData()
    } catch (e) {
      console.error('接受失败', e)
    }
  }).catch(() => {})
}

function handleReject(item: EnergySuggestion) {
  currentSuggestion.value = item
  rejectForm.remark = ''
  rejectDialogVisible.value = true
}

async function submitReject() {
  if (!currentSuggestion.value) return
  if (!rejectForm.remark.trim()) {
    ElMessage.warning('请输入拒绝原因')
    return
  }

  try {
    await rejectSuggestion(currentSuggestion.value.id, { remark: rejectForm.remark })
    ElMessage.success('已拒绝建议')
    rejectDialogVisible.value = false
    loadData()
  } catch (e) {
    console.error('拒绝失败', e)
  }
}

function handleComplete(item: EnergySuggestion) {
  currentSuggestion.value = item
  completeForm.actual_saving = item.potential_saving || 0
  completeForm.remark = ''
  completeDialogVisible.value = true
}

async function submitComplete() {
  if (!currentSuggestion.value) return

  try {
    await completeSuggestion(currentSuggestion.value.id, {
      actual_saving: completeForm.actual_saving,
      remark: completeForm.remark
    })
    ElMessage.success('已完成建议')
    completeDialogVisible.value = false
    loadData()
  } catch (e) {
    console.error('完成失败', e)
  }
}

function handleViewDetail(item: EnergySuggestion) {
  currentSuggestion.value = item
  detailDrawerVisible.value = true
}

function handleDetailAccepted() {
  loadData()
}
</script>

<style scoped lang="scss">
.energy-suggestions {
  .potential-cards {
    margin-bottom: 20px;
  }

  .potential-card {
    background: var(--bg-card-solid, #1a2a4a);

    .card-content {
      display: flex;
      align-items: center;
      gap: 16px;

      .icon-wrapper {
        width: 56px;
        height: 56px;
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #fff;

        &--primary {
          background: var(--primary-color, #1890ff);
        }

        &--success {
          background: var(--success-color, #52c41a);
        }

        &--warning {
          background: var(--warning-color, #faad14);
        }

        &--danger {
          background: var(--error-color, #f5222d);
        }
      }

      .info {
        .value {
          font-size: 24px;
          font-weight: bold;
          color: var(--text-primary, rgba(255, 255, 255, 0.95));
        }

        .label {
          font-size: 14px;
          color: var(--text-secondary, rgba(255, 255, 255, 0.65));
          margin-top: 4px;
        }
      }
    }
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;

    .header-actions {
      display: flex;
      align-items: center;
      gap: 12px;
    }
  }

  .stats-chart {
    height: 200px;
  }

  .stats-summary {
    display: flex;
    justify-content: center;
    gap: 12px;
    margin-top: 16px;
  }

  .suggestion-list {
    max-height: 600px;
    overflow-y: auto;
  }

  .suggestion-item {
    border: 1px solid var(--border-color, rgba(255, 255, 255, 0.1));
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 12px;
    transition: all 0.3s;
    background: var(--bg-card-solid, #1a2a4a);

    &:hover {
      box-shadow: 0 2px 12px rgba(0, 0, 0, 0.3);
    }

    &.priority-high {
      border-left: 4px solid var(--error-color, #f5222d);
    }

    &.priority-medium {
      border-left: 4px solid var(--warning-color, #faad14);
    }

    &.priority-low {
      border-left: 4px solid var(--text-secondary, rgba(255, 255, 255, 0.65));
    }

    .suggestion-header {
      display: flex;
      gap: 8px;
      margin-bottom: 12px;

      .priority-badge, .status-badge {
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 12px;
      }

      .priority-badge {
        &.high { background: rgba(245, 34, 45, 0.1); color: var(--error-color, #f5222d); }
        &.medium { background: rgba(250, 173, 20, 0.1); color: var(--warning-color, #faad14); }
        &.low { background: rgba(255, 255, 255, 0.1); color: var(--text-secondary, rgba(255, 255, 255, 0.65)); }
      }

      .status-badge {
        &.pending { background: rgba(24, 144, 255, 0.1); color: var(--primary-color, #1890ff); }
        &.accepted { background: rgba(250, 173, 20, 0.1); color: var(--warning-color, #faad14); }
        &.rejected { background: rgba(245, 34, 45, 0.1); color: var(--error-color, #f5222d); }
        &.completed { background: rgba(82, 196, 26, 0.1); color: var(--success-color, #52c41a); }
      }
    }

    .suggestion-content {
      margin-bottom: 12px;

      .rule-name {
        font-weight: bold;
        color: var(--text-primary, rgba(255, 255, 255, 0.95));
        margin-bottom: 4px;
      }

      .suggestion-text {
        color: var(--text-regular, rgba(255, 255, 255, 0.85));
        line-height: 1.6;
      }
    }

    .suggestion-stats {
      display: flex;
      gap: 24px;
      margin-bottom: 12px;

      .stat {
        .label {
          color: var(--text-secondary, rgba(255, 255, 255, 0.65));
          margin-right: 4px;
        }

        .value {
          font-weight: bold;
          color: var(--success-color, #52c41a);
        }
      }
    }

    .suggestion-actions {
      display: flex;
      gap: 8px;
    }

    .suggestion-footer {
      margin-top: 12px;
      padding-top: 12px;
      border-top: 1px dashed var(--border-color, rgba(255, 255, 255, 0.1));
      font-size: 13px;
      color: var(--text-secondary, rgba(255, 255, 255, 0.65));

      .remark {
        font-style: italic;
      }
    }
  }
}
</style>
