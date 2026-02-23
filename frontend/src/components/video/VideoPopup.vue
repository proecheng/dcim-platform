<template>
  <el-dialog append-to-body
    v-model="visible"
    title="视频监控 - 告警联动"
    :width="dialogWidth"
    draggable
    :close-on-click-modal="false"
    class="video-popup-dialog"
    @close="hide"
  >
    <!-- 工具栏 -->
    <template #header>
      <div class="popup-header">
        <div class="popup-title">
          <el-icon :size="20" class="title-icon"><VideoCamera /></el-icon>
          <span>视频监控 - 告警联动</span>
          <el-tag v-if="cameras.length" size="small" type="info" class="camera-count">
            {{ cameras.length }} 路
          </el-tag>
        </div>
        <div class="layout-switcher">
          <el-radio-group v-model="gridMode" size="small">
            <el-radio-button :value="1">
              <el-icon><FullScreen /></el-icon> 1
            </el-radio-button>
            <el-radio-button :value="4">
              <el-icon><Grid /></el-icon> 4
            </el-radio-button>
            <el-radio-button :value="9">
              <el-icon><Menu /></el-icon> 9
            </el-radio-button>
          </el-radio-group>
        </div>
      </div>
    </template>

    <!-- 加载状态 -->
    <div v-if="loading" class="loading-mask">
      <el-icon class="spin-icon" :size="36"><Loading /></el-icon>
      <span>正在获取摄像头信息...</span>
    </div>

    <!-- 空状态 -->
    <div v-else-if="!cameras.length" class="empty-state">
      <el-icon :size="48"><VideoCamera /></el-icon>
      <p>暂无关联摄像头</p>
    </div>

    <!-- 视频网格 -->
    <div v-else class="video-grid" :class="gridClass">
      <div
        v-for="(cam, idx) in displayCameras"
        :key="cam.id"
        class="grid-cell"
      >
        <div class="cell-header">
          <span class="cam-name">{{ cam.name }}</span>
          <el-tag
            :type="cam.status === 'online' ? 'success' : 'danger'"
            size="small"
            effect="dark"
            class="status-tag"
          >
            {{ cam.status === 'online' ? '在线' : '离线' }}
          </el-tag>
        </div>

        <!-- 占位播放区域 -->
        <div class="player-placeholder">
          <el-icon :size="placeholderIconSize" class="cam-icon"><VideoCamera /></el-icon>
          <span class="stream-url">{{ cam.hls_url || cam.rtsp_url || '未配置流地址' }}</span>
          <span class="channel-label">CH-{{ String(idx + 1).padStart(2, '0') }}</span>
        </div>

        <div class="cell-footer">
          <el-tag size="small" effect="plain" class="type-badge">
            {{ cameraTypeLabel(cam.camera_type) }}
          </el-tag>
          <span class="cam-code">{{ cam.code }}</span>
        </div>
      </div>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { getCamerasByAlarm } from '@/api/modules/video'
import type { CameraItem } from '@/api/modules/video'
import {
  VideoCamera, FullScreen, Grid, Menu, Loading
} from '@element-plus/icons-vue'

const visible = ref(false)
const loading = ref(false)
const cameras = ref<CameraItem[]>([])
const gridMode = ref<1 | 4 | 9>(4)

// 根据摄像头数量自动选择网格模式
const autoGridMode = computed(() => {
  const count = cameras.value.length
  if (count <= 1) return 1
  if (count <= 4) return 4
  return 9
})

// 对话框宽度随网格模式变化
const dialogWidth = computed(() => {
  if (gridMode.value === 1) return '640px'
  if (gridMode.value === 4) return '860px'
  return '1080px'
})

// 网格 CSS class
const gridClass = computed(() => {
  return `grid-${gridMode.value}`
})

// 占位图标大小
const placeholderIconSize = computed(() => {
  if (gridMode.value === 1) return 64
  if (gridMode.value === 4) return 40
  return 28
})

// 截取显示的摄像头（不超过网格数）
const displayCameras = computed(() => {
  return cameras.value.slice(0, gridMode.value)
})

// 摄像头类型标签
function cameraTypeLabel(type: string): string {
  const map: Record<string, string> = {
    fixed: '固定',
    ptz: '云台',
    dome: '球机',
    bullet: '枪机',
    panoramic: '全景',
  }
  return map[type] || type
}

/** 显示弹窗，传入摄像头列表 */
function show(cameraList: CameraItem[]) {
  cameras.value = cameraList
  gridMode.value = autoGridMode.value as 1 | 4 | 9
  visible.value = true
}

/** 隐藏弹窗 */
function hide() {
  visible.value = false
  cameras.value = []
}

/** 根据告警 ID 查询关联摄像头并显示 */
async function showForAlarm(alarmId: number) {
  visible.value = true
  loading.value = true
  try {
    const list = await getCamerasByAlarm(alarmId)
    cameras.value = list
    gridMode.value = autoGridMode.value as 1 | 4 | 9
  } catch (e) {
    console.error('获取告警关联摄像头失败', e)
    ElMessage.error('获取摄像头信息失败')
  } finally {
    loading.value = false
  }
}

defineExpose({ show, hide, showForAlarm })
</script>

<style scoped lang="scss">
// 对话框整体覆盖
:deep(.el-dialog) {
  background: #0f0f1a;
  border: 1px solid rgba(56, 189, 248, 0.15);
  border-radius: 12px;
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.6), 0 0 40px rgba(56, 189, 248, 0.08);
}

:deep(.el-dialog__header) {
  padding: 0;
  margin: 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

:deep(.el-dialog__body) {
  padding: 16px;
  min-height: 300px;
}

:deep(.el-dialog__headerbtn .el-dialog__close) {
  color: rgba(255, 255, 255, 0.5);
  font-size: 18px;

  &:hover {
    color: #f87171;
  }
}

// 头部
.popup-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 20px;
}

.popup-title {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #e2e8f0;
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 0.3px;

  .title-icon {
    color: #38bdf8;
    filter: drop-shadow(0 0 6px rgba(56, 189, 248, 0.4));
  }

  .camera-count {
    background: rgba(56, 189, 248, 0.12);
    border-color: rgba(56, 189, 248, 0.25);
    color: #7dd3fc;
    font-variant-numeric: tabular-nums;
  }
}

.layout-switcher {
  :deep(.el-radio-group) {
    --el-radio-button-checked-bg-color: rgba(56, 189, 248, 0.2);
    --el-radio-button-checked-border-color: rgba(56, 189, 248, 0.4);
    --el-radio-button-checked-text-color: #7dd3fc;
  }

  :deep(.el-radio-button__inner) {
    background: rgba(255, 255, 255, 0.04);
    border-color: rgba(255, 255, 255, 0.1);
    color: rgba(255, 255, 255, 0.45);
    padding: 6px 12px;
    font-size: 12px;
    display: flex;
    align-items: center;
    gap: 4px;

    &:hover {
      color: rgba(255, 255, 255, 0.7);
    }
  }
}

// 加载 & 空状态
.loading-mask,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  min-height: 260px;
  color: rgba(255, 255, 255, 0.35);
  font-size: 14px;
}

.spin-icon {
  animation: spin 1.2s linear infinite;
  color: #38bdf8;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

// 视频网格
.video-grid {
  display: grid;
  gap: 8px;

  &.grid-1 {
    grid-template-columns: 1fr;
  }

  &.grid-4 {
    grid-template-columns: repeat(2, 1fr);
  }

  &.grid-9 {
    grid-template-columns: repeat(3, 1fr);
  }
}

.grid-cell {
  background: #1a1a2e;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.06);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  transition: border-color 0.2s;

  &:hover {
    border-color: rgba(56, 189, 248, 0.25);
  }
}

.cell-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 10px;
  background: rgba(255, 255, 255, 0.03);
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);

  .cam-name {
    color: #e2e8f0;
    font-size: 12px;
    font-weight: 500;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 70%;
  }

  .status-tag {
    font-size: 10px;
    padding: 0 6px;
    height: 18px;
    line-height: 18px;
  }
}

.player-placeholder {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 20px 12px;
  position: relative;
  min-height: 120px;
  background:
    radial-gradient(ellipse at center, rgba(56, 189, 248, 0.03) 0%, transparent 70%),
    linear-gradient(180deg, rgba(0, 0, 0, 0.1) 0%, transparent 100%);

  .cam-icon {
    color: rgba(255, 255, 255, 0.12);
  }

  .stream-url {
    color: rgba(255, 255, 255, 0.2);
    font-size: 10px;
    font-family: 'Courier New', monospace;
    max-width: 90%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    text-align: center;
  }

  .channel-label {
    position: absolute;
    top: 6px;
    left: 8px;
    font-size: 10px;
    font-weight: 700;
    color: rgba(56, 189, 248, 0.5);
    font-variant-numeric: tabular-nums;
    letter-spacing: 1px;
  }
}

.cell-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 10px;
  background: rgba(255, 255, 255, 0.02);
  border-top: 1px solid rgba(255, 255, 255, 0.04);

  .type-badge {
    font-size: 10px;
    background: rgba(139, 92, 246, 0.1);
    border-color: rgba(139, 92, 246, 0.2);
    color: #a78bfa;
  }

  .cam-code {
    color: rgba(255, 255, 255, 0.25);
    font-size: 10px;
    font-family: 'Courier New', monospace;
  }
}
</style>
