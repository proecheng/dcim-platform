<template>
  <el-card class="rl-panel" shadow="hover">
    <template #header>
      <div class="panel-header">
        <div class="panel-title">
          <el-icon><Cpu /></el-icon>
          <span>RL 自适应优化</span>
          <el-tag :type="modelInfo?.is_available ? 'success' : 'danger'" size="small">
            {{ modelInfo?.is_available ? '模型可用' : '模型不可用' }}
          </el-tag>
        </div>
        <div class="header-actions">
          <el-button :icon="Refresh" :loading="loading.model" @click="loadModelInfo">刷新模型</el-button>
          <el-button :icon="Download" :loading="loading.checkpoint" @click="handleSaveCheckpoint">
            保存检查点
          </el-button>
        </div>
      </div>
    </template>

    <el-row :gutter="16" class="model-stats">
      <el-col :xs="12" :sm="6">
        <el-statistic title="训练步数" :value="modelInfo?.total_steps || 0" />
      </el-col>
      <el-col :xs="12" :sm="6">
        <el-statistic title="探索率" :value="modelInfo?.exploration_rate || 0" :precision="2" />
      </el-col>
      <el-col :xs="12" :sm="6">
        <el-statistic title="状态维度" :value="modelInfo?.state_dim || 0" />
      </el-col>
      <el-col :xs="12" :sm="6">
        <el-statistic title="平均奖励" :value="modelInfo?.avg_reward || 0" :precision="3" />
      </el-col>
    </el-row>

    <el-divider />

    <div class="control-grid">
      <section class="control-section">
        <h4>模型参数</h4>
        <div class="slider-row">
          <span class="field-label">探索率</span>
          <el-slider
            v-model="explorationDraft"
            :min="0"
            :max="1"
            :step="0.01"
            show-input
            :show-input-controls="false"
          />
          <el-button
            type="primary"
            :icon="Edit"
            :loading="loading.rate"
            @click="handleUpdateRate"
          >
            更新
          </el-button>
        </div>
        <el-alert
          :title="`当前阶段：${phaseText[modelInfo?.exploration_phase || 'initial'] || modelInfo?.exploration_phase || '-'}`"
          type="info"
          :closable="false"
          show-icon
        />
      </section>

      <section class="control-section">
        <h4>方案优化</h4>
        <div class="proposal-row">
          <el-select
            v-model="selectedProposalId"
            placeholder="选择节能方案"
            filterable
            @change="loadHistory"
          >
            <el-option
              v-for="proposal in proposals"
              :key="proposal.id"
              :label="`${proposal.rule_name || proposal.template_id || '方案'} (#${proposal.id})`"
              :value="proposal.id"
            />
          </el-select>
          <el-button
            type="primary"
            :icon="DataAnalysis"
            :disabled="!selectedProposalId"
            :loading="loading.optimize"
            @click="handleOptimize"
          >
            执行 RL 优化
          </el-button>
          <el-button
            :icon="RefreshRight"
            :disabled="!selectedProposalId"
            :loading="loading.monitoring"
            @click="handleTrainFromMonitoring"
          >
            从监测数据训练
          </el-button>
        </div>
      </section>
    </div>

    <el-alert
      v-if="latestOptimization"
      class="optimization-result"
      :title="`优化完成：置信度 ${(latestOptimization.confidence * 100).toFixed(1)}%，探索率 ${latestOptimization.exploration_rate.toFixed(2)}`"
      :type="latestOptimization.exploration ? 'warning' : 'success'"
      :closable="false"
      show-icon
    >
      <template #default>
        <div class="adjustment-list">
          <span v-for="(item, key) in latestOptimization.adjustments" :key="key">
            {{ item.description || key }}：{{ item.value }}{{ item.unit || '' }}
          </span>
        </div>
      </template>
    </el-alert>

    <el-tabs v-model="activeTab" class="result-tabs">
      <el-tab-pane label="优化历史" name="history">
        <el-table :data="history.items" stripe max-height="280" v-loading="loading.history">
          <el-table-column prop="created_at" label="时间" min-width="165">
            <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="置信度" width="100">
            <template #default="{ row }">{{ formatPercent(row.confidence) }}</template>
          </el-table-column>
          <el-table-column label="探索" width="80">
            <template #default="{ row }">
              <el-tag :type="row.exploration ? 'warning' : 'success'" size="small">
                {{ row.exploration ? '是' : '否' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="调整建议" min-width="220" show-overflow-tooltip>
            <template #default="{ row }">{{ summarizeAdjustments(row.adjustments) }}</template>
          </el-table-column>
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tag :type="row.applied ? 'success' : 'info'" size="small">
                {{ row.applied ? '已应用' : '待应用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="90" fixed="right">
            <template #default="{ row }">
              <el-button
                link
                type="primary"
                :disabled="row.applied"
                @click="handleApply(row)"
              >
                应用
              </el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!loading.history && history.items.length === 0" description="暂无优化历史" />
      </el-tab-pane>

      <el-tab-pane label="在线训练" name="training">
        <el-form :model="trainingForm" label-width="110px" class="training-form">
          <el-form-item label="实际节能收益">
            <el-input-number v-model="trainingForm.actual_saving" :min="0" :precision="2" />
          </el-form-item>
          <el-form-item label="预期节能收益">
            <el-input-number v-model="trainingForm.expected_saving" :min="0.01" :precision="2" />
          </el-form-item>
          <el-form-item label="舒适度违反">
            <el-slider v-model="trainingForm.comfort_violation" :min="0" :max="1" :step="0.01" />
          </el-form-item>
          <el-form-item label="安全约束违反">
            <el-slider v-model="trainingForm.safety_violation" :min="0" :max="1" :step="0.01" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :icon="Promotion" :loading="loading.training" @click="handleTrain">
              执行训练步骤
            </el-button>
          </el-form-item>
        </el-form>
        <el-alert
          v-if="trainingResult"
          :title="`训练完成：奖励 ${trainingResult.reward.toFixed(3)}，达成率 ${(trainingResult.achievement_rate * 100).toFixed(1)}%，步骤 ${trainingResult.step}`"
          :type="trainingResult.network_updated ? 'success' : 'info'"
          :closable="false"
          show-icon
        />
      </el-tab-pane>
    </el-tabs>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Cpu, DataAnalysis, Download, Edit, Promotion, Refresh, RefreshRight } from '@element-plus/icons-vue'
import {
  applyProposalRLOptimization,
  getProposalRLHistory,
  getRLModelInfo,
  optimizeProposalWithRL,
  saveRLCheckpoint,
  trainRLFromMonitoring,
  trainRLModel,
  updateRLExplorationRate,
  type RLAdjustment,
  type RLModelInfo,
  type RLOptimizationHistory,
  type RLOptimizationHistoryItem,
  type RLOptimizationResult,
  type RLTrainingResult
} from '@/api/modules/proposal'

interface ProposalOption {
  id: number
  rule_name?: string
  template_id?: string
  status?: string
}

const props = defineProps<{ proposals: ProposalOption[] }>()

const phaseText: Record<string, string> = {
  initial: '初始探索',
  stable: '稳定利用',
  fluctuating: '动态探索',
  decaying: '探索衰减',
  manual: '人工设定'
}

const activeTab = ref('history')
const modelInfo = ref<RLModelInfo | null>(null)
const explorationDraft = ref(0.3)
const selectedProposalId = ref<number | null>(null)
const latestOptimization = ref<RLOptimizationResult | null>(null)
const history = reactive<RLOptimizationHistory>({ total: 0, items: [] })
const trainingResult = ref<RLTrainingResult | null>(null)
const trainingForm = reactive({
  actual_saving: 90,
  expected_saving: 100,
  comfort_violation: 0,
  safety_violation: 0
})
const loading = reactive({
  model: false,
  checkpoint: false,
  rate: false,
  optimize: false,
  history: false,
  training: false,
  monitoring: false
})

onMounted(loadModelInfo)

watch(
  () => props.proposals,
  (items) => {
    if (!items.length) {
      selectedProposalId.value = null
      history.items = []
      return
    }
    if (!selectedProposalId.value || !items.some(item => item.id === selectedProposalId.value)) {
      selectedProposalId.value = items[0].id
      loadHistory()
    }
  },
  { immediate: true }
)

function unwrap<T>(response: unknown): T {
  const value = response as { data?: T }
  return value?.data ?? (response as T)
}

function errorMessage(error: unknown, fallback: string): string {
  const detail = (error as any)?.response?.data?.detail
  return typeof detail === 'string' ? detail : fallback
}

async function loadModelInfo() {
  loading.model = true
  try {
    modelInfo.value = unwrap<RLModelInfo>(await getRLModelInfo())
    explorationDraft.value = modelInfo.value.exploration_rate
  } catch (error) {
    ElMessage.error(errorMessage(error, '加载 RL 模型信息失败'))
  } finally {
    loading.model = false
  }
}

async function handleUpdateRate() {
  loading.rate = true
  try {
    await updateRLExplorationRate(explorationDraft.value)
    ElMessage.success('探索率已更新')
    await loadModelInfo()
  } catch (error) {
    ElMessage.error(errorMessage(error, '更新探索率失败'))
  } finally {
    loading.rate = false
  }
}

async function handleSaveCheckpoint() {
  loading.checkpoint = true
  try {
    await saveRLCheckpoint()
    ElMessage.success('模型检查点已保存')
    await loadModelInfo()
  } catch (error) {
    ElMessage.error(errorMessage(error, '保存模型检查点失败'))
  } finally {
    loading.checkpoint = false
  }
}

async function handleOptimize() {
  if (!selectedProposalId.value) return
  loading.optimize = true
  try {
    latestOptimization.value = unwrap<RLOptimizationResult>(
      await optimizeProposalWithRL(selectedProposalId.value)
    )
    ElMessage.success('RL 优化已完成')
    await loadHistory()
  } catch (error) {
    ElMessage.error(errorMessage(error, 'RL 优化失败'))
  } finally {
    loading.optimize = false
  }
}

async function loadHistory() {
  if (!selectedProposalId.value) return
  loading.history = true
  try {
    const result = unwrap<RLOptimizationHistory>(
      await getProposalRLHistory(selectedProposalId.value)
    )
    history.total = result.total
    history.items = result.items || []
  } catch (error) {
    ElMessage.error(errorMessage(error, '加载优化历史失败'))
  } finally {
    loading.history = false
  }
}

async function handleApply(row: RLOptimizationHistoryItem) {
  if (!selectedProposalId.value) return
  await ElMessageBox.confirm('确认将该组参数建议标记为已应用？', '应用优化建议', { type: 'warning' })
  try {
    await applyProposalRLOptimization(selectedProposalId.value, row.id)
    ElMessage.success('优化建议已标记为应用')
    await loadHistory()
  } catch (error) {
    ElMessage.error(errorMessage(error, '应用优化建议失败'))
  }
}

async function handleTrain() {
  loading.training = true
  try {
    trainingResult.value = unwrap<RLTrainingResult>(
      await trainRLModel({
        proposal_id: selectedProposalId.value || undefined,
        ...trainingForm
      })
    )
    ElMessage.success('在线训练步骤已完成')
    await loadModelInfo()
  } catch (error) {
    ElMessage.error(errorMessage(error, '在线训练失败'))
  } finally {
    loading.training = false
  }
}

async function handleTrainFromMonitoring() {
  if (!selectedProposalId.value) return
  loading.monitoring = true
  try {
    trainingResult.value = unwrap<RLTrainingResult>(
      await trainRLFromMonitoring(selectedProposalId.value)
    )
    activeTab.value = 'training'
    ElMessage.success('监测数据训练已完成')
    await loadModelInfo()
  } catch (error) {
    ElMessage.warning(errorMessage(error, '当前方案暂无可用于训练的监测数据'))
  } finally {
    loading.monitoring = false
  }
}

function formatTime(value: string): string {
  return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '-'
}

function formatPercent(value?: number | null): string {
  return value == null ? '-' : `${(value * 100).toFixed(1)}%`
}

function summarizeAdjustments(adjustments?: Record<string, RLAdjustment> | null): string {
  if (!adjustments || Object.keys(adjustments).length === 0) return '无参数调整'
  return Object.entries(adjustments)
    .map(([key, item]) => `${item.description || key}: ${String(item.value)}${item.unit || ''}`)
    .join('；')
}
</script>

<style scoped lang="scss">
.rl-panel {
  margin-bottom: 20px;
  background: var(--bg-card-solid, #1a2a4a);

  .panel-header,
  .panel-title,
  .header-actions,
  .proposal-row,
  .slider-row {
    display: flex;
    align-items: center;
  }

  .panel-header {
    justify-content: space-between;
    gap: 16px;
  }

  .panel-title,
  .header-actions,
  .proposal-row {
    gap: 10px;
  }

  .panel-title {
    font-weight: 600;
  }

  .model-stats {
    min-height: 72px;
  }

  .control-grid {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
    gap: 24px;
  }

  .control-section h4 {
    margin: 0 0 14px;
    font-size: 15px;
  }

  .slider-row {
    gap: 14px;
    margin-bottom: 14px;
  }

  .slider-row .el-slider {
    flex: 1;
    min-width: 220px;
  }

  .field-label {
    flex: 0 0 52px;
    color: var(--text-secondary, rgba(255, 255, 255, 0.65));
  }

  .proposal-row {
    flex-wrap: wrap;
  }

  .proposal-row .el-select {
    flex: 1;
    min-width: 240px;
  }

  .optimization-result,
  .result-tabs {
    margin-top: 20px;
  }

  .adjustment-list {
    display: flex;
    flex-wrap: wrap;
    gap: 8px 18px;
    margin-top: 8px;
  }

  .training-form {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0 24px;
    max-width: 920px;
  }

  .training-form :deep(.el-form-item__content) {
    min-width: 0;
  }

  .training-form .el-input-number,
  .training-form .el-slider {
    width: 100%;
  }
}

@media (max-width: 1100px) {
  .rl-panel {
    .control-grid,
    .training-form {
      grid-template-columns: 1fr;
    }

    .panel-header {
      align-items: flex-start;
      flex-direction: column;
    }
  }
}
</style>
