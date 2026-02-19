<template>
  <div class="video-control-page">
    <el-row :gutter="16" class="main-row">
      <!-- 左侧面板: 云台控制 -->
      <el-col :span="10">
        <el-card shadow="hover" class="ptz-card">
          <template #header>
            <div class="card-header">
              <span class="card-title">
                <el-icon><VideoCamera /></el-icon>
                云台控制
              </span>
            </div>
          </template>

          <!-- 摄像头选择 -->
          <div class="camera-selector">
            <el-select
              v-model="selectedCameraId"
              placeholder="选择摄像头"
              filterable
              style="width: 100%"
              @change="handleCameraChange"
            >
              <el-option
                v-for="cam in cameraList"
                :key="cam.id"
                :label="cam.name"
                :value="cam.id"
              />
            </el-select>
          </div>

          <!-- PTZ 方向控制盘 -->
          <div class="ptz-pad">
            <div class="ptz-row">
              <div class="ptz-spacer" />
              <el-button
                class="ptz-btn"
                :icon="ArrowUp"
                :disabled="!selectedCameraId"
                @click="handlePtz('up')"
              />
              <div class="ptz-spacer" />
            </div>
            <div class="ptz-row">
              <el-button
                class="ptz-btn"
                :icon="ArrowLeft"
                :disabled="!selectedCameraId"
                @click="handlePtz('left')"
              />
              <el-button
                class="ptz-btn ptz-stop"
                :icon="VideoPause"
                :disabled="!selectedCameraId"
                @click="handlePtz('stop')"
              />
              <el-button
                class="ptz-btn"
                :icon="ArrowRight"
                :disabled="!selectedCameraId"
                @click="handlePtz('right')"
              />
            </div>
            <div class="ptz-row">
              <div class="ptz-spacer" />
              <el-button
                class="ptz-btn"
                :icon="ArrowDown"
                :disabled="!selectedCameraId"
                @click="handlePtz('down')"
              />
              <div class="ptz-spacer" />
            </div>
          </div>

          <!-- 变焦控制 -->
          <div class="zoom-bar">
            <el-button
              :icon="ZoomOut"
              :disabled="!selectedCameraId"
              @click="handlePtz('zoom_out')"
            >
              缩小
            </el-button>
            <el-button
              :icon="ZoomIn"
              :disabled="!selectedCameraId"
              @click="handlePtz('zoom_in')"
            >
              放大
            </el-button>
          </div>

          <!-- 预置位快捷按钮 -->
          <el-divider content-position="left">预置位</el-divider>
          <div class="preset-grid">
            <template v-if="currentPresets.length">
              <el-button
                v-for="preset in currentPresets"
                :key="preset.preset_index"
                size="small"
                @click="handleCallPreset(preset.preset_index)"
              >
                {{ preset.name || `预置位 ${preset.preset_index}` }}
              </el-button>
            </template>
            <el-empty v-else description="暂无预置位" :image-size="48" />
          </div>
        </el-card>
      </el-col>

      <!-- 右侧面板: 录像 + 事件日志 -->
      <el-col :span="14">
        <!-- 录像控制 -->
        <el-card shadow="hover" class="recording-card">
          <template #header>
            <div class="card-header">
              <span class="card-title">
                <el-icon><VideoPlay /></el-icon>
                录像控制
              </span>
              <el-tag v-if="isRecording" type="danger" effect="dark" class="rec-badge">
                ● REC
              </el-tag>
            </div>
          </template>
          <div class="recording-actions">
            <el-button
              type="danger"
              :icon="VideoPlay"
              :disabled="!selectedCameraId || isRecording"
              :loading="recordingLoading"
              @click="handleStartRecording"
            >
              开始录像
            </el-button>
            <el-button
              type="warning"
              :icon="VideoPause"
              :disabled="!selectedCameraId || !isRecording"
              :loading="recordingLoading"
              @click="handleStopRecording"
            >
              停止录像
            </el-button>
          </div>
        </el-card>

        <!-- 事件日志 -->
        <el-card shadow="hover" class="events-card">
          <template #header>
            <div class="card-header">
              <span class="card-title">事件日志</span>
              <el-button :icon="Refresh" text @click="loadEvents">刷新</el-button>
            </div>
          </template>
          <el-table :data="eventList" stripe border v-loading="eventsLoading" row-key="id" size="small">
            <el-table-column prop="created_at" label="时间" width="170">
              <template #default="{ row }">{{ row.created_at ?? '-' }}</template>
            </el-table-column>
            <el-table-column prop="camera_name" label="摄像头" min-width="120" show-overflow-tooltip>
              <template #default="{ row }">{{ row.camera_name ?? '-' }}</template>
            </el-table-column>
            <el-table-column prop="event_type" label="事件类型" width="120" align="center">
              <template #default="{ row }">
                <el-tag size="small" :type="eventTagType(row.event_type)">
                  {{ eventTypeLabel(row.event_type) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="trigger_source" label="触发来源" width="110" align="center">
              <template #default="{ row }">{{ triggerSourceLabel(row.trigger_source) }}</template>
            </el-table-column>
            <el-table-column prop="operator" label="操作人" width="100" align="center">
              <template #default="{ row }">{{ row.operator ?? '-' }}</template>
            </el-table-column>
            <el-table-column prop="detail" label="详情" min-width="160" show-overflow-tooltip>
              <template #default="{ row }">{{ row.detail ?? '-' }}</template>
            </el-table-column>
          </el-table>
          <el-pagination
            v-model:current-page="evtPage.page"
            v-model:page-size="evtPage.pageSize"
            :total="evtPage.total"
            :page-sizes="[10, 20, 50]"
            layout="total, sizes, prev, pager, next"
            class="pagination"
            @size-change="loadEvents"
            @current-change="loadEvents"
          />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import {
  ArrowUp,
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  VideoPause,
  ZoomIn,
  ZoomOut,
  VideoPlay,
  VideoCamera,
  Refresh,
} from '@element-plus/icons-vue'
import {
  getCameraList,
  ptzControl,
  callPreset,
  startRecording,
  stopRecording,
  getVideoEvents,
} from '@/api/modules/video'
import type { CameraItem, VideoEventItem } from '@/api/modules/video'

// ==================== 摄像头列表 ====================
const cameraList = ref<CameraItem[]>([])
const selectedCameraId = ref<number | undefined>(undefined)

const currentPresets = computed(() => {
  if (!selectedCameraId.value) return []
  const cam = cameraList.value.find(c => c.id === selectedCameraId.value)
  return cam?.presets ?? []
})

async function loadCameras() {
  try {
    const res = await getCameraList({ page: 1, page_size: 200 })
    cameraList.value = res.items || []
  } catch {
    ElMessage.error('加载摄像头列表失败')
  }
}

function handleCameraChange() {
  isRecording.value = false
  loadEvents()
}

// ==================== PTZ 控制 ====================
async function handlePtz(action: string) {
  if (!selectedCameraId.value) return
  try {
    await ptzControl({ camera_id: selectedCameraId.value, action })
    if (action !== 'stop') {
      ElMessage.success(`云台${ptzActionLabel(action)}`)
    }
    loadEvents()
  } catch {
    ElMessage.error('云台控制失败')
  }
}

function ptzActionLabel(action: string): string {
  const map: Record<string, string> = {
    up: '上移', down: '下移', left: '左转', right: '右转',
    zoom_in: '放大', zoom_out: '缩小', stop: '停止',
  }
  return map[action] || action
}

// ==================== 预置位 ====================
async function handleCallPreset(presetIndex: number) {
  if (!selectedCameraId.value) return
  try {
    await callPreset({ camera_id: selectedCameraId.value, preset_index: presetIndex })
    ElMessage.success('预置位调用成功')
    loadEvents()
  } catch {
    ElMessage.error('预置位调用失败')
  }
}

// ==================== 录像控制 ====================
const isRecording = ref(false)
const recordingLoading = ref(false)

async function handleStartRecording() {
  if (!selectedCameraId.value) return
  recordingLoading.value = true
  try {
    await startRecording({ camera_id: selectedCameraId.value })
    isRecording.value = true
    ElMessage.success('录像已开始')
    loadEvents()
  } catch {
    ElMessage.error('开始录像失败')
  } finally {
    recordingLoading.value = false
  }
}

async function handleStopRecording() {
  if (!selectedCameraId.value) return
  recordingLoading.value = true
  try {
    await stopRecording({ camera_id: selectedCameraId.value })
    isRecording.value = false
    ElMessage.success('录像已停止')
    loadEvents()
  } catch {
    ElMessage.error('停止录像失败')
  } finally {
    recordingLoading.value = false
  }
}

// ==================== 事件日志 ====================
const eventsLoading = ref(false)
const eventList = ref<VideoEventItem[]>([])
const evtPage = reactive({ page: 1, pageSize: 10, total: 0 })

async function loadEvents() {
  eventsLoading.value = true
  try {
    const params: Record<string, unknown> = {
      page: evtPage.page,
      page_size: evtPage.pageSize,
    }
    if (selectedCameraId.value) params.camera_id = selectedCameraId.value
    const res = await getVideoEvents(params as Parameters<typeof getVideoEvents>[0])
    eventList.value = res.items || []
    evtPage.total = res.total || 0
  } catch {
    ElMessage.error('加载事件日志失败')
  } finally {
    eventsLoading.value = false
  }
}

// ==================== 显示映射 ====================
function eventTypeLabel(type: string): string {
  const map: Record<string, string> = {
    recording_start: '开始录像',
    recording_stop: '停止录像',
    ptz_control: '云台控制',
    preset_call: '预置位调用',
  }
  return map[type] || type
}

function eventTagType(type: string): 'success' | 'warning' | 'info' | 'danger' {
  const map: Record<string, 'success' | 'warning' | 'info' | 'danger'> = {
    recording_start: 'danger',
    recording_stop: 'warning',
    ptz_control: 'info',
    preset_call: 'success',
  }
  return map[type] || 'info'
}

function triggerSourceLabel(source: string): string {
  const map: Record<string, string> = {
    linkage: '联动触发',
    manual: '手动操作',
  }
  return map[source] || source
}

// ==================== 生命周期 ====================
onMounted(() => {
  loadCameras()
  loadEvents()
})
</script>

<style lang="scss" scoped>
@use '@/styles/_mixins-25d' as *;

.video-control-page {
  height: 100%;
  padding: 16px;
  overflow-y: auto;
  @include page-list;
}

.main-row {
  height: 100%;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 15px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.camera-selector {
  margin-bottom: 20px;
}

// ── PTZ 控制盘 ──
.ptz-pad {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  margin: 16px 0;
}

.ptz-row {
  display: flex;
  align-items: center;
  gap: 4px;
}

.ptz-spacer {
  width: 48px;
  height: 48px;
}

.ptz-btn {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  font-size: 18px;
  transition: all 0.25s ease;

  &:hover:not(:disabled) {
    transform: scale(1.12);
    box-shadow: 0 4px 16px rgba(0, 120, 255, 0.3);
  }
}

.ptz-stop {
  background: var(--el-color-danger-light-3);
  border-color: var(--el-color-danger);
  color: #fff;

  &:hover:not(:disabled) {
    background: var(--el-color-danger);
    box-shadow: 0 4px 16px rgba(245, 108, 108, 0.4);
  }
}

// ── 变焦 ──
.zoom-bar {
  display: flex;
  justify-content: center;
  gap: 16px;
  margin: 8px 0 4px;
}

// ── 预置位 ──
.preset-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

// ── 录像 ──
.recording-card {
  margin-bottom: 16px;
}

.rec-badge {
  animation: recBlink 1s ease-in-out infinite;
}

@keyframes recBlink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.recording-actions {
  display: flex;
  gap: 12px;
}

// ── 事件日志 ──
.events-card {
  margin-bottom: 16px;
}

.pagination {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}
</style>
