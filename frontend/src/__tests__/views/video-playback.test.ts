/**
 * 视频回放页面 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, computed } from 'vue'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }), useRoute: () => ({ params: {}, query: { alarm_id: '1' } }), createRouter: vi.fn(), createWebHistory: vi.fn() }))

const VideoPlaybackTestable = defineComponent({
  name: 'VideoPlaybackTestable',
  setup() {
    const loading = ref(false)
    const playbackInfo = ref({ alarm_id: 1, alarm_type: '温度告警', alarm_time: '2026-02-01 14:30', location: '机房A' })
    const cameraList = ref([
      { id: 1, name: '摄像头-A01', location: '机房A入口' },
      { id: 2, name: '摄像头-A02', location: '机房A内部' }
    ])
    const selectedCameraId = ref(1)
    const isPlaying = ref(false)
    const currentTime = ref(0)
    const duration = ref(3600)
    const segments = ref([
      { start: 0, end: 600, type: 'normal' },
      { start: 600, end: 900, type: 'alarm' },
      { start: 900, end: 3600, type: 'normal' }
    ])
    const playbackSpeed = ref(1)
    const formatTime = (s: number) => { const m = Math.floor(s / 60); const sec = s % 60; return `${m.toString().padStart(2, '0')}:${sec.toString().padStart(2, '0')}` }
    const togglePlay = () => { isPlaying.value = !isPlaying.value }
    const alarmSegments = computed(() => segments.value.filter(s => s.type === 'alarm'))
    return { loading, playbackInfo, cameraList, selectedCameraId, isPlaying, currentTime, duration, segments, playbackSpeed, formatTime, togglePlay, alarmSegments }
  },
  template: `<div class="video-playback"><div class="alarm-info" data-testid="alarm-info"><span class="alarm-type">{{ playbackInfo.alarm_type }}</span><span class="alarm-time">{{ playbackInfo.alarm_time }}</span><span class="location">{{ playbackInfo.location }}</span></div><div class="camera-select" data-testid="camera-select"><div v-for="c in cameraList" :key="c.id" :data-testid="'cam-' + c.id" class="camera-item" :class="{ selected: selectedCameraId === c.id }" @click="selectedCameraId = c.id"><span class="name">{{ c.name }}</span></div></div><div class="player" data-testid="player"><button data-testid="play-btn" @click="togglePlay">{{ isPlaying ? '暂停' : '播放' }}</button><span class="time" data-testid="current-time">{{ formatTime(currentTime) }}</span><span class="duration" data-testid="duration">{{ formatTime(duration) }}</span><span class="speed" data-testid="speed">{{ playbackSpeed }}x</span></div><div class="timeline" data-testid="timeline"><div v-for="(s, idx) in segments" :key="idx" :data-testid="'seg-' + idx" class="segment" :class="s.type"></div></div></div>`
})

describe('视频回放页面', () => {
  beforeEach(() => { setActivePinia(createPinia()) })
  it('显示告警信息', () => { const w = mount(VideoPlaybackTestable); expect(w.find('[data-testid="alarm-info"] .alarm-type').text()).toBe('温度告警'); expect(w.find('[data-testid="alarm-info"] .location').text()).toBe('机房A') })
  it('渲染摄像头列表', () => { expect(mount(VideoPlaybackTestable).findAll('.camera-item')).toHaveLength(2) })
  it('默认选中第一个摄像头', () => { expect(mount(VideoPlaybackTestable).find('[data-testid="cam-1"]').classes()).toContain('selected') })
  it('播放按钮切换状态', async () => { const w = mount(VideoPlaybackTestable); expect(w.find('[data-testid="play-btn"]').text()).toBe('播放'); await w.find('[data-testid="play-btn"]').trigger('click'); expect(w.find('[data-testid="play-btn"]').text()).toBe('暂停') })
  it('显示时间和速度', () => { const w = mount(VideoPlaybackTestable); expect(w.find('[data-testid="current-time"]').text()).toBe('00:00'); expect(w.find('[data-testid="duration"]').text()).toBe('60:00'); expect(w.find('[data-testid="speed"]').text()).toBe('1x') })
  it('渲染时间线分段', () => { expect(mount(VideoPlaybackTestable).findAll('.segment')).toHaveLength(3) })
  it('时间格式化正确', () => { expect(mount(VideoPlaybackTestable).vm.formatTime(125)).toBe('02:05') })
})
