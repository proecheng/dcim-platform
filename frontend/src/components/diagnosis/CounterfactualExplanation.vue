<script setup lang="ts">
/**
 * 反事实解释组件
 * Story 26.1: 反事实分析
 */
import { ref, computed, onMounted } from 'vue'
import { getCounterfactualAnalysis, type CounterfactualAnalysis } from '@/api/modules/diagnosis'
import { ElMessage } from 'element-plus'

interface Props {
  sessionId: number
}

const props = defineProps<Props>()

const loading = ref(false)
const analysis = ref<CounterfactualAnalysis | null>(null)
const error = ref<string | null>(null)

// 证据类型映射
const evidenceTypeMap: Record<string, string> = {
  sensor: '传感器',
  threshold: '阈值',
  rule: '规则',
  history: '历史',
  unknown: '未知',
}

// 格式化证据类型
const formatEvidenceType = (type: string) => evidenceTypeMap[type] || type

// 格式化置信度变化
const formatConfidenceChange = (change: number) => {
  const sign = change >= 0 ? '+' : ''
  return `${sign}${(change * 100).toFixed(1)}%`
}

// 置信度变化标签类型
const getConfidenceChangeType = (change: number) => {
  if (change >= 0.1) return 'success'
  if (change <= -0.1) return 'danger'
  return 'info'
}

// Top 3 证据（用于展示）
const topEvidences = computed(() => {
  if (!analysis.value) return []
  return analysis.value.top_evidences.slice(0, 3)
})

// 加载反事实分析
async function loadAnalysis() {
  loading.value = true
  error.value = null
  try {
    analysis.value = await getCounterfactualAnalysis(props.sessionId)
  } catch (e: any) {
    if (e.response?.status === 404) {
      error.value = '反事实分析不存在，可能尚未生成'
    } else {
      error.value = e.message || '加载失败'
      ElMessage.error('加载反事实分析失败')
    }
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadAnalysis()
})
</script>

<template>
  <el-card shadow="never" class="counterfactual-card">
    <template #header>
      <div class="card-header">
        <span class="card-title">反事实解释</span>
        <el-tooltip content="反事实分析通过移除关键证据，评估诊断结论的稳定性" placement="top">
          <el-icon><QuestionFilled /></el-icon>
        </el-tooltip>
      </div>
    </template>

    <!-- 加载状态 -->
    <div v-if="loading" class="loading-container">
      <el-skeleton :rows="5" animated />
    </div>

    <!-- 错误状态 -->
    <div v-else-if="error" class="error-container">
      <el-empty :description="error">
        <el-button type="primary" @click="loadAnalysis">重试</el-button>
      </el-empty>
    </div>

    <!-- 分析结果 -->
    <div v-else-if="analysis" class="analysis-content">
      <!-- 原始诊断信息 -->
      <div class="original-diagnosis">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="原始根因">
            {{ analysis.original_root_cause || '未知' }}
          </el-descriptions-item>
          <el-descriptions-item label="原始置信度">
            <el-tag type="success">{{ (analysis.original_confidence * 100).toFixed(1) }}%</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="分析耗时">
            {{ analysis.analysis_time_ms }} ms
          </el-descriptions-item>
          <el-descriptions-item label="分析时间">
            {{ new Date(analysis.created_at).toLocaleString() }}
          </el-descriptions-item>
        </el-descriptions>
      </div>

      <!-- Top 证据影响分析 -->
      <div class="evidence-impact">
        <h4 class="section-title">关键证据影响分析</h4>
        <el-table :data="topEvidences" border size="small" style="width: 100%">
          <el-table-column label="证据ID" prop="node_id" width="100" />
          <el-table-column label="类型" width="120">
            <template #default="{ row }">
              {{ formatEvidenceType(row.evidence_type) }}
            </template>
          </el-table-column>
          <el-table-column label="概率" width="100">
            <template #default="{ row }">
              {{ (row.probability * 100).toFixed(1) }}%
            </template>
          </el-table-column>
          <el-table-column label="传感器权重" width="120">
            <template #default="{ row }">
              {{ row.sensor_weight.toFixed(2) }}
            </template>
          </el-table-column>
          <el-table-column label="路径长度" width="100" prop="path_length" />
        </el-table>
      </div>

      <!-- 反事实场景 -->
      <div class="counterfactual-scenarios">
        <h4 class="section-title">反事实场景分析</h4>
        <el-collapse accordion>
          <el-collapse-item
            v-for="(scenario, index) in analysis.analysis_results"
            :key="index"
            :name="index"
          >
            <template #title>
              <div class="scenario-title">
                <span>移除证据 #{{ scenario.removed_evidence_id }}</span>
                <el-tag
                  :type="getConfidenceChangeType(scenario.confidence_change)"
                  size="small"
                  style="margin-left: 12px"
                >
                  {{ formatConfidenceChange(scenario.confidence_change) }}
                </el-tag>
                <el-tag
                  v-if="scenario.conclusion_changed"
                  type="warning"
                  size="small"
                  style="margin-left: 8px"
                >
                  结论改变
                </el-tag>
              </div>
            </template>
            <div class="scenario-content">
              <el-descriptions :column="1" border size="small">
                <el-descriptions-item label="新根因">
                  {{ scenario.new_root_cause || '无变化' }}
                </el-descriptions-item>
                <el-descriptions-item label="新置信度">
                  <el-tag>{{ (scenario.new_confidence * 100).toFixed(1) }}%</el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="置信度变化">
                  <el-tag :type="getConfidenceChangeType(scenario.confidence_change)">
                    {{ formatConfidenceChange(scenario.confidence_change) }}
                  </el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="结论是否改变">
                  <el-tag :type="scenario.conclusion_changed ? 'warning' : 'success'">
                    {{ scenario.conclusion_changed ? '是' : '否' }}
                  </el-tag>
                </el-descriptions-item>
              </el-descriptions>
            </div>
          </el-collapse-item>
        </el-collapse>
      </div>

      <!-- 解释说明 -->
      <el-alert
        type="info"
        :closable="false"
        style="margin-top: 16px"
      >
        <template #title>
          <strong>如何理解反事实分析？</strong>
        </template>
        <ul style="margin: 8px 0; padding-left: 20px">
          <li>如果移除某个证据后结论改变，说明该证据对诊断结果影响较大</li>
          <li>如果移除所有关键证据后结论仍不变，说明诊断结论较为稳定</li>
          <li>置信度变化幅度反映了证据的重要性</li>
        </ul>
      </el-alert>
    </div>
  </el-card>
</template>

<style scoped>
.counterfactual-card {
  margin-top: 16px;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.card-title {
  font-weight: 600;
  font-size: 16px;
}

.loading-container,
.error-container {
  padding: 24px;
}

.analysis-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.section-title {
  margin: 0 0 12px 0;
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.scenario-title {
  display: flex;
  align-items: center;
  width: 100%;
}

.scenario-content {
  padding: 12px;
  background-color: #f5f7fa;
  border-radius: 4px;
}
</style>
