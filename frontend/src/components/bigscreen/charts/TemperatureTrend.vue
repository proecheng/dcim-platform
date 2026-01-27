<!-- frontend/src/components/bigscreen/charts/TemperatureTrend.vue -->
<template>
  <BaseChart :option="chartOption" :loading="loading" />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { EChartsOption } from 'echarts'
import BaseChart from './BaseChart.vue'

const props = withDefaults(defineProps<{
  data: { time: string; value: number }[]
  loading?: boolean
  title?: string
  unit?: string
  thresholds?: { warning: number; danger: number }
}>(), {
  loading: false,
  title: '温度趋势',
  unit: '°C',
  thresholds: () => ({ warning: 28, danger: 32 })
})

const chartOption = computed<EChartsOption>(() => {
  const times = props.data.map(d => d.time)
  const values = props.data.map(d => d.value)

  return {
    grid: {
      top: 30,
      right: 20,
      bottom: 25,
      left: 45
    },
    tooltip: {
      trigger: 'axis',
      formatter: (params: unknown) => {
        const p = params as { name: string; value: number }[]
        if (p && p[0]) {
          return `${p[0].name}<br/>温度: ${p[0].value}${props.unit}`
        }
        return ''
      }
    },
    xAxis: {
      type: 'category',
      data: times,
      axisLine: {
        lineStyle: { color: 'rgba(136, 153, 170, 0.3)' }
      },
      axisLabel: {
        color: '#8899aa',
        fontSize: 10
      },
      axisTick: { show: false }
    },
    yAxis: {
      type: 'value',
      name: props.unit,
      nameTextStyle: {
        color: '#8899aa',
        fontSize: 10
      },
      axisLine: { show: false },
      axisLabel: {
        color: '#8899aa',
        fontSize: 10
      },
      splitLine: {
        lineStyle: { color: 'rgba(136, 153, 170, 0.1)' }
      }
    },
    series: [
      {
        name: '温度',
        type: 'line',
        data: values,
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: {
          width: 2,
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 1, y2: 0,
            colorStops: [
              { offset: 0, color: '#00ccff' },
              { offset: 1, color: '#00ff88' }
            ]
          }
        },
        itemStyle: {
          color: '#00ccff',
          borderColor: '#00ccff',
          borderWidth: 2
        },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(0, 204, 255, 0.3)' },
              { offset: 1, color: 'rgba(0, 204, 255, 0.02)' }
            ]
          }
        },
        markLine: {
          silent: true,
          symbol: 'none',
          lineStyle: { type: 'dashed' },
          data: [
            {
              yAxis: props.thresholds.warning,
              lineStyle: { color: '#ffaa00' },
              label: {
                formatter: '警告',
                color: '#ffaa00',
                fontSize: 10
              }
            },
            {
              yAxis: props.thresholds.danger,
              lineStyle: { color: '#ff4d4f' },
              label: {
                formatter: '危险',
                color: '#ff4d4f',
                fontSize: 10
              }
            }
          ]
        }
      }
    ]
  }
})
</script>
