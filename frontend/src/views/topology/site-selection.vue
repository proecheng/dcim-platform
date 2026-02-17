<template>
  <div class="site-selection-page">
    <!-- 左侧面板：查询条件 + 权重 -->
    <aside class="query-panel">
      <div class="panel-header">
        <el-icon :size="18"><MapLocation /></el-icon>
        <span>智能选址</span>
      </div>

      <el-form label-position="top" class="query-form" @submit.prevent>
        <!-- 需求参数 -->
        <div class="form-section-title">设备需求</div>

        <el-form-item label="所需U位" required>
          <el-input-number
            v-model="form.required_u"
            :min="1"
            :max="48"
            placeholder="U"
            style="width: 100%"
          />
        </el-form-item>

        <el-form-item label="功率需求 (kW)">
          <el-input-number
            v-model="form.required_power_kw"
            :min="0"
            :precision="1"
            placeholder="可选"
            style="width: 100%"
          />
        </el-form-item>

        <el-form-item label="承重需求 (kg)">
          <el-input-number
            v-model="form.required_weight_kg"
            :min="0"
            :precision="0"
            placeholder="可选"
            style="width: 100%"
          />
        </el-form-item>

        <!-- 权重滑块 -->
        <div class="form-section-title">评分权重</div>

        <div v-for="(w, idx) in weightSliders" :key="w.key" class="weight-item">
          <div class="weight-label">
            <span>{{ w.label }}</span>
            <span class="weight-value">{{ weights[w.key] }}%</span>
          </div>
          <el-slider
            v-model="weights[w.key]"
            :min="0"
            :max="100"
            :show-tooltip="false"
            @input="onWeightChange(idx)"
          />
        </div>

        <el-button
          type="primary"
          :loading="loading"
          :disabled="!form.required_u"
          style="width: 100%; margin-top: 12px"
          @click="handleSearch"
        >
          <el-icon><Search /></el-icon>
          推荐选址
        </el-button>
      </el-form>
    </aside>

    <!-- 右侧主区域 -->
    <main class="result-area">
      <!-- 候选列表 -->
      <div class="result-table-panel">
        <div class="panel-header">
          <span>候选机柜</span>
          <el-tag v-if="result" size="small" type="info">
            评估 {{ result.total_evaluated }} 台 · 合格 {{ result.qualified_count }} 台
          </el-tag>
        </div>

        <el-table
          v-if="result && result.candidates.length"
          :data="result.candidates"
          size="small"
          v-loading="loading"
          highlight-current-row
          @current-change="onRowSelect"
          class="candidate-table"
        >
          <el-table-column label="#" width="50" align="center">
            <template #default="{ $index }">
              <span class="rank-badge" :class="rankClass($index)">{{ $index + 1 }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="cabinet_code" label="机柜编码" min-width="120" show-overflow-tooltip />
          <el-table-column label="位置" min-width="150" show-overflow-tooltip>
            <template #default="{ row }">
              {{ [row.room_name, row.row_name].filter(Boolean).join(' / ') || '-' }}
            </template>
          </el-table-column>
          <el-table-column prop="available_u" label="可用U" width="80" align="center" />
          <el-table-column label="综合评分" min-width="160">
            <template #default="{ row }">
              <el-progress
                :percentage="Math.round(row.total_score)"
                :color="getScoreColor(row.total_score)"
                :stroke-width="14"
                :text-inside="true"
              />
            </template>
          </el-table-column>
          <el-table-column label="置信度" width="90" align="center">
            <template #default="{ row }">
              <el-tag
                size="small"
                :type="confidenceType(row.confidence)"
              >
                {{ confidenceLabel(row.confidence) }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>

        <el-empty v-else-if="!loading" description="输入需求参数后点击「推荐选址」" />
      </div>

      <!-- 维度评分详情 -->
      <div v-if="selectedCandidate" class="dimension-panel">
        <div class="panel-header">
          <span>{{ selectedCandidate.cabinet_code }} 评分详情</span>
        </div>
        <div class="dimension-list">
          <div
            v-for="d in selectedCandidate.dimensions"
            :key="d.dimension"
            class="dimension-item"
          >
            <div class="dim-header">
              <span class="dim-name">{{ d.dimension }}</span>
              <span class="dim-score">{{ d.weighted_score.toFixed(1) }}</span>
            </div>
            <el-progress
              :percentage="Math.round(d.score)"
              :color="getScoreColor(d.score)"
              :stroke-width="8"
            />
            <div class="dim-detail">{{ d.detail }}</div>
          </div>
        </div>
      </div>

      <!-- 平面图 -->
      <div v-if="hasGridData" class="floorplan-panel">
        <div class="panel-header"><span>机柜平面分布</span></div>
        <div class="floorplan-grid" :style="gridStyle">
          <div
            v-for="cell in gridCells"
            :key="`${cell.x}-${cell.y}`"
            class="grid-cell"
            :class="{ 'grid-cell--active': cell.candidate }"
            :style="{
              gridColumn: cell.x + 1,
              gridRow: cell.y + 1,
              background: cell.candidate ? getScoreColor(cell.candidate.total_score) : undefined
            }"
            :title="cell.candidate ? `${cell.candidate.cabinet_code}: ${Math.round(cell.candidate.total_score)}分` : ''"
          >
            <span v-if="cell.candidate" class="grid-label">{{ cell.candidate.cabinet_code }}</span>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { MapLocation, Search } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { getSmartSiteSelection } from '@/api/modules/topologyConfig'
import type { SmartSiteResponse, CabinetSiteScore, DimensionScore } from '@/api/modules/topologyConfig'

// ==================== 表单 ====================

const form = reactive({
  required_u: 4,
  required_power_kw: undefined as number | undefined,
  required_weight_kg: undefined as number | undefined
})

// ==================== 权重 ====================

type WeightKey = 'space' | 'power' | 'phase_balance' | 'temperature' | 'cooling'

const weightSliders: { key: WeightKey; label: string }[] = [
  { key: 'space', label: '空间余量' },
  { key: 'power', label: '电力余量' },
  { key: 'phase_balance', label: '相位均衡' },
  { key: 'temperature', label: '温度环境' },
  { key: 'cooling', label: '制冷能力' }
]

const weights = reactive<Record<WeightKey, number>>({
  space: 30,
  power: 25,
  phase_balance: 20,
  temperature: 15,
  cooling: 10
})

function onWeightChange(changedIdx: number) {
  const keys = weightSliders.map(w => w.key)
  const changedKey = keys[changedIdx]
  const changedVal = weights[changedKey]
  const remaining = 100 - changedVal
  const otherKeys = keys.filter((_, i) => i !== changedIdx)
  const otherSum = otherKeys.reduce((s, k) => s + weights[k], 0)

  if (otherSum === 0) {
    const each = Math.floor(remaining / otherKeys.length)
    const remainder = remaining - each * otherKeys.length
    otherKeys.forEach((k, i) => {
      weights[k] = each + (i < remainder ? 1 : 0)
    })
  } else {
    let distributed = 0
    otherKeys.forEach((k, i) => {
      if (i === otherKeys.length - 1) {
        weights[k] = Math.max(0, remaining - distributed)
      } else {
        const scaled = Math.max(0, Math.round((weights[k] / otherSum) * remaining))
        weights[k] = scaled
        distributed += scaled
      }
    })
  }
}

// ==================== 查询 ====================

const loading = ref(false)
const result = ref<SmartSiteResponse | null>(null)
const selectedCandidate = ref<CabinetSiteScore | null>(null)

async function handleSearch() {
  if (!form.required_u) {
    ElMessage.warning('请输入所需U位')
    return
  }
  loading.value = true
  selectedCandidate.value = null
  try {
    const res = await getSmartSiteSelection({
      required_u: form.required_u,
      required_power_kw: form.required_power_kw || undefined,
      required_weight_kg: form.required_weight_kg || undefined,
      limit: 20,
      weights: { ...weights }
    })
    const data = (res as unknown as { data?: SmartSiteResponse })
    result.value = data.data || (res as unknown as SmartSiteResponse)
    if (result.value.candidates.length) {
      selectedCandidate.value = result.value.candidates[0]
    }
  } catch {
    ElMessage.error('智能选址请求失败')
  } finally {
    loading.value = false
  }
}

function onRowSelect(row: CabinetSiteScore | null) {
  selectedCandidate.value = row
}

// ==================== 辅助函数 ====================

function getScoreColor(score: number): string {
  if (score >= 80) return '#67C23A'
  if (score >= 60) return '#E6A23C'
  return '#F56C6C'
}

function confidenceType(c: string): 'success' | 'warning' | 'danger' {
  if (c === 'high') return 'success'
  if (c === 'medium') return 'warning'
  return 'danger'
}

function confidenceLabel(c: string): string {
  if (c === 'high') return '高'
  if (c === 'medium') return '中'
  return '低'
}

function rankClass(idx: number): string {
  if (idx === 0) return 'rank--gold'
  if (idx === 1) return 'rank--silver'
  if (idx === 2) return 'rank--bronze'
  return ''
}

// ==================== 平面图 ====================

const hasGridData = computed(() => {
  if (!result.value) return false
  return result.value.candidates.some(c => c.grid_x != null && c.grid_y != null)
})

const gridCells = computed(() => {
  if (!result.value) return []
  const candidates = result.value.candidates.filter(c => c.grid_x != null && c.grid_y != null)
  return candidates.map(c => ({
    x: c.grid_x!,
    y: c.grid_y!,
    candidate: c
  }))
})

const gridStyle = computed(() => {
  if (!gridCells.value.length) return {}
  const maxX = Math.max(...gridCells.value.map(c => c.x)) + 1
  const maxY = Math.max(...gridCells.value.map(c => c.y)) + 1
  return {
    gridTemplateColumns: `repeat(${maxX}, 1fr)`,
    gridTemplateRows: `repeat(${maxY}, 1fr)`
  }
})

// suppress unused import warning
void (undefined as unknown as DimensionScore)
</script>

<style lang="scss" scoped>
@use '@/styles/mixins-25d' as *;

.site-selection-page {
  display: flex;
  height: 100%;
  gap: 16px;
  padding: 16px;
  background: #f0f2f5;
  @include page-dashboard(2);
}

/* ── 左侧面板 ── */
.query-panel {
  width: 300px;
  flex-shrink: 0;
  background: #fff;
  border-radius: 10px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
  padding: 20px 16px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.panel-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 16px;
}

.form-section-title {
  font-size: 12px;
  font-weight: 600;
  color: #909399;
  text-transform: uppercase;
  letter-spacing: 1px;
  margin: 16px 0 8px;
  padding-bottom: 6px;
  border-bottom: 1px solid #ebeef5;
}

.query-form {
  flex: 1;

  :deep(.el-form-item) {
    margin-bottom: 14px;
  }

  :deep(.el-form-item__label) {
    font-size: 13px;
    color: #606266;
    padding-bottom: 4px;
  }
}

/* ── 权重滑块 ── */
.weight-item {
  margin-bottom: 10px;
}

.weight-label {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  color: #606266;
  margin-bottom: 2px;
}

.weight-value {
  font-weight: 600;
  color: #409eff;
  font-size: 12px;
}

/* ── 右侧主区域 ── */
.result-area {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow-y: auto;
}

.result-table-panel,
.dimension-panel,
.floorplan-panel {
  background: #fff;
  border-radius: 10px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
  padding: 16px;
}

/* ── 排名徽章 ── */
.rank-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  font-size: 12px;
  font-weight: 700;
  color: #909399;
  background: #f4f4f5;
}

.rank--gold {
  background: linear-gradient(135deg, #f7d774, #e6a23c);
  color: #fff;
}

.rank--silver {
  background: linear-gradient(135deg, #d3dce6, #909399);
  color: #fff;
}

.rank--bronze {
  background: linear-gradient(135deg, #f0c78a, #c88a3a);
  color: #fff;
}

/* ── 候选表格 ── */
.candidate-table {
  :deep(.el-table__row) {
    cursor: pointer;
  }
}

/* ── 维度评分 ── */
.dimension-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 14px;
}

.dimension-item {
  padding: 10px 12px;
  border-radius: 8px;
  background: #fafafa;
  border: 1px solid #ebeef5;
}

.dim-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 6px;
}

.dim-name {
  font-size: 13px;
  font-weight: 500;
  color: #303133;
}

.dim-score {
  font-size: 13px;
  font-weight: 700;
  color: #409eff;
}

.dim-detail {
  font-size: 11px;
  color: #909399;
  margin-top: 4px;
  line-height: 1.4;
}

/* ── 平面图 ── */
.floorplan-grid {
  display: grid;
  gap: 4px;
  min-height: 120px;
  padding: 8px;
}

.grid-cell {
  aspect-ratio: 1;
  border-radius: 4px;
  background: #f0f2f5;
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 40px;
  min-height: 40px;
  transition: transform 0.2s ease;
}

.grid-cell--active {
  color: #fff;
  font-weight: 600;
  cursor: default;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);

  &:hover {
    transform: scale(1.08);
  }
}

.grid-label {
  font-size: 10px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
  padding: 0 2px;
}
</style>
