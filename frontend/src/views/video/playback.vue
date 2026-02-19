<template>
  <div class="playback-page">
    <!-- 顶部: 告警信息卡 -->
    <el-card shadow="hover" class="alarm-bar">
      <div class="alarm-bar__inner">
        <template v-if="playbackInfo">
          <el-tag
            :type="levelTagType[playbackInfo.alarm_info.alarm_level] ?? 'info'"
            effect="dark"
            size="large"
            class="alarm-level-tag"
          >
            {{ levelLabel[playbackInfo.alarm_info.alarm_level] ?? playbackInfo.alarm_info.alarm_level }}
          </el-tag>
          <span class="alarm-msg">{{ playbackInfo.alarm_info.alarm_message }}</span>
          <span class="alarm-time">
            <el-icon><Timer /></el-icon>
            {{ playbackInfo.alarm_info.alarm_time ?? '未知时间' }}
          </span>
        </template>
        <span v-else class="alarm-placeholder">请输入告警 ID 查询回放信息</span>

        <div class="alarm-search">
          <el-input
            v-model="manualAlarmId"
            placeholder="告警 ID"
            clearable
            style="width: 140px"
            @keyup.enter="handleSearch"
          />
          <el-button :icon="Search" type="primary" @click="handleSearch">查询</el-button>
        </div>
      </div>
    </el-card>

    <!-- 三栏主体 -->
    <div class="main-panels">
      <!-- 左: 摄像头列表 -->
      <div class="panel panel--cameras">
        <div class="panel__title">
          <el-icon><VideoCamera /></el-icon>
          关联摄像头
        </div>
        <div v-if="!playbackInfo" class="panel__empty">
          <el-empty description="暂无数据" :image-size="64" />
        </div>
        <div v-else class="camera-list">
          <div
            v-for="cam in playbackInfo.cameras"
            :key="cam.id"
            class="camera-card"
            :class="{ 'camera-card--active': selectedCameraId === cam.id }"
            @click="selectCamera(cam)"
          >
            <div class="camera-card__name">{{ cam.name }}</div>
            <div class="camera-card__code">{{ cam.code }}</div>
            <div class="camera-card__loc">{{ cam.location_description ?? '未设置位置' }}</div>
          </div>
        </div>
      </div>

      <!-- 中: 模拟播放器 -->
      <div class="panel panel--player">
        <div class="player-viewport">
          <div class="player-viewport__overlay">
            <el-icon class="player-viewport__icon"><VideoPlay /></el-icon>
            <span class="player-viewport__cam">
              {{ selectedCamera ? selectedCamera.name : '未选择摄像头' }}
            </span>
            <span class="player-viewport__label">模拟回放</span>
            <span v-if="playbackInfo && selectedCamera" class="player-viewport__url">
              {{ buildPlaybackUrl() }}
            </span>
          </div>
        </div>

        <!-- 控制栏 -->
        <div class="player-controls">
          <el-button
            :icon="isPlaying ? VideoPause : VideoPlay"
            circle
            size="large"
            type="primary"
            @click="isPlaying = !isPlaying"
          />
          <el-radio-group v-model="playSpeed" size="small" class="speed-group">
            <el-radio-button :value="0.5">0.5x</el-radio-button>
            <el-radio-button :value="1">1x</el-radio-button>
            <el-radio-button :value="2">2x</el-radio-button>
            <el-radio-button :value="4">4x</el-radio-button>
          </el-radio-group>
          <el-slider
            v-model="progress"
            :max="100"
            :show-tooltip="false"
            class="progress-slider"
          />
          <span class="time-display">{{ formatProgress(progress) }}</span>
        </div>
      </div>

      <!-- 右: 录像片段时间线 -->
      <div class="panel panel--segments">
        <div class="panel__title">
          <el-icon><Timer /></el-icon>
          录像片段
        </div>
        <div v-if="segmentsLoading" v-loading="true" class="panel__loading" />
        <div v-else-if="segments.length === 0" class="panel__empty">
          <el-empty description="暂无录像片段" :image-size="64" />
        </div>
        <el-timeline v-else class="segment-timeline">
          <el-timeline-item
            v-for="seg in segments"
            :key="seg.id"
            :timestamp="seg.start_time ?? ''"
            placement="top"
            type="primary"
          >
            <div class="seg-item">
              <div class="seg-item__range">
                <span>{{ seg.start_time ?? '-' }}</span>
                <span class="seg-item__arrow">→</span>
                <span>{{ seg.end_time ?? '录像中' }}</span>
              </div>
              <el-tag v-if="!seg.end_time" type="danger" size="small" effect="dark" class="rec-live">
                ● 录像中
              </el-tag>
              <div v-if="seg.duration_seconds != null" class="seg-item__dur">
                时长: {{ formatDuration(seg.duration_seconds) }}
              </div>
            </div>
          </el-timeline-item>
        </el-timeline>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { VideoPlay, VideoPause, Search, Timer, VideoCamera } from '@element-plus/icons-vue'
import { useRoute } from 'vue-router'
import {
  getPlaybackInfo,
  getRecordingSegments,
} from '@/api/modules/video'
import type {
  PlaybackInfo,
  CameraBrief,
  RecordingSegment,
} from '@/api/modules/video'

// ==================== 路由 & 状态 ====================
const route = useRoute()

const manualAlarmId = ref('')
const currentAlarmId = ref<number | null>(null)
const playbackInfo = ref<PlaybackInfo | null>(null)
const selectedCameraId = ref<number | null>(null)
const segments = ref<RecordingSegment[]>([])
const segmentsLoading = ref(false)

// 播放器状态
const isPlaying = ref(false)
const playSpeed = ref(1)
const progress = ref(0)

// ==================== 映射 ====================
const levelTagType: Record<string, 'danger' | 'warning' | 'info' | 'success'> = {
  critical: 'danger',
  major: 'warning',
  minor: 'info',
  info: 'success',
}

const levelLabel: Record<string, string> = {
  critical: '紧急',
  major: '重要',
  minor: '次要',
  info: '提示',
}

// ==================== 计算属性 ====================
const selectedCamera = computed<CameraBrief | null>(() => {
  if (!playbackInfo.value || !selectedCameraId.value) return null
  return playbackInfo.value.cameras.find(c => c.id === selectedCameraId.value) ?? null
})

// ==================== 方法 ====================
function handleSearch() {
  const id = Number(manualAlarmId.value)
  if (!id || id <= 0) {
    ElMessage.warning('请输入有效的告警 ID')
    return
  }
  currentAlarmId.value = id
}

function selectCamera(cam: CameraBrief) {
  selectedCameraId.value = cam.id
}

async function loadPlaybackInfo(alarmId: number) {
  try {
    const res = await getPlaybackInfo(alarmId)
    playbackInfo.value = res
    // 默认选中第一个摄像头
    if (res.cameras.length > 0) {
      selectedCameraId.value = res.cameras[0].id
    } else {
      selectedCameraId.value = null
    }
  } catch {
    ElMessage.error('获取回放信息失败')
    playbackInfo.value = null
    selectedCameraId.value = null
  }
}

async function loadSegments(cameraId: number) {
  segmentsLoading.value = true
  try {
    const res = await getRecordingSegments({ camera_id: cameraId, page: 1, page_size: 50 })
    segments.value = res.items || []
  } catch {
    ElMessage.error('获取录像片段失败')
    segments.value = []
  } finally {
    segmentsLoading.value = false
  }
}

function buildPlaybackUrl(): string {
  if (!playbackInfo.value || !selectedCamera.value) return ''
  const tpl = playbackInfo.value.playback_url_template
  const now = new Date()
  const start = new Date(now.getTime() - 3600_000).toISOString()
  const end = now.toISOString()
  return tpl
    .replace('{camera_id}', String(selectedCamera.value.id))
    .replace('{start_time}', start)
    .replace('{end_time}', end)
}

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return m > 0 ? `${m}分${s}秒` : `${s}秒`
}

function formatProgress(val: number): string {
  const totalSec = Math.round((val / 100) * 3600)
  const mm = String(Math.floor(totalSec / 60)).padStart(2, '0')
  const ss = String(totalSec % 60).padStart(2, '0')
  return `${mm}:${ss}`
}

// ==================== 侦听器 ====================
watch(currentAlarmId, (id) => {
  if (id) {
    loadPlaybackInfo(id)
    progress.value = 0
    isPlaying.value = false
  }
})

watch(selectedCameraId, (id) => {
  segments.value = []
  if (id) {
    loadSegments(id)
    progress.value = 0
    isPlaying.value = false
  }
})

// ==================== 生命周期 ====================
onMounted(() => {
  const qid = route.query.alarm_id
  if (qid) {
    const id = Number(qid)
    if (id > 0) {
      manualAlarmId.value = String(id)
      currentAlarmId.value = id
    }
  }
})
</script>

<style lang="scss" scoped>
@use '@/styles/_mixins-25d' as *;

.playback-page {
  height: 100%;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow: hidden;
  @include page-list;
}

// ── 告警信息栏 ──
.alarm-bar {
  flex-shrink: 0;

  :deep(.el-card__body) {
    padding: 12px 20px;
  }
}

.alarm-bar__inner {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.alarm-level-tag {
  font-weight: 700;
  letter-spacing: 0.5px;
}

.alarm-msg {
  font-size: 14px;
  font-weight: 500;
  color: var(--el-text-color-primary);
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.alarm-time {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
}

.alarm-placeholder {
  color: var(--el-text-color-placeholder);
  flex: 1;
}

.alarm-search {
  display: flex;
  gap: 8px;
  margin-left: auto;
}

// ── 三栏主体 ──
.main-panels {
  flex: 1;
  display: flex;
  gap: 16px;
  min-height: 0;
}

.panel {
  display: flex;
  flex-direction: column;
  background: var(--el-bg-color-overlay);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  overflow: hidden;
}

.panel__title {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 12px 16px;
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  border-bottom: 1px solid var(--el-border-color-lighter);
  background: var(--el-fill-color-lighter);
}

.panel__empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.panel__loading {
  flex: 1;
  min-height: 120px;
}

// ── 左: 摄像头列表 ──
.panel--cameras {
  width: 25%;
  flex-shrink: 0;
}

.camera-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.camera-card {
  padding: 12px;
  border-radius: 6px;
  border: 1px solid var(--el-border-color-lighter);
  cursor: pointer;
  transition: all 0.25s ease;

  &:hover {
    border-color: var(--el-color-primary-light-3);
    background: var(--el-color-primary-light-9);
  }

  &--active {
    border-color: var(--el-color-primary);
    background: var(--el-color-primary-light-9);
    box-shadow: 0 0 0 2px var(--el-color-primary-light-7);
  }
}

.camera-card__name {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin-bottom: 4px;
}

.camera-card__code {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  font-family: 'Courier New', monospace;
}

.camera-card__loc {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
  margin-top: 4px;
}

// ── 中: 模拟播放器 ──
.panel--player {
  width: 50%;
  flex-shrink: 0;
}

.player-viewport {
  flex: 1;
  background: #1a1a2e;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  min-height: 0;
}

.player-viewport__overlay {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  color: rgba(255, 255, 255, 0.7);
}

.player-viewport__icon {
  font-size: 56px;
  color: rgba(255, 255, 255, 0.25);
}

.player-viewport__cam {
  font-size: 16px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.85);
}

.player-viewport__label {
  font-size: 13px;
  padding: 2px 12px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.12);
}

.player-viewport__url {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.35);
  max-width: 90%;
  text-align: center;
  word-break: break-all;
  font-family: 'Courier New', monospace;
}

// ── 控制栏 ──
.player-controls {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  background: var(--el-fill-color-darker);
  border-top: 1px solid var(--el-border-color-darker);
}

.speed-group {
  flex-shrink: 0;
}

.progress-slider {
  flex: 1;
  margin: 0 8px;
}

.time-display {
  font-size: 13px;
  font-family: 'Courier New', monospace;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
  min-width: 48px;
  text-align: right;
}

// ── 右: 录像片段 ──
.panel--segments {
  width: 25%;
  flex-shrink: 0;
}

.segment-timeline {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.seg-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.seg-item__range {
  font-size: 12px;
  color: var(--el-text-color-regular);
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}

.seg-item__arrow {
  color: var(--el-text-color-placeholder);
}

.seg-item__dur {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.rec-live {
  align-self: flex-start;
  animation: recBlink 1s ease-in-out infinite;
}

@keyframes recBlink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
</style>
