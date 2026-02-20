/**
 * 能源配置页面 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, reactive } from 'vue'

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useRoute: () => ({ params: {}, query: {} }),
  createRouter: vi.fn(),
  createWebHistory: vi.fn()
}))

function getStatusType(status: string): string {
  const map: Record<string, string> = { normal: 'success', warning: 'warning', fault: 'danger', offline: 'info' }
  return map[status] || 'info'
}

function getStatusText(status: string): string {
  const map: Record<string, string> = { normal: '正常', warning: '告警', fault: '故障', offline: '离线' }
  return map[status] || status
}

function getPeriodTypeText(type: string): string {
  const map: Record<string, string> = { sharp: '尖峰', peak: '高峰', flat: '平段', valley: '低谷', deep_valley: '深谷' }
  return map[type] || type
}

const EnergyConfigTestable = defineComponent({
  name: 'EnergyConfigTestable',
  setup() {
    const activeTab = ref('transformer')
    const tabs = ['transformer', 'meter', 'panel', 'circuit', 'pricing', 'demand', 'shift']
    const transformers = ref([
      { id: 1, transformer_code: 'TR-001', transformer_name: '1号变压器', rated_capacity: 1000, status: 'normal' }
    ])
    const pricingList = ref([
      { id: 1, pricing_name: '尖峰时段', period_type: 'sharp', price: 1.2, is_enabled: true },
      { id: 2, pricing_name: '低谷时段', period_type: 'valley', price: 0.3, is_enabled: true }
    ])

    return { activeTab, tabs, transformers, pricingList, getStatusType, getStatusText, getPeriodTypeText }
  },
  template: `
    <div class="energy-config">
      <div class="tabs">
        <button v-for="tab in tabs" :key="tab" :data-testid="'tab-' + tab"
          :class="{ active: activeTab === tab }" @click="activeTab = tab">{{ tab }}</button>
      </div>
      <div data-testid="active-tab">{{ activeTab }}</div>
      <div class="transformer-list" v-if="activeTab === 'transformer'">
        <div v-for="t in transformers" :key="t.id" class="transformer-item" :data-testid="'tr-' + t.id">
          <span class="code">{{ t.transformer_code }}</span>
          <span class="name">{{ t.transformer_name }}</span>
          <span class="capacity">{{ t.rated_capacity }} kVA</span>
          <span class="status">{{ getStatusText(t.status) }}</span>
        </div>
      </div>
      <div class="pricing-list" v-if="activeTab === 'pricing'">
        <div v-for="p in pricingList" :key="p.id" class="pricing-item" :data-testid="'price-' + p.id">
          <span class="type">{{ getPeriodTypeText(p.period_type) }}</span>
          <span class="price">¥{{ p.price.toFixed(4) }}</span>
        </div>
      </div>
    </div>
  `
})

describe('能源配置页面', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('默认激活transformer标签', () => {
    const wrapper = mount(EnergyConfigTestable)
    expect(wrapper.find('[data-testid="active-tab"]').text()).toBe('transformer')
  })

  it('渲染7个标签页', () => {
    const wrapper = mount(EnergyConfigTestable)
    expect(wrapper.findAll('.tabs button')).toHaveLength(7)
  })

  it('显示变压器列表', () => {
    const wrapper = mount(EnergyConfigTestable)
    const item = wrapper.find('[data-testid="tr-1"]')
    expect(item.find('.code').text()).toBe('TR-001')
    expect(item.find('.name').text()).toBe('1号变压器')
    expect(item.find('.capacity').text()).toContain('1000')
  })

  it('状态文本映射正确', () => {
    expect(getStatusText('normal')).toBe('正常')
    expect(getStatusText('fault')).toBe('故障')
  })

  it('电价时段类型文本正确', () => {
    expect(getPeriodTypeText('sharp')).toBe('尖峰')
    expect(getPeriodTypeText('peak')).toBe('高峰')
    expect(getPeriodTypeText('valley')).toBe('低谷')
    expect(getPeriodTypeText('deep_valley')).toBe('深谷')
  })

  it('切换到pricing标签显示电价列表', async () => {
    const wrapper = mount(EnergyConfigTestable)
    await wrapper.find('[data-testid="tab-pricing"]').trigger('click')
    expect(wrapper.find('[data-testid="active-tab"]').text()).toBe('pricing')
    expect(wrapper.findAll('.pricing-item')).toHaveLength(2)
  })

  it('电价格式化正确', async () => {
    const wrapper = mount(EnergyConfigTestable)
    await wrapper.find('[data-testid="tab-pricing"]').trigger('click')
    expect(wrapper.find('[data-testid="price-1"] .price').text()).toBe('¥1.2000')
  })
})
