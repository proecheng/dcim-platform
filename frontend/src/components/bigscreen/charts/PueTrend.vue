<!-- frontend/src/components/bigscreen/charts/PueTrend.vue -->
<template>
  <BaseChart :option="chartOption" :loading="loading" />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { EChartsOption } from 'echarts'
import BaseChart from './BaseChart.vue'

const props = withDefaults(defineProps<{
  data: { date: string; value: number }[]
  loading?: boolean
  title?: string
  targetValue?: number
}>(), {
  loading: false,
  title: 'PUE趋势',
  targetValue: 1.5
})

// PUE 颜色分级：越低越好
function getPueColor(value: number): string {
  if (value <= 1.4) return '#00ff88' // 优秀
  if (value <= 1.6) return '#00ccff' // 良好
  if (value <= 1.8) return '#ffaa00' // 一般
  return '#ff4d4f' // 较差
}

const chartOption = computed<EChartsOption>(() => {
  const dates = props.data.map(d => d.date)
  const values = props.data.map(d => d.value)
  const latestValue = values[values.length - 1] || 0

  return {
    grid: {
      top: 35,
      right: 20,
      bottom: 25,
      left: 45
    },
    tooltip: {
      trigger: 'axis',
      formatter: (params: unknown) => {
        const p = params as { name: string; value: number }[]
        if (p && p[0]) {
          const color = getPueColor(p[0].value)
          return `${p[0].name}<br/>PUE: <span style="color:${color};font-weight:bold">${p[0].value.toFixed(2)}</span>`
        }
        return ''
      }
    },
    xAxis: {
      type: 'category',
      data: dates,
      boundaryGap: false,
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
      name: 'PUE',
      min: 1,
      max: 2.5,
      nameTextStyle: {
        color: '#8899aa',
        fontSize: 10
      },
      axisLine: { show: false },
      axisLabel: {
        color: '#8899aa',
        fontSize: 10,
        formatter: (value: number) => value.toFixed(1)
      },
      splitLine: {
        lineStyle: { color: 'rgba(136, 153, 170, 0.1)' }
      }
    },
    series: [
      {
        name: 'PUE',
        type: 'line',
        data: values,
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: {
          width: 2,
          color: getPueColor(latestValue)
        },
        itemStyle: {
          color: getPueColor(latestValue),
          borderColor: getPueColor(latestValue),
          borderWidth: 2
        },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: `${getPueColor(latestValue)}40` },
              { offset: 1, color: `${getPueColor(latestValue)}05` }
            ]
          }
        },
        markLine: {
          silent: true,
          symbol: 'none',
          lineStyle: {
            type: 'dashed',
            color: '#00ff88'
          },
          data: [
            {
              yAxis: props.targetValue,
              label: {
                formatter: `目标 ${props.targetValue}`,
                color: '#00ff88',
                fontSize: 10,
                position: 'end'
              }
            }
          ]
        }
      }
    ],
    visualMap: {
      show: false,
      pieces: [
        { lte: 1.4, color: '#00ff88' },
        { gt: 1.4, lte: 1.6, color: '#00ccff' },
        { gt: 1.6, lte: 1.8, color: '#ffaa00' },
        { gt: 1.8, color: '#ff4d4f' }
      ]
    }
  }
})
</script>
