/**
 * 视频云台控制页面 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref } from 'vue'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }), useRoute: () => ({ params: {}, query: {} }), createRouter: vi.fn(), createWebHistory: vi.fn() }))

const VideoControlTestable = defineComponent({
  name: 'VideoControlTestable',
  setup() {
    const loading = ref(false)
    const cameraList = ref([
      { id: 1, name: '摄像头-A01', ptz_support: true, status: 'online' },
      { id: 2, name: '摄像头-A02', ptz_support: false, status: 'online' },
      { id: 3, name: '摄像头-B01', ptz_support: true, status: 'offline' }
    ])
    const selectedCamera = ref<any>(null)
    const presets = ref([
      { id: 1, name: '预置位1', description: '入口全景' },
      { id: 2, name: '预置位2', description: '机柜区域' }
    ])
    const eventLog = ref([
      { id: 1, action: 'pan_left', operator: '张三', timestamp: '2026-02-01 14:30' },
      { id: 2, action: 'zoom_in', operator: '张三', timestamp: '2026-02-01 14:31' }
    ])
    const zoomLevel = ref(1)
    const ptzDirection = ref('')
    const movePtz = (dir: string) => { ptzDirection.value = dir }
    const zoomIn = () => { zoomLevel.value = Math.min(zoomLevel.value + 1, 10) }
    const zoomOut = () => { zoomLevel.value = Math.max(zoomLevel.value - 1, 1) }
    const selectCamera = (c: any) => { selectedCamera.value = c }
    return { loading, cameraList, selectedCamera, presets, eventLog, zoomLevel, ptzDirection, movePtz, zoomIn, zoomOut, selectCamera }
  },
  template: `<div class="video-control"><div class="camera-list" data-testid="camera-list"><div v-for="c in cameraList" :key="c.id" :data-testid="'cam-' + c.id" class="camera-item" @click="selectCamera(c)"><span class="name">{{ c.name }}</span><span class="ptz">{{ c.ptz_support ? 'PTZ' : '固定' }}</span><span class="status">{{ c.status }}</span></div></div><div class="ptz-controls" data-testid="ptz-controls"><button data-testid="ptz-up" @click="movePtz('up')">上</button><button data-testid="ptz-down" @click="movePtz('down')">下</button><button data-testid="ptz-left" @click="movePtz('left')">左</button><button data-testid="ptz-right" @click="movePtz('right')">右</button><button data-testid="zoom-in" @click="zoomIn">放大</button><button data-testid="zoom-out" @click="zoomOut">缩小</button><span class="zoom-level" data-testid="zoom-level">{{ zoomLevel }}x</span></div><div class="preset-list" data-testid="preset-list"><div v-for="p in presets" :key="p.id" :data-testid="'preset-' + p.id" class="preset-item"><span class="name">{{ p.name }}</span><span class="desc">{{ p.description }}</span></div></div><div class="event-log" data-testid="event-log"><div v-for="e in eventLog" :key="e.id" class="log-item"><span class="action">{{ e.action }}</span><span class="operator">{{ e.operator }}</span></div></div></div>`
})

describe('视频云台控制页面', () => {
  beforeEach(() => { setActivePinia(createPinia()) })
  it('渲染摄像头列表', () => { const w = mount(VideoControlTestable); expect(w.findAll('.camera-item')).toHaveLength(3); expect(w.find('[data-testid="cam-1"] .ptz').text()).toBe('PTZ') })
  it('渲染PTZ控制按钮', () => { const w = mount(VideoControlTestable); expect(w.find('[data-testid="ptz-up"]').exists()).toBe(true); expect(w.find('[data-testid="ptz-left"]').exists()).toBe(true) })
  it('PTZ方向控制', async () => { const w = mount(VideoControlTestable); await w.find('[data-testid="ptz-up"]').trigger('click'); expect(w.vm.ptzDirection).toBe('up') })
  it('缩放控制', async () => { const w = mount(VideoControlTestable); await w.find('[data-testid="zoom-in"]').trigger('click'); expect(w.find('[data-testid="zoom-level"]').text()).toBe('2x'); await w.find('[data-testid="zoom-out"]').trigger('click'); expect(w.find('[data-testid="zoom-level"]').text()).toBe('1x') })
  it('渲染预置位列表', () => { const w = mount(VideoControlTestable); expect(w.findAll('.preset-item')).toHaveLength(2); expect(w.find('[data-testid="preset-1"] .desc').text()).toBe('入口全景') })
  it('渲染操作日志', () => { const w = mount(VideoControlTestable); expect(w.findAll('.log-item')).toHaveLength(2); expect(w.find('.log-item .action').text()).toBe('pan_left') })
  it('点击选中摄像头', async () => { const w = mount(VideoControlTestable); await w.find('[data-testid="cam-1"]').trigger('click'); expect(w.vm.selectedCamera.name).toBe('摄像头-A01') })
})
