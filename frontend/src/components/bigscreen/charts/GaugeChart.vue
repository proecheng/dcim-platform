<!-- frontend/src/components/bigscreen/charts/GaugeChart.vue -->
<template>
  <BaseChart :option="chartOption" :loading="loading" />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { EChartsOption } from 'echarts'
import BaseChart from './BaseChart.vue'

const props = withDefaults(defineProps<{
  value: number
  loading?: boolean
  title?: string
  unit?: string
  min?: number
  max?: number
  thresholds?: { warning: number; danger: number }
  showPointer?: boolean
}>(), {
  loading: false,
  title: '',
  unit: '',
  min: 0,
  max: 100,
  thresholds: () => ({ warning: 70, danger: 90 }),
  showPointer: true
})

function getValueColor(value: number): string {
  if (value >= props.thresholds.danger) return '#ff4d4f'
  if (value >= props.thresholds.warning) return '#ffaa00'
  return '#00ccff'
}

const chartOption = computed<EChartsOption>(() => {
  const color = getValueColor(props.value)

  return {
    series: [
      {
        name: props.title,
        type: 'gauge',
        center: ['50%', '60%'],
        radius: '90%',
        startAngle: 200,
        endAngle: -20,
        min: props.min,
        max: props.max,
        splitNumber: 5,
        itemStyle: {
          color: color
        },
        progress: {
          show: true,
          roundCap: true,
          width: 12
        },
        pointer: {
          show: props.showPointer,
          length: '60%',
          width: 4,
          itemStyle: {
            color: '#ffffff'
          }
        },
        axisLine: {
          roundCap: true,
          lineStyle: {
            width: 12,
            color: [
              [props.thresholds.warning / props.max, 'rgba(0, 204, 255, 0.2)'],
              [props.thresholds.danger / props.max, 'rgba(255, 170, 0, 0.2)'],
              [1, 'rgba(255, 77, 79, 0.2)']
            ]
          }
        },
        axisTick: {
          show: false
        },
        splitLine: {
          show: false
        },
        axisLabel: {
          show: true,
          distance: 20,
          color: '#8899aa',
          fontSize: 10,
          formatter: (value: number) => {
            if (value === props.min || value === props.max) {
              return `${value}`
            }
            return ''
          }
        },
        title: {
          show: true,
          offsetCenter: [0, '75%'],
          fontSize: 12,
          color: '#8899aa'
        },
        detail: {
          valueAnimation: true,
          fontSize: 24,
          fontWeight: 'bold',
          offsetCenter: [0, '30%'],
          formatter: `{value}${props.unit}`,
          color: color
        },
        data: [
          {
            value: props.value,
            name: props.title
          }
        ]
      }
    ]
  }
})
</script>
