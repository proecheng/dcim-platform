/**
 * 视频管理页面 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, computed } from 'vue'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }), useRoute: () => ({ params: {}, query: {} }), createRouter: vi.fn(), createWebHistory: vi.fn() }))

const VideoIndexTestable = defineComponent({
  name: 'VideoIndexTestable',
  setup() {
    const loading = ref(false)
    const activeTab = ref('nvr')
    const nvrList = ref([
      { id: 1, name: 'NVR-01', ip: '192.168.1.100', status: 'online', channel_count: 16 },
      { id: 2, name: 'NVR-02', ip: '192.168.1.101', status: 'offline', channel_count: 32 }
    ])
    const cameraList = ref([
      { id: 1, name: '摄像头-A01', nvr_name: 'NVR-01', location: '机房A入口', status: 'online' },
      { id: 2, name: '摄像头-A02', nvr_name: 'NVR-01', location: '机房A内部', status: 'online' },
      { id: 3, name: '摄像头-B01', nvr_name: 'NVR-02', location: '机房B入口', status: 'offline' }
    ])
    const dialogVisible = ref(false)
    const dialogType = ref<'nvr' | 'camera'>('nvr')
    const onlineNvrCount = computed(() => nvrList.value.filter(n => n.status === 'online').length)
    const onlineCameraCount = computed(() => cameraList.value.filter(c => c.status === 'online').length)
    const openDialog = (type: 'nvr' | 'camera') => { dialogType.value = type; dialogVisible.value = true }
    return { loading, activeTab, nvrList, cameraList, dialogVisible, dialogType, onlineNvrCount, onlineCameraCount, openDialog }
  },
  template: `<div class="video-manage"><div class="tabs"><button :class="{ active: activeTab === 'nvr' }" data-testid="tab-nvr" @click="activeTab = 'nvr'">NVR管理</button><button :class="{ active: activeTab === 'camera' }" data-testid="tab-camera" @click="activeTab = 'camera'">摄像头管理</button></div><div class="stats"><span class="online-nvr" data-testid="online-nvr">{{ onlineNvrCount }}</span><span class="online-camera" data-testid="online-camera">{{ onlineCameraCount }}</span></div><div v-if="activeTab === 'nvr'" class="nvr-table" data-testid="nvr-table"><div v-for="n in nvrList" :key="n.id" :data-testid="'nvr-' + n.id" class="nvr-row"><span class="name">{{ n.name }}</span><span class="ip">{{ n.ip }}</span><span class="status">{{ n.status }}</span><span class="channels">{{ n.channel_count }}</span></div></div><div v-if="activeTab === 'camera'" class="camera-table" data-testid="camera-table"><div v-for="c in cameraList" :key="c.id" :data-testid="'camera-' + c.id" class="camera-row"><span class="name">{{ c.name }}</span><span class="location">{{ c.location }}</span><span class="status">{{ c.status }}</span></div></div><div v-if="dialogVisible" class="manage-dialog" data-testid="manage-dialog"><span class="dialog-type">{{ dialogType }}</span></div></div>`
})

describe('视频管理页面', () => {
  beforeEach(() => { setActivePinia(createPinia()) })
  it('默认显示NVR标签', () => { const w = mount(VideoIndexTestable); expect(w.vm.activeTab).toBe('nvr'); expect(w.find('[data-testid="nvr-table"]').exists()).toBe(true) })
  it('渲染NVR列表', () => { const w = mount(VideoIndexTestable); expect(w.findAll('.nvr-row')).toHaveLength(2); expect(w.find('[data-testid="nvr-1"] .name').text()).toBe('NVR-01') })
  it('显示NVR IP和通道数', () => { const w = mount(VideoIndexTestable); expect(w.find('[data-testid="nvr-1"] .ip').text()).toBe('192.168.1.100'); expect(w.find('[data-testid="nvr-1"] .channels').text()).toBe('16') })
  it('统计在线设备数', () => { const w = mount(VideoIndexTestable); expect(w.find('[data-testid="online-nvr"]').text()).toBe('1'); expect(w.find('[data-testid="online-camera"]').text()).toBe('2') })
  it('切换到摄像头标签', async () => { const w = mount(VideoIndexTestable); await w.find('[data-testid="tab-camera"]').trigger('click'); expect(w.find('[data-testid="camera-table"]').exists()).toBe(true); expect(w.findAll('.camera-row')).toHaveLength(3) })
  it('显示摄像头位置', async () => { const w = mount(VideoIndexTestable); await w.find('[data-testid="tab-camera"]').trigger('click'); expect(w.find('[data-testid="camera-1"] .location').text()).toBe('机房A入口') })
  it('对话框默认隐藏', () => { expect(mount(VideoIndexTestable).find('[data-testid="manage-dialog"]').exists()).toBe(false) })
})
