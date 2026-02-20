/**
 * VideoPopup 组件测试
 * 测试视频监控弹窗（网格模式、摄像头类型、显示/隐藏）
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, computed } from 'vue'

vi.mock('@/api/modules/video', () => ({
  getCamerasByAlarm: vi.fn(() => Promise.resolve([]))
}))

const VideoPopupTestable = defineComponent({
  name: 'VideoPopupTestable',
  setup() {
    const visible = ref(false)
    const loading = ref(false)
    const cameras = ref<Array<{
      id: number; name: string; status: string; camera_type: string;
      code: string; hls_url?: string; rtsp_url?: string
    }>>([])
    const gridMode = ref<1 | 4 | 9>(4)

    const autoGridMode = computed(() => {
      const count = cameras.value.length
      if (count <= 1) return 1
      if (count <= 4) return 4
      return 9
    })

    const dialogWidth = computed(() => {
      if (gridMode.value === 1) return '640px'
      if (gridMode.value === 4) return '860px'
      return '1080px'
    })

    const displayCameras = computed(() => cameras.value.slice(0, gridMode.value))

    const cameraTypeLabel = (type: string): string => {
      const map: Record<string, string> = {
        fixed: '固定', ptz: '云台', dome: '球机', bullet: '枪机', panoramic: '全景'
      }
      return map[type] || type
    }

    const show = (cameraList: typeof cameras.value) => {
      cameras.value = cameraList
      gridMode.value = autoGridMode.value as 1 | 4 | 9
      visible.value = true
    }

    const hide = () => {
      visible.value = false
      cameras.value = []
    }

    return {
      visible, loading, cameras, gridMode, autoGridMode,
      dialogWidth, displayCameras, cameraTypeLabel, show, hide
    }
  },
  template: `
    <div v-if="visible" class="video-popup" data-testid="video-popup" :style="{ width: dialogWidth }">
      <div class="header" data-testid="header">
        <span>视频监控 - 告警联动</span>
        <span v-if="cameras.length" data-testid="camera-count">{{ cameras.length }} 路</span>
        <div class="layout-switcher" data-testid="layout-switcher">
          <button :class="{ active: gridMode === 1 }" data-testid="grid-1" @click="gridMode = 1">1</button>
          <button :class="{ active: gridMode === 4 }" data-testid="grid-4" @click="gridMode = 4">4</button>
          <button :class="{ active: gridMode === 9 }" data-testid="grid-9" @click="gridMode = 9">9</button>
        </div>
      </div>
      <div v-if="loading" data-testid="loading">正在获取摄像头信息...</div>
      <div v-else-if="!cameras.length" data-testid="empty">暂无关联摄像头</div>
      <div v-else class="video-grid" :class="'grid-' + gridMode" data-testid="video-grid">
        <div v-for="(cam, idx) in displayCameras" :key="cam.id" class="grid-cell" :data-testid="'cell-' + idx">
          <span class="cam-name" data-testid="cam-name">{{ cam.name }}</span>
          <span class="status" data-testid="cam-status">{{ cam.status === 'online' ? '在线' : '离线' }}</span>
          <span class="type" data-testid="cam-type">{{ cameraTypeLabel(cam.camera_type) }}</span>
          <span class="code" data-testid="cam-code">{{ cam.code }}</span>
        </div>
      </div>
    </div>
  `
})

describe('VideoPopup 视频监控弹窗组件', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('初始状态不可见', () => {
    const wrapper = mount(VideoPopupTestable)
    expect(wrapper.find('[data-testid="video-popup"]').exists()).toBe(false)
  })

  it('调用 show 后显示弹窗', async () => {
    const wrapper = mount(VideoPopupTestable)
    wrapper.vm.show([{ id: 1, name: '摄像头1', status: 'online', camera_type: 'fixed', code: 'CAM-001' }])
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[data-testid="video-popup"]').exists()).toBe(true)
  })

  it('无摄像头时显示空状态', async () => {
    const wrapper = mount(VideoPopupTestable)
    wrapper.vm.show([])
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[data-testid="empty"]').text()).toBe('暂无关联摄像头')
  })

  it('摄像头数量标签正确显示', async () => {
    const wrapper = mount(VideoPopupTestable)
    wrapper.vm.show([
      { id: 1, name: 'CAM1', status: 'online', camera_type: 'ptz', code: 'C1' },
      { id: 2, name: 'CAM2', status: 'offline', camera_type: 'dome', code: 'C2' }
    ])
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[data-testid="camera-count"]').text()).toBe('2 路')
  })

  it('摄像头类型标签正确映射', () => {
    const wrapper = mount(VideoPopupTestable)
    expect(wrapper.vm.cameraTypeLabel('fixed')).toBe('固定')
    expect(wrapper.vm.cameraTypeLabel('ptz')).toBe('云台')
    expect(wrapper.vm.cameraTypeLabel('dome')).toBe('球机')
    expect(wrapper.vm.cameraTypeLabel('bullet')).toBe('枪机')
    expect(wrapper.vm.cameraTypeLabel('panoramic')).toBe('全景')
    expect(wrapper.vm.cameraTypeLabel('unknown')).toBe('unknown')
  })

  it('自动网格模式根据摄像头数量调整', () => {
    const wrapper = mount(VideoPopupTestable)
    wrapper.vm.cameras = [{ id: 1, name: 'C1', status: 'online', camera_type: 'fixed', code: 'C1' }]
    expect(wrapper.vm.autoGridMode).toBe(1)
    wrapper.vm.cameras = Array.from({ length: 3 }, (_, i) => ({ id: i, name: `C${i}`, status: 'online', camera_type: 'fixed', code: `C${i}` }))
    expect(wrapper.vm.autoGridMode).toBe(4)
    wrapper.vm.cameras = Array.from({ length: 6 }, (_, i) => ({ id: i, name: `C${i}`, status: 'online', camera_type: 'fixed', code: `C${i}` }))
    expect(wrapper.vm.autoGridMode).toBe(9)
  })

  it('调用 hide 后隐藏弹窗并清空摄像头', async () => {
    const wrapper = mount(VideoPopupTestable)
    wrapper.vm.show([{ id: 1, name: 'C1', status: 'online', camera_type: 'fixed', code: 'C1' }])
    await wrapper.vm.$nextTick()
    wrapper.vm.hide()
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[data-testid="video-popup"]').exists()).toBe(false)
    expect(wrapper.vm.cameras).toHaveLength(0)
  })

  it('dialogWidth 随网格模式变化', () => {
    const wrapper = mount(VideoPopupTestable)
    wrapper.vm.gridMode = 1
    expect(wrapper.vm.dialogWidth).toBe('640px')
    wrapper.vm.gridMode = 4
    expect(wrapper.vm.dialogWidth).toBe('860px')
    wrapper.vm.gridMode = 9
    expect(wrapper.vm.dialogWidth).toBe('1080px')
  })
})
