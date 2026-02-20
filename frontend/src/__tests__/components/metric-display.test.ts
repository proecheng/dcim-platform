/**
 * MetricDisplay 组件测试
 * 测试指标显示组件（值格式化、tooltip、单位）
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent } from 'vue'

const MetricDisplayTestable = defineComponent({
  name: 'MetricDisplayTestable',
  props: {
    metric: {
      type: Object as () => {
        value: number
        unit?: string
        formula?: string
        data_source?: any
        typical_range?: string
        description?: string
        parameters?: any
      } | null,
      default: null
    }
  },
  setup(props) {
    const formatValue = (value: number): string => {
      if (value === null || value === undefined || isNaN(value)) return '--'
      if (Math.abs(value) >= 1000) {
        return value.toLocaleString('zh-CN', {
          minimumFractionDigits: 0,
          maximumFractionDigits: 2
        })
      }
      return value.toFixed(2)
    }

    const formatDataSource = (data: any): string => {
      if (typeof data === 'string') return data
      return JSON.stringify(data, null, 2)
    }

    return { formatValue, formatDataSource }
  },
  template: `
    <div v-if="metric" class="metric-display" data-testid="metric-display">
      <div class="metric-value">
        <span class="value" data-testid="value">{{ formatValue(metric.value) }}</span>
        <span v-if="metric.unit" class="unit" data-testid="unit">{{ metric.unit }}</span>
        <div class="tooltip-content" data-testid="tooltip">
          <div v-if="metric.formula" data-testid="formula">{{ metric.formula }}</div>
          <div v-if="metric.data_source" data-testid="data-source">{{ formatDataSource(metric.data_source) }}</div>
          <div v-if="metric.typical_range" data-testid="typical-range">{{ metric.typical_range }}</div>
          <div v-if="metric.description" data-testid="description">{{ metric.description }}</div>
          <div v-if="metric.parameters" data-testid="parameters">{{ formatDataSource(metric.parameters) }}</div>
        </div>
      </div>
    </div>
    <span v-else class="no-data" data-testid="no-data">--</span>
  `
})

describe('MetricDisplay 指标显示组件', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('metric 为 null 时显示占位符', () => {
    const wrapper = mount(MetricDisplayTestable, { props: { metric: null } })
    expect(wrapper.find('[data-testid="no-data"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="no-data"]').text()).toBe('--')
  })

  it('正确显示指标值和单位', () => {
    const wrapper = mount(MetricDisplayTestable, {
      props: { metric: { value: 1.85, unit: 'PUE' } }
    })
    expect(wrapper.find('[data-testid="value"]').text()).toBe('1.85')
    expect(wrapper.find('[data-testid="unit"]').text()).toBe('PUE')
  })

  it('大数值使用千分位格式化', () => {
    const wrapper = mount(MetricDisplayTestable, {
      props: { metric: { value: 12345.67 } }
    })
    const text = wrapper.find('[data-testid="value"]').text()
    expect(text).toContain('12')
    expect(text).toContain('345')
  })

  it('小数值保留两位小数', () => {
    const wrapper = mount(MetricDisplayTestable, {
      props: { metric: { value: 3.1 } }
    })
    expect(wrapper.find('[data-testid="value"]').text()).toBe('3.10')
  })

  it('无单位时不渲染单位元素', () => {
    const wrapper = mount(MetricDisplayTestable, {
      props: { metric: { value: 42 } }
    })
    expect(wrapper.find('[data-testid="unit"]').exists()).toBe(false)
  })

  it('显示公式和典型范围', () => {
    const wrapper = mount(MetricDisplayTestable, {
      props: {
        metric: {
          value: 1.5,
          formula: 'IT总功率/总功率',
          typical_range: '1.2 - 2.0'
        }
      }
    })
    expect(wrapper.find('[data-testid="formula"]').text()).toBe('IT总功率/总功率')
    expect(wrapper.find('[data-testid="typical-range"]').text()).toBe('1.2 - 2.0')
  })

  it('data_source 为对象时 JSON 格式化', () => {
    const wrapper = mount(MetricDisplayTestable, {
      props: {
        metric: {
          value: 100,
          data_source: { sensor: 'temp-01', location: 'F1' }
        }
      }
    })
    const text = wrapper.find('[data-testid="data-source"]').text()
    expect(text).toContain('sensor')
    expect(text).toContain('temp-01')
  })

  it('显示描述信息', () => {
    const wrapper = mount(MetricDisplayTestable, {
      props: {
        metric: { value: 25.5, description: '当前温度' }
      }
    })
    expect(wrapper.find('[data-testid="description"]').text()).toBe('当前温度')
  })
})
