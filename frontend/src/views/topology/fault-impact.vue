<template>
  <div class="fault-impact-page">
    <!-- 顶部操作栏 -->
    <div class="action-bar">
      <div class="action-bar-inner">
        <el-icon :size="20" class="action-bar-icon"><Warning /></el-icon>
        <span class="action-bar-title">故障影响分析</span>

        <div class="action-controls">
          <el-select
            v-model="faultSourceType"
            placeholder="故障源类型"
            style="width: 140px"
            @change="handleSourceTypeChange"
          >
            <el-option label="PDU" value="pdu" />
            <el-option label="配电柜" value="panel" />
          </el-select>

          <el-select
            v-if="faultSourceType === 'pdu'"
            v-model="faultSourceId"
            placeholder="选择 PDU 设备"
            filterable
            style="width: 240px"
          >
            <el-option
              v-for="item in pduOptions"
              :key="item.id"
              :label="`${item.device_code} - ${item.device_name}`"
              :value="item.id"
            />
          </el-select>

          <el-input-number
            v-else
            v-model="faultSourceId"
            :min="1"
            placeholder="配电柜 ID"
            style="width: 180px"
            controls-position="right"
          />

          <el-button
            type="danger"
            :loading="loading"
            :disabled="!faultSourceId"
            @click="handleAnalyze"
          >
            <el-icon><Search /></el-icon>
            开始分析
          </el-button>
        </div>
      </div>
    </div>

    <!-- 影响概览卡片 -->
    <el-row :gutter="16" class="summary-row" v-if="result">
      <el-col :span="6" v-for="card in summaryCards" :key="card.label">
        <div class="summary-card" :class="card.cls">
          <div class="summary-card-value">{{ card.value }}</div>
          <div class="summary-card-label">{{ card.label }}</div>
        </div>
      </el-col>
    </el-row>

    <!-- 分析结果区域 -->
    <div class="result-area" v-if="result">
      <!-- 受影响机柜 -->
      <div class="result-panel">
        <div class="panel-header">
          <span class="panel-title">受影响机柜</span>
          <el-tag size="small" type="info">{{ result.affected_cabinets.length }} 台</el-tag>
        </div>
        <el-table :data="result.affected_cabinets" size="small" stripe>
          <el-table-column prop="cabinet_code" label="机柜编码" min-width="110" show-overflow-tooltip />
          <el-table-column prop="cabinet_name" label="机柜名称" min-width="130" show-overflow-tooltip />
          <el-table-column prop="location" label="位置" min-width="120" show-overflow-tooltip>
            <template #default="{ row }">{{ row.location || '-' }}</template>
          </el-table-column>
          <el-table-column prop="feed_type" label="供电路径" width="100" align="center">
            <template #default="{ row }">
              <el-tag v-if="row.feed_type" size="small" :type="row.feed_type === 'primary' ? 'success' : 'warning'">
                {{ row.feed_type === 'primary' ? '主路' : '备路' }}
              </el-tag>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column prop="phase" label="相位" width="80" align="center">
            <template #default="{ row }">{{ row.phase || '-' }}</template>
          </el-table-column>
          <el-table-column prop="asset_count" label="设备数" width="80" align="center" />
          <el-table-column prop="impact_level" label="影响级别" width="100" align="center">
            <template #default="{ row }">
              <el-tag
                size="small"
                :type="row.impact_level === 'power_loss' ? 'danger' : row.impact_level === 'degraded' ? 'warning' : 'info'"
              >
                {{ row.impact_level === 'power_loss' ? '断电' : row.impact_level === 'degraded' ? '降级' : row.impact_level }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="has_redundancy" label="冗余供电" width="100" align="center">
            <template #default="{ row }">
              <el-tag size="small" :type="row.has_redundancy ? 'success' : 'danger'">
                {{ row.has_redundancy ? '有' : '无' }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <!-- 受影响设备 -->
      <div class="result-panel">
        <div class="panel-header">
          <span class="panel-title">受影响设备</span>
          <el-tag size="small" type="info">{{ result.affected_assets.length }} 台</el-tag>
        </div>
        <el-table :data="result.affected_assets" size="small" stripe>
          <el-table-column prop="asset_code" label="资产编码" min-width="130" show-overflow-tooltip />
          <el-table-column prop="asset_name" label="资产名称" min-width="160" show-overflow-tooltip />
          <el-table-column prop="asset_type" label="资产类型" min-width="120" show-overflow-tooltip>
            <template #default="{ row }">{{ row.asset_type || '-' }}</template>
          </el-table-column>
          <el-table-column prop="cabinet_code" label="所属机柜" min-width="120" show-overflow-tooltip>
            <template #default="{ row }">{{ row.cabinet_code || '-' }}</template>
          </el-table-column>
        </el-table>
      </div>

      <!-- 制冷交叉影响 -->
      <div class="result-panel" v-if="result.cooling_impacts.length">
        <div class="panel-header">
          <span class="panel-title">制冷交叉影响</span>
          <el-tag size="small" type="info">{{ result.cooling_impacts.length }} 个区域</el-tag>
        </div>
        <el-table :data="result.cooling_impacts" size="small" stripe>
          <el-table-column prop="zone_name" label="制冷区域" min-width="140" show-overflow-tooltip />
          <el-table-column label="受影响/总机柜" width="140" align="center">
            <template #default="{ row }">
              {{ row.affected_cabinet_count }} / {{ row.total_cabinet_count }}
            </template>
          </el-table-column>
          <el-table-column label="空调设备" min-width="200" show-overflow-tooltip>
            <template #default="{ row }">
              {{ row.cooling_units.join(', ') || '-' }}
            </template>
          </el-table-column>
          <el-table-column prop="same_power_circuit" label="同回路" width="100" align="center">
            <template #default="{ row }">
              <el-tag size="small" :type="row.same_power_circuit ? 'danger' : 'success'">
                {{ row.same_power_circuit ? '是' : '否' }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <!-- 关联告警 -->
      <div class="result-panel" v-if="result.related_alarms.length">
        <div class="panel-header">
          <span class="panel-title">关联告警</span>
          <el-tag size="small" type="info">{{ result.related_alarms.length }} 条</el-tag>
        </div>
        <el-table :data="result.related_alarms" size="small" stripe>
          <el-table-column prop="alarm_no" label="告警编号" min-width="140" show-overflow-tooltip />
          <el-table-column prop="alarm_level" label="告警级别" width="100" align="center">
            <template #default="{ row }">
              <el-tag size="small" :type="alarmLevelType(row.alarm_level)">
                {{ row.alarm_level }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="alarm_message" label="告警消息" min-width="220" show-overflow-tooltip />
          <el-table-column prop="status" label="状态" width="100" align="center">
            <template #default="{ row }">{{ row.status }}</template>
          </el-table-column>
        </el-table>
      </div>

      <!-- 建议操作 -->
      <div class="result-panel" v-if="result.suggestions.length">
        <div class="panel-header">
          <span class="panel-title">建议操作</span>
        </div>
        <div class="suggestions-list">
          <el-alert
            v-for="(s, idx) in result.suggestions"
            :key="idx"
            :title="s"
            type="warning"
            show-icon
            :closable="false"
            class="suggestion-item"
          />
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div class="empty-state" v-if="!result && !loading">
      <el-empty description="选择故障源设备后点击「开始分析」查看影响范围" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { Warning, Search } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { getFaultImpactAnalysis } from '@/api/modules/topologyConfig'
import type { FaultImpactResponse } from '@/api/modules/topologyConfig'
import { getPDUList } from '@/api/modules/power'

// ==================== 状态 ====================

const faultSourceType = ref<'pdu' | 'panel'>('pdu')
const faultSourceId = ref<number | undefined>(undefined)
const loading = ref(false)
const result = ref<FaultImpactResponse | null>(null)

// ==================== PDU 选项 ====================

interface PduOption {
  id: number
  device_code: string
  device_name: string
}

const pduOptions = ref<PduOption[]>([])

async function loadPduOptions() {
  try {
    const res = await getPDUList({ page: 1, page_size: 500 })
    const data = res as unknown as { items?: PduOption[]; data?: PduOption[] }
    pduOptions.value = data.items || data.data || (Array.isArray(res) ? (res as PduOption[]) : [])
  } catch {
    pduOptions.value = []
  }
}

function handleSourceTypeChange() {
  faultSourceId.value = undefined
  result.value = null
}

// ==================== 分析 ====================

async function handleAnalyze() {
  if (!faultSourceId.value) {
    ElMessage.warning('请选择故障源设备')
    return
  }
  loading.value = true
  result.value = null
  try {
    const res = await getFaultImpactAnalysis({
      fault_source_type: faultSourceType.value,
      fault_source_id: faultSourceId.value
    })
    const data = res as unknown as { data?: FaultImpactResponse }
    result.value = data.data || (res as unknown as FaultImpactResponse)
  } catch {
    ElMessage.error('故障影响分析请求失败')
  } finally {
    loading.value = false
  }
}

// ==================== 概览卡片 ====================

const summaryCards = computed(() => {
  if (!result.value) return []
  return [
    { label: '受影响机柜', value: result.value.affected_cabinets.length, cls: 'card-cabinet' },
    { label: '受影响设备', value: result.value.affected_assets.length, cls: 'card-asset' },
    { label: '制冷区域影响', value: result.value.cooling_impacts.length, cls: 'card-cooling' },
    { label: '关联告警', value: result.value.related_alarms.length, cls: 'card-alarm' }
  ]
})

// ==================== 辅助 ====================

function alarmLevelType(level: string): 'danger' | 'warning' | 'info' | 'success' {
  if (level === '紧急' || level === 'critical') return 'danger'
  if (level === '重要' || level === 'major') return 'warning'
  if (level === '次要' || level === 'minor') return 'info'
  return 'success'
}

// ==================== 生命周期 ====================

onMounted(() => {
  loadPduOptions()
})
</script>

<style lang="scss" scoped>
@use '@/styles/_mixins-25d' as *;

.fault-impact-page {
  height: 100%;
  padding: 16px;
  background: #f0f2f5;
  overflow-y: auto;
  @include page-dashboard(2);
}

/* ── 操作栏 ── */
.action-bar {
  background: #fff;
  border-radius: 10px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
  padding: 16px 20px;
  margin-bottom: 16px;
}

.action-bar-inner {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.action-bar-icon {
  color: #e6a23c;
}

.action-bar-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
  margin-right: 16px;
}

.action-controls {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

/* ── 概览卡片 ── */
.summary-row {
  margin-bottom: 16px;
}

.summary-card {
  background: #fff;
  border-radius: 10px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
  padding: 20px;
  text-align: center;
  border-top: 3px solid #dcdfe6;
  transition: transform 0.2s ease, box-shadow 0.2s ease;

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
  }
}

.summary-card-value {
  font-size: 32px;
  font-weight: 700;
  color: #303133;
  line-height: 1.2;
}

.summary-card-label {
  font-size: 13px;
  color: #909399;
  margin-top: 6px;
}

.card-cabinet {
  border-top-color: #f56c6c;

  .summary-card-value {
    color: #f56c6c;
  }
}

.card-asset {
  border-top-color: #e6a23c;

  .summary-card-value {
    color: #e6a23c;
  }
}

.card-cooling {
  border-top-color: #409eff;

  .summary-card-value {
    color: #409eff;
  }
}

.card-alarm {
  border-top-color: #f56c6c;

  .summary-card-value {
    color: #f56c6c;
  }
}

/* ── 结果区域 ── */
.result-area {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.result-panel {
  background: #fff;
  border-radius: 10px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
  padding: 16px;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.panel-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

/* ── 建议列表 ── */
.suggestions-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.suggestion-item {
  border-radius: 6px;
}

/* ── 空状态 ── */
.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 300px;
  background: #fff;
  border-radius: 10px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
}
</style>
