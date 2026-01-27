<!-- frontend/src/components/bigscreen/charts/PowerDistribution.vue -->
<template>
  <BaseChart :option="chartOption" :loading="loading" />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { EChartsOption } from 'echarts'
import BaseChart from './BaseChart.vue'

const props = withDefaults(defineProps<{
  data: { name: string; value: number; color?: string }[]
  loading?: boolean
  title?: string
  unit?: string
  roseType?: 'radius' | 'area' | false
}>(), {
  loading: false,
  title: '功率分布',
  unit: 'kW',
  roseType: 'radius'
})

const defaultColors = [
  '#00ccff', '#00ff88', '#ffaa00', '#ff4d4f',
  '#9254de', '#36cfc9', '#597ef7', '#73d13d'
]

const chartOption = computed<EChartsOption>(() => {
  const seriesData = props.data.map((d, index) => ({
    name: d.name,
    value: d.value,
    itemStyle: {
      color: d.color || defaultColors[index % defaultColors.length]
    }
  }))

  const total = props.data.reduce((sum, d) => sum + d.value, 0)

  return {
    tooltip: {
      trigger: 'item',
      formatter: (params: unknown) => {
        const p = params as { name: string; value: number; percent: number }
        return `${p.name}<br/>功率: ${p.value} ${props.unit}<br/>占比: ${p.percent.toFixed(1)}%`
      }
    },
    legend: {
      orient: 'vertical',
      right: 10,
      top: 'center',
      textStyle: {
        color: '#8899aa',
        fontSize: 11
      },
      itemWidth: 10,
      itemHeight: 10,
      formatter: (name: string) => {
        const item = props.data.find(d => d.name === name)
        if (item) {
          const percent = ((item.value / total) * 100).toFixed(1)
          return `${name}  ${percent}%`
        }
        return name
      }
    },
    series: [
      {
        name: props.title,
        type: 'pie',
        radius: props.roseType ? ['20%', '70%'] : ['40%', '65%'],
        center: ['35%', '50%'],
        roseType: props.roseType || undefined,
        itemStyle: {
          borderRadius: props.roseType ? 5 : 3,
          borderColor: 'rgba(10, 10, 26, 0.8)',
          borderWidth: 2
        },
        label: {
          show: false
        },
        emphasis: {
          itemStyle: {
            shadowBlur: 20,
            shadowColor: 'rgba(0, 204, 255, 0.5)'
          },
          label: {
            show: true,
            fontSize: 12,
            fontWeight: 'bold',
            color: '#ffffff'
          }
        },
        data: seriesData
      }
    ],
    graphic: [
      {
        type: 'text',
        left: '26%',
        top: '45%',
        style: {
          text: props.roseType ? '' : `${total.toFixed(0)}`,
          fill: '#00ccff',
          fontSize: 20,
          fontWeight: 'bold',
          textAlign: 'center'
        }
      },
      {
        type: 'text',
        left: '27%',
        top: '55%',
        style: {
          text: props.roseType ? '' : props.unit,
          fill: '#8899aa',
          fontSize: 11,
          textAlign: 'center'
        }
      }
    ]
  }
})
</script>
