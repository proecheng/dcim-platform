<template>
  <div class="energy-regulation">
    <!-- 统计卡片 -->
    <el-row :gutter="20" class="stat-cards">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-value">{{ configs.length }}</div>
            <div class="stat-label">调节配置数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-value success">{{ recommendations.length }}</div>
            <div class="stat-label">调节建议</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-value warning">{{ totalPowerSaving.toFixed(1) }}</div>
            <div class="stat-label">潜在节能 (kW)</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-value primary">{{ historyCount }}</div>
            <div class="stat-label">调节记录</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20">
      <!-- 调节配置列表 -->
      <el-col :span="14">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>负荷调节配置</span>
              <el-button type="primary" size="small" @click="showCreateDialog">
                <el-icon><Plus /></el-icon> 新增配置
              </el-button>
            </div>
          </template>

          <el-table :data="configs" stripe border v-loading="loading" max-height="400">
            <el-table-column prop="device_name" label="设备" width="120" />
            <el-table-column prop="regulation_type" label="调节类型" width="100">
              <template #default="{ row }">
                <el-tag :type="typeTagMap[row.regulation_type]" size="small">
                  {{ typeTextMap[row.regulation_type] }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="当前值" width="100">
              <template #default="{ row }">
                {{ row.current_value ?? row.default_value }}{{ row.unit }}
              </template>
            </el-table-column>
            <el-table-column label="范围" width="100">
              <template #default="{ row }">
                {{ row.min_value }} - {{ row.max_value }}{{ row.unit }}
              </template>
            </el-table-column>
            <el-table-column label="调节" width="200">
              <template #default="{ row }">
                <el-slider
                  v-model="row.current_value"
                  :min="row.min_value"
                  :max="row.max_value"
                  :step="row.step_size"
                  :disabled="!row.is_enabled"
                  @change="(val: number) => handleSliderChange(row, val)"
                  size="small"
                />
              </template>
            </el-table-column>
            <el-table-column label="状态" width="80">
              <template #default="{ row }">
                <el-switch v-model="row.is_enabled" @change="toggleConfig(row)" size="small" />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" link size="small" @click="simulateConfig(row)">
                  模拟
                </el-button>
                <el-button type="danger" link size="small" @click="deleteConfig(row)">
                  删除
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>

      <!-- 调节建议 -->
      <el-col :span="10">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>调节建议</span>
              <el-button type="primary" link @click="loadRecommendations">
                <el-icon><Refresh /></el-icon> 刷新
              </el-button>
            </div>
          </template>

          <div class="recommendations-list">
            <div
              v-for="rec in recommendations"
              :key="rec.config_id"
              class="recommendation-item"
              @click="applyRecommendation(rec)"
            >
              <div class="rec-header">
                <span class="device-name">{{ rec.device_name }}</span>
                <el-tag :type="rec.priority === 'high' ? 'danger' : 'warning'" size="small">
                  {{ rec.priority === 'high' ? '高优先' : '中优先' }}
                </el-tag>
              </div>
              <div class="rec-content">
                <span class="type">{{ typeTextMap[rec.regulation_type] }}</span>
                <span class="change">
                  {{ rec.current_value }} -> {{ rec.recommended_value }}
                </span>
              </div>
              <div class="rec-saving">
                预计节省: <strong>{{ rec.power_saving.toFixed(1) }} kW</strong>
              </div>
              <div class="rec-reason">{{ rec.reason }}</div>
            </div>
            <el-empty v-if="recommendations.length === 0" description="暂无调节建议" />
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 调节历史 -->
    <el-card shadow="hover" style="margin-top: 20px;">
      <template #header>
        <div class="card-header">
          <span>调节历史</span>
        </div>
      </template>

      <el-table :data="history" stripe border max-height="300">
        <el-table-column prop="device_name" label="设备" width="120" />
        <el-table-column prop="regulation_type" label="类型" width="100">
          <template #default="{ row }">
            {{ typeTextMap[row.regulation_type] }}
          </template>
        </el-table-column>
        <el-table-column label="调节" width="150">
          <template #default="{ row }">
            {{ row.old_value }} -> {{ row.new_value }}
          </template>
        </el-table-column>
        <el-table-column label="功率变化" width="120">
          <template #default="{ row }">
            <span :class="row.power_saved > 0 ? 'text-success' : ''">
              {{ row.power_saved > 0 ? '-' : '' }}{{ row.power_saved?.toFixed(1) }} kW
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="trigger_reason" label="原因" width="100" />
        <el-table-column prop="status" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.status === 'completed' ? 'success' : 'info'" size="small">
              {{ row.status === 'completed' ? '已完成' : row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="executed_at" label="执行时间" width="160" />
      </el-table>
    </el-card>

    <!-- 模拟结果对话框 -->
    <el-dialog v-model="simulateDialogVisible" title="调节模拟" width="500px">
      <div v-if="simulateResult" class="simulate-result">
        <div class="result-item">
          <span class="label">设备:</span>
          <span class="value">{{ simulateResult.device_name }}</span>
        </div>
        <div class="result-item">
          <span class="label">调节类型:</span>
          <span class="value">{{ typeTextMap[simulateResult.regulation_type] }}</span>
        </div>
        <div class="result-item">
          <span class="label">当前值:</span>
          <span class="value">{{ simulateResult.current_value }}</span>
        </div>
        <div class="result-item">
          <span class="label">目标值:</span>
          <span class="value">{{ simulateResult.target_value }}</span>
        </div>
        <div class="result-item">
          <span class="label">当前功率:</span>
          <span class="value">{{ simulateResult.current_power?.toFixed(2) }} kW</span>
        </div>
        <div class="result-item">
          <span class="label">预计功率:</span>
          <span class="value">{{ simulateResult.estimated_power?.toFixed(2) }} kW</span>
        </div>
        <div class="result-item highlight">
          <span class="label">功率变化:</span>
          <span class="value" :class="simulateResult.power_change < 0 ? 'text-success' : 'text-danger'">
            {{ simulateResult.power_change?.toFixed(2) }} kW
          </span>
        </div>
        <div class="result-item">
          <span class="label">舒适度影响:</span>
          <span class="value">{{ impactTextMap[simulateResult.comfort_impact] || '无' }}</span>
        </div>
        <div class="result-item">
          <span class="label">性能影响:</span>
          <span class="value">{{ impactTextMap[simulateResult.performance_impact] || '无' }}</span>
        </div>
      </div>
      <template #footer>
        <el-button @click="simulateDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="applySimulateResult">应用调节</el-button>
      </template>
    </el-dialog>

    <!-- 新增配置对话框 -->
    <el-dialog v-model="createDialogVisible" title="新增调节配置" width="500px">
      <el-form :model="createForm" label-width="100px">
        <el-form-item label="设备" required>
          <el-select v-model="createForm.device_id" placeholder="选择设备" style="width: 100%">
            <el-option
              v-for="device in devices"
              :key="device.id"
              :label="device.device_name"
              :value="device.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="调节类型" required>
          <el-select v-model="createForm.regulation_type" placeholder="选择类型" style="width: 100%">
            <el-option label="温度调节" value="temperature" />
            <el-option label="亮度调节" value="brightness" />
            <el-option label="运行模式" value="mode" />
            <el-option label="负载优先级" value="load" />
          </el-select>
        </el-form-item>
        <el-form-item label="最小值" required>
          <el-input-number v-model="createForm.min_value" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="最大值" required>
          <el-input-number v-model="createForm.max_value" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="默认值">
          <el-input-number v-model="createForm.default_value" style="width: 100%" />
        </el-form-item>
        <el-form-item label="步长" required>
          <el-input-number v-model="createForm.step_size" :min="0.1" :step="0.1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="基准功率">
          <el-input-number v-model="createForm.base_power" :min="0" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitCreate">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Plus, Refresh } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getRegulationConfigs,
  getRegulationHistory,
  getRegulationRecommendations,
  simulateRegulation,
  applyRegulation,
  createRegulationConfig,
  updateRegulationConfig,
  deleteRegulationConfig,
  getPowerDevices,
  type LoadRegulationConfig,
  type RegulationHistory,
  type RegulationRecommendation,
  type RegulationSimulateResponse,
  type PowerDevice
} from '@/api/modules/energy'

const loading = ref(false)
const configs = ref<LoadRegulationConfig[]>([])
const history = ref<RegulationHistory[]>([])
const recommendations = ref<RegulationRecommendation[]>([])
const devices = ref<PowerDevice[]>([])

const simulateDialogVisible = ref(false)
const simulateResult = ref<RegulationSimulateResponse | null>(null)
const currentSimulateConfig = ref<LoadRegulationConfig | null>(null)

const createDialogVisible = ref(false)
const createForm = ref({
  device_id: undefined as number | undefined,
  regulation_type: '',
  min_value: 0,
  max_value: 100,
  default_value: undefined as number | undefined,
  step_size: 1,
  base_power: undefined as number | undefined
})

const typeTextMap: Record<string, string> = {
  temperature: '温度',
  brightness: '亮度',
  mode: '模式',
  load: '负载'
}

type TagType = 'success' | 'warning' | 'danger' | 'info' | 'primary'

const typeTagMap: Record<string, TagType> = {
  temperature: 'danger',
  brightness: 'warning',
  mode: 'primary',
  load: 'success'
}

const impactTextMap: Record<string, string> = {
  none: '无影响',
  low: '轻微',
  medium: '中等',
  high: '较大'
}

const totalPowerSaving = computed(() => {
  return recommendations.value.reduce((sum, r) => sum + r.power_saving, 0)
})

const historyCount = computed(() => history.value.length)

onMounted(async () => {
  await loadAllData()
})

async function loadAllData() {
  loading.value = true
  try {
    await Promise.all([
      loadConfigs(),
      loadHistory(),
      loadRecommendations(),
      loadDevices()
    ])
  } finally {
    loading.value = false
  }
}

async function loadConfigs() {
  try {
    const res = await getRegulationConfigs()
    configs.value = res.data || []
  } catch (e) {
    console.error('加载配置失败', e)
  }
}

async function loadHistory() {
  try {
    const res = await getRegulationHistory({ limit: 50 })
    history.value = res.data || []
  } catch (e) {
    console.error('加载历史失败', e)
  }
}

async function loadRecommendations() {
  try {
    const res = await getRegulationRecommendations()
    recommendations.value = res.data || []
  } catch (e) {
    console.error('加载建议失败', e)
  }
}

async function loadDevices() {
  try {
    const res = await getPowerDevices({ is_enabled: true })
    devices.value = res.data || []
  } catch (e) {
    console.error('加载设备失败', e)
  }
}

async function handleSliderChange(config: LoadRegulationConfig, value: number) {
  currentSimulateConfig.value = config
  await simulateConfig(config, value)
}

async function simulateConfig(config: LoadRegulationConfig, targetValue?: number) {
  try {
    const res = await simulateRegulation({
      config_id: config.id,
      target_value: targetValue ?? config.current_value ?? config.default_value ?? config.min_value
    })
    simulateResult.value = res.data
    currentSimulateConfig.value = config
    simulateDialogVisible.value = true
  } catch (e) {
    ElMessage.error('模拟失败')
  }
}

async function applySimulateResult() {
  if (!simulateResult.value || !currentSimulateConfig.value) return

  try {
    await applyRegulation({
      config_id: simulateResult.value.config_id,
      target_value: simulateResult.value.target_value,
      reason: 'manual'
    })
    ElMessage.success('调节已应用')
    simulateDialogVisible.value = false
    await loadAllData()
  } catch (e) {
    ElMessage.error('应用失败')
  }
}

async function applyRecommendation(rec: RegulationRecommendation) {
  try {
    await ElMessageBox.confirm(
      `确定要将 ${rec.device_name} 的${typeTextMap[rec.regulation_type]}从 ${rec.current_value} 调整为 ${rec.recommended_value} 吗？`,
      '确认调节'
    )
    await applyRegulation({
      config_id: rec.config_id,
      target_value: rec.recommended_value,
      reason: 'recommendation'
    })
    ElMessage.success('调节已应用')
    await loadAllData()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('应用失败')
    }
  }
}

async function toggleConfig(config: LoadRegulationConfig) {
  try {
    await updateRegulationConfig(config.id, { is_enabled: config.is_enabled })
    ElMessage.success(config.is_enabled ? '已启用' : '已禁用')
  } catch (e) {
    ElMessage.error('操作失败')
    config.is_enabled = !config.is_enabled
  }
}

async function deleteConfig(config: LoadRegulationConfig) {
  try {
    await ElMessageBox.confirm(`确定要删除 ${config.device_name} 的调节配置吗？`, '确认删除')
    await deleteRegulationConfig(config.id)
    ElMessage.success('删除成功')
    await loadConfigs()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

function showCreateDialog() {
  createForm.value = {
    device_id: undefined,
    regulation_type: '',
    min_value: 0,
    max_value: 100,
    default_value: undefined,
    step_size: 1,
    base_power: undefined
  }
  createDialogVisible.value = true
}

async function submitCreate() {
  if (!createForm.value.device_id || !createForm.value.regulation_type) {
    ElMessage.warning('请填写必填项')
    return
  }
  try {
    await createRegulationConfig({
      device_id: createForm.value.device_id,
      regulation_type: createForm.value.regulation_type,
      min_value: createForm.value.min_value,
      max_value: createForm.value.max_value,
      default_value: createForm.value.default_value,
      step_size: createForm.value.step_size,
      base_power: createForm.value.base_power
    })
    ElMessage.success('创建成功')
    createDialogVisible.value = false
    await loadConfigs()
  } catch (e) {
    ElMessage.error('创建失败')
  }
}
</script>

<style scoped lang="scss">
.energy-regulation {
  .stat-cards {
    margin-bottom: 20px;
  }

  .stat-card {
    text-align: center;

    :deep(.el-card__body) {
      background-color: var(--bg-card-solid);
    }

    .stat-content {
      padding: 10px 0;
    }

    .stat-value {
      font-size: 28px;
      font-weight: bold;
      color: var(--primary-color);

      &.success { color: var(--success-color); }
      &.warning { color: var(--warning-color); }
      &.primary { color: var(--primary-color); }
    }

    .stat-label {
      font-size: 14px;
      color: var(--text-secondary);
      margin-top: 8px;
    }
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    color: var(--text-primary);
  }

  // Dark theme styles for el-card
  :deep(.el-card) {
    background-color: var(--bg-card-solid);
    border-color: var(--border-color);

    .el-card__header {
      background-color: var(--bg-card-solid);
      border-bottom-color: var(--border-color);
      color: var(--text-primary);
    }

    .el-card__body {
      background-color: var(--bg-card-solid);
      color: var(--text-regular);
    }
  }

  // Dark theme styles for el-table
  :deep(.el-table) {
    background-color: var(--bg-card-solid);
    color: var(--text-regular);

    th.el-table__cell {
      background-color: var(--bg-tertiary);
      color: var(--text-primary);
      border-bottom-color: var(--border-color);
    }

    td.el-table__cell {
      border-bottom-color: var(--border-color);
    }

    tr {
      background-color: var(--bg-card-solid);

      &:hover > td.el-table__cell {
        background-color: var(--bg-tertiary);
      }
    }

    &.el-table--striped .el-table__body tr.el-table__row--striped td.el-table__cell {
      background-color: var(--bg-tertiary);
    }

    &.el-table--border::after,
    &.el-table--border::before,
    .el-table__inner-wrapper::before {
      background-color: var(--border-color);
    }

    &.el-table--border .el-table__inner-wrapper {
      border-color: var(--border-color);
    }

    .el-table__border-left-patch,
    .el-table__border-bottom-patch {
      background-color: var(--border-color);
    }

    --el-table-border-color: var(--border-color);
    --el-table-header-bg-color: var(--bg-tertiary);
    --el-table-tr-bg-color: var(--bg-card-solid);
    --el-table-row-hover-bg-color: var(--bg-tertiary);
  }

  // Dark theme styles for el-dialog
  :deep(.el-dialog) {
    background-color: var(--bg-card-solid);

    .el-dialog__header {
      color: var(--text-primary);
    }

    .el-dialog__title {
      color: var(--text-primary);
    }

    .el-dialog__body {
      color: var(--text-regular);
    }
  }

  // Dark theme styles for el-form
  :deep(.el-form) {
    .el-form-item__label {
      color: var(--text-regular);
    }
  }

  // Dark theme styles for el-empty
  :deep(.el-empty) {
    .el-empty__description {
      color: var(--text-secondary);
    }
  }

  .recommendations-list {
    max-height: 400px;
    overflow-y: auto;

    .recommendation-item {
      padding: 12px;
      border: 1px solid var(--border-color);
      border-radius: 8px;
      margin-bottom: 12px;
      cursor: pointer;
      transition: all 0.3s;
      background-color: var(--bg-tertiary);

      &:hover {
        border-color: var(--primary-color);
        box-shadow: 0 2px 8px rgba(24, 144, 255, 0.2);
      }

      .rec-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 8px;

        .device-name {
          font-weight: bold;
          color: var(--text-primary);
        }
      }

      .rec-content {
        display: flex;
        gap: 16px;
        margin-bottom: 8px;
        color: var(--text-regular);

        .change {
          color: var(--primary-color);
          font-weight: bold;
        }
      }

      .rec-saving {
        color: var(--success-color);
        margin-bottom: 4px;
      }

      .rec-reason {
        font-size: 12px;
        color: var(--text-secondary);
      }
    }
  }

  .simulate-result {
    .result-item {
      display: flex;
      justify-content: space-between;
      padding: 8px 0;
      border-bottom: 1px solid var(--border-color);

      &.highlight {
        background: var(--bg-tertiary);
        padding: 12px;
        border-radius: 4px;
        margin: 8px 0;
        border-bottom: none;
      }

      .label {
        color: var(--text-secondary);
      }

      .value {
        font-weight: bold;
        color: var(--text-primary);
      }
    }
  }

  .text-success {
    color: var(--success-color);
  }

  .text-danger {
    color: var(--error-color);
  }
}
</style>
