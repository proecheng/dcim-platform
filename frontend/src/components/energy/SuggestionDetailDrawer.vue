<template>
  <el-drawer
    v-model="visible"
    :title="suggestion?.suggestion || '建议详情'"
    direction="rtl"
    size="60%"
    :before-close="handleClose"
    class="suggestion-detail-drawer"
  >
    <template #header>
      <div class="drawer-header">
        <div class="header-title">
          <el-tag :type="priorityType[suggestion?.priority || 'medium']" size="small">
            {{ priorityText[suggestion?.priority || 'medium'] }}
          </el-tag>
          <span class="title-text">{{ suggestion?.suggestion || '建议详情' }}</span>
        </div>
        <div class="header-meta">
          <el-tag size="small" :type="statusType[suggestion?.status || 'pending']">
            {{ statusText[suggestion?.status || 'pending'] }}
          </el-tag>
          <span class="template-id">{{ suggestion?.template_id }}</span>
        </div>
      </div>
    </template>

    <div class="drawer-content" v-loading="loading">
      <el-tabs v-model="activeTab" class="detail-tabs">
        <!-- 概览标签页 -->
        <el-tab-pane label="概览" name="overview">
          <SuggestionOverview v-if="suggestionDetail" :suggestion="suggestionDetail" />
        </el-tab-pane>

        <!-- 参数调整标签页 -->
        <el-tab-pane label="参数调整" name="params" :disabled="!hasAdjustableParams">
          <ParameterAdjustment
            v-if="suggestionDetail && hasAdjustableParams"
            ref="paramAdjustmentRef"
            :suggestion="suggestionDetail"
            @params-changed="handleParamsChanged"
          />
          <el-empty v-else description="该建议类型不支持参数调整" />
        </el-tab-pane>

        <!-- 计算详情标签页 -->
        <el-tab-pane label="计算详情" name="calculation" :disabled="!hasCalculation">
          <CalculationDetails
            v-if="suggestionDetail && hasCalculation"
            :suggestion="suggestionDetail"
          />
          <el-empty v-else description="暂无计算详情" />
        </el-tab-pane>

        <!-- 涉及设备标签页 -->
        <el-tab-pane label="涉及设备" name="devices" :disabled="!hasDevices">
          <DeviceList
            v-if="suggestionDetail && hasDevices"
            :suggestion="suggestionDetail"
          />
          <el-empty v-else description="暂无设备信息" />
        </el-tab-pane>

        <!-- 可视化分析标签页（V2.5新增） -->
        <el-tab-pane label="可视化分析" name="visualization" :disabled="!hasVisualization">
          <div v-if="suggestionDetail && hasVisualization" class="visualization-container">
            <!-- A1: 峰谷套利优化 - 显示负荷分布和对比图 -->
            <template v-if="suggestion?.template_id === 'A1'">
              <LoadPeriodChart
                :meter-point-id="suggestionDetail.meter_point_id"
                :show-pricing="true"
                :highlight-periods="['peak', 'valley']"
                class="embedded-chart"
              />
              <LoadComparisonChart
                v-if="suggestionDetail.hourly_data"
                :hourly-data="suggestionDetail.hourly_data"
                :shift-power="suggestionDetail.shift_power || 0"
                :shift-hours="suggestionDetail.shift_hours || 0"
                :source-period="suggestionDetail.source_period || 'peak'"
                :target-period="suggestionDetail.target_period || 'valley'"
                class="embedded-chart"
              />
            </template>

            <!-- A2: 需量控制方案 - 显示需量曲线和配置对比 -->
            <template v-else-if="suggestion?.template_id === 'A2'">
              <DemandCurveMini
                :meter-point-id="suggestionDetail.meter_point_id"
                time-range="12m"
                :show-threshold="suggestionDetail.current_declared"
                :highlight-max="true"
                :height="240"
                class="embedded-chart"
              />
              <DemandComparisonCard
                :meter-point-id="suggestionDetail.meter_point_id"
                :analysis-data="suggestionDetail"
                :compact="true"
                class="embedded-chart"
              />
            </template>

            <!-- A3/A5: 设备运行优化 / 负荷调度优化 - 显示负荷分布 -->
            <template v-else-if="['A3', 'A5'].includes(suggestion?.template_id || '')">
              <LoadPeriodChart
                :meter-point-id="suggestionDetail.meter_point_id"
                :show-pricing="true"
                class="embedded-chart"
              />
            </template>

            <!-- 其他模板 - 显示通用提示 -->
            <template v-else>
              <el-empty description="该方案类型暂无可视化分析" :image-size="100" />
            </template>
          </div>
          <el-empty v-else description="暂无可视化数据" />
        </el-tab-pane>
      </el-tabs>
    </div>

    <template #footer>
      <div class="drawer-footer">
        <div class="footer-info" v-if="adjustedEffects">
          <span class="adjusted-label">调整后预计年节省:</span>
          <span class="adjusted-value">
            {{ (adjustedEffects.annual_saving_yuan / 10000).toFixed(2) }} 万元
          </span>
        </div>
        <div class="footer-actions">
          <el-button @click="handleClose">取消</el-button>
          <el-button
            v-if="suggestion?.status === 'pending'"
            type="primary"
            @click="handleAccept"
            :loading="accepting"
          >
            接受建议
          </el-button>
        </div>
      </div>
    </template>
  </el-drawer>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import SuggestionOverview from './SuggestionOverview.vue'
import ParameterAdjustment from './ParameterAdjustment.vue'
import CalculationDetails from './CalculationDetails.vue'
import DeviceList from './DeviceList.vue'
import {
  getSuggestionFullDetail,
  acceptSuggestion,
  type SuggestionDetail,
  type EnergySuggestion
} from '@/api/modules/energy'

// V2.5: 导入可视化组件
import { DemandComparisonCard, DemandCurveMini, LoadPeriodChart } from '@/components/demand'
import { LoadComparisonChart } from '@/components/energy'

const props = defineProps<{
  modelValue: boolean
  suggestion: EnergySuggestion | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'accepted'): void
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const loading = ref(false)
const accepting = ref(false)
const activeTab = ref('overview')
const suggestionDetail = ref<SuggestionDetail | null>(null)
const adjustedEffects = ref<any>(null)
const paramAdjustmentRef = ref<InstanceType<typeof ParameterAdjustment> | null>(null)

// 标签映射
const priorityText: Record<string, string> = {
  urgent: '紧急',
  high: '高',
  medium: '中',
  low: '低'
}

const priorityType: Record<string, 'danger' | 'warning' | 'info' | 'success' | 'primary'> = {
  urgent: 'danger',
  high: 'danger',
  medium: 'warning',
  low: 'info'
}

const statusText: Record<string, string> = {
  pending: '待处理',
  accepted: '已接受',
  rejected: '已拒绝',
  completed: '已完成'
}

const statusType: Record<string, 'danger' | 'warning' | 'info' | 'success' | 'primary'> = {
  pending: 'primary',
  accepted: 'warning',
  rejected: 'danger',
  completed: 'success'
}

// 是否有可调整参数
const hasAdjustableParams = computed(() => {
  const params = suggestionDetail.value?.parameters
  console.log('检查可调整参数:', params?.adjustable_params)
  const hasParams = (params?.adjustable_params?.length || 0) > 0
  const hasDevices = (params?.devices?.length || 0) > 0
  return hasParams || hasDevices
})

// 是否有计算公式
const hasCalculation = computed(() => {
  const hasFormula = !!suggestionDetail.value?.parameters?.calculation_formula
  console.log('检查计算公式:', hasFormula, suggestionDetail.value?.parameters?.calculation_formula)
  return hasFormula
})

// 是否有设备信息
const hasDevices = computed(() => {
  const detail = suggestionDetail.value
  const paramsDevices = (detail?.parameters?.devices?.length || 0) > 0
  const rootDevices = (detail?.shiftable_devices?.length || 0) > 0
  console.log('检查设备信息:', { paramsDevices, rootDevices,
    params_devices: detail?.parameters?.devices,
    shiftable_devices: detail?.shiftable_devices
  })
  return paramsDevices || rootDevices
})

// V2.5: 是否有可视化分析（基于模板类型）
const hasVisualization = computed(() => {
  const templateId = props.suggestion?.template_id
  // A1(峰谷套利), A2(需量控制), A3(设备运行优化), A5(负荷调度) 支持可视化
  const supportedTemplates = ['A1', 'A2', 'A3', 'A5']
  return templateId && supportedTemplates.includes(templateId)
})

// 监听建议变化
watch(() => props.suggestion, async (newVal) => {
  console.log('[Drawer] suggestion变化:', { newVal, visible: visible.value, id: newVal?.id })
  if (newVal && visible.value) {
    console.log('[Drawer] suggestion watch 触发loadDetail')
    await loadDetail()
  }
}, { immediate: true })

watch(visible, async (newVal) => {
  console.log('[Drawer] visible变化:', { newVal, suggestion: props.suggestion, id: props.suggestion?.id })
  if (newVal && props.suggestion) {
    console.log('[Drawer] visible watch 触发loadDetail')
    await loadDetail()
  } else {
    // 重置状态
    activeTab.value = 'overview'
    adjustedEffects.value = null
  }
})

async function loadDetail() {
  console.log('[Drawer] loadDetail 被调用, suggestion:', props.suggestion)
  if (!props.suggestion?.id) {
    console.warn('[Drawer] loadDetail 提前返回: suggestion.id 不存在')
    return
  }

  console.log('[Drawer] 开始加载详情, id:', props.suggestion.id)
  loading.value = true
  try {
    console.log('[Drawer] 调用 getSuggestionFullDetail API...')
    const res = await getSuggestionFullDetail(props.suggestion.id)
    console.log('建议详情API响应:', res)
    if (res.code === 0 && res.data) {
      suggestionDetail.value = res.data
      console.log('加载的建议详情:', suggestionDetail.value)
      console.log('参数字段:', suggestionDetail.value.parameters)
    } else {
      console.warn('API返回异常:', res)
      ElMessage.warning('未能加载建议详情数据')
    }
  } catch (e) {
    console.error('加载详情失败', e)
    ElMessage.error('加载详情失败')
  } finally {
    loading.value = false
  }
}

function handleParamsChanged(params: any, effects: any) {
  adjustedEffects.value = effects
}

async function handleAccept() {
  if (!props.suggestion?.id) return

  // 获取调整后的参数
  const adjustedParams = paramAdjustmentRef.value?.getParams()

  await ElMessageBox.confirm(
    adjustedEffects.value
      ? `确定接受该建议？调整后预计年节省 ${(adjustedEffects.value.annual_saving_yuan / 10000).toFixed(2)} 万元`
      : '确定接受该建议？',
    '确认',
    { type: 'info' }
  )

  accepting.value = true
  try {
    await acceptSuggestion(props.suggestion.id, {
      remark: adjustedParams ? `已调整参数: ${JSON.stringify(adjustedParams)}` : undefined
    })
    ElMessage.success('已接受建议')
    emit('accepted')
    handleClose()
  } catch (e) {
    console.error('接受建议失败', e)
    ElMessage.error('操作失败')
  } finally {
    accepting.value = false
  }
}

function handleClose() {
  visible.value = false
}
</script>

<style scoped lang="scss">
.suggestion-detail-drawer {
  :deep(.el-drawer__header) {
    margin-bottom: 0;
    padding: 16px 20px;
    border-bottom: 1px solid var(--border-color, rgba(255, 255, 255, 0.1));
  }

  :deep(.el-drawer__body) {
    padding: 0;
  }

  :deep(.el-drawer__footer) {
    padding: 16px 20px;
    border-top: 1px solid var(--border-color, rgba(255, 255, 255, 0.1));
  }

  .drawer-header {
    .header-title {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 8px;

      .title-text {
        font-size: 16px;
        font-weight: 500;
      }
    }

    .header-meta {
      display: flex;
      align-items: center;
      gap: 12px;

      .template-id {
        font-size: 12px;
        color: var(--text-secondary, rgba(255, 255, 255, 0.65));
      }
    }
  }

  .drawer-content {
    height: calc(100% - 70px);
    overflow: hidden;

    .detail-tabs {
      height: 100%;

      :deep(.el-tabs__header) {
        padding: 0 20px;
        margin-bottom: 0;
        background: var(--bg-color-overlay, rgba(0, 0, 0, 0.2));
      }

      :deep(.el-tabs__content) {
        height: calc(100% - 55px);
        padding: 20px;
        overflow-y: auto;
      }
    }
  }

  // V2.5: 可视化容器样式
  .visualization-container {
    display: flex;
    flex-direction: column;
    gap: 20px;

    .embedded-chart {
      background: var(--bg-card-solid, #1a2a4a);
      border-radius: 8px;
      padding: 16px;
    }
  }

  .drawer-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;

    .footer-info {
      .adjusted-label {
        color: var(--text-secondary, rgba(255, 255, 255, 0.65));
        margin-right: 8px;
      }

      .adjusted-value {
        font-size: 18px;
        font-weight: bold;
        color: var(--success-color, #52c41a);
      }
    }

    .footer-actions {
      display: flex;
      gap: 12px;
    }
  }
}
</style>
