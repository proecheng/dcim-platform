<template>
  <div class="optimization-overview">
    <!-- 优化潜力汇总卡片 -->
    <el-row :gutter="20" class="summary-cards">
      <el-col :span="6">
        <el-card shadow="hover" class="summary-card">
          <div class="card-content">
            <div class="icon-wrapper icon-wrapper--primary">
              <el-icon :size="28"><Lightning /></el-icon>
            </div>
            <div class="info">
              <div class="value">¥{{ formatNumber(potential.total_cost_saving || 0) }}</div>
              <div class="label">潜在年节省</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="summary-card">
          <div class="card-content">
            <div class="icon-wrapper icon-wrapper--warning">
              <el-icon :size="28"><Warning /></el-icon>
            </div>
            <div class="info">
              <div class="value">{{ potential.pending_count || 0 }}</div>
              <div class="label">待处理建议</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="summary-card">
          <div class="card-content">
            <div class="icon-wrapper icon-wrapper--success">
              <el-icon :size="28"><Select /></el-icon>
            </div>
            <div class="info">
              <div class="value">{{ potential.accepted_count || 0 }}</div>
              <div class="label">执行中建议</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="summary-card">
          <div class="card-content">
            <div class="icon-wrapper icon-wrapper--info">
              <el-icon :size="28"><CircleCheck /></el-icon>
            </div>
            <div class="info">
              <div class="value">{{ potential.completed_count || 0 }}</div>
              <div class="label">已完成建议</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 快速操作区 -->
    <el-card shadow="hover" class="action-card">
      <template #header>
        <div class="card-header">
          <span>快速优化分析</span>
          <el-tag type="info" size="small">适合初学者</el-tag>
        </div>
      </template>
      <div class="action-content">
        <div class="action-desc">
          <el-icon :size="48" color="#409eff"><DataAnalysis /></el-icon>
          <div class="desc-text">
            <h3>一键智能分析</h3>
            <p>系统将自动分析您的用电数据，识别节能机会和优化建议</p>
          </div>
        </div>
        <el-divider />
        <div class="action-buttons">
          <el-button type="primary" size="large" :loading="analyzing" @click="runAnalysis">
            <el-icon><MagicStick /></el-icon> 开始智能分析
          </el-button>
          <el-button size="large" @click="gotoCenter">
            <el-icon><Management /></el-icon> 查看所有建议
          </el-button>
          <el-button size="large" @click="gotoReport">
            <el-icon><Document /></el-icon> 查看优化报告
          </el-button>
        </div>
      </div>
    </el-card>

    <!-- 高优先级建议列表 -->
    <el-card shadow="hover" class="suggestions-card">
      <template #header>
        <div class="card-header">
          <span>重点关注建议</span>
          <el-button type="primary" link size="small" @click="gotoCenter">
            查看全部 <el-icon><ArrowRight /></el-icon>
          </el-button>
        </div>
      </template>
      <div class="suggestions-list" v-loading="loading">
        <div
          v-for="item in topSuggestions"
          :key="item.id"
          class="suggestion-item"
          :class="'priority-' + item.priority"
        >
          <div class="suggestion-header">
            <div class="priority-badge" :class="item.priority">
              {{ priorityText[item.priority] }}优先级
            </div>
            <div class="status-badge" :class="item.status">
              {{ statusText[item.status] }}
            </div>
            <el-tag size="small" type="info" v-if="item.template_id || item.rule_name">
              {{ getTemplateTypeName(item.template_id, item.rule_name) }}
            </el-tag>
          </div>
          <div class="suggestion-content">
            <div class="rule-name">{{ item.rule_name || '节能建议' }}</div>
            <div class="suggestion-text">{{ item.suggestion }}</div>
          </div>
          <div class="suggestion-footer">
            <div class="stats">
              <span class="stat-item">
                <el-icon><TrendCharts /></el-icon>
                预计节省: <strong>¥{{ (item.potential_cost_saving || 0).toFixed(0) }}</strong>/月
              </span>
              <span class="stat-item">
                <el-icon><Lightning /></el-icon>
                节能: <strong>{{ (item.potential_saving || 0).toFixed(0) }}</strong> kWh/月
              </span>
            </div>
            <div class="actions">
              <el-button type="primary" size="small" @click="goToExecution(item)">
                执行 <el-icon><VideoPlay /></el-icon>
              </el-button>
            </div>
          </div>
        </div>
        <el-empty v-if="topSuggestions.length === 0 && !loading" description="暂无重点建议">
          <template #extra>
            <el-button type="primary" @click="runAnalysis">
              <el-icon><MagicStick /></el-icon> 开始分析
            </el-button>
          </template>
        </el-empty>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  Lightning, Warning, Select, CircleCheck, DataAnalysis, MagicStick,
  Management, Document, ArrowRight, TrendCharts, VideoPlay
} from '@element-plus/icons-vue'
import {
  getSuggestions, getSavingPotential, triggerSuggestionAnalysis,
  type EnergySuggestion, type SavingPotential
} from '@/api/modules/energy'

const props = defineProps<{ activeTab?: string }>()
const emit = defineEmits<{ (e: 'update:activeTab', value: string): void }>()

const router = useRouter()
const loading = ref(false)
const analyzing = ref(false)
const potential = ref<Partial<SavingPotential>>({})
const topSuggestions = ref<EnergySuggestion[]>([])

const priorityText: Record<string, string> = { high: '高', medium: '中', low: '低' }
const statusText: Record<string, string> = { pending: '待处理', accepted: '执行中', rejected: '已拒绝', completed: '已完成' }

function getTemplateTypeName(templateId?: string, ruleName?: string): string {
  if (templateId) {
    const names: Record<string, string> = {
      'peak_valley_optimizer': '峰谷套利优化',
      'demand_optimizer': '需量控制方案',
      'device_operation_optimizer': '设备运行优化',
      'vpp_demand_response': 'VPP需求响应',
      'load_scheduling_optimizer': '负荷调度优化'
    }
    if (names[templateId]) return names[templateId]
  }
  if (ruleName) {
    if (ruleName.includes('峰谷') || ruleName.includes('套利')) return '峰谷套利优化'
    if (ruleName.includes('需量') || ruleName.includes('申报')) return '需量控制方案'
    if (ruleName.includes('设备') || ruleName.includes('运行')) return '设备运行优化'
  }
  return '节能方案'
}

function formatNumber(num: number): string {
  return num >= 10000 ? (num / 10000).toFixed(2) + '万' : num.toFixed(0)
}

// 数据加载
onMounted(() => loadData())

async function loadData() {
  loading.value = true
  try {
    await Promise.all([loadPotential(), loadTopSuggestions()])
  } finally {
    loading.value = false
  }
}

async function loadPotential() {
  try {
    const res = await getSavingPotential()
    potential.value = res.data || {}
  } catch (e) {
    console.error('加载节能潜力失败', e)
  }
}

async function loadTopSuggestions() {
  try {
    const res = await getSuggestions({ status: 'pending', priority: 'high' })
    topSuggestions.value = (res.data || []).slice(0, 5)
  } catch (e) {
    console.error('加载建议失败', e)
  }
}

async function runAnalysis() {
  analyzing.value = true
  try {
    const res = await triggerSuggestionAnalysis()
    const count = res.data?.new_suggestions || 0
    if (count > 0) {
      ElMessage.success(`分析完成，生成了 ${count} 条新建议`)
      await loadData()
    } else {
      ElMessage.info('分析完成，暂无新建议')
    }
  } catch (e) {
    ElMessage.error('分析失败')
  } finally {
    analyzing.value = false
  }
}

function gotoCenter() { router.push('/energy/analysis') }
function goToExecution(item: EnergySuggestion) {
  router.push({
    path: '/energy/execution',
    query: {
      suggestion_id: item.id.toString(),
      rule_name: item.rule_name || ''
    }
  })
}
function gotoReport() { emit('update:activeTab', 'schedule') }
</script>

<style lang="scss" scoped>
.optimization-overview { padding: 20px 0; }
.summary-cards { margin-bottom: 20px; }

.summary-card {
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  border: 1px solid #2d3a4f;
  border-radius: 12px;
  :deep(.el-card__body) { padding: 20px; }
  .card-content {
    display: flex; align-items: center; gap: 16px;
    .icon-wrapper {
      width: 56px; height: 56px; border-radius: 12px;
      display: flex; align-items: center; justify-content: center;
      &--primary { background: rgba(24, 144, 255, 0.2); color: #409eff; }
      &--warning { background: rgba(250, 173, 20, 0.2); color: #e6a23c; }
      &--success { background: rgba(103, 194, 58, 0.2); color: #67c23a; }
      &--info { background: rgba(144, 147, 153, 0.2); color: #909399; }
    }
    .info {
      .value { font-size: 28px; font-weight: bold; color: #fff; margin-bottom: 4px; }
      .label { font-size: 14px; color: #999; }
    }
  }
}

.action-card, .suggestions-card {
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  border: 1px solid #2d3a4f; border-radius: 12px; margin-bottom: 20px;
  :deep(.el-card__header) {
    background: transparent; border-bottom: 1px solid #2d3a4f;
    color: #fff; padding: 16px 20px;
  }
}

.action-content {
  .action-desc {
    display: flex; align-items: center; gap: 20px; padding: 20px 0;
    .desc-text {
      h3 { color: #fff; font-size: 20px; margin: 0 0 8px 0; }
      p { color: #999; font-size: 14px; margin: 0; }
    }
  }
  .action-buttons { display: flex; gap: 12px; justify-content: center; padding: 20px 0; }
}

.card-header { display: flex; justify-content: space-between; align-items: center; }
.suggestions-list { max-height: 600px; overflow-y: auto; }

.suggestion-item {
  border: 1px solid #2d3a4f; border-radius: 8px; padding: 16px; margin-bottom: 12px;
  transition: all 0.3s; background: #12121f;
  &:hover { border-color: #409eff; background: rgba(64, 158, 255, 0.05); }
  &.priority-high { border-left: 4px solid #f56c6c; }
  &.priority-medium { border-left: 4px solid #e6a23c; }
  .suggestion-header {
    display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; align-items: center;
    .priority-badge, .status-badge { padding: 2px 8px; border-radius: 4px; font-size: 12px; }
    .priority-badge {
      &.high { background: rgba(245, 108, 108, 0.2); color: #f56c6c; }
      &.medium { background: rgba(230, 162, 60, 0.2); color: #e6a23c; }
      &.low { background: rgba(255, 255, 255, 0.1); color: #999; }
    }
    .status-badge {
      &.pending { background: rgba(64, 158, 255, 0.2); color: #409eff; }
      &.accepted { background: rgba(230, 162, 60, 0.2); color: #e6a23c; }
      &.completed { background: rgba(103, 194, 58, 0.2); color: #67c23a; }
    }
  }
  .suggestion-content {
    margin-bottom: 12px;
    .rule-name { font-weight: bold; color: #fff; margin-bottom: 4px; }
    .suggestion-text { color: #ccc; line-height: 1.6; }
  }
  .suggestion-footer {
    display: flex; justify-content: space-between; align-items: center;
    .stats { display: flex; gap: 16px;
      .stat-item { font-size: 13px; color: #999; display: flex; align-items: center; gap: 4px;
        strong { color: #67c23a; }
      }
    }
  }
}
</style>
