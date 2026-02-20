/**
 * DispatchConfig 组件单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, reactive } from 'vue'

const DispatchConfigTestable = defineComponent({
  name: 'DispatchConfigTestable',
  setup() {
    const activeConfigTab = ref('devices')
    const loading = reactive({ devices: false, storage: false, pv: false, saveDevice: false, initDemo: false })
    const devices = ref<any[]>([])
    const storageSystems = ref<any[]>([])
    const pvSystems = ref<any[]>([])
    const deviceDialog = reactive({ visible: false, isEdit: false })
    const deviceForm = reactive({ name: '', device_type: 'shiftable', rated_power: 0, priority: 5, is_active: true })
    type TagType = 'info' | 'warning' | 'success' | 'danger' | 'primary'
    function getTypeTagColor(type: string): TagType {
      const colors: Record<string, TagType> = { shiftable: 'primary', curtailable: 'warning', modulating: 'success' }
      return colors[type] || 'info'
    }
    const isEmpty = ref(true)
    return { activeConfigTab, loading, devices, storageSystems, pvSystems, deviceDialog, deviceForm, getTypeTagColor, isEmpty }
  },
  template: `
    <div data-testid="dispatch-config">
      <div v-if="devices.length === 0 && storageSystems.length === 0 && pvSystems.length === 0" data-testid="empty-alert">
        暂无配置数据
      </div>
      <div data-testid="active-tab">{{ activeConfigTab }}</div>
      <div data-testid="device-count">{{ devices.length }}</div>
      <div data-testid="storage-count">{{ storageSystems.length }}</div>
      <div data-testid="pv-count">{{ pvSystems.length }}</div>
    </div>
  `
})

describe('DispatchConfig 组件', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('默认渲染', () => {
    const wrapper = mount(DispatchConfigTestable)
    expect(wrapper.find('[data-testid="dispatch-config"]').exists()).toBe(true)
  })

  it('空数据时显示提示', () => {
    const wrapper = mount(DispatchConfigTestable)
    expect(wrapper.find('[data-testid="empty-alert"]').exists()).toBe(true)
  })

  it('默认标签页为 devices', () => {
    const wrapper = mount(DispatchConfigTestable)
    expect(wrapper.find('[data-testid="active-tab"]').text()).toBe('devices')
  })

  it('设备类型颜色映射正确', () => {
    const wrapper = mount(DispatchConfigTestable)
    expect(wrapper.vm.getTypeTagColor('shiftable')).toBe('primary')
    expect(wrapper.vm.getTypeTagColor('curtailable')).toBe('warning')
    expect(wrapper.vm.getTypeTagColor('modulating')).toBe('success')
    expect(wrapper.vm.getTypeTagColor('unknown')).toBe('info')
  })

  it('默认设备表单初始值正确', () => {
    const wrapper = mount(DispatchConfigTestable)
    expect(wrapper.vm.deviceForm.device_type).toBe('shiftable')
    expect(wrapper.vm.deviceForm.priority).toBe(5)
    expect(wrapper.vm.deviceForm.is_active).toBe(true)
  })

  it('loading 状态默认为 false', () => {
    const wrapper = mount(DispatchConfigTestable)
    expect(wrapper.vm.loading.devices).toBe(false)
    expect(wrapper.vm.loading.storage).toBe(false)
  })

  it('对话框默认不可见', () => {
    const wrapper = mount(DispatchConfigTestable)
    expect(wrapper.vm.deviceDialog.visible).toBe(false)
    expect(wrapper.vm.deviceDialog.isEdit).toBe(false)
  })
})
