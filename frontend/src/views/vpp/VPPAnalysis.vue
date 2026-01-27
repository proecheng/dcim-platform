<template>
  <div class="vpp-analysis">
    <el-card class="header-card">
      <h2>虚拟电厂方案分析</h2>
      <p class="subtitle">所有数据指标均包含计算公式和数据来源</p>
    </el-card>

    <!-- 分析参数配置 -->
    <el-card class="config-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">分析参数配置</span>
        </div>
      </template>
      <el-form :inline="true" label-width="120px">
        <el-form-item label="分析月份">
          <el-select
            v-model="analysisMonths"
            multiple
            placeholder="选择月份"
            style="width: 300px"
          >
            <el-option
              v-for="month in availableMonths"
              :key="month"
              :label="month"
              :value="month"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="负荷数据范围">
          <el-date-picker
            v-model="dateRange"
            type="daterange"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
            style="width: 300px"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="runAnalysis" :loading="loading">
            生成分析报告
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 分析结果展示 -->
    <template v-if="analysisResult">
      <!-- 用电规模指标 -->
      <el-card class="metric-card">
        <template #header>
          <div class="card-header">
            <span class="card-title">A. 用电规模指标</span>
          </div>
        </template>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="平均电价">
            <MetricDisplay :metric="analysisResult.electricity_usage?.average_price" />
          </el-descriptions-item>
          <el-descriptions-item label="月度波动率">
            <MetricDisplay :metric="analysisResult.electricity_usage?.fluctuation_rate" />
          </el-descriptions-item>
          <el-descriptions-item label="峰段用电占比">
            <MetricDisplay :metric="analysisResult.electricity_usage?.peak_ratio" />
          </el-descriptions-item>
          <el-descriptions-item label="谷段用电占比">
            <MetricDisplay :metric="analysisResult.electricity_usage?.valley_ratio" />
          </el-descriptions-item>
        </el-descriptions>
      </el-card>

      <!-- 负荷特性指标 -->
      <el-card class="metric-card">
        <template #header>
          <div class="card-header">
            <span class="card-title">B. 负荷特性指标</span>
          </div>
        </template>
        <el-descriptions :column="3" border>
          <el-descriptions-item label="最大负荷 (P_max)">
            <MetricDisplay :metric="analysisResult.load_characteristics?.P_max" />
          </el-descriptions-item>
          <el-descriptions-item label="平均负荷 (P_avg)">
            <MetricDisplay :metric="analysisResult.load_characteristics?.P_avg" />
          </el-descriptions-item>
          <el-descriptions-item label="最小负荷 (P_min)">
            <MetricDisplay :metric="analysisResult.load_characteristics?.P_min" />
          </el-descriptions-item>
          <el-descriptions-item label="日负荷率 (η)">
            <MetricDisplay :metric="analysisResult.load_characteristics?.load_rate" />
          </el-descriptions-item>
          <el-descriptions-item label="峰谷差 (ΔP)">
            <MetricDisplay :metric="analysisResult.load_characteristics?.peak_valley_diff" />
          </el-descriptions-item>
          <el-descriptions-item label="负荷标准差">
            <MetricDisplay :metric="analysisResult.load_characteristics?.load_std" />
          </el-descriptions-item>
        </el-descriptions>
      </el-card>

      <!-- 电费结构指标 -->
      <el-card class="metric-card">
        <template #header>
          <div class="card-header">
            <span class="card-title">C. 电费结构指标</span>
          </div>
        </template>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="市场化购电占比">
            <MetricDisplay :metric="analysisResult.cost_structure?.market_ratio" />
          </el-descriptions-item>
          <el-descriptions-item label="输配电费占比">
            <MetricDisplay :metric="analysisResult.cost_structure?.transmission_ratio" />
          </el-descriptions-item>
          <el-descriptions-item label="基本电费占比">
            <MetricDisplay :metric="analysisResult.cost_structure?.basic_fee_ratio" />
          </el-descriptions-item>
          <el-descriptions-item label="系统运行费占比">
            <MetricDisplay :metric="analysisResult.cost_structure?.system_operation_ratio" />
          </el-descriptions-item>
          <el-descriptions-item label="政府性基金占比" :span="2">
            <MetricDisplay :metric="analysisResult.cost_structure?.government_fund_ratio" />
          </el-descriptions-item>
        </el-descriptions>
      </el-card>

      <!-- 峰谷转移潜力 -->
      <el-card class="metric-card">
        <template #header>
          <div class="card-header">
            <span class="card-title">D. 峰谷转移潜力</span>
          </div>
        </template>
        <el-descriptions :column="3" border>
          <el-descriptions-item label="可转移负荷量">
            <MetricDisplay :metric="analysisResult.transfer_potential?.transferable_load" />
          </el-descriptions-item>
          <el-descriptions-item label="峰谷电价差">
            <MetricDisplay :metric="analysisResult.transfer_potential?.price_spread" />
          </el-descriptions-item>
          <el-descriptions-item label="年收益潜力">
            <MetricDisplay :metric="analysisResult.transfer_potential?.annual_transfer_benefit" />
          </el-descriptions-item>
        </el-descriptions>
      </el-card>

      <!-- 需量优化 -->
      <el-card class="metric-card">
        <template #header>
          <div class="card-header">
            <span class="card-title">E. 需量优化</span>
          </div>
        </template>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="削峰空间">
            <MetricDisplay :metric="analysisResult.demand_optimization?.peak_reduction_potential" />
          </el-descriptions-item>
          <el-descriptions-item label="需量优化年收益">
            <MetricDisplay :metric="analysisResult.demand_optimization?.demand_optimization_benefit" />
          </el-descriptions-item>
        </el-descriptions>
      </el-card>

      <!-- VPP收益测算 -->
      <el-card class="metric-card">
        <template #header>
          <div class="card-header">
            <span class="card-title">F. 虚拟电厂收益测算</span>
          </div>
        </template>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="需求响应收益">
            <MetricDisplay :metric="analysisResult.vpp_revenue?.demand_response_revenue" />
          </el-descriptions-item>
          <el-descriptions-item label="辅助服务收益">
            <MetricDisplay :metric="analysisResult.vpp_revenue?.ancillary_service_revenue" />
          </el-descriptions-item>
          <el-descriptions-item label="现货市场套利收益">
            <MetricDisplay :metric="analysisResult.vpp_revenue?.spot_arbitrage_revenue" />
          </el-descriptions-item>
          <el-descriptions-item label="VPP年总收益">
            <MetricDisplay :metric="analysisResult.vpp_revenue?.total_vpp_revenue" />
          </el-descriptions-item>
        </el-descriptions>
      </el-card>

      <!-- 投资回报分析 -->
      <el-card class="metric-card">
        <template #header>
          <div class="card-header">
            <span class="card-title">G. 投资回报分析</span>
          </div>
        </template>
        <el-row :gutter="20" class="roi-summary">
          <el-col :span="12">
            <el-descriptions :column="1" border>
              <el-descriptions-item label="总投资额">
                <MetricDisplay :metric="analysisResult.investment_return?.total_investment" />
              </el-descriptions-item>
              <el-descriptions-item label="年总收益">
                <MetricDisplay :metric="analysisResult.investment_return?.annual_total_benefit" />
              </el-descriptions-item>
            </el-descriptions>
          </el-col>
          <el-col :span="12">
            <el-descriptions :column="1" border>
              <el-descriptions-item label="投资回收期">
                <MetricDisplay :metric="analysisResult.investment_return?.payback_period" />
              </el-descriptions-item>
              <el-descriptions-item label="投资收益率 (ROI)">
                <MetricDisplay :metric="analysisResult.investment_return?.roi" />
              </el-descriptions-item>
            </el-descriptions>
          </el-col>
        </el-row>
      </el-card>

      <!-- 收益汇总 -->
      <el-card class="summary-card">
        <template #header>
          <div class="card-header">
            <span class="card-title">收益汇总</span>
          </div>
        </template>
        <el-row :gutter="20">
          <el-col :span="8">
            <div class="summary-item">
              <el-statistic
                title="年总收益"
                :value="analysisResult.summary?.annual_total_benefit?.value || 0"
                suffix="元/年"
              >
                <template #prefix>
                  <el-icon><TrendCharts /></el-icon>
                </template>
              </el-statistic>
              <div class="formula-text">
                {{ analysisResult.summary?.annual_total_benefit?.formula }}
              </div>
            </div>
          </el-col>
          <el-col :span="8">
            <div class="summary-item">
              <el-statistic
                title="投资回收期"
                :value="analysisResult.investment_return?.payback_period?.value || 0"
                :precision="2"
                suffix="年"
              >
                <template #prefix>
                  <el-icon><Clock /></el-icon>
                </template>
              </el-statistic>
            </div>
          </el-col>
          <el-col :span="8">
            <div class="summary-item">
              <el-statistic
                title="投资收益率"
                :value="analysisResult.investment_return?.roi?.value || 0"
                :precision="2"
                suffix="%"
              >
                <template #prefix>
                  <el-icon><Odometer /></el-icon>
                </template>
              </el-statistic>
            </div>
          </el-col>
        </el-row>

        <!-- 收益明细 -->
        <el-divider />
        <div v-if="analysisResult.summary?.annual_total_benefit?.breakdown" class="breakdown">
          <h4>收益明细构成</h4>
          <el-descriptions :column="3" border>
            <el-descriptions-item
              v-for="(value, key) in analysisResult.summary.annual_total_benefit.breakdown"
              :key="String(key)"
              :label="String(key)"
            >
              <span class="breakdown-value">
                {{ formatNumber(value as number) }} 元/年
              </span>
            </el-descriptions-item>
          </el-descriptions>
        </div>
      </el-card>
    </template>

    <!-- 空状态 -->
    <el-empty
      v-else
      description="请配置分析参数并点击生成分析报告按钮"
      :image-size="200"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { TrendCharts, Clock, Odometer } from '@element-plus/icons-vue'
import { vppApi, type AnalysisResponse } from '@/api/modules/vpp'
import MetricDisplay from '@/components/MetricDisplay.vue'

const loading = ref(false)
const analysisMonths = ref(['2025-01', '2025-03', '2025-06', '2025-08', '2025-10'])
const dateRange = ref<[string, string]>(['2025-10-01', '2025-10-30'])
const analysisResult = ref<AnalysisResponse | null>(null)

// 可选月份列表
const availableMonths = ref([
  '2025-01', '2025-02', '2025-03', '2025-04', '2025-05', '2025-06',
  '2025-07', '2025-08', '2025-09', '2025-10', '2025-11', '2025-12'
])

/**
 * 运行分析
 */
const runAnalysis = async () => {
  if (!analysisMonths.value.length) {
    ElMessage.warning('请至少选择一个分析月份')
    return
  }

  if (!dateRange.value || !dateRange.value[0] || !dateRange.value[1]) {
    ElMessage.warning('请选择负荷数据日期范围')
    return
  }

  loading.value = true
  try {
    const response = await vppApi.generateAnalysis({
      months: analysisMonths.value,
      start_date: dateRange.value[0],
      end_date: dateRange.value[1]
    })

    if (response.code === 0) {
      analysisResult.value = response.data
      ElMessage.success('分析报告生成成功')
    } else {
      ElMessage.error(response.message || '分析失败')
    }
  } catch (error: any) {
    console.error('Analysis failed:', error)
    ElMessage.error(error.message || '分析报告生成失败，请检查数据是否完整')
  } finally {
    loading.value = false
  }
}

/**
 * 格式化数字
 */
const formatNumber = (value: number): string => {
  if (value === null || value === undefined || isNaN(value)) {
    return '--'
  }
  return value.toLocaleString('zh-CN', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2
  })
}

onMounted(() => {
  // 可以在这里添加初始化逻辑，比如获取可用月份列表
})
</script>

<style lang="scss" scoped>
.vpp-analysis {
  padding: 20px;
  background-color: #f5f7fa;
  min-height: calc(100vh - 60px);

  .header-card {
    margin-bottom: 20px;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;

    h2 {
      margin: 0 0 10px 0;
      font-size: 28px;
      font-weight: 600;
    }

    .subtitle {
      margin: 0;
      opacity: 0.9;
      font-size: 14px;
    }
  }

  .config-card {
    margin-bottom: 20px;
  }

  .metric-card {
    margin-bottom: 20px;
    transition: all 0.3s;

    &:hover {
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
    }
  }

  .summary-card {
    margin-bottom: 20px;
    background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
  }

  .card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;

    .card-title {
      font-size: 16px;
      font-weight: 600;
      color: var(--el-text-color-primary);
    }
  }

  .roi-summary {
    margin-bottom: 20px;
  }

  .summary-item {
    text-align: center;
    padding: 20px;
    background: white;
    border-radius: 8px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);

    .formula-text {
      font-size: 12px;
      color: var(--el-text-color-secondary);
      margin-top: 10px;
      font-family: 'Courier New', monospace;
      background-color: rgba(0, 0, 0, 0.02);
      padding: 8px;
      border-radius: 4px;
    }
  }

  .breakdown {
    h4 {
      margin: 0 0 15px 0;
      font-size: 16px;
      font-weight: 600;
      color: var(--el-text-color-primary);
    }

    .breakdown-value {
      font-weight: 600;
      color: var(--el-color-success);
      font-family: 'Roboto Mono', monospace;
    }
  }
}

:deep(.el-statistic) {
  .el-statistic__head {
    font-size: 14px;
    margin-bottom: 10px;
  }

  .el-statistic__content {
    font-size: 28px;
    font-weight: 600;
  }
}

:deep(.el-descriptions__label) {
  font-weight: 500;
  background-color: #fafafa;
}

:deep(.el-descriptions__content) {
  font-weight: 400;
}
</style>
