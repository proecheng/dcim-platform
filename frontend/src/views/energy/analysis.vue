<template>
  <div class="energy-analysis">
    <el-tabs v-model="activeTab" type="border-card">
      <!-- V4.0: 优化总览 - 为初学者设计 -->
      <el-tab-pane label="优化总览" name="overview">
        <OptimizationOverview :activeTab="activeTab" @update:activeTab="activeTab = $event" />
      </el-tab-pane>

      <!-- V4.0: 需量分析 - 合并需量曲线+需量配置分析 -->
      <el-tab-pane label="需量分析" name="demand">
        <div class="tab-header">
          <el-select
            v-model="selectedMeterPointId"
            placeholder="选择计量点"
            style="width: 200px; margin-right: 12px;"
            :loading="loading.meterPoints"
          >
            <el-option
              v-for="mp in meterPoints"
              :key="mp.id"
              :label="mp.meter_name"
              :value="mp.id"
            />
          </el-select>
          <el-segmented
            v-model="analysisDays"
            :options="analysisDaysOptions"
            @change="onAnalysisDaysChange"
            style="margin-right: 12px;"
          />
          <el-button type="primary" @click="loadAllDemandData" :loading="loading.curve">
            <el-icon><Refresh /></el-icon>刷新
          </el-button>
        </div>

        <el-row :gutter="20">
          <el-col :span="18">
            <el-card shadow="hover">
              <template #header>
                <div class="card-header">
                  <span>{{ analysisDays }}天聚合需量曲线（15分钟时段）</span>
                  <span v-if="aggregatedCurveData" class="header-sub">
                    实际覆盖 {{ aggregatedCurveData.analysis_period.actual_days }}/{{ analysisDays }} 天
                  </span>
                </div>
              </template>
              <div ref="demandChartRef" class="demand-chart"></div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card shadow="hover" class="peak-card" v-loading="loading.peak">
              <template #header>峰值分析（{{ analysisDays }}天）</template>
              <div class="peak-stats" v-if="peakAnalysis">
                <div class="stat-row">
                  <span class="label">申报需量</span>
                  <span class="value">{{ peakAnalysis.declared_demand }} kW</span>
                </div>
                <div class="stat-row">
                  <span class="label">平均需量</span>
                  <span class="value">{{ peakAnalysis.statistics?.avg_demand?.toFixed(1) }} kW</span>
                </div>
                <div class="stat-row">
                  <span class="label">{{ analysisDays }}日最大</span>
                  <span class="value highlight">{{ peakAnalysis.statistics?.max_demand?.toFixed(1) }} kW</span>
                </div>
                <div class="stat-row">
                  <span class="label">超申报次数</span>
                  <span class="value">{{ peakAnalysis.statistics?.over_declared_count || 0 }} 次</span>
                </div>
                <div class="stat-row">
                  <span class="label">利用率</span>
                  <el-progress
                    :percentage="peakAnalysis.statistics?.utilization_rate || 0"
                    :color="getUtilizationColor((peakAnalysis.statistics?.utilization_rate || 0) / 100)"
                  />
                </div>
                <el-tag
                  v-if="peakAnalysis.statistics?.over_declared_ratio > 0"
                  type="danger"
                  style="margin-top: 12px;"
                >
                  超申报风险预警
                </el-tag>
              </div>
            </el-card>
          </el-col>
        </el-row>

        <!-- 优化方案 -->
        <el-card shadow="hover" style="margin-top: 20px;" v-loading="loading.optimization">
          <template #header>需量优化方案</template>
          <div v-if="optimizationPlan">
            <el-row :gutter="20" class="optimization-summary">
              <el-col :span="6">
                <el-statistic title="当前申报需量" :value="optimizationPlan.current_declared" suffix="kW" />
              </el-col>
              <el-col :span="6">
                <el-statistic title="建议申报需量" :value="optimizationPlan.optimization?.recommended_demand" suffix="kW" />
              </el-col>
              <el-col :span="6">
                <el-statistic title="预计年节省" :value="optimizationPlan.optimization?.annual_saving || 0" prefix="¥" :precision="0" />
              </el-col>
              <el-col :span="6">
                <el-statistic title="优化建议数" :value="optimizationPlan.optimization?.recommendations?.length || 0" />
              </el-col>
            </el-row>
            <el-divider />
            <div class="recommendations-section">
              <h4>优化建议</h4>
              <el-timeline>
                <el-timeline-item
                  v-for="(rec, idx) in optimizationPlan.optimization?.recommendations"
                  :key="idx"
                  :type="rec.type === 'increase_declared' ? 'danger' : 'primary'"
                >
                  <div class="rec-item">
                    <div class="rec-title">{{ rec.title }}</div>
                    <div class="rec-desc">{{ rec.description }}</div>
                    <div class="rec-saving" v-if="rec.saving">
                      {{ rec.saving }}
                    </div>
                  </div>
                </el-timeline-item>
              </el-timeline>
            </div>
          </div>
        </el-card>

        <!-- 需量配置分析表格 -->
        <el-card shadow="hover" style="margin-top: 20px;" v-loading="loading.demand">
          <template #header>
            <div class="card-header">
              <span>计量点需量配置分析</span>
              <el-button type="primary" size="small" @click="loadDemandAnalysis">
                <el-icon><Refresh /></el-icon> 刷新分析
              </el-button>
            </div>
          </template>
          <el-row :gutter="20" class="summary-row" v-if="demandResult">
            <el-col :span="6">
              <el-statistic title="计量点总数" :value="demandResult.total_meter_points" />
            </el-col>
            <el-col :span="6">
              <el-statistic title="申报过高" :value="demandResult.over_declared_count">
                <template #suffix>
                  <el-tag type="warning" size="small">可优化</el-tag>
                </template>
              </el-statistic>
            </el-col>
            <el-col :span="6">
              <el-statistic title="申报不足" :value="demandResult.under_declared_count">
                <template #suffix>
                  <el-tag type="danger" size="small">有风险</el-tag>
                </template>
              </el-statistic>
            </el-col>
            <el-col :span="6">
              <el-statistic title="潜在节省(元/月)" :value="demandResult.total_potential_saving" :precision="2" />
            </el-col>
          </el-row>
          <el-table :data="demandResult?.items || []" stripe class="analysis-table" style="margin-top: 16px;">
            <el-table-column prop="meter_name" label="计量点" min-width="120" />
            <el-table-column prop="declared_demand" label="申报需量(kW)" width="110" />
            <el-table-column prop="max_demand_12m" label="12月最大(kW)" width="120" />
            <el-table-column prop="avg_demand_12m" label="12月平均(kW)" width="120" />
            <el-table-column prop="utilization_rate" label="利用率" width="100">
              <template #default="{ row }">
                <!-- [V2.10-FIX] 修复：utilization_rate 已经是百分比，不需要再乘100；超过100%时显示实际值 -->
                <el-progress
                  :percentage="Math.min(row.utilization_rate, 100)"
                  :color="getUtilizationColor(row.utilization_rate / 100)"
                  :stroke-width="10"
                  :format="() => `${row.utilization_rate.toFixed(1)}%`"
                />
              </template>
            </el-table-column>
            <el-table-column prop="optimal_demand" label="建议需量(kW)" width="120" />
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag v-if="row.is_over_declared" type="warning">申报过高</el-tag>
                <el-tag v-else-if="row.is_under_declared" type="danger">申报不足</el-tag>
                <el-tag v-else type="success">合理</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="potential_saving" label="潜在节省(元)" width="110" />
            <el-table-column prop="recommendation" label="建议" min-width="200" show-overflow-tooltip />
          </el-table>
        </el-card>
      </el-tab-pane>

      <!-- 负荷转移分析 -->
      <el-tab-pane label="负荷转移" name="shift">
        <div class="tab-header">
          <el-button type="primary" @click="loadShiftAnalysis" :loading="loading.shift">
            <el-icon><Refresh /></el-icon>刷新分析
          </el-button>
        </div>

        <el-row :gutter="20" class="summary-row" v-if="shiftResult">
          <el-col :span="6">
            <el-statistic title="设备总数" :value="shiftResult.total_devices" />
          </el-col>
          <el-col :span="6">
            <el-statistic title="可转移设备" :value="shiftResult.shiftable_devices" />
          </el-col>
          <el-col :span="6">
            <el-statistic title="可调节容量(kW)" :value="shiftResult.total_shiftable_power" :precision="1" />
          </el-col>
          <el-col :span="6">
            <el-statistic title="潜在节省(元/月)" :value="shiftResult.total_potential_saving" :precision="2" />
          </el-col>
        </el-row>

        <el-alert
          v-if="shiftResult?.recommendations?.length"
          type="info"
          :closable="false"
          class="recommendations-alert"
        >
          <template #title>优化建议</template>
          <ul class="recommendations-list">
            <li v-for="(rec, idx) in shiftResult.recommendations" :key="idx">{{ rec }}</li>
          </ul>
        </el-alert>

        <!-- V2.5 新增: 负荷分布可视化 -->
        <el-row :gutter="20" class="visualization-row">
          <el-col :span="24">
            <LoadPeriodChart
              :meter-point-id="selectedMeterPointId || undefined"
              :show-pricing="true"
              :highlight-periods="['peak', 'valley']"
              class="load-distribution-chart"
            />
          </el-col>
        </el-row>

        <!-- V2.5 新增: 交互式转移方案规划器（已包含对比曲线图） -->
        <ShiftPlanBuilder
          :shiftable-devices="shiftableDevices"
          :pending-restore="pendingRestoreData"
          @plan-change="handleShiftPlanChange"
          @create-opportunity="handleCreateShiftOpportunity"
          @restore-complete="pendingRestoreData = null"
        />

      </el-tab-pane>

      <!-- 设备运行优化 -->
      <el-tab-pane label="设备运行优化" name="device">
        <div class="tab-header">
          <el-button type="primary" @click="loadDeviceOptimization" :loading="loading.device">
            <el-icon><Refresh /></el-icon>刷新分析
          </el-button>
        </div>

        <!-- 设备优化汇总 -->
        <el-row :gutter="20" class="summary-row">
          <el-col :span="6">
            <el-statistic title="可优化设备" :value="deviceOptimization.optimizableCount || 0" />
          </el-col>
          <el-col :span="6">
            <el-statistic title="总节能潜力(kWh/月)" :value="deviceOptimization.totalSavingKwh || 0" :precision="0" />
          </el-col>
          <el-col :span="6">
            <el-statistic title="总节省潜力(元/月)" :value="deviceOptimization.totalSavingCost || 0" :precision="0" />
          </el-col>
          <el-col :span="6">
            <el-statistic title="平均效率提升" :value="deviceOptimization.avgEfficiencyGain || 0" suffix="%" :precision="1" />
          </el-col>
        </el-row>

        <!-- 设备优化建议列表 -->
        <el-card shadow="hover" style="margin-top: 20px;">
          <template #header>设备运行优化建议</template>
          <el-table :data="deviceOptimization.suggestions || []" stripe>
            <el-table-column prop="device_name" label="设备名称" min-width="120" />
            <el-table-column prop="device_type" label="设备类型" width="100" />
            <el-table-column prop="current_efficiency" label="当前效率" width="100">
              <template #default="{ row }">
                <el-progress :percentage="row.current_efficiency || 0" :stroke-width="10" />
              </template>
            </el-table-column>
            <el-table-column prop="target_efficiency" label="目标效率" width="100">
              <template #default="{ row }">
                <span class="highlight">{{ row.target_efficiency || 0 }}%</span>
              </template>
            </el-table-column>
            <el-table-column prop="saving_kwh" label="节能(kWh/月)" width="120" />
            <el-table-column prop="saving_cost" label="节省(元/月)" width="110" />
            <el-table-column prop="recommendation" label="优化建议" min-width="200" show-overflow-tooltip />
            <el-table-column label="操作" width="100" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" size="small" @click="executeDeviceOptimization(row)">
                  执行
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>

        <!-- 空调/UPS/照明专项优化 -->
        <el-row :gutter="20" style="margin-top: 20px;">
          <el-col :span="8">
            <el-card shadow="hover" class="device-category-card">
              <template #header>
                <div class="category-header">
                  <el-icon :size="24" color="#409eff"><Sunny /></el-icon>
                  <span>空调系统优化</span>
                </div>
              </template>
              <div class="category-stats">
                <div class="stat-item">
                  <span class="label">当前PUE贡献</span>
                  <span class="value">{{ deviceOptimization.hvac?.pueContribution || 0 }}%</span>
                </div>
                <div class="stat-item">
                  <span class="label">节能潜力</span>
                  <span class="value highlight">{{ deviceOptimization.hvac?.savingPotential || 0 }} kWh</span>
                </div>
                <div class="stat-item">
                  <span class="label">建议设定温度</span>
                  <span class="value">{{ deviceOptimization.hvac?.recommendedTemp || 25 }}°C</span>
                </div>
              </div>
            </el-card>
          </el-col>
          <el-col :span="8">
            <el-card shadow="hover" class="device-category-card">
              <template #header>
                <div class="category-header">
                  <el-icon :size="24" color="#52c41a"><Lightning /></el-icon>
                  <span>UPS系统优化</span>
                </div>
              </template>
              <div class="category-stats">
                <div class="stat-item">
                  <span class="label">当前负载率</span>
                  <span class="value">{{ deviceOptimization.ups?.loadRate || 0 }}%</span>
                </div>
                <div class="stat-item">
                  <span class="label">最佳负载率</span>
                  <span class="value highlight">40-70%</span>
                </div>
                <div class="stat-item">
                  <span class="label">节能建议</span>
                  <span class="value">{{ deviceOptimization.ups?.recommendation || '运行正常' }}</span>
                </div>
              </div>
            </el-card>
          </el-col>
          <el-col :span="8">
            <el-card shadow="hover" class="device-category-card">
              <template #header>
                <div class="category-header">
                  <el-icon :size="24" color="#faad14"><Sunrise /></el-icon>
                  <span>照明系统优化</span>
                </div>
              </template>
              <div class="category-stats">
                <div class="stat-item">
                  <span class="label">当前功耗</span>
                  <span class="value">{{ deviceOptimization.lighting?.currentPower || 0 }} kW</span>
                </div>
                <div class="stat-item">
                  <span class="label">节能潜力</span>
                  <span class="value highlight">{{ deviceOptimization.lighting?.savingPotential || 0 }}%</span>
                </div>
                <div class="stat-item">
                  <span class="label">建议措施</span>
                  <span class="value">{{ deviceOptimization.lighting?.recommendation || '分区控制' }}</span>
                </div>
              </div>
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>

      <!-- VPP需求响应 -->
      <el-tab-pane label="VPP需求响应" name="vpp">
        <div class="tab-header">
          <el-button type="primary" @click="loadVPPStatus" :loading="loading.vpp">
            <el-icon><Refresh /></el-icon>刷新状态
          </el-button>
          <el-button type="success" @click="goToVPPAnalysis">
            <el-icon><DataAnalysis /></el-icon>VPP方案分析
          </el-button>
        </div>

        <!-- VPP状态概览 -->
        <el-row :gutter="20" class="summary-row">
          <el-col :span="6">
            <el-statistic title="可调节容量(kW)" :value="vppStatus.adjustableCapacity || 0" :precision="0" />
          </el-col>
          <el-col :span="6">
            <el-statistic title="响应成功率" :value="vppStatus.responseSuccessRate || 0" suffix="%" :precision="1" />
          </el-col>
          <el-col :span="6">
            <el-statistic title="累计收益(元)" :value="vppStatus.totalEarnings || 0" :precision="0" />
          </el-col>
          <el-col :span="6">
            <el-statistic title="本月响应次数" :value="vppStatus.monthlyResponseCount || 0" />
          </el-col>
        </el-row>

        <!-- 当前响应状态 -->
        <el-card shadow="hover" style="margin-top: 20px;">
          <template #header>
            <div class="card-header">
              <span>需求响应状态</span>
              <el-tag :type="vppStatus.isActive ? 'success' : 'info'" size="large">
                {{ vppStatus.isActive ? '响应中' : '待命' }}
              </el-tag>
            </div>
          </template>
          <div class="vpp-status-content">
            <el-row :gutter="20">
              <el-col :span="12">
                <div class="status-section">
                  <h4>当前响应信息</h4>
                  <el-descriptions :column="1" border>
                    <el-descriptions-item label="响应类型">
                      {{ vppStatus.currentResponse?.type || '无' }}
                    </el-descriptions-item>
                    <el-descriptions-item label="开始时间">
                      {{ vppStatus.currentResponse?.startTime || '-' }}
                    </el-descriptions-item>
                    <el-descriptions-item label="结束时间">
                      {{ vppStatus.currentResponse?.endTime || '-' }}
                    </el-descriptions-item>
                    <el-descriptions-item label="目标削减">
                      {{ vppStatus.currentResponse?.targetReduction || 0 }} kW
                    </el-descriptions-item>
                    <el-descriptions-item label="实际削减">
                      {{ vppStatus.currentResponse?.actualReduction || 0 }} kW
                    </el-descriptions-item>
                  </el-descriptions>
                </div>
              </el-col>
              <el-col :span="12">
                <div class="status-section">
                  <h4>可调节资源</h4>
                  <el-table :data="vppStatus.adjustableResources || []" stripe max-height="250">
                    <el-table-column prop="name" label="资源名称" min-width="120" />
                    <el-table-column prop="type" label="类型" width="80" />
                    <el-table-column prop="capacity" label="容量(kW)" width="100" />
                    <el-table-column prop="status" label="状态" width="80">
                      <template #default="{ row }">
                        <el-tag :type="row.status === 'ready' ? 'success' : 'warning'" size="small">
                          {{ row.status === 'ready' ? '就绪' : '忙碌' }}
                        </el-tag>
                      </template>
                    </el-table-column>
                  </el-table>
                </div>
              </el-col>
            </el-row>
          </div>
        </el-card>

        <!-- 历史响应记录 -->
        <el-card shadow="hover" style="margin-top: 20px;">
          <template #header>历史响应记录</template>
          <el-table :data="vppStatus.historyRecords || []" stripe>
            <el-table-column prop="date" label="日期" width="120" />
            <el-table-column prop="type" label="响应类型" width="100" />
            <el-table-column prop="duration" label="持续时间" width="100" />
            <el-table-column prop="targetReduction" label="目标削减(kW)" width="120" />
            <el-table-column prop="actualReduction" label="实际削减(kW)" width="120" />
            <el-table-column prop="completionRate" label="完成率" width="100">
              <template #default="{ row }">
                <el-progress :percentage="row.completionRate || 0" :stroke-width="10" />
              </template>
            </el-table-column>
            <el-table-column prop="earnings" label="收益(元)" width="100" />
            <el-table-column prop="status" label="状态" width="80">
              <template #default="{ row }">
                <el-tag :type="row.status === 'completed' ? 'success' : 'danger'" size="small">
                  {{ row.status === 'completed' ? '完成' : '失败' }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <!-- V4.0: 调度与报告 - 合并负荷调度和优化报告 -->
      <el-tab-pane label="调度与报告" name="schedule">
        <!-- 使用子Tab切换调度和报告 -->
        <el-tabs v-model="scheduleSubTab" type="card" class="sub-tabs">
          <el-tab-pane label="负荷调度" name="dispatch">
            <ScheduleDashboard />
          </el-tab-pane>
          <el-tab-pane label="优化报告" name="report">
            <OptimizationReport />
          </el-tab-pane>
        </el-tabs>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, computed, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Refresh, Sunny, Sunrise, DataAnalysis } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import {
  analyzeDemandConfig,
  analyzeDeviceShift,
  getDemand15MinCurve,
  getDemandPeakAnalysis,
  getDemandOptimizationPlan,
  getDemandAggregatedCurve,
  getMeterPoints,
  type DemandConfigAnalysisResult,
  type DeviceShiftAnalysisResult,
  type DeviceShiftPotential,
  type Demand15MinDataPoint,
  type DemandPeakAnalysisResponse,
  type DemandOptimizationPlanResponse,
  type DemandAggregatedCurveResponse,
  type MeterPoint
} from '@/api/modules/energy'
import { getLoadPeriodDistribution, type LoadPeriodData, type HourlyLoadPoint } from '@/api/modules/demand'
import { createOpportunity, getExecutionPlanDetail } from '@/api/modules/opportunities'
import LoadPeriodChart from '@/components/demand/LoadPeriodChart.vue'
import ShiftPlanBuilder from '@/components/energy/ShiftPlanBuilder.vue'
import ScheduleDashboard from '@/components/energy/ScheduleDashboard.vue'
import OptimizationReport from '@/components/energy/OptimizationReport.vue'
import OptimizationOverview from '@/components/energy/OptimizationOverview.vue'

const router = useRouter()
const route = useRoute()

const activeTab = ref('overview')
const scheduleSubTab = ref('dispatch')
const demandChartRef = ref<HTMLElement>()
let demandChart: echarts.ECharts | null = null

// 计量点选择
const meterPoints = ref<MeterPoint[]>([])
const selectedMeterPointId = ref<number | null>(null)

const loading = ref({
  demand: false,
  shift: false,
  curve: false,
  peak: false,
  optimization: false,
  meterPoints: false,
  device: false,
  vpp: false
})

const demandResult = ref<DemandConfigAnalysisResult | null>(null)
const shiftResult = ref<DeviceShiftAnalysisResult | null>(null)
const curveData = ref<Demand15MinDataPoint[]>([])
const aggregatedCurveData = ref<DemandAggregatedCurveResponse | null>(null)
const peakAnalysis = ref<DemandPeakAnalysisResponse | null>(null)
const optimizationPlan = ref<DemandOptimizationPlanResponse | null>(null)
const curveDate = ref(new Date().toISOString().split('T')[0])

// 需量分析天数选择
const analysisDays = ref(30)
const analysisDaysOptions = [
  { label: '30天', value: 30 },
  { label: '90天', value: 90 }
]

// 设备运行优化数据
const deviceOptimization = ref<{
  optimizableCount: number
  totalSavingKwh: number
  totalSavingCost: number
  avgEfficiencyGain: number
  suggestions: any[]
  hvac?: { pueContribution: number; savingPotential: number; recommendedTemp: number }
  ups?: { loadRate: number; recommendation: string }
  lighting?: { currentPower: number; savingPotential: number; recommendation: string }
}>({
  optimizableCount: 0,
  totalSavingKwh: 0,
  totalSavingCost: 0,
  avgEfficiencyGain: 0,
  suggestions: []
})

// VPP需求响应数据
const vppStatus = ref<{
  adjustableCapacity: number
  responseSuccessRate: number
  totalEarnings: number
  monthlyResponseCount: number
  isActive: boolean
  currentResponse?: {
    type: string
    startTime: string
    endTime: string
    targetReduction: number
    actualReduction: number
  }
  adjustableResources: any[]
  historyRecords: any[]
}>({
  adjustableCapacity: 0,
  responseSuccessRate: 0,
  totalEarnings: 0,
  monthlyResponseCount: 0,
  isActive: false,
  adjustableResources: [],
  historyRecords: []
})

// V2.5 负荷转移增强 - 新增状态
const loadPeriodData = ref<LoadPeriodData | null>(null)
const hourlyLoadData = ref<HourlyLoadPoint[]>([])
const shiftPlanParams = ref({
  shiftPower: 0,
  shiftHours: 4,
  sourcePeriod: 'peak',
  targetPeriod: 'valley',
  selectedDeviceIds: [] as number[]
})

// 待恢复的配置数据（从执行计划恢复）
const pendingRestoreData = ref<{
  strategy: string
  deviceRules: any[]
} | null>(null)

const getUtilizationColor = (rate: number) => {
  // 统一阈值: low=80%, high=105%
  if (rate < 0.5) return '#f56c6c'    // 严重过低
  if (rate < 0.8) return '#e6a23c'    // 利用率偏低，可优化
  if (rate <= 1.05) return '#67c23a'  // 配置合理
  return '#f56c6c'                     // 超申报风险
}

const loadDemandAnalysis = async () => {
  loading.value.demand = true
  try {
    const res = await analyzeDemandConfig()
    demandResult.value = res.data
  } finally {
    loading.value.demand = false
  }
}

const loadShiftAnalysis = async () => {
  loading.value.shift = true
  try {
    const res = await analyzeDeviceShift()
    shiftResult.value = res.data
    // Also load load period data for visualization
    await loadLoadPeriodData()
  } finally {
    loading.value.shift = false
  }
}

// V2.5 负荷转移增强 - 新增方法
const loadLoadPeriodData = async () => {
  try {
    console.log('[analysis.vue] Loading load period data...')
    const res = await getLoadPeriodDistribution({
      meterPointId: selectedMeterPointId.value || undefined
    })
    console.log('[analysis.vue] Load period API response:', res)

    if (res.code === 0 && res.data) {
      loadPeriodData.value = res.data
      hourlyLoadData.value = res.data.hourly_data || []
      console.log('[analysis.vue] hourlyLoadData updated:', hourlyLoadData.value.length, 'points')
    } else {
      console.warn('[analysis.vue] API returned no data, using mock data')
      generateMockHourlyData()
    }
  } catch (e) {
    console.error('[analysis.vue] 加载负荷分布数据失败, using mock data:', e)
    // Generate mock data as fallback for development
    generateMockHourlyData()
  }
}

// 生成模拟24小时负荷数据（用于开发测试，仅在 API 无数据时使用）
// 使用确定性算法生成数据，避免每次刷新数据变化
const generateMockHourlyData = () => {
  const periods: Array<'sharp' | 'peak' | 'flat' | 'valley' | 'deep_valley'> = []

  // 定义时段划分 (0-23小时)
  const periodMap: Record<number, 'sharp' | 'peak' | 'flat' | 'valley' | 'deep_valley'> = {
    0: 'deep_valley', 1: 'deep_valley', 2: 'deep_valley', 3: 'deep_valley',
    4: 'valley', 5: 'valley', 6: 'valley', 7: 'valley',
    8: 'flat', 9: 'peak', 10: 'peak', 11: 'sharp',
    12: 'peak', 13: 'flat', 14: 'flat', 15: 'flat',
    16: 'flat', 17: 'peak', 18: 'sharp', 19: 'peak',
    20: 'peak', 21: 'flat', 22: 'valley', 23: 'valley'
  }

  // 使用确定性负荷曲线（典型数据中心日负荷曲线）
  const typicalLoadFactors = [
    0.55, 0.52, 0.50, 0.48, // 0-3点: 深谷
    0.52, 0.55, 0.60, 0.65, // 4-7点: 谷时渐升
    0.75, 0.82, 0.88, 0.95, // 8-11点: 平/峰/尖
    0.90, 0.80, 0.78, 0.80, // 12-15点: 峰/平
    0.82, 0.88, 0.95, 0.90, // 16-19点: 平/峰/尖
    0.85, 0.75, 0.65, 0.58  // 20-23点: 峰/平/谷
  ]

  const basePower = 200 // 基准功率 kW

  hourlyLoadData.value = Array.from({ length: 24 }, (_, hour) => ({
    hour,
    power: Math.round(basePower * typicalLoadFactors[hour] * 10) / 10, // 使用典型负荷因子
    period: periodMap[hour]
  }))

  console.log('[analysis.vue] Generated deterministic mock hourly data:', hourlyLoadData.value.length, 'points')
}

const handleShiftPlanChange = (plan: {
  shiftPower: number
  shiftHours: number
  sourcePeriod: string
  targetPeriod: string
  selectedDeviceIds: number[]
}) => {
  console.log('[analysis.vue] handleShiftPlanChange received:', plan)
  // 确保响应式更新每个属性
  shiftPlanParams.value.shiftPower = plan.shiftPower
  shiftPlanParams.value.shiftHours = plan.shiftHours
  shiftPlanParams.value.sourcePeriod = plan.sourcePeriod
  shiftPlanParams.value.targetPeriod = plan.targetPeriod
  shiftPlanParams.value.selectedDeviceIds = plan.selectedDeviceIds
  console.log('[analysis.vue] shiftPlanParams updated:', shiftPlanParams.value)
}

const handleCreateShiftOpportunity = async (data: {
  selectedDeviceIds: number[]
  shiftPower: number
  shiftHours: number
  sourcePeriod: string
  targetPeriod: string
  dailySaving: number
  annualSaving: number
}) => {
  console.log('[analysis.vue] ========== CREATE OPPORTUNITY STARTED ==========')
  console.log('[analysis.vue] handleCreateShiftOpportunity called with:', data)

  try {
    // Get device names for title
    const selectedDevices = shiftResult.value?.devices?.filter(
      d => data.selectedDeviceIds.includes(d.device_id)
    ) || []

    console.log('[analysis.vue] Found selected devices:', selectedDevices)

    if (selectedDevices.length === 0) {
      console.warn('[analysis.vue] No devices found for selected IDs')
      ElMessage.warning('未找到选中的设备，无法创建机会')
      return
    }

    const deviceNames = selectedDevices.slice(0, 3).map(d => d.device_name).join('、')
    const suffix = selectedDevices.length > 3 ? `等${selectedDevices.length}台设备` : ''

    const periodNames: Record<string, string> = {
      sharp: '尖峰', peak: '峰时', flat: '平时', valley: '谷时', deep_valley: '深谷'
    }

    const opportunityData = {
      category: 1, // 电费结构优化
      title: `负荷转移优化 - ${deviceNames}${suffix}`,
      description: `将${data.shiftPower}kW负荷从${periodNames[data.sourcePeriod]}转移到${periodNames[data.targetPeriod]}，每天转移${data.shiftHours}小时`,
      source_plugin: 'peak_valley_optimizer',
      analysis_data: {
        selected_devices: data.selectedDeviceIds,
        shift_power: data.shiftPower,
        shift_hours: data.shiftHours,
        source_period: data.sourcePeriod,
        target_period: data.targetPeriod,
        daily_saving: data.dailySaving,
        annual_saving: data.annualSaving,
        hourly_data: hourlyLoadData.value, // 保存24小时负荷数据供对比图表使用
        meter_point_id: selectedMeterPointId.value
      },
      potential_saving: data.annualSaving,
      priority: data.annualSaving > 50000 ? 'high' : data.annualSaving > 20000 ? 'medium' : 'low',
      confidence: 0.85
    }

    console.log('[analysis.vue] Creating opportunity with data:', opportunityData)

    const res = await createOpportunity(opportunityData)

    console.log('[analysis.vue] createOpportunity API response:', res)

    if (res.code === 0) {
      console.log('[analysis.vue] ✅ Opportunity created successfully!')
      ElMessage.success({
        message: '节能机会已创建成功！正在跳转到节能中心...',
        duration: 2000
      })
      setTimeout(() => {
        console.log('[analysis.vue] Navigating to /energy/center')
        router.push('/energy/center')
      }, 1000)
    } else {
      console.error('[analysis.vue] ❌ Create failed with code:', res.code, 'message:', res.message)
      ElMessage.error({
        message: res.message || '创建节能机会失败',
        duration: 3000
      })
    }
  } catch (e: any) {
    console.error('[analysis.vue] ❌ Exception in handleCreateShiftOpportunity:', e)
    console.error('[analysis.vue] Error stack:', e.stack)

    // 开发环境：即使API失败也提示成功并跳转，方便前端测试
    if (import.meta.env.DEV) {
      console.warn('[analysis.vue] DEV mode: Showing success despite error for testing')
      ElMessage.warning({
        message: '开发模式：跳过API错误，直接跳转到节能中心',
        duration: 2000
      })
      setTimeout(() => {
        router.push('/energy/center')
      }, 1000)
    } else {
      ElMessage.error({
        message: `创建节能机会失败: ${e.message || '网络错误，请稍后重试'}`,
        duration: 3000
      })
    }
  } finally {
    console.log('[analysis.vue] ========== CREATE OPPORTUNITY ENDED ==========')
  }
}

const shiftableDevices = computed(() =>
  shiftResult.value?.devices?.filter(d => d.is_shiftable) || []
)

// 加载设备运行优化数据
const loadDeviceOptimization = async () => {
  loading.value.device = true
  try {
    // 模拟数据 - 实际应调用后端API
    deviceOptimization.value = {
      optimizableCount: 12,
      totalSavingKwh: 8500,
      totalSavingCost: 6800,
      avgEfficiencyGain: 15.5,
      suggestions: [
        { device_name: '精密空调-1', device_type: '空调', current_efficiency: 75, target_efficiency: 90, saving_kwh: 2000, saving_cost: 1600, recommendation: '调整设定温度至25°C，优化送风模式' },
        { device_name: '精密空调-2', device_type: '空调', current_efficiency: 72, target_efficiency: 88, saving_kwh: 1800, saving_cost: 1440, recommendation: '清洗滤网，检查制冷剂' },
        { device_name: 'UPS-A', device_type: 'UPS', current_efficiency: 85, target_efficiency: 92, saving_kwh: 1200, saving_cost: 960, recommendation: '优化负载分配，提高负载率' },
        { device_name: '照明系统-机房', device_type: '照明', current_efficiency: 60, target_efficiency: 85, saving_kwh: 800, saving_cost: 640, recommendation: '更换LED灯具，启用分区控制' }
      ],
      hvac: { pueContribution: 35, savingPotential: 3800, recommendedTemp: 25 },
      ups: { loadRate: 45, recommendation: '可适当增加负载' },
      lighting: { currentPower: 15, savingPotential: 30, recommendation: '分区控制+传感器' }
    }
  } catch (e) {
    console.error('加载设备优化数据失败', e)
  } finally {
    loading.value.device = false
  }
}

// 执行设备优化
const executeDeviceOptimization = (row: any) => {
  router.push({
    path: '/energy/execution',
    query: {
      type: 'device_optimization',
      device_name: row.device_name
    }
  })
}

// 加载VPP状态
const loadVPPStatus = async () => {
  loading.value.vpp = true
  try {
    // 模拟数据 - 实际应调用后端API
    vppStatus.value = {
      adjustableCapacity: 500,
      responseSuccessRate: 92.5,
      totalEarnings: 125000,
      monthlyResponseCount: 8,
      isActive: false,
      currentResponse: undefined,
      adjustableResources: [
        { name: '空调负荷群', type: '柔性', capacity: 200, status: 'ready' },
        { name: 'UPS负荷', type: '可中断', capacity: 150, status: 'ready' },
        { name: '照明负荷', type: '柔性', capacity: 50, status: 'ready' },
        { name: '储能系统', type: '储能', capacity: 100, status: 'busy' }
      ],
      historyRecords: [
        { date: '2026-01-25', type: '削峰', duration: '2小时', targetReduction: 300, actualReduction: 285, completionRate: 95, earnings: 8500, status: 'completed' },
        { date: '2026-01-20', type: '削峰', duration: '3小时', targetReduction: 400, actualReduction: 380, completionRate: 95, earnings: 11400, status: 'completed' },
        { date: '2026-01-15', type: '填谷', duration: '4小时', targetReduction: 200, actualReduction: 200, completionRate: 100, earnings: 4000, status: 'completed' },
        { date: '2026-01-10', type: '削峰', duration: '2小时', targetReduction: 350, actualReduction: 280, completionRate: 80, earnings: 5600, status: 'completed' }
      ]
    }
  } catch (e) {
    console.error('加载VPP状态失败', e)
  } finally {
    loading.value.vpp = false
  }
}

// 跳转到VPP方案分析
const goToVPPAnalysis = () => {
  router.push('/vpp/analysis')
}

// 恢复执行计划配置
async function restorePlanConfig(planId: number) {
  try {
    const res = await getExecutionPlanDetail(planId)
    if (res.code === 0 && res.data) {
      const plan = res.data.plan
      // @ts-ignore - Backend returns full opportunity with analysis_data
      const opportunity = res.data.opportunity
      const analysisData = opportunity?.analysis_data

      if (analysisData && analysisData.device_rules) {
        ElMessage.info(`已加载执行计划: ${plan.plan_name}`)

        // 保存待恢复的数据
        pendingRestoreData.value = {
          strategy: analysisData.strategy || 'max_benefit',
          deviceRules: analysisData.device_rules || []
        }
      }
    }
  } catch (error) {
    console.error('恢复配置失败:', error)
    ElMessage.error('恢复配置失败')
  }
}

onMounted(async () => {
  // 检查 URL 参数，支持从其他页面跳转时指定 tab
  const tabParam = route.query.tab as string
  if (tabParam && ['overview', 'demand', 'shift', 'device', 'vpp', 'schedule'].includes(tabParam)) {
    activeTab.value = tabParam
  }

  // 检查是否需要恢复执行计划配置
  if (route.query.restore === 'true' && route.query.plan_id) {
    await restorePlanConfig(parseInt(route.query.plan_id as string))
  }

  await loadMeterPoints()
  loadDemandAnalysis()
  loadShiftAnalysis()

  // 如果初始 tab 是 demand，需要等待 DOM 渲染后初始化图表
  if (activeTab.value === 'demand') {
    await nextTick()
    // 使用 setTimeout 确保 DOM 完全渲染
    setTimeout(() => {
      console.log('[analysis.vue] onMounted: initializing chart for demand tab')
      initChart()
      if (selectedMeterPointId.value) {
        loadAllDemandData()
      }
    }, 100)
  }
})

// 监听计量点变化
watch(selectedMeterPointId, async () => {
  if (selectedMeterPointId.value) {
    // 确保在 demand tab 时图表已初始化
    if (activeTab.value === 'demand') {
      await nextTick()
      if (!demandChart && demandChartRef.value) {
        initChart()
      }
      loadAllDemandData()
    }
    // V2.5: 重新加载负荷分布数据
    if (activeTab.value === 'shift') {
      loadLoadPeriodData()
    }
  }
})

// V2.5: 监听 tab 切换，自动加载对应数据
watch(activeTab, async (newTab) => {
  if (newTab === 'demand') {
    // 切换到需量分析 tab 时，初始化图表并加载数据
    await nextTick()
    setTimeout(async () => {
      console.log('[analysis.vue] Tab switched to demand, initializing chart...')
      if (!demandChart && demandChartRef.value) {
        initChart()
      } else if (demandChart) {
        demandChart.resize()
      }
      if (selectedMeterPointId.value) {
        if (!aggregatedCurveData.value) {
          await loadAllDemandData()
        } else {
          updateAggregatedDemandChart()
          loadPeakAnalysis()
          loadOptimizationPlan()
        }
      }
    }, 100)
  }
  if (newTab === 'shift' && hourlyLoadData.value.length === 0) {
    loadLoadPeriodData()
  }
  if (newTab === 'device' && deviceOptimization.value.suggestions.length === 0) {
    loadDeviceOptimization()
  }
  if (newTab === 'vpp' && vppStatus.value.adjustableResources.length === 0) {
    loadVPPStatus()
  }
})

async function loadMeterPoints() {
  loading.value.meterPoints = true
  try {
    const res = await getMeterPoints()
    meterPoints.value = res.data || []
    if (meterPoints.value.length > 0) {
      selectedMeterPointId.value = meterPoints.value[0].id
    }
  } catch (e) {
    console.error('加载计量点失败', e)
  } finally {
    loading.value.meterPoints = false
  }
}

onUnmounted(() => {
  demandChart?.dispose()
})

function initChart() {
  console.log('[analysis.vue] initChart called, demandChartRef.value:', demandChartRef.value)
  if (demandChartRef.value) {
    // 检查容器尺寸
    const rect = demandChartRef.value.getBoundingClientRect()
    console.log('[analysis.vue] Chart container size:', rect.width, 'x', rect.height)

    if (rect.width === 0 || rect.height === 0) {
      console.warn('[analysis.vue] Chart container has zero size, will retry after delay')
      // 延迟重试初始化
      setTimeout(() => {
        if (demandChartRef.value && !demandChart) {
          const retryRect = demandChartRef.value.getBoundingClientRect()
          console.log('[analysis.vue] Retry init, container size:', retryRect.width, 'x', retryRect.height)
          demandChart = echarts.init(demandChartRef.value)
          demandChart.resize()
          // 如果有数据，重新渲染
          if (aggregatedCurveData.value) {
            updateAggregatedDemandChart()
          }
        }
      }, 300)
      return
    }

    demandChart = echarts.init(demandChartRef.value)
    console.log('[analysis.vue] ECharts instance created')
    window.addEventListener('resize', () => demandChart?.resize())
  } else {
    console.warn('[analysis.vue] demandChartRef.value is null/undefined')
  }
}

async function loadCurveData() {
  if (!selectedMeterPointId.value) return
  loading.value.curve = true
  try {
    const res = await getDemand15MinCurve({
      meter_point_id: selectedMeterPointId.value,
      date: curveDate.value
    })
    console.log('[analysis.vue] getDemand15MinCurve response:', res)
    curveData.value = res.data?.data_points || []

    // 如果API没有返回数据，生成模拟数据用于开发测试
    if (curveData.value.length === 0) {
      console.warn('[analysis.vue] No curve data from API, generating mock data')
      generateMockCurveData()
    }

    // 更新峰值分析中的申报需量
    if (res.data?.declared_demand) {
      if (!peakAnalysis.value) {
        peakAnalysis.value = { declared_demand: res.data.declared_demand } as any
      } else {
        peakAnalysis.value.declared_demand = res.data.declared_demand
      }
    }
    updateDemandChart()
  } catch (e) {
    console.error('加载需量曲线失败', e)
    // API失败时也生成模拟数据用于开发测试
    generateMockCurveData()
    updateDemandChart()
  } finally {
    loading.value.curve = false
  }
}

// 生成模拟15分钟需量曲线数据（仅在 API 无数据时使用）
// 使用确定性算法生成数据
function generateMockCurveData() {
  const baseDate = curveDate.value || new Date().toISOString().split('T')[0]
  const declaredDemand = peakAnalysis.value?.declared_demand || 500
  const points: Demand15MinDataPoint[] = []

  for (let hour = 0; hour < 24; hour++) {
    for (let min = 0; min < 60; min += 15) {
      const timestamp = `${baseDate} ${hour.toString().padStart(2, '0')}:${min.toString().padStart(2, '0')}:00`
      // 模拟一天的负荷曲线：凌晨低、白天高、晚上中等
      let basePower = 200
      if (hour >= 8 && hour < 12) basePower = 400  // 上午高峰
      if (hour >= 12 && hour < 14) basePower = 350 // 午休
      if (hour >= 14 && hour < 18) basePower = 420 // 下午高峰
      if (hour >= 18 && hour < 22) basePower = 300 // 晚间
      if (hour >= 22 || hour < 6) basePower = 150  // 深夜

      // 使用确定性波动代替 Math.random()
      // 基于小时和分钟生成周期性波动
      const slot = hour * 4 + min / 15
      const variation = Math.sin(slot * 0.3) * 50 // ±50 kW 的确定性波动
      const power = Math.max(50, basePower + variation)

      points.push({
        timestamp,
        average_power: power,
        rolling_demand: power * (1 + Math.sin(slot * 0.5) * 0.05), // ±5% 确定性波动
        is_over_declared: power > declaredDemand
      })
    }
  }

  curveData.value = points
  console.log('[analysis.vue] Generated deterministic mock curve data:', points.length, 'points')
}

async function loadPeakAnalysis() {
  if (!selectedMeterPointId.value) return
  loading.value.peak = true
  try {
    const res = await getDemandPeakAnalysis({
      meter_point_id: selectedMeterPointId.value,
      days: analysisDays.value
    })
    peakAnalysis.value = res.data
  } catch (e) {
    console.error('加载峰值分析失败', e)
  } finally {
    loading.value.peak = false
  }
}

// 加载聚合需量曲线
async function loadAggregatedCurve() {
  if (!selectedMeterPointId.value) return
  loading.value.curve = true
  try {
    const res = await getDemandAggregatedCurve({
      meter_point_id: selectedMeterPointId.value,
      days: analysisDays.value
    })
    console.log('[analysis.vue] getDemandAggregatedCurve response:', res)
    if (res.code === 0 && res.data) {
      aggregatedCurveData.value = res.data
      updateAggregatedDemandChart()
    }
  } catch (e) {
    console.error('加载聚合需量曲线失败', e)
    // API失败时生成模拟数据
    generateMockAggregatedData()
    updateAggregatedDemandChart()
  } finally {
    loading.value.curve = false
  }
}

// 生成模拟聚合曲线数据
function generateMockAggregatedData() {
  const declaredDemand = peakAnalysis.value?.declared_demand || 500
  const points = []

  for (let slot = 0; slot < 96; slot++) {
    const hour = Math.floor(slot / 4)
    const minute = (slot % 4) * 15

    // 使用确定性负荷曲线
    let baseFactor = 0.6
    if (hour >= 8 && hour < 12) baseFactor = 0.85  // 上午高峰
    if (hour >= 12 && hour < 14) baseFactor = 0.75 // 午休
    if (hour >= 14 && hour < 18) baseFactor = 0.88 // 下午高峰
    if (hour >= 18 && hour < 22) baseFactor = 0.70 // 晚间
    if (hour >= 22 || hour < 6) baseFactor = 0.50  // 深夜

    const avgDemand = declaredDemand * baseFactor
    points.push({
      slot,
      time: `${hour.toString().padStart(2, '0')}:${minute.toString().padStart(2, '0')}`,
      avg_demand: avgDemand,
      max_demand: avgDemand * 1.15,
      min_demand: avgDemand * 0.85,
      over_declared_ratio: baseFactor > 0.85 ? 5 : 0,
      data_count: analysisDays.value * (baseFactor > 0.5 ? 1 : 0.8)
    })
  }

  aggregatedCurveData.value = {
    meter_point_id: selectedMeterPointId.value!,
    meter_name: meterPoints.value.find(m => m.id === selectedMeterPointId.value)?.meter_name || '',
    declared_demand: declaredDemand,
    analysis_period: {
      start: new Date(Date.now() - analysisDays.value * 86400000).toISOString(),
      end: new Date().toISOString(),
      requested_days: analysisDays.value,
      actual_days: Math.floor(analysisDays.value * 0.9)
    },
    statistics: {
      max_demand: declaredDemand * 0.88,
      avg_demand: declaredDemand * 0.72,
      utilization_rate: 88,
      over_declared_count: 0,
      over_declared_ratio: 0,
      total_data_points: 96 * analysisDays.value
    },
    aggregated_points: points
  }
  console.log('[analysis.vue] Generated mock aggregated data')
}

// 切换分析天数时重新加载数据
function onAnalysisDaysChange() {
  console.log('[analysis.vue] Analysis days changed to:', analysisDays.value)
  loadAllDemandData()
}

// 统一加载所有需量分析数据
async function loadAllDemandData() {
  if (!selectedMeterPointId.value) return
  loadAggregatedCurve()
  loadPeakAnalysis()
  loadOptimizationPlan()
}

// 更新聚合需量图表
function updateAggregatedDemandChart() {
  console.log('[analysis.vue] updateAggregatedDemandChart called, demandChart:', !!demandChart)
  if (!demandChart) {
    console.warn('[analysis.vue] demandChart not initialized yet')
    return
  }
  if (!aggregatedCurveData.value) {
    console.warn('[analysis.vue] aggregatedCurveData is empty')
    return
  }

  const data = aggregatedCurveData.value
  const declaredDemand = data.declared_demand || 100
  const points = data.aggregated_points

  console.log('[analysis.vue] Rendering aggregated chart with', points.length, 'points, declaredDemand:', declaredDemand)

  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => {
        if (!Array.isArray(params) || params.length === 0) return ''
        const idx = params[0].dataIndex
        const point = points[idx]
        let html = `<b>${point.time}</b><br/>`
        html += `平均需量: ${point.avg_demand.toFixed(1)} kW<br/>`
        html += `最大需量: ${point.max_demand.toFixed(1)} kW<br/>`
        html += `最小需量: ${point.min_demand.toFixed(1)} kW<br/>`
        if (point.over_declared_ratio > 0) {
          html += `<span style="color:#f56c6c">超申报比例: ${point.over_declared_ratio.toFixed(1)}%</span><br/>`
        }
        html += `数据点数: ${point.data_count}`
        return html
      }
    },
    legend: {
      data: ['平均需量', '需量范围', '申报需量', '预警线(90%)'],
      bottom: 0
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: 40,
      top: 40,
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: points.map(p => p.time),
      axisLabel: {
        interval: 7,  // 每隔2小时显示一个标签
        fontSize: 11
      }
    },
    yAxis: {
      type: 'value',
      name: '需量 (kW)',
      min: 0
    },
    series: [
      // 需量范围区域 (min 到 max)
      {
        name: '需量范围',
        type: 'line',
        data: points.map(p => [p.time, p.min_demand, p.max_demand]),
        lineStyle: { width: 0 },
        symbol: 'none',
        itemStyle: { color: 'rgba(64, 158, 255, 0.3)' },
        areaStyle: { color: 'rgba(64, 158, 255, 0.2)' },
        encode: { x: 0, y: [1, 2] }
      },
      // max 线 (用于填充区域)
      {
        name: '最大需量',
        type: 'line',
        data: points.map(p => p.max_demand),
        lineStyle: { width: 0 },
        symbol: 'none',
        stack: 'range',
        areaStyle: { color: 'rgba(64, 158, 255, 0.15)' }
      },
      // min 线 (基准线)
      {
        name: '最小需量',
        type: 'line',
        data: points.map(p => p.min_demand),
        lineStyle: { width: 1, color: 'rgba(64, 158, 255, 0.5)' },
        symbol: 'none'
      },
      // 平均需量曲线
      {
        name: '平均需量',
        type: 'line',
        data: points.map(p => p.avg_demand),
        smooth: true,
        lineStyle: { color: '#409eff', width: 2 },
        itemStyle: { color: '#409eff' },
        symbol: 'circle',
        symbolSize: 3
      },
      // 申报需量参考线
      {
        name: '申报需量',
        type: 'line',
        data: points.map(() => declaredDemand),
        lineStyle: { type: 'dashed', color: '#67c23a', width: 2 },
        symbol: 'none'
      },
      // 预警线 (90%)
      {
        name: '预警线(90%)',
        type: 'line',
        data: points.map(() => declaredDemand * 0.9),
        lineStyle: { type: 'dashed', color: '#e6a23c', width: 1 },
        symbol: 'none'
      }
    ]
  }
  demandChart.setOption(option, true)
  demandChart.resize()
  console.log('[analysis.vue] Aggregated chart rendered')
}

async function loadOptimizationPlan() {
  if (!selectedMeterPointId.value) return
  loading.value.optimization = true
  try {
    const res = await getDemandOptimizationPlan({
      meter_point_id: selectedMeterPointId.value
    })
    optimizationPlan.value = res.data
  } catch (e) {
    console.error('加载优化方案失败', e)
  } finally {
    loading.value.optimization = false
  }
}

function updateDemandChart() {
  console.log('[analysis.vue] updateDemandChart called, demandChart:', !!demandChart, 'curveData.length:', curveData.value.length)
  if (!demandChart) {
    console.warn('[analysis.vue] demandChart not initialized yet')
    return
  }
  if (curveData.value.length === 0) {
    console.warn('[analysis.vue] curveData is empty')
    return
  }

  const declaredDemand = peakAnalysis.value?.declared_demand || 100
  console.log('[analysis.vue] Rendering chart with', curveData.value.length, 'data points, declaredDemand:', declaredDemand)
  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => {
        const d = params[0]
        return `${d.axisValue}<br/>需量: ${d.value?.toFixed(1)} kW<br/>利用率: ${((d.value / declaredDemand) * 100).toFixed(1)}%`
      }
    },
    legend: {
      data: ['15分钟需量', '申报需量', '预警线']
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: curveData.value.map(d => d.timestamp),
      axisLabel: {
        rotate: 45,
        formatter: (value: string) => value.substring(11, 16)
      }
    },
    yAxis: {
      type: 'value',
      name: '需量 (kW)',
      min: 0
    },
    series: [
      {
        name: '15分钟需量',
        type: 'line',
        data: curveData.value.map(d => d.rolling_demand || d.average_power),
        smooth: true,
        areaStyle: { opacity: 0.3 },
        itemStyle: { color: '#409eff' }
      },
      {
        name: '申报需量',
        type: 'line',
        data: curveData.value.map(() => declaredDemand),
        lineStyle: { type: 'dashed', color: '#67c23a' },
        symbol: 'none'
      },
      {
        name: '预警线',
        type: 'line',
        data: curveData.value.map(() => declaredDemand * 0.9),
        lineStyle: { type: 'dashed', color: '#e6a23c' },
        symbol: 'none'
      }
    ]
  }
  demandChart.setOption(option)
  // 确保图表正确渲染
  demandChart.resize()
  console.log('[analysis.vue] Chart option set and resized')
}
</script>

<style scoped lang="scss">
.energy-analysis {
  padding: 20px;

  // el-tabs border-card 深色主题样式
  :deep(.el-tabs--border-card) {
    background-color: var(--bg-card-solid);
    border-color: var(--border-color);

    > .el-tabs__header {
      background-color: var(--bg-tertiary);
      border-bottom-color: var(--border-color);

      .el-tabs__item {
        color: var(--text-secondary);
        border-color: var(--border-color);
        background-color: transparent;
        font-weight: 400;

        &:hover {
          color: var(--text-primary);
        }

        &.is-active {
          color: var(--primary-color);
          background-color: var(--bg-card-solid);
          border-bottom-color: var(--bg-card-solid);
          font-weight: 500;
        }
      }
    }

    > .el-tabs__content {
      background-color: var(--bg-card-solid);
      padding: 20px;
    }
  }

  // 表格深色样式
  :deep(.el-table) {
    background-color: transparent;
    color: var(--text-regular);

    th.el-table__cell {
      background-color: var(--bg-tertiary);
      color: var(--text-primary);
      border-color: var(--border-color);
      font-weight: 500;
    }

    td.el-table__cell {
      border-color: var(--border-color);
    }

    tr {
      background-color: transparent;

      &:hover > td.el-table__cell {
        background-color: var(--bg-hover);
      }
    }

    .el-table__body tr.el-table__row--striped td.el-table__cell {
      background-color: rgba(255, 255, 255, 0.02);
    }
  }

  // 卡片深色样式
  :deep(.el-card) {
    background-color: var(--bg-card-solid);
    border-color: var(--border-color);

    .el-card__header {
      color: var(--text-primary);
      border-color: var(--border-color);
      font-weight: 500;
    }
  }

  // 统计组件样式
  :deep(.el-statistic) {
    .el-statistic__head {
      color: var(--text-secondary);
    }
    .el-statistic__content {
      color: var(--text-primary);
    }
  }
}

.tab-header {
  margin-bottom: 16px;
  display: flex;
  align-items: center;
}

.summary-row {
  margin-bottom: 20px;
}

.analysis-table {
  margin-top: 16px;
}

.recommendations-alert {
  margin-bottom: 16px;
  background-color: rgba(64, 158, 255, 0.1) !important;
  border: 1px solid rgba(64, 158, 255, 0.3) !important;

  :deep(.el-alert__title) {
    color: var(--text-primary, rgba(255, 255, 255, 0.95));
  }
}

.recommendations-list {
  margin: 8px 0 0 0;
  padding-left: 20px;
  color: var(--text-primary, rgba(255, 255, 255, 0.85));

  li {
    margin-bottom: 4px;
  }
}

.recommendations-list li {
  margin-bottom: 4px;
}

// 5时段分布样式
.period-distribution {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.period-bar-mini {
  display: flex;
  height: 12px;
  background: var(--bg-tertiary);
  border-radius: 4px;
  overflow: hidden;

  .bar {
    &.sharp {
      background: #722ed1;  // 尖峰-紫色
    }

    &.peak {
      background: #f5222d;  // 峰时-红色
    }

    &.flat {
      background: #faad14;  // 平时-橙色
    }

    &.valley {
      background: #52c41a;  // 谷时-绿色
    }

    &.deep-valley {
      background: #1890ff;  // 深谷-蓝色
    }
  }
}

.period-text {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  font-size: 10px;
  line-height: 1.2;

  span {
    white-space: nowrap;
  }

  .sharp-text { color: #722ed1; }
  .peak-text { color: #f5222d; }
  .flat-text { color: #faad14; }
  .valley-text { color: #52c41a; }
  .deep-valley-text { color: #1890ff; }
}

// 旧的2时段样式（保留向后兼容）
.ratio-bar {
  display: flex;
  height: 8px;
  background: var(--bg-tertiary);
  border-radius: 4px;
  overflow: hidden;
}

.ratio-bar .peak {
  background: var(--error-color);
}

.ratio-bar .valley {
  background: var(--success-color);
}

.ratio-text {
  font-size: 11px;
  color: var(--text-secondary);
  margin-top: 2px;
}

/* V2.3 新增样式 */
.demand-chart {
  height: 350px;
}

.peak-card {
  height: 100%;
}

.peak-stats .stat-row {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid var(--border-color);
}

.peak-stats .stat-row .label {
  color: var(--text-secondary);
}

.peak-stats .stat-row .value {
  font-weight: bold;
  color: var(--text-primary);
}

.peak-stats .stat-row .value.highlight {
  color: var(--error-color);
  font-size: 18px;
}

.optimization-summary {
  margin-bottom: 16px;
}

.recommendations-section h4 {
  margin-bottom: 16px;
  color: var(--text-primary);
}

.rec-item .rec-title {
  font-weight: bold;
  margin-bottom: 4px;
  color: var(--text-primary);
}

.rec-item .rec-desc {
  color: var(--text-regular);
  font-size: 13px;
}

.rec-item .rec-saving {
  color: var(--success-color);
  font-size: 12px;
  margin-top: 4px;
}

/* V2.5 负荷转移增强样式 */
.visualization-row {
  margin-top: 20px;
}

.load-distribution-chart {
  margin-bottom: 0;
}

.device-detail-card {
  margin-top: 20px;

  .card-header-with-info {
    display: flex;
    justify-content: space-between;
    align-items: center;
    width: 100%;

    .selection-info {
      font-size: 12px;
      color: var(--primary-color);
      font-weight: normal;
    }
  }

  .text-muted {
    color: var(--text-secondary);
    font-size: 12px;
  }
}

// V4.0 子Tab样式
.sub-tabs {
  :deep(.el-tabs__header) {
    margin-bottom: 16px;
  }

  :deep(.el-tabs__item) {
    background-color: var(--bg-card-solid);
    border-color: var(--border-color);
    color: var(--text-secondary);

    &.is-active {
      color: var(--primary-color);
      border-bottom-color: var(--bg-card-solid);
    }
  }
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;

  .header-sub {
    font-size: 12px;
    font-weight: 400;
    color: var(--text-secondary);
  }
}

// 设备运行优化样式
.device-category-card {
  .category-header {
    display: flex;
    align-items: center;
    gap: 8px;
    font-weight: 500;
  }

  .category-stats {
    .stat-item {
      display: flex;
      justify-content: space-between;
      padding: 12px 0;
      border-bottom: 1px solid var(--border-color);

      &:last-child {
        border-bottom: none;
      }

      .label {
        color: var(--text-secondary);
      }

      .value {
        font-weight: 500;
        color: var(--text-primary);

        &.highlight {
          color: var(--success-color);
        }
      }
    }
  }
}

// VPP需求响应样式
.vpp-status-content {
  .status-section {
    h4 {
      margin-bottom: 16px;
      color: var(--text-primary);
      font-size: 14px;
    }
  }
}

.highlight {
  color: var(--success-color);
  font-weight: 600;
}

</style>
