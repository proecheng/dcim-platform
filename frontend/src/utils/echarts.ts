/**
 * ECharts 按需引入 — 减少打包体积
 * 所有 chart 组件统一从此文件导入 echarts
 */
import * as echarts from 'echarts/core'

// 图表类型
import { BarChart, LineChart, PieChart, GaugeChart } from 'echarts/charts'

// 组件
import {
  TitleComponent,
  TooltipComponent,
  GridComponent,
  LegendComponent,
  DataZoomComponent,
  MarkLineComponent,
} from 'echarts/components'

// 渲染器
import { CanvasRenderer } from 'echarts/renderers'

// 注册
echarts.use([
  BarChart,
  LineChart,
  PieChart,
  GaugeChart,
  TitleComponent,
  TooltipComponent,
  GridComponent,
  LegendComponent,
  DataZoomComponent,
  MarkLineComponent,
  CanvasRenderer,
])

export type { EChartsCoreOption as EChartsOption } from 'echarts/core'

export default echarts
export { echarts }
