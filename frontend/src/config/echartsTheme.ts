// ============================================
// ECharts 深色科技风主题配置
// ============================================

import * as echarts from 'echarts'

// 主题色板 - 科技风配色
const colorPalette = [
  '#5470c6',  // 蓝
  '#91cc75',  // 绿
  '#fac858',  // 黄
  '#ee6666',  // 红
  '#73c0de',  // 青
  '#3ba272',  // 深绿
  '#fc8452',  // 橙
  '#9a60b4',  // 紫
  '#ea7ccc',  // 粉
  '#48b8d0'   // 湖蓝
]

// 深色科技风主题配置
export const darkTechTheme: any = {
  // 调色盘
  color: colorPalette,

  // 背景色
  backgroundColor: 'transparent',

  // 标题
  title: {
    textStyle: {
      color: 'rgba(255, 255, 255, 0.95)',
      fontSize: 16,
      fontWeight: 600
    },
    subtextStyle: {
      color: 'rgba(255, 255, 255, 0.65)',
      fontSize: 12
    }
  },

  // 图例
  legend: {
    textStyle: {
      color: 'rgba(255, 255, 255, 0.85)'
    },
    pageTextStyle: {
      color: 'rgba(255, 255, 255, 0.65)'
    },
    pageIconColor: '#1890ff',
    pageIconInactiveColor: 'rgba(255, 255, 255, 0.25)'
  },

  // 提示框
  tooltip: {
    backgroundColor: 'rgba(26, 42, 74, 0.95)',
    borderColor: 'rgba(255, 255, 255, 0.1)',
    borderWidth: 1,
    textStyle: {
      color: 'rgba(255, 255, 255, 0.85)'
    },
    axisPointer: {
      lineStyle: {
        color: 'rgba(0, 212, 255, 0.5)',
        width: 1
      },
      crossStyle: {
        color: 'rgba(0, 212, 255, 0.5)',
        width: 1
      },
      shadowStyle: {
        color: 'rgba(0, 212, 255, 0.1)'
      }
    }
  },

  // 坐标轴
  categoryAxis: {
    axisLine: {
      show: true,
      lineStyle: {
        color: 'rgba(255, 255, 255, 0.1)'
      }
    },
    axisTick: {
      show: false
    },
    axisLabel: {
      color: 'rgba(255, 255, 255, 0.65)'
    },
    splitLine: {
      show: false
    },
    splitArea: {
      show: false
    }
  },

  valueAxis: {
    axisLine: {
      show: false
    },
    axisTick: {
      show: false
    },
    axisLabel: {
      color: 'rgba(255, 255, 255, 0.65)'
    },
    splitLine: {
      lineStyle: {
        color: 'rgba(255, 255, 255, 0.06)',
        type: 'dashed'
      }
    },
    splitArea: {
      show: false
    }
  },

  // 数据区域缩放
  dataZoom: [
    {
      type: 'inside',
      textStyle: {
        color: 'rgba(255, 255, 255, 0.65)'
      },
      borderColor: 'rgba(255, 255, 255, 0.1)'
    },
    {
      type: 'slider',
      textStyle: {
        color: 'rgba(255, 255, 255, 0.65)'
      },
      borderColor: 'rgba(255, 255, 255, 0.1)',
      backgroundColor: 'rgba(17, 34, 64, 0.8)',
      fillerColor: 'rgba(24, 144, 255, 0.2)',
      handleStyle: {
        color: '#1890ff',
        borderColor: '#1890ff'
      },
      dataBackground: {
        lineStyle: {
          color: 'rgba(24, 144, 255, 0.3)'
        },
        areaStyle: {
          color: 'rgba(24, 144, 255, 0.1)'
        }
      }
    }
  ],

  // 工具栏
  toolbox: {
    iconStyle: {
      borderColor: 'rgba(255, 255, 255, 0.45)'
    },
    emphasis: {
      iconStyle: {
        borderColor: '#1890ff'
      }
    }
  },

  // 时间轴
  timeline: {
    lineStyle: {
      color: 'rgba(255, 255, 255, 0.1)'
    },
    itemStyle: {
      color: '#1890ff',
      borderColor: '#1890ff'
    },
    controlStyle: {
      color: 'rgba(255, 255, 255, 0.65)',
      borderColor: 'rgba(255, 255, 255, 0.25)'
    },
    checkpointStyle: {
      color: '#00d4ff',
      borderColor: 'rgba(0, 212, 255, 0.3)'
    },
    label: {
      color: 'rgba(255, 255, 255, 0.65)'
    }
  },

  // 视觉映射
  visualMap: {
    textStyle: {
      color: 'rgba(255, 255, 255, 0.65)'
    }
  },

  // 折线图
  line: {
    symbol: 'circle',
    symbolSize: 6,
    smooth: true,
    lineStyle: {
      width: 2
    },
    emphasis: {
      lineStyle: {
        width: 3
      }
    }
  },

  // 柱状图
  bar: {
    barMaxWidth: 40,
    itemStyle: {
      borderRadius: [4, 4, 0, 0]
    }
  },

  // 饼图
  pie: {
    itemStyle: {
      borderColor: '#0a1628',
      borderWidth: 2
    },
    label: {
      color: 'rgba(255, 255, 255, 0.85)'
    }
  },

  // 仪表盘
  gauge: {
    axisLine: {
      lineStyle: {
        color: [
          [0.3, '#52c41a'],
          [0.7, '#1890ff'],
          [1, '#f5222d']
        ],
        width: 15
      }
    },
    axisTick: {
      lineStyle: {
        color: 'rgba(255, 255, 255, 0.3)'
      }
    },
    axisLabel: {
      color: 'rgba(255, 255, 255, 0.65)'
    },
    splitLine: {
      lineStyle: {
        color: 'rgba(255, 255, 255, 0.3)'
      }
    },
    pointer: {
      itemStyle: {
        color: '#00d4ff'
      }
    },
    detail: {
      color: 'rgba(255, 255, 255, 0.95)',
      fontSize: 24,
      fontWeight: 'bold'
    },
    title: {
      color: 'rgba(255, 255, 255, 0.65)'
    }
  },

  // 雷达图
  radar: {
    axisName: {
      color: 'rgba(255, 255, 255, 0.65)'
    },
    splitLine: {
      lineStyle: {
        color: 'rgba(255, 255, 255, 0.1)'
      }
    },
    splitArea: {
      areaStyle: {
        color: ['rgba(255, 255, 255, 0.02)', 'rgba(255, 255, 255, 0.04)']
      }
    },
    axisLine: {
      lineStyle: {
        color: 'rgba(255, 255, 255, 0.1)'
      }
    }
  },

  // 地图
  geo: {
    itemStyle: {
      areaColor: '#112240',
      borderColor: 'rgba(0, 212, 255, 0.3)'
    },
    emphasis: {
      itemStyle: {
        areaColor: 'rgba(24, 144, 255, 0.3)'
      }
    },
    label: {
      color: 'rgba(255, 255, 255, 0.65)'
    }
  },

  // 地图系列
  map: {
    itemStyle: {
      areaColor: '#112240',
      borderColor: 'rgba(0, 212, 255, 0.3)'
    },
    emphasis: {
      itemStyle: {
        areaColor: 'rgba(24, 144, 255, 0.3)'
      }
    },
    label: {
      color: 'rgba(255, 255, 255, 0.65)'
    }
  }
}

// 注册主题
export function registerDarkTechTheme() {
  echarts.registerTheme('dark-tech', darkTechTheme)
}

// 获取图表通用配置
export function getChartBaseOption(): echarts.EChartsOption {
  return {
    backgroundColor: 'transparent',
    textStyle: {
      color: 'rgba(255, 255, 255, 0.85)',
      fontFamily: 'Microsoft YaHei, sans-serif'
    },
    animation: true,
    animationDuration: 500,
    animationEasing: 'cubicOut'
  }
}

// 获取渐变色
export function getGradientColor(startColor: string, endColor: string): echarts.LinearGradientObject {
  return {
    type: 'linear',
    x: 0,
    y: 0,
    x2: 0,
    y2: 1,
    colorStops: [
      { offset: 0, color: startColor },
      { offset: 1, color: endColor }
    ]
  }
}

// 科技风渐变色预设
export const gradientPresets = {
  // 主色渐变
  primary: getGradientColor('rgba(24, 144, 255, 0.8)', 'rgba(24, 144, 255, 0.2)'),
  // 强调色渐变
  accent: getGradientColor('rgba(0, 212, 255, 0.8)', 'rgba(0, 212, 255, 0.2)'),
  // 成功色渐变
  success: getGradientColor('rgba(82, 196, 26, 0.8)', 'rgba(82, 196, 26, 0.2)'),
  // 警告色渐变
  warning: getGradientColor('rgba(250, 173, 20, 0.8)', 'rgba(250, 173, 20, 0.2)'),
  // 错误色渐变
  error: getGradientColor('rgba(245, 34, 45, 0.8)', 'rgba(245, 34, 45, 0.2)')
}

// 默认导出
export default {
  darkTechTheme,
  registerDarkTechTheme,
  getChartBaseOption,
  getGradientColor,
  gradientPresets,
  colorPalette
}
