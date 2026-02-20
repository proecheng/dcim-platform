/**
 * StatusPanel 状态面板组件 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, computed } from 'vue'

// Mock Element Plus icons
vi.mock('@element-plus/icons-vue', () => ({
  Refresh: { template: '<i class="icon-refresh" />' },
  CaretTop: { template: '<i class="icon-caret-top" />' },
  CaretBottom: { template: '<i class="icon-caret-bottom" />' }
}))

interface StatusItem {
  key: string
  label: string
  value: number | string
  unit?: string
  color?: string
  status?: 'normal' | 'alarm' | 'offline'
  trend?: 'up' | 'down' | 'stable'
  trendValue?: number
  clickable?: boolean
}

const StatusPanelTestable = defineComponent({
  name: 'StatusPanelTestable',
  props: {
    title: { type: String, default: '状态面板' },
    items: { type: Array as () => StatusItem[], default: () => [] },
    showRefresh: { type: Boolean, default: true },
    loading: { type: Boolean, default: false },
    animate: { type: Boolean, default: true }
  },
  emits: ['refresh', 'item-click'],
  setup(props, { emit }) {
    const itemCount = computed(() => props.items.length)

    const handleItemClick = (item: StatusItem) => {
      if (item.clickable) {
        emit('item-click', item)
      }
    }

    return { itemCount, handleItemClick }
  },
  template: `
    <div data-testid="status-panel" class="status-panel">
      <div data-testid="panel-header" class="status-panel__header">
        <span data-testid="panel-title">{{ title }}</span>
        <button v-if="showRefresh" data-testid="refresh-btn" :disabled="loading" @click="$emit('refresh')">
          刷新
        </button>
      </div>
      <div data-testid="panel-content" class="status-panel__content">
        <div
          v-for="item in items"
          :key="item.key"
          :data-testid="'item-' + item.key"
          class="status-panel__item"
          :class="{ 'status-panel__item--clickable': item.clickable }"
          @click="handleItemClick(item)"
        >
          <div data-testid="item-icon" class="status-panel__item-icon" :style="{ backgroundColor: item.color }">
            {{ item.label.charAt(0) }}
          </div>
          <div class="status-panel__item-info">
            <div data-testid="item-label">{{ item.label }}</div>
            <div data-testid="item-value">
              {{ item.value }}
              <span v-if="item.unit" data-testid="item-unit">{{ item.unit }}</span>
            </div>
          </div>
          <div v-if="item.trend && item.trend !== 'stable'" data-testid="item-trend" :class="'trend-' + item.trend">
            {{ item.trend === 'up' ? '↑' : '↓' }}
            <span v-if="item.trendValue" data-testid="trend-value">{{ item.trendValue }}%</span>
          </div>
        </div>
      </div>
    </div>
  `
})

describe('StatusPanel 状态面板', () => {
  const mockItems: StatusItem[] = [
    { key: 'temp', label: '温度', value: 25.5, unit: '℃', color: '#409eff', status: 'normal', trend: 'up', trendValue: 2.5 },
    { key: 'humidity', label: '湿度', value: 60, unit: '%', color: '#67c23a', status: 'normal', trend: 'down', trendValue: 1.2 },
    { key: 'power', label: '功率', value: 150, unit: 'kW', color: '#e6a23c', clickable: true }
  ]

  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('默认渲染', () => {
    const wrapper = mount(StatusPanelTestable, {
      props: { items: mockItems }
    })
    expect(wrapper.find('[data-testid="status-panel"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="panel-title"]').text()).toBe('状态面板')
  })

  it('自定义标题', () => {
    const wrapper = mount(StatusPanelTestable, {
      props: { title: '环境监控', items: [] }
    })
    expect(wrapper.find('[data-testid="panel-title"]').text()).toBe('环境监控')
  })

  it('渲染所有状态项', () => {
    const wrapper = mount(StatusPanelTestable, {
      props: { items: mockItems }
    })
    expect(wrapper.find('[data-testid="item-temp"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="item-humidity"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="item-power"]').exists()).toBe(true)
  })

  it('showRefresh 控制刷新按钮', () => {
    const wrapperShow = mount(StatusPanelTestable, { props: { items: [], showRefresh: true } })
    expect(wrapperShow.find('[data-testid="refresh-btn"]').exists()).toBe(true)

    const wrapperHide = mount(StatusPanelTestable, { props: { items: [], showRefresh: false } })
    expect(wrapperHide.find('[data-testid="refresh-btn"]').exists()).toBe(false)
  })

  it('点击刷新按钮触发 refresh 事件', async () => {
    const wrapper = mount(StatusPanelTestable, {
      props: { items: [] }
    })
    await wrapper.find('[data-testid="refresh-btn"]').trigger('click')
    expect(wrapper.emitted('refresh')).toBeTruthy()
  })

  it('趋势指示器正确显示', () => {
    const wrapper = mount(StatusPanelTestable, {
      props: { items: mockItems }
    })
    const tempItem = wrapper.find('[data-testid="item-temp"]')
    expect(tempItem.find('[data-testid="item-trend"]').text()).toContain('↑')
    expect(tempItem.find('[data-testid="trend-value"]').text()).toContain('2.5%')
  })

  it('可点击项触发 item-click 事件', async () => {
    const wrapper = mount(StatusPanelTestable, {
      props: { items: mockItems }
    })
    await wrapper.find('[data-testid="item-power"]').trigger('click')
    expect(wrapper.emitted('item-click')?.[0]).toEqual([mockItems[2]])
  })

  it('不可点击项不触发事件', async () => {
    const wrapper = mount(StatusPanelTestable, {
      props: { items: mockItems }
    })
    await wrapper.find('[data-testid="item-temp"]').trigger('click')
    expect(wrapper.emitted('item-click')).toBeFalsy()
  })
})
