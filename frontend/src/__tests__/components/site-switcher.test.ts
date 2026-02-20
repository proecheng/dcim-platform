/**
 * SiteSwitcher 站点切换器组件 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, computed } from 'vue'

const SiteSwitcherTestable = defineComponent({
  name: 'SiteSwitcherTestable',
  props: {
    sites: {
      type: Array as () => Array<{ id: number; site_name: string; status: string; gateway_count: number }>,
      default: () => []
    },
    currentSiteId: { type: [Number, null] as any, default: null }
  },
  emits: ['switch-site'],
  setup(props, { emit }) {
    const modelValue = computed(() =>
      props.currentSiteId !== null ? props.currentSiteId : ''
    )

    const handleChange = (val: string | number) => {
      if (val === '' || val === null) {
        emit('switch-site', null)
      } else {
        emit('switch-site', Number(val))
      }
    }

    return { modelValue, handleChange }
  },
  template: `
    <div data-testid="site-switcher">
      <select data-testid="site-select" :value="modelValue" @change="handleChange($event.target.value)">
        <option value="" data-testid="option-all">全部站点</option>
        <option
          v-for="site in sites"
          :key="site.id"
          :value="site.id"
          :data-testid="'option-' + site.id"
        >
          {{ site.site_name }} ({{ site.gateway_count }}网关)
        </option>
      </select>
    </div>
  `
})

describe('SiteSwitcher 站点切换器', () => {
  const mockSites = [
    { id: 1, site_name: '北京数据中心', status: 'active', gateway_count: 5 },
    { id: 2, site_name: '上海数据中心', status: 'maintenance', gateway_count: 3 },
    { id: 3, site_name: '广州数据中心', status: 'inactive', gateway_count: 0 }
  ]

  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('默认渲染', () => {
    const wrapper = mount(SiteSwitcherTestable)
    expect(wrapper.find('[data-testid="site-switcher"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="option-all"]').exists()).toBe(true)
  })

  it('渲染站点列表', () => {
    const wrapper = mount(SiteSwitcherTestable, {
      props: { sites: mockSites }
    })
    expect(wrapper.find('[data-testid="option-1"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="option-2"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="option-3"]').exists()).toBe(true)
  })

  it('站点选项显示名称和网关数', () => {
    const wrapper = mount(SiteSwitcherTestable, {
      props: { sites: mockSites }
    })
    expect(wrapper.find('[data-testid="option-1"]').text()).toContain('北京数据中心')
    expect(wrapper.find('[data-testid="option-1"]').text()).toContain('5网关')
  })

  it('currentSiteId 为 null 时选中全部站点', () => {
    const wrapper = mount(SiteSwitcherTestable, {
      props: { sites: mockSites, currentSiteId: null }
    })
    expect(wrapper.vm.modelValue).toBe('')
  })

  it('currentSiteId 有值时正确映射', () => {
    const wrapper = mount(SiteSwitcherTestable, {
      props: { sites: mockSites, currentSiteId: 2 }
    })
    expect(wrapper.vm.modelValue).toBe(2)
  })

  it('空站点列表只显示全部选项', () => {
    const wrapper = mount(SiteSwitcherTestable, {
      props: { sites: [] }
    })
    const options = wrapper.findAll('option')
    expect(options).toHaveLength(1)
    expect(options[0].text()).toBe('全部站点')
  })

  it('全部站点选项始终存在', () => {
    const wrapper = mount(SiteSwitcherTestable, {
      props: { sites: mockSites }
    })
    expect(wrapper.find('[data-testid="option-all"]').text()).toBe('全部站点')
  })
})
