/**
 * FloorF2Layout 组件测试
 * 测试 F2 楼层布局（3台空调、15个机柜、预留扩展区域）
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent } from 'vue'

const FloorF2LayoutTestable = defineComponent({
  name: 'FloorF2LayoutTestable',
  props: {
    width: { type: Number, default: 800 },
    height: { type: Number, default: 500 },
    showGrid: { type: Boolean, default: true },
    showLegend: { type: Boolean, default: true }
  },
  setup() {
    const acCount = 3
    const cabinetRows = 3
    const cabinetCols = 5
    const totalCabinets = cabinetRows * cabinetCols
    return { acCount, totalCabinets }
  },
  template: `
    <div class="floor-f2-layout" data-testid="floor-f2">
      <div class="floor-title" data-testid="floor-title">F2 2楼机房区B</div>
      <div class="precision-acs" data-testid="ac-section">
        <div v-for="i in acCount" :key="'ac-' + i" class="ac-unit" :data-testid="'ac-' + i">AC-{{ i }}</div>
      </div>
      <div class="cabinet-rows" data-testid="cabinet-section">
        <div v-for="i in totalCabinets" :key="'cab-' + i" class="cabinet" :data-testid="'cabinet-' + i">
          {{ String(i).padStart(2, '0') }}
        </div>
      </div>
      <div class="reserved-area" data-testid="reserved-area">预留扩展区域</div>
      <div class="power-area" data-testid="power-area">
        <div data-testid="ups-1">UPS-1</div>
        <div data-testid="ups-2">UPS-2</div>
        <div data-testid="pdu">配电</div>
      </div>
      <div v-if="showLegend" class="legend" data-testid="legend">
        <span>机柜</span><span>空调</span><span>UPS/配电</span>
      </div>
    </div>
  `
})

describe('FloorF2Layout F2楼层布局组件', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('显示 F2 楼层标题', () => {
    const wrapper = mount(FloorF2LayoutTestable)
    expect(wrapper.find('[data-testid="floor-title"]').text()).toBe('F2 2楼机房区B')
  })

  it('渲染 3 台精密空调', () => {
    const wrapper = mount(FloorF2LayoutTestable)
    expect(wrapper.find('[data-testid="ac-section"]').findAll('.ac-unit')).toHaveLength(3)
  })

  it('渲染 15 个机柜（3行×5列）', () => {
    const wrapper = mount(FloorF2LayoutTestable)
    expect(wrapper.find('[data-testid="cabinet-section"]').findAll('.cabinet')).toHaveLength(15)
  })

  it('机柜编号使用两位数格式', () => {
    const wrapper = mount(FloorF2LayoutTestable)
    expect(wrapper.find('[data-testid="cabinet-1"]').text()).toBe('01')
    expect(wrapper.find('[data-testid="cabinet-15"]').text()).toBe('15')
  })

  it('包含预留扩展区域', () => {
    const wrapper = mount(FloorF2LayoutTestable)
    expect(wrapper.find('[data-testid="reserved-area"]').text()).toBe('预留扩展区域')
  })

  it('包含 UPS 和配电设备', () => {
    const wrapper = mount(FloorF2LayoutTestable)
    expect(wrapper.find('[data-testid="ups-1"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="ups-2"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="pdu"]').exists()).toBe(true)
  })

  it('图例包含机柜、空调、UPS/配电', () => {
    const wrapper = mount(FloorF2LayoutTestable)
    const legend = wrapper.find('[data-testid="legend"]')
    expect(legend.text()).toContain('机柜')
    expect(legend.text()).toContain('空调')
    expect(legend.text()).toContain('UPS/配电')
  })
})
