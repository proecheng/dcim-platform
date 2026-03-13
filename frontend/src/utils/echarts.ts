/**
 * ECharts 按需引入 — 减少打包体积
 *
 * 本文件是项目中唯一的 ECharts 入口，所有图表组件必须从此文件导入 echarts，
 * 而非直接 import 'echarts'。只有在下方 echarts.use([...]) 中注册过的图表类型
 * 和组件才能在运行时正常渲染，未注册的功能不会报编译错误，但会在运行时静默失败。
 *
 * 新增图表类型或组件时：
 *   1. 从 'echarts/charts' 或 'echarts/components' 导入
 *   2. 添加到 echarts.use([...]) 数组中
 *   3. 参考 https://echarts.apache.org/handbook/zh/basics/import 查找模块名
 */
import * as echarts from 'echarts/core'

// 图表类型
import { BarChart, LineChart, PieChart, GaugeChart, CustomChart } from 'echarts/charts'

// 组件
import {
  TitleComponent,
  TooltipComponent,
  GridComponent,
  LegendComponent,
  DataZoomComponent,
  MarkLineComponent,
  MarkAreaComponent,
  MarkPointComponent,
} from 'echarts/components'

// 渲染器
import { CanvasRenderer } from 'echarts/renderers'

// 注册
echarts.use([
  BarChart,
  LineChart,
  PieChart,
  GaugeChart,
  CustomChart,
  TitleComponent,
  TooltipComponent,
  GridComponent,
  LegendComponent,
  DataZoomComponent,
  MarkLineComponent,
  MarkAreaComponent,
  MarkPointComponent,
  CanvasRenderer,
])

export type { EChartsCoreOption as EChartsOption } from 'echarts/core'

export default echarts
export { echarts }
