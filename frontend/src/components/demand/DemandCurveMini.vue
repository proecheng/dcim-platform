<template>
  <div class="demand-curve-mini">
    <div class="chart-header">
      <span class="title">近{{ timeRange === '12m' ? 12 : 6 }}个月需量趋势</span>
      <el-link type="primary" @click="goToFullCurve">
        查看完整曲线 →
      </el-link>
    </div>

    <div class="chart-container" v-loading="loading" @click="goToFullCurve">
      <div ref="chartRef" :style="{ height: height + 'px', width: '100%' }"></div>
    </div>

    <div class="chart-legend" v-if="data">
      <div class="legend-item">
        <span class="dot max"></span>
        <span>最大需量: <strong>{{ data.max_value }} kW</strong> ({{ data.max_month }})</span>
      </div>
      <div class="legend-item" v-if="data.declared_demand">
        <span class="dot threshold"></span>
        <span>申报需量: {{ data.declared_demand }} kW</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import * as echarts from 'echarts'
import type { EChartsOption } from 'echarts'
import { getDemandCurveMini, type DemandCurveMiniData } from '@/api/modules/demand'

const props = withDefaults(
  defineProps<{
    meterPointId?: number
    timeRange?: '6m' | '12m'
    highlightMax?: boolean
    showThreshold?: number
    height?: number
  }>(),
  {
    timeRange: '12m',
    highlightMax: true,
    height: 200
  }
)

const router = useRouter()
const loading = ref(false)
const data = ref<DemandCurveMiniData | null>(null)
const chartRef = ref<HTMLElement>()
let chartInstance: echarts.ECharts | null = null

onMounted(() => {
  loadData()
})

watch(() => [props.meterPointId, props.timeRange], () => {
  loadData()
})

async function loadData() {
  loading.value = true
  try {
    const months = props.timeRange === '12m' ? 12 : 6
    const res = await getDemandCurveMini({
      meterPointId: props.meterPointId,
      months
    })
    if (res.code === 0 && res.data) {
      data.value = res.data
      await nextTick()
      renderChart()
    }
  } catch (e) {
    console.error('加载需量曲线失败', e)
  } finally {
    loading.value = false
  }
}

function renderChart() {
  if (!chartRef.value || !data.value) return

  if (chartInstance) {
    chartInstance.dispose()
  }

  chartInstance = echarts.init(chartRef.value)

  const months = data.value.data.map(d => d.month)
  const demands = data.value.data.map(d => d.max_demand)
  const threshold = props.showThreshold || data.value.declared_demand

  // 找到最大值的索引
  const maxIdx = demands.indexOf(data.value.max_value)

  const option: EChartsOption = {
    grid: {
      top: 20,
      right: 20,
      bottom: 30,
      left: 45
    },
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => {
        const point = params[0]
        return `${point.axisValue}<br/>最大需量: ${point.value} kW`
      }
    },
    xAxis: {
      type: 'category',
      data: months,
      axisLabel: {
        color: 'rgba(255, 255, 255, 0.65)',
        fontSize: 11,
        rotate: 30
      },
      axisLine: {
        lineStyle: {
          color: 'rgba(255, 255, 255, 0.15)'
        }
      }
    },
    yAxis: {
      type: 'value',
      name: 'kW',
      nameTextStyle: {
        color: 'rgba(255, 255, 255, 0.65)',
        fontSize: 11
      },
      axisLabel: {
        color: 'rgba(255, 255, 255, 0.65)',
        fontSize: 11
      },
      splitLine: {
        lineStyle: {
          color: 'rgba(255, 255, 255, 0.1)'
        }
      }
    },
    series: [
      {
        name: '最大需量',
        type: 'line',
        data: demands,
        smooth: true,
        symbol: 'circle',
        symbolSize: (value: number, params: any) => {
          // 最大值点高亮
          return props.highlightMax && params.dataIndex === maxIdx ? 8 : 4
        },
        itemStyle: {
          color: (params: any) => {
            return props.highlightMax && params.dataIndex === maxIdx
              ? '#f5222d'
              : '#1890ff'
          }
        },
        lineStyle: {
          color: '#1890ff',
          width: 2
        },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(24, 144, 255, 0.3)' },
            { offset: 1, color: 'rgba(24, 144, 255, 0.05)' }
          ])
        },
        markLine: threshold ? {
          symbol: 'none',
          label: {
            show: false
          },
          lineStyle: {
            color: '#faad14',
            type: 'dashed',
            width: 2
          },
          data: [{ yAxis: threshold }]
        } : undefined,
        markPoint: props.highlightMax ? {
          data: [
            {
              name: '最大值',
              coord: [maxIdx, data.value.max_value],
              value: data.value.max_value,
              itemStyle: {
                color: '#f5222d'
              },
              label: {
                show: true,
                formatter: '{c} kW',
                color: '#fff',
                backgroundColor: '#f5222d',
                padding: [4, 8],
                borderRadius: 4,
                fontSize: 11
              }
            }
          ]
        } : undefined
      }
    ]
  }

  chartInstance.setOption(option)

  // 响应式
  const resizeObserver = new ResizeObserver(() => {
    chartInstance?.resize()
  })
  resizeObserver.observe(chartRef.value)
}

function goToFullCurve() {
  router.push('/energy/demand/curve')
}
</script>

<style scoped lang="scss">
.demand-curve-mini {
  background: var(--bg-card-solid, #1a2a4a);
  border-radius: 8px;
  padding: 12px;

  .chart-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;

    .title {
      font-size: 13px;
      font-weight: 600;
      color: var(--text-primary, rgba(255, 255, 255, 0.95));
    }
  }

  .chart-container {
    cursor: pointer;
    transition: opacity 0.2s;

    &:hover {
      opacity: 0.85;
    }
  }

  .chart-legend {
    display: flex;
    gap: 20px;
    margin-top: 8px;
    font-size: 12px;
    color: var(--text-secondary, rgba(255, 255, 255, 0.65));

    .legend-item {
      display: flex;
      align-items: center;
      gap: 6px;

      .dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;

        &.max {
          background: #f5222d;
        }

        &.threshold {
          background: #faad14;
        }
      }

      strong {
        color: var(--text-primary, rgba(255, 255, 255, 0.95));
        font-weight: 600;
      }
    }
  }
}
</style>
