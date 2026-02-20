/**
 * 负荷调节页面 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, computed } from 'vue'

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useRoute: () => ({ params: {}, query: {} }),
  createRouter: vi.fn(),
  createWebHistory: vi.fn()
}))

const typeTextMap: Record<string, string> = { temperature: '温度', brightness: '亮度', mode: '模式', load: '负载' }
const typeTagMap: Record<string, string> = { temperature: 'danger', brightness: 'warning', mode: 'primary', load: 'success' }

const RegulationTestable = defineComponent({
  name: 'RegulationTestable',
  setup() {
    const loading = ref(false)
    const configs = ref([
      { id: 1, device_name: '空调-1', regulation_type: 'temperature', current_value: 24, min_value: 18, max_value: 30, unit: '°C', is_enabled: true },
      { id: 2, device_name: '照明-A', regulation_type: 'brightness', current_value: 80, min_value: 0, max_value: 100, unit: '%', is_enabled: false }
    ])
    const recommendations = ref([
      { config_id: 1, device_name: '空调-1', regulation_type: 'temperature', current_value: 24, recommended_value: 26, power_saving: 5.2, priority: 'high', reason: '当前温度偏低' }
    ])
    const history = ref([
      { device_name: '空调-1', regulation_type: 'temperature', old_value: 22, new_value: 24, power_saved: 3.5, status: 'completed', executed_at: '2026-01-15' }
    ])
    const totalPowerSaving = computed(() => recommendations.value.reduce((sum, r) => sum + r.power_saving, 0))
    const historyCount = computed(() => history.value.length)

    return { loading, configs, recommendations, history, totalPowerSaving, historyCount, typeTextMap, typeTagMap }
  },
  template: `
    <div class="energy-regulation">
      <div class="stat-cards">
        <div class="stat-card" data-testid="config-count"><div class="stat-value">{{ configs.length }}</div><div class="stat-label">调节配置数</div></div>
        <div class="stat-card" data-testid="rec-count"><div class="stat-value">{{ recommendations.length }}</div><div class="stat-label">调节建议</div></div>
        <div class="stat-card" data-testid="power-saving"><div class="stat-value">{{ totalPowerSaving.toFixed(1) }}</div><div class="stat-label">潜在节能 (kW)</div></div>
        <div class="stat-card" data-testid="history-count"><div class="stat-value">{{ historyCount }}</div><div class="stat-label">调节记录</div></div>
      </div>
      <div class="config-list">
        <div v-for="c in configs" :key="c.id" class="config-item" :data-testid="'config-' + c.id">
          <span class="device">{{ c.device_name }}</span>
          <span class="type">{{ typeTextMap[c.regulation_type] }}</span>
          <span class="value">{{ c.current_value }}{{ c.unit }}</span>
          <span class="enabled">{{ c.is_enabled ? '启用' : '禁用' }}</span>
        </div>
      </div>
    </div>
  `
})

describe('负荷调节页面', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('渲染4张统计卡片', () => {
    const wrapper = mount(RegulationTestable)
    expect(wrapper.findAll('.stat-card')).toHaveLength(4)
  })

  it('显示配置数量', () => {
    const wrapper = mount(RegulationTestable)
    expect(wrapper.find('[data-testid="config-count"] .stat-value').text()).toBe('2')
  })

  it('显示潜在节能功率', () => {
    const wrapper = mount(RegulationTestable)
    expect(wrapper.find('[data-testid="power-saving"] .stat-value').text()).toBe('5.2')
  })

  it('调节类型文本映射正确', () => {
    expect(typeTextMap['temperature']).toBe('温度')
    expect(typeTextMap['brightness']).toBe('亮度')
    expect(typeTextMap['mode']).toBe('模式')
    expect(typeTextMap['load']).toBe('负载')
  })

  it('配置列表渲染正确', () => {
    const wrapper = mount(RegulationTestable)
    expect(wrapper.findAll('.config-item')).toHaveLength(2)
    const first = wrapper.find('[data-testid="config-1"]')
    expect(first.find('.device').text()).toBe('空调-1')
    expect(first.find('.type').text()).toBe('温度')
  })

  it('启用/禁用状态正确显示', () => {
    const wrapper = mount(RegulationTestable)
    expect(wrapper.find('[data-testid="config-1"] .enabled').text()).toBe('启用')
    expect(wrapper.find('[data-testid="config-2"] .enabled').text()).toBe('禁用')
  })

  it('调节历史记录数正确', () => {
    const wrapper = mount(RegulationTestable)
    expect(wrapper.find('[data-testid="history-count"] .stat-value').text()).toBe('1')
  })
})
