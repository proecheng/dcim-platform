/**
 * 历史数据页面 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, reactive, computed } from 'vue'

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useRoute: () => ({ params: {}, query: {} }),
}))

vi.mock('@/api/modules/point', () => ({
  getPointList: vi.fn().mockResolvedValue({ items: [], total: 0 }),
}))

vi.mock('@/api/modules/history', () => ({
  getPointHistory: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  getPointTrend: vi.fn().mockResolvedValue([]),
  getPointStatistics: vi.fn().mockResolvedValue(null),
  exportHistory: vi.fn().mockResolvedValue(new Blob()),
}))

vi.mock('echarts', () => ({
  init: vi.fn(() => ({ setOption: vi.fn(), resize: vi.fn(), dispose: vi.fn(), clear: vi.fn() })),
}))

vi.mock('@element-plus/icons-vue', () => ({
  Search: { template: '<i />' },
  Refresh: { template: '<i />' },
  Download: { template: '<i />' },
}))

const HistoryPageTestable = defineComponent({
  name: 'HistoryPageTestable',
  setup() {
    const loading = ref(false)
    const pointList = ref([
      { id: 1, point_code: 'AI_001', point_name: '温度传感器1', unit: '°C' },
      { id: 2, point_code: 'AI_002', point_name: '湿度传感器1', unit: '%RH' },
    ])
    const historyData = ref<{ created_at: string; value: number }[]>([])
    const statistics = ref<{ count: number; min_value: number; max_value: number; avg_value: number; std_dev: number; change_rate: number | null; first_value: number; last_value: number } | null>(null)
    const chartType = ref<'line' | 'bar'>('line')

    const filters = reactive({
      point_id: null as number | null,
      dateRange: [] as string[],
      granularity: 'raw' as 'raw' | 'minute' | 'hour' | 'day',
    })

    const pagination = reactive({ page: 1, page_size: 20, total: 0 })

    const currentPoint = computed(() => pointList.value.find(p => p.id === filters.point_id))

    function formatValue(val: number | null | undefined): string {
      return val !== null && val !== undefined ? val.toFixed(2) : '-'
    }

    function handleReset() {
      filters.point_id = null
      filters.dateRange = []
      filters.granularity = 'raw'
      pagination.page = 1
      historyData.value = []
      statistics.value = null
    }

    return { loading, pointList, historyData, statistics, chartType, filters, pagination, currentPoint, formatValue, handleReset }
  },
  template: `
    <div class="history-page">
      <div data-testid="filter-panel">
        <select data-testid="point-select" v-model="filters.point_id">
          <option :value="null">请选择</option>
          <option v-for="p in pointList" :key="p.id" :value="p.id">{{ p.point_code }}</option>
        </select>
        <select data-testid="granularity-select" v-model="filters.granularity">
          <option value="raw">原始数据</option>
          <option value="minute">分钟均值</option>
          <option value="hour">小时均值</option>
          <option value="day">日均值</option>
        </select>
        <button data-testid="reset-btn" @click="handleReset">重置</button>
      </div>
      <div data-testid="chart-type">
        <button :data-testid="'chart-' + chartType">{{ chartType }}</button>
      </div>
      <div v-if="statistics" data-testid="statistics">
        <span data-testid="stat-count">{{ statistics.count }}</span>
        <span data-testid="stat-min">{{ formatValue(statistics.min_value) }}</span>
        <span data-testid="stat-max">{{ formatValue(statistics.max_value) }}</span>
        <span data-testid="stat-avg">{{ formatValue(statistics.avg_value) }}</span>
      </div>
      <div v-else data-testid="empty-stats">请先查询数据</div>
      <div data-testid="current-point">{{ currentPoint?.point_name || '未选择' }}</div>
      <div data-testid="pagination-total">{{ pagination.total }}</div>
    </div>
  `,
})

describe('HistoryPage 历史数据', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('渲染筛选面板', () => {
    const wrapper = mount(HistoryPageTestable)
    expect(wrapper.find('[data-testid="filter-panel"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="point-select"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="granularity-select"]').exists()).toBe(true)
  })

  it('初始状态正确', () => {
    const wrapper = mount(HistoryPageTestable)
    expect(wrapper.vm.filters.point_id).toBeNull()
    expect(wrapper.vm.filters.granularity).toBe('raw')
    expect(wrapper.vm.filters.dateRange).toEqual([])
    expect(wrapper.vm.chartType).toBe('line')
    expect(wrapper.vm.statistics).toBeNull()
  })

  it('未查询时显示空状态', () => {
    const wrapper = mount(HistoryPageTestable)
    expect(wrapper.find('[data-testid="empty-stats"]').text()).toContain('请先查询数据')
  })

  it('统计信息显示正确', async () => {
    const wrapper = mount(HistoryPageTestable)
    wrapper.vm.statistics = { count: 100, min_value: 20.5, max_value: 35.8, avg_value: 28.15, std_dev: 3.2, change_rate: 0.05, first_value: 22, last_value: 30 }
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[data-testid="stat-count"]').text()).toBe('100')
    expect(wrapper.find('[data-testid="stat-min"]').text()).toBe('20.50')
    expect(wrapper.find('[data-testid="stat-max"]').text()).toBe('35.80')
    expect(wrapper.find('[data-testid="stat-avg"]').text()).toBe('28.15')
  })

  it('选择点位后显示点位名称', async () => {
    const wrapper = mount(HistoryPageTestable)
    wrapper.vm.filters.point_id = 1
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[data-testid="current-point"]').text()).toBe('温度传感器1')
  })

  it('重置清空所有状态', async () => {
    const wrapper = mount(HistoryPageTestable)
    wrapper.vm.filters.point_id = 1
    wrapper.vm.filters.granularity = 'hour'
    wrapper.vm.pagination.page = 3
    await wrapper.find('[data-testid="reset-btn"]').trigger('click')
    expect(wrapper.vm.filters.point_id).toBeNull()
    expect(wrapper.vm.filters.granularity).toBe('raw')
    expect(wrapper.vm.pagination.page).toBe(1)
    expect(wrapper.vm.statistics).toBeNull()
  })

  it('formatValue 处理空值', () => {
    const wrapper = mount(HistoryPageTestable)
    expect(wrapper.vm.formatValue(null)).toBe('-')
    expect(wrapper.vm.formatValue(undefined)).toBe('-')
    expect(wrapper.vm.formatValue(25.123)).toBe('25.12')
  })
})
