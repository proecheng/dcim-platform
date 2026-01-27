<template>
  <div
    ref="panelRef"
    class="draggable-panel"
    :class="{ collapsed: isCollapsed, dragging: isDragging }"
    :style="panelStyle"
  >
    <!-- 拖拽手柄/标题栏 - 始终显示 -->
    <div
      class="panel-header"
      :class="{ 'collapsed-header': isCollapsed }"
      @mousedown="startDrag"
      @touchstart="startDrag"
    >
      <div class="header-left">
        <span class="panel-title">{{ title }}</span>
      </div>
      <div class="header-controls">
        <button class="control-btn" @click.stop="toggleCollapse" :title="isCollapsed ? '展开' : '收起'">
          <span class="icon">{{ isCollapsed ? '▼' : '▲' }}</span>
        </button>
        <button v-if="closable" class="control-btn close" @click.stop="$emit('close')" title="关闭">
          <span class="icon">×</span>
        </button>
      </div>
    </div>

    <!-- 内容区域 - 仅在展开时显示 -->
    <Transition name="collapse">
      <div v-show="!isCollapsed" class="panel-content">
        <slot></slot>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onUnmounted } from 'vue'

const props = withDefaults(defineProps<{
  title: string
  initialX?: number
  initialY?: number
  initialCollapsed?: boolean
  closable?: boolean
  panelId: string
  minWidth?: number
  minHeight?: number
}>(), {
  initialX: 20,
  initialY: 60,
  initialCollapsed: false,
  closable: false,
  minWidth: 50,
  minHeight: 40
})

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'positionChange', data: { id: string; x: number; y: number }): void
  (e: 'collapseChange', data: { id: string; collapsed: boolean }): void
}>()

const panelRef = ref<HTMLDivElement>()
const isDragging = ref(false)
const isCollapsed = ref(props.initialCollapsed)

// 位置状态
const position = ref({ x: props.initialX, y: props.initialY })

// 拖拽起始位置
const dragStart = ref({ x: 0, y: 0 })
const positionStart = ref({ x: 0, y: 0 })

const panelStyle = computed(() => ({
  left: `${position.value.x}px`,
  top: `${position.value.y}px`
}))

function startDrag(e: MouseEvent | TouchEvent) {
  // 允许在折叠状态下拖拽（移除了之前的限制）

  isDragging.value = true

  const clientX = 'touches' in e ? e.touches[0].clientX : e.clientX
  const clientY = 'touches' in e ? e.touches[0].clientY : e.clientY

  dragStart.value = { x: clientX, y: clientY }
  positionStart.value = { ...position.value }

  document.addEventListener('mousemove', onDrag)
  document.addEventListener('mouseup', stopDrag)
  document.addEventListener('touchmove', onDrag)
  document.addEventListener('touchend', stopDrag)
}

function onDrag(e: MouseEvent | TouchEvent) {
  if (!isDragging.value) return

  const clientX = 'touches' in e ? e.touches[0].clientX : e.clientX
  const clientY = 'touches' in e ? e.touches[0].clientY : e.clientY

  const deltaX = clientX - dragStart.value.x
  const deltaY = clientY - dragStart.value.y

  // 计算新位置，限制在视口内
  const newX = Math.max(0, Math.min(window.innerWidth - 100, positionStart.value.x + deltaX))
  const newY = Math.max(0, Math.min(window.innerHeight - 50, positionStart.value.y + deltaY))

  position.value = { x: newX, y: newY }
}

function stopDrag() {
  if (isDragging.value) {
    isDragging.value = false
    emit('positionChange', { id: props.panelId, x: position.value.x, y: position.value.y })
  }

  document.removeEventListener('mousemove', onDrag)
  document.removeEventListener('mouseup', stopDrag)
  document.removeEventListener('touchmove', onDrag)
  document.removeEventListener('touchend', stopDrag)
}

function toggleCollapse() {
  isCollapsed.value = !isCollapsed.value
  emit('collapseChange', { id: props.panelId, collapsed: isCollapsed.value })
}

// 暴露方法供外部控制
function setPosition(x: number, y: number) {
  position.value = { x, y }
}

function setCollapsed(collapsed: boolean) {
  isCollapsed.value = collapsed
}

defineExpose({ setPosition, setCollapsed, position, isCollapsed })

onUnmounted(() => {
  document.removeEventListener('mousemove', onDrag)
  document.removeEventListener('mouseup', stopDrag)
  document.removeEventListener('touchmove', onDrag)
  document.removeEventListener('touchend', stopDrag)
})
</script>

<style scoped lang="scss">
.draggable-panel {
  position: absolute;
  z-index: 100;
  background: rgba(0, 20, 40, 0.9);
  border: 1px solid rgba(0, 200, 255, 0.3);
  border-radius: 8px;
  backdrop-filter: blur(10px);
  transition: box-shadow 0.2s ease;

  &.dragging {
    box-shadow: 0 8px 32px rgba(0, 200, 255, 0.3);
    z-index: 200;
    cursor: grabbing;
  }

  &.collapsed {
    // 折叠时保持原有宽度，不再缩小
    // 只有标题栏可见，内容被隐藏

    .panel-header {
      // 折叠时标题栏变为半透明
      background: rgba(0, 50, 80, 0.6);
      border-bottom: none;
      border-radius: 8px;
    }
  }
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  background: linear-gradient(180deg, rgba(0, 100, 150, 0.4) 0%, rgba(0, 50, 100, 0.2) 100%);
  border-bottom: 1px solid rgba(0, 200, 255, 0.2);
  border-radius: 8px 8px 0 0;
  cursor: grab;
  user-select: none;

  &:active {
    cursor: grabbing;
  }

  &.collapsed-header {
    border-radius: 8px;
  }
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.panel-title {
  color: #00ccff;
  font-size: 13px;
  font-weight: 500;
  letter-spacing: 1px;
}

.header-controls {
  display: flex;
  align-items: center;
  gap: 4px;
}

.control-btn {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 100, 150, 0.3);
  border: 1px solid rgba(0, 200, 255, 0.2);
  border-radius: 4px;
  color: #88ccff;
  cursor: pointer;
  transition: all 0.2s ease;

  &:hover {
    background: rgba(0, 150, 200, 0.4);
    color: #ffffff;
  }

  &.close:hover {
    background: rgba(255, 50, 50, 0.4);
    border-color: rgba(255, 100, 100, 0.5);
  }

  .icon {
    font-size: 12px;
    line-height: 1;
  }
}

.panel-content {
  overflow: hidden;
}

// 折叠动画
.collapse-enter-active,
.collapse-leave-active {
  transition: all 0.3s ease;
  max-height: 800px;
  opacity: 1;
}

.collapse-enter-from,
.collapse-leave-to {
  max-height: 0;
  opacity: 0;
}
</style>
