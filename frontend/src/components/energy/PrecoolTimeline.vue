<template>
  <div v-loading="loading" class="precool-timeline">
    <div v-if="!schedules.length && !loading" class="timeline-empty">
      <el-empty description="暂无预冷计划" />
    </div>
    <div v-else ref="chartRef" style="width: 100%; height: 200px"></div>
  </div>
</template>

<script setup lang="ts">
import echarts from '@/utils/echarts'
import { useDebounceFn } from '@vueuse/core'
import type { ScheduleListItem } from '@/api/modules/precool'

const props = defineProps<{
  schedules: ScheduleListItem[]
  loading?: boolean
}>()

const emit = defineEmits<{
  (e: 'select', schedule: ScheduleListItem): void
}>()

const chartRef = ref<HTMLElement>()
const chartInstance = shallowRef<echarts.ECharts>()

const STATUS_COLORS: Record<string, string> = {
  pending: '#409EFF',
  executing: '#67C23A',
  completed: '#909399',
  aborted: '#F56C6C',
}

const STATUS_LABELS: Record<string, string> = {
  pending: '待执行',
  executing: '执行中',
  completed: '已完成',
  aborted: '已中止',
}

/** 从时间字符串提取当天小时数（0-24） */
function timeToHour(timeStr: string): number {
  const d = new Date(timeStr)
  return d.getHours() + d.getMinutes() / 60
}

function renderChart() {
  if (!chartInstance.value || !props.schedules.length) return

  const schedules = props.schedules
  // 从 schedule 推断电价时段 markArea
  const markAreaData: any[] = []
  const peakSeen = new Set<string>()
  for (const s of schedules) {
    const key = `${s.peak_start_time}-${s.peak_end_time}`
    if (!peakSeen.has(key)) {
      peakSeen.add(key)
      markAreaData.push([
        { xAxis: timeToHour(s.peak_start_time), itemStyle: { color: 'rgba(245, 108, 108, 0.1)' } },
        { xAxis: timeToHour(s.peak_end_time) },
      ])
      // 预冷时段（谷电）
      markAreaData.push([
        { xAxis: timeToHour(s.precool_start_time), itemStyle: { color: 'rgba(103, 194, 58, 0.1)' } },
        { xAxis: timeToHour(s.precool_end_time) },
      ])
    }
  }

  // custom series 数据
  const customData = schedules.map((s, i) => ({
    value: [timeToHour(s.precool_start_time), timeToHour(s.precool_end_time), 0, i],
    schedule: s,
  }))

  const option: any = {
    tooltip: {
      trigger: 'item',
      formatter: (params: any) => {
        const s = params.data?.schedule as ScheduleListItem | undefined
        if (!s) return ''
        const startH = timeToHour(s.precool_start_time).toFixed(1)
        const endH = timeToHour(s.precool_end_time).toFixed(1)
        const savings = s.planned_savings_kwh != null ? `${s.planned_savings_kwh.toFixed(1)} kWh` : '-'
        const actual = s.actual_savings_kwh != null ? `${s.actual_savings_kwh.toFixed(1)} kWh` : '-'
        return `<strong>预冷计划 #${s.id}</strong><br/>
          时段: ${startH}h - ${endH}h<br/>
          目标温度: ${s.target_temp}°C<br/>
          状态: ${STATUS_LABELS[s.status] || s.status}<br/>
          计划节省: ${savings}<br/>
          实际节省: ${actual}`
      },
    },
    grid: { top: 30, right: 40, bottom: 30, left: 50 },
    xAxis: {
      type: 'value',
      min: 0,
      max: 24,
      interval: 2,
      axisLabel: { formatter: '{value}h' },
      name: '时间',
    },
    yAxis: {
      type: 'value',
      min: -0.5,
      max: 0.5,
      show: false,
    },
    series: [
      // markArea 占位系列（用于电价底色）
      {
        type: 'line',
        data: [],
        markArea: { silent: true, data: markAreaData },
      },
      // custom 系列（甘特图条）
      {
        type: 'custom',
        data: customData,
        renderItem: (params: any, api: any) => {
          const startVal = api.value(0)
          const endVal = api.value(1)
          const idx = api.value(3)
          const schedule = schedules[idx]
          const color = STATUS_COLORS[schedule?.status] || '#909399'

          const startCoord = api.coord([startVal, 0])
          const endCoord = api.coord([endVal, 0])
          const barHeight = 30

          return {
            type: 'rect',
            shape: {
              x: startCoord[0],
              y: startCoord[1] - barHeight / 2,
              width: endCoord[0] - startCoord[0],
              height: barHeight,
            },
            style: {
              fill: color,
              stroke: '#fff',
              lineWidth: 1,
            },
            textContent: {
              type: 'text',
              style: {
                text: `#${schedule?.id || ''} ${STATUS_LABELS[schedule?.status] || ''}`,
                fill: '#fff',
                fontSize: 11,
              },
            },
            textConfig: {
              position: 'inside',
            },
          }
        },
        encode: { x: [0, 1], y: 2 },
      },
    ],
  }

  chartInstance.value.setOption(option, true)

  // 点击事件
  chartInstance.value.off('click')
  chartInstance.value.on('click', (params: any) => {
    const s = params.data?.schedule as ScheduleListItem | undefined
    if (s) emit('select', s)
  })
}

const handleResize = useDebounceFn(() => {
  chartInstance.value?.resize()
}, 200)

watch(() => props.schedules, () => {
  renderChart()
}, { deep: true })

onMounted(() => {
  if (chartRef.value) {
    chartInstance.value = echarts.init(chartRef.value)
  }
  window.addEventListener('resize', handleResize)
  renderChart()
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  chartInstance.value?.dispose()
})
</script>

<style scoped lang="scss">
.precool-timeline {
  .timeline-empty {
    min-height: 150px;
    display: flex;
    align-items: center;
    justify-content: center;
  }
}
</style>
