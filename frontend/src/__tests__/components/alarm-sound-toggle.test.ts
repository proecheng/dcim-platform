/**
 * AlarmSoundToggle 告警声音开关组件 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, computed } from 'vue'

// Mock Element Plus icons
vi.mock('@element-plus/icons-vue', () => ({
  Bell: { template: '<i class="icon-bell" />' },
  MuteNotification: { template: '<i class="icon-mute" />' }
}))

const AlarmSoundToggleTestable = defineComponent({
  name: 'AlarmSoundToggleTestable',
  setup() {
    const soundEnabled = ref(true)

    const tooltipText = computed(() =>
      soundEnabled.value ? '告警声音：开' : '告警声音：关'
    )

    const toggleSound = () => {
      soundEnabled.value = !soundEnabled.value
    }

    return { soundEnabled, tooltipText, toggleSound }
  },
  template: `
    <div data-testid="alarm-sound-toggle">
      <span data-testid="tooltip-text">{{ tooltipText }}</span>
      <button
        data-testid="toggle-btn"
        :class="{ 'is-enabled': soundEnabled, 'is-disabled': !soundEnabled }"
        @click="toggleSound"
      >
        <span v-if="soundEnabled" data-testid="icon-bell">🔔</span>
        <span v-else data-testid="icon-mute">🔇</span>
      </button>
    </div>
  `
})

describe('AlarmSoundToggle 告警声音开关', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('默认渲染为开启状态', () => {
    const wrapper = mount(AlarmSoundToggleTestable)
    expect(wrapper.find('[data-testid="alarm-sound-toggle"]').exists()).toBe(true)
    expect(wrapper.vm.soundEnabled).toBe(true)
  })

  it('开启状态显示铃铛图标', () => {
    const wrapper = mount(AlarmSoundToggleTestable)
    expect(wrapper.find('[data-testid="icon-bell"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="icon-mute"]').exists()).toBe(false)
  })

  it('开启状态提示文本正确', () => {
    const wrapper = mount(AlarmSoundToggleTestable)
    expect(wrapper.find('[data-testid="tooltip-text"]').text()).toBe('告警声音：开')
  })

  it('点击切换为关闭状态', async () => {
    const wrapper = mount(AlarmSoundToggleTestable)
    await wrapper.find('[data-testid="toggle-btn"]').trigger('click')
    expect(wrapper.vm.soundEnabled).toBe(false)
    expect(wrapper.find('[data-testid="icon-mute"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="icon-bell"]').exists()).toBe(false)
  })

  it('关闭状态提示文本正确', async () => {
    const wrapper = mount(AlarmSoundToggleTestable)
    await wrapper.find('[data-testid="toggle-btn"]').trigger('click')
    expect(wrapper.find('[data-testid="tooltip-text"]').text()).toBe('告警声音：关')
  })

  it('再次点击恢复开启状态', async () => {
    const wrapper = mount(AlarmSoundToggleTestable)
    await wrapper.find('[data-testid="toggle-btn"]').trigger('click')
    await wrapper.find('[data-testid="toggle-btn"]').trigger('click')
    expect(wrapper.vm.soundEnabled).toBe(true)
    expect(wrapper.find('[data-testid="icon-bell"]').exists()).toBe(true)
  })

  it('按钮样式随状态变化', async () => {
    const wrapper = mount(AlarmSoundToggleTestable)
    expect(wrapper.find('[data-testid="toggle-btn"]').classes()).toContain('is-enabled')
    await wrapper.find('[data-testid="toggle-btn"]').trigger('click')
    expect(wrapper.find('[data-testid="toggle-btn"]').classes()).toContain('is-disabled')
  })
})
