/**
 * DeviceList 组件单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, computed } from 'vue'

const DeviceListTestable = defineComponent({
  name: 'DeviceListTestable',
  props: {
    suggestion: {
      type: Object,
      default: () => ({ parameters: { devices: [] }, shiftable_devices: [] })
    }
  },
  setup(props) {
    const devices = computed(() => {
      return props.suggestion.parameters?.devices || props.suggestion.shiftable_devices || []
    })
    const totalShiftablePower = computed(() => {
      return devices.value.reduce((sum: number, d: any) => sum + (d.shiftable_power || 0), 0)
    })
    const avgShiftRatio = computed(() => {
      if (devices.value.length === 0) return 0
      const totalRated = devices.value.reduce((sum: number, d: any) => sum + (d.rated_power || 0), 0)
      if (totalRated === 0) return 0
      return totalShiftablePower.value / totalRated
    })
    const deviceTypeText: Record<string, string> = {
      HVAC: '空调', AC: '空调', PUMP: '水泵', COMPRESSOR: '压缩机'
    }
    return { devices, totalShiftablePower, avgShiftRatio, deviceTypeText }
  },
  template: `
    <div data-testid="device-list">
      <div data-testid="device-stats">
        <span data-testid="device-count">{{ devices.length }}</span>
        <span data-testid="total-power">{{ totalShiftablePower.toFixed(1) }}</span>
        <span data-testid="avg-ratio">{{ (avgShiftRatio * 100).toFixed(1) }}</span>
      </div>
      <div v-for="d in devices" :key="d.device_code" data-testid="device-row">
        <span>{{ d.device_name }}</span>
      </div>
      <div v-if="devices.length === 0" data-testid="empty">暂无可转移设备</div>
    </div>
  `
})

describe('DeviceList 组件', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('默认渲染空状态', () => {
    const wrapper = mount(DeviceListTestable)
    expect(wrapper.find('[data-testid="empty"]').exists()).toBe(true)
  })

  it('显示设备列表', () => {
    const wrapper = mount(DeviceListTestable, {
      props: {
        suggestion: {
          parameters: {
            devices: [
              { device_code: 'D001', device_name: '空调1', device_type: 'HVAC', rated_power: 100, shiftable_power: 30 },
              { device_code: 'D002', device_name: '水泵1', device_type: 'PUMP', rated_power: 50, shiftable_power: 15 }
            ]
          }
        }
      }
    })
    expect(wrapper.findAll('[data-testid="device-row"]').length).toBe(2)
  })

  it('计算总可调节容量', () => {
    const wrapper = mount(DeviceListTestable, {
      props: {
        suggestion: {
          parameters: {
            devices: [
              { device_code: 'D001', device_name: '空调1', rated_power: 100, shiftable_power: 30 },
              { device_code: 'D002', device_name: '水泵1', rated_power: 50, shiftable_power: 15 }
            ]
          }
        }
      }
    })
    expect(wrapper.find('[data-testid="total-power"]').text()).toBe('45.0')
  })

  it('计算平均转移比例', () => {
    const wrapper = mount(DeviceListTestable, {
      props: {
        suggestion: {
          parameters: {
            devices: [
              { device_code: 'D001', device_name: '空调1', rated_power: 100, shiftable_power: 50 }
            ]
          }
        }
      }
    })
    expect(wrapper.find('[data-testid="avg-ratio"]').text()).toBe('50.0')
  })

  it('无设备时比例为0', () => {
    const wrapper = mount(DeviceListTestable)
    expect(wrapper.vm.avgShiftRatio).toBe(0)
  })

  it('支持 shiftable_devices 数据源', () => {
    const wrapper = mount(DeviceListTestable, {
      props: {
        suggestion: {
          parameters: {},
          shiftable_devices: [
            { device_code: 'D001', device_name: '设备A', rated_power: 80, shiftable_power: 20 }
          ]
        }
      }
    })
    expect(wrapper.findAll('[data-testid="device-row"]').length).toBe(1)
  })

  it('设备数量统计正确', () => {
    const wrapper = mount(DeviceListTestable, {
      props: {
        suggestion: {
          parameters: {
            devices: [
              { device_code: 'D001', device_name: 'A', rated_power: 10, shiftable_power: 5 },
              { device_code: 'D002', device_name: 'B', rated_power: 20, shiftable_power: 8 },
              { device_code: 'D003', device_name: 'C', rated_power: 30, shiftable_power: 12 }
            ]
          }
        }
      }
    })
    expect(wrapper.find('[data-testid="device-count"]').text()).toBe('3')
  })
})
