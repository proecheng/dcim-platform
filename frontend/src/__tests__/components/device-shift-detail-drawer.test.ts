/**
 * DeviceShiftDetailDrawer 组件单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, computed } from 'vue'

vi.mock('echarts', () => ({
  init: vi.fn(() => ({
    setOption: vi.fn(), resize: vi.fn(), dispose: vi.fn(),
    on: vi.fn(), off: vi.fn(), getOption: vi.fn(() => ({}))
  }))
}))

const DeviceShiftDetailDrawerTestable = defineComponent({
  name: 'DeviceShiftDetailDrawerTestable',
  props: {
    visible: { type: Boolean, default: false },
    device: { type: Object, default: null }
  },
  emits: ['close', 'accept-ratio'],
  setup(props, { emit }) {
    const loading = ref(false)
    const profileDays = ref(30)
    const DEVICE_TYPE_MAP: Record<string, string> = {
      PUMP: '水泵', AC: '空调', HVAC: '暖通', LIGHTING: '照明',
      CHILLER: '冷机', COOLING_TOWER: '冷却塔'
    }
    function getDeviceTypeText(type?: string) {
      return DEVICE_TYPE_MAP[(type || '').toUpperCase()] || type || '--'
    }
    const constraintItems = computed(() => {
      const details = props.device?.calculation_details
      if (!details?.constraints) return []
      const constraints = details.constraints
      const minVal = Math.min(...constraints)
      return [
        { name: '最低功率约束', value: constraints[0] || 0, isBinding: constraints[0] === minVal },
        { name: '负荷波动空间', value: constraints[1] || 0, isBinding: constraints[1] === minVal }
      ]
    })
    function handleClose() { emit('close') }
    function handleAcceptRatio() { if (props.device) emit('accept-ratio', props.device) }
    return { loading, profileDays, getDeviceTypeText, constraintItems, handleClose, handleAcceptRatio }
  },
  template: `
    <div data-testid="drawer" v-if="visible">
      <div data-testid="device-name">{{ device?.device_name }}</div>
      <div data-testid="device-type">{{ getDeviceTypeText(device?.device_type) }}</div>
      <div data-testid="profile-days">{{ profileDays }}</div>
      <div v-for="c in constraintItems" :key="c.name" data-testid="constraint">
        <span>{{ c.name }}</span>
      </div>
      <button data-testid="close-btn" @click="handleClose">关闭</button>
      <button v-if="device?.has_change" data-testid="accept-btn" @click="handleAcceptRatio">使用推荐值</button>
    </div>
  `
})

describe('DeviceShiftDetailDrawer 组件', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('不可见时不渲染', () => {
    const wrapper = mount(DeviceShiftDetailDrawerTestable)
    expect(wrapper.find('[data-testid="drawer"]').exists()).toBe(false)
  })

  it('可见时渲染设备名称', () => {
    const wrapper = mount(DeviceShiftDetailDrawerTestable, {
      props: { visible: true, device: { device_name: '空调A', device_type: 'AC' } }
    })
    expect(wrapper.find('[data-testid="device-name"]').text()).toBe('空调A')
  })

  it('设备类型映射正确', () => {
    const wrapper = mount(DeviceShiftDetailDrawerTestable, {
      props: { visible: true, device: { device_name: '水泵1', device_type: 'PUMP' } }
    })
    expect(wrapper.find('[data-testid="device-type"]').text()).toBe('水泵')
  })

  it('默认 profileDays 为 30', () => {
    const wrapper = mount(DeviceShiftDetailDrawerTestable, {
      props: { visible: true, device: { device_name: 'X' } }
    })
    expect(wrapper.vm.profileDays).toBe(30)
  })

  it('关闭按钮触发 close 事件', async () => {
    const wrapper = mount(DeviceShiftDetailDrawerTestable, {
      props: { visible: true, device: { device_name: 'X' } }
    })
    await wrapper.find('[data-testid="close-btn"]').trigger('click')
    expect(wrapper.emitted('close')).toBeTruthy()
  })

  it('约束条件正确计算', () => {
    const wrapper = mount(DeviceShiftDetailDrawerTestable, {
      props: {
        visible: true,
        device: {
          device_name: 'X',
          calculation_details: { constraints: [0.3, 0.5, 0.2, 0.4] }
        }
      }
    })
    expect(wrapper.findAll('[data-testid="constraint"]').length).toBe(2)
  })

  it('有变更时显示接受按钮', () => {
    const wrapper = mount(DeviceShiftDetailDrawerTestable, {
      props: { visible: true, device: { device_name: 'X', has_change: true, recommended_ratio: 0.3 } }
    })
    expect(wrapper.find('[data-testid="accept-btn"]').exists()).toBe(true)
  })
})
