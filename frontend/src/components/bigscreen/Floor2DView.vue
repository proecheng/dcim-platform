<template>
  <div class="floor-2d-view" ref="containerRef">
    <canvas ref="canvasRef" @click="handleClick" @mousemove="handleHover"></canvas>

    <div v-if="hoveredElement" class="tooltip" :style="tooltipStyle">
      <div class="tooltip-title">{{ hoveredElement.name }}</div>
      <div class="tooltip-type">{{ getTypeLabel(hoveredElement.type) }}</div>
      <div v-if="hoveredElement.deviceType" class="tooltip-device">
        {{ getDeviceTypeLabel(hoveredElement.deviceType) }}
      </div>
      <div v-if="hoveredElement.status" :class="['status', hoveredElement.status]">
        {{ statusText(hoveredElement.status) }}
      </div>
    </div>

    <div v-if="!mapData" class="no-data">
      <div class="no-data-icon">📐</div>
      <div class="no-data-text">暂无楼层图数据</div>
      <div class="no-data-hint">请先加载演示数据</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch, computed, onUnmounted } from 'vue'
import type { MapData2D, MapElement2D } from '@/api/modules/floorMap'

const props = defineProps<{
  mapData: MapData2D | null
}>()

const emit = defineEmits<{
  (e: 'elementClick', element: MapElement2D): void
}>()

const containerRef = ref<HTMLDivElement>()
const canvasRef = ref<HTMLCanvasElement>()
const hoveredElement = ref<MapElement2D | null>(null)
const mousePos = ref({ x: 0, y: 0 })

const scale = ref(1)
const offsetX = ref(0)
const offsetY = ref(0)

const tooltipStyle = computed(() => ({
  left: `${mousePos.value.x + 15}px`,
  top: `${mousePos.value.y + 15}px`
}))

function statusText(status: string) {
  const map: Record<string, string> = {
    normal: '正常运行',
    warning: '告警中',
    error: '故障',
    offline: '离线'
  }
  return map[status] || status
}

function getTypeLabel(type: string) {
  const map: Record<string, string> = {
    zone: '功能区域',
    cabinet: '机柜',
    device: '设备',
    equipment: '设备'
  }
  return map[type] || type
}

function getDeviceTypeLabel(deviceType: string) {
  const map: Record<string, string> = {
    chiller: '冷水机组',
    cooling_tower: '冷却塔',
    pump: '冷冻水泵',
    ups: 'UPS电源',
    ac: '精密空调'
  }
  return map[deviceType] || deviceType
}

function draw() {
  const canvas = canvasRef.value
  const container = containerRef.value
  if (!canvas || !container) return

  const ctx = canvas.getContext('2d')
  if (!ctx) return

  // 设置canvas尺寸
  const rect = container.getBoundingClientRect()
  const dpr = window.devicePixelRatio || 1
  canvas.width = rect.width * dpr
  canvas.height = rect.height * dpr
  canvas.style.width = `${rect.width}px`
  canvas.style.height = `${rect.height}px`
  ctx.scale(dpr, dpr)

  // 如果没有数据，显示空白背景
  if (!props.mapData) {
    ctx.fillStyle = '#0a1628'
    ctx.fillRect(0, 0, rect.width, rect.height)
    return
  }

  const { dimensions, background, elements, name } = props.mapData

  // 计算缩放和偏移使地图居中
  const padding = 60
  const scaleX = (rect.width - padding * 2) / dimensions.width
  const scaleY = (rect.height - padding * 2) / dimensions.height
  scale.value = Math.min(scaleX, scaleY)
  offsetX.value = (rect.width - dimensions.width * scale.value) / 2
  offsetY.value = (rect.height - dimensions.height * scale.value) / 2

  // 清空画布
  ctx.fillStyle = '#0a1628'
  ctx.fillRect(0, 0, rect.width, rect.height)

  // 绘制背景区域
  ctx.fillStyle = background
  ctx.fillRect(
    offsetX.value,
    offsetY.value,
    dimensions.width * scale.value,
    dimensions.height * scale.value
  )

  // 绘制网格
  ctx.strokeStyle = 'rgba(0, 200, 255, 0.1)'
  ctx.lineWidth = 0.5
  for (let x = 0; x <= dimensions.width; x += 5) {
    ctx.beginPath()
    ctx.moveTo(offsetX.value + x * scale.value, offsetY.value)
    ctx.lineTo(offsetX.value + x * scale.value, offsetY.value + dimensions.height * scale.value)
    ctx.stroke()
  }
  for (let y = 0; y <= dimensions.height; y += 5) {
    ctx.beginPath()
    ctx.moveTo(offsetX.value, offsetY.value + y * scale.value)
    ctx.lineTo(offsetX.value + dimensions.width * scale.value, offsetY.value + y * scale.value)
    ctx.stroke()
  }

  // 绘制元素
  for (const el of elements) {
    const x = offsetX.value + el.x * scale.value
    const y = offsetY.value + el.y * scale.value
    const w = el.width * scale.value
    const h = el.height * scale.value

    // 背景
    ctx.fillStyle = el.color || getTypeColor(el.type, el.status)
    ctx.fillRect(x, y, w, h)

    // 边框
    const isHovered = el === hoveredElement.value
    ctx.strokeStyle = isHovered ? '#00ffff' : 'rgba(0, 200, 255, 0.5)'
    ctx.lineWidth = isHovered ? 2 : 1
    ctx.strokeRect(x, y, w, h)

    // 发光效果（悬停时）
    if (isHovered) {
      ctx.shadowColor = '#00ffff'
      ctx.shadowBlur = 10
      ctx.strokeRect(x, y, w, h)
      ctx.shadowBlur = 0
    }

    // 标签
    if (w > 30 && h > 20) {
      ctx.fillStyle = '#ffffff'
      ctx.font = `${Math.max(10, Math.min(12, w / 5))}px "Microsoft YaHei", sans-serif`
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'

      // 截断过长文本
      let label = el.name
      if (ctx.measureText(label).width > w - 6) {
        while (ctx.measureText(label + '...').width > w - 6 && label.length > 1) {
          label = label.slice(0, -1)
        }
        label += '...'
      }
      ctx.fillText(label, x + w / 2, y + h / 2)
    }

    // 状态指示器
    if (el.status && el.status !== 'normal') {
      const indicatorSize = Math.min(8, w / 4, h / 4)
      ctx.fillStyle = getStatusColor(el.status)
      ctx.beginPath()
      ctx.arc(x + w - indicatorSize, y + indicatorSize, indicatorSize / 2, 0, Math.PI * 2)
      ctx.fill()
    }
  }

  // 绘制标题
  ctx.fillStyle = '#00ccff'
  ctx.font = 'bold 16px "Microsoft YaHei", sans-serif'
  ctx.textAlign = 'left'
  ctx.textBaseline = 'top'
  ctx.fillText(name, 20, 20)

  // 绘制比例尺
  drawScaleBar(ctx, rect.width, rect.height)
}

function drawScaleBar(ctx: CanvasRenderingContext2D, canvasWidth: number, canvasHeight: number) {
  const scaleBarLength = 10 * scale.value // 10米
  const x = canvasWidth - 100
  const y = canvasHeight - 30

  ctx.strokeStyle = '#00ccff'
  ctx.lineWidth = 2
  ctx.beginPath()
  ctx.moveTo(x, y)
  ctx.lineTo(x + scaleBarLength, y)
  ctx.moveTo(x, y - 5)
  ctx.lineTo(x, y + 5)
  ctx.moveTo(x + scaleBarLength, y - 5)
  ctx.lineTo(x + scaleBarLength, y + 5)
  ctx.stroke()

  ctx.fillStyle = '#00ccff'
  ctx.font = '11px "Microsoft YaHei", sans-serif'
  ctx.textAlign = 'center'
  ctx.fillText('10m', x + scaleBarLength / 2, y + 15)
}

function getTypeColor(type: string, status?: string): string {
  if (status === 'error') return 'rgba(255, 50, 50, 0.6)'
  if (status === 'warning') return 'rgba(255, 200, 0, 0.6)'
  if (status === 'offline') return 'rgba(100, 100, 100, 0.6)'

  const colors: Record<string, string> = {
    zone: 'rgba(0, 100, 150, 0.4)',
    cabinet: 'rgba(50, 80, 120, 0.7)',
    device: 'rgba(0, 150, 100, 0.6)',
    equipment: 'rgba(100, 100, 200, 0.6)'
  }
  return colors[type] || 'rgba(50, 100, 150, 0.5)'
}

function getStatusColor(status: string): string {
  const colors: Record<string, string> = {
    warning: '#ffcc00',
    error: '#ff3333',
    offline: '#666666'
  }
  return colors[status] || '#00ff88'
}

function getElementAt(clientX: number, clientY: number): MapElement2D | null {
  if (!props.mapData || !canvasRef.value) return null

  const rect = canvasRef.value.getBoundingClientRect()
  const x = (clientX - rect.left - offsetX.value) / scale.value
  const y = (clientY - rect.top - offsetY.value) / scale.value

  // 从后向前检查（后绘制的在上层）
  for (let i = props.mapData.elements.length - 1; i >= 0; i--) {
    const el = props.mapData.elements[i]
    if (x >= el.x && x <= el.x + el.width && y >= el.y && y <= el.y + el.height) {
      return el
    }
  }
  return null
}

function handleHover(e: MouseEvent) {
  mousePos.value = { x: e.clientX, y: e.clientY }
  const el = getElementAt(e.clientX, e.clientY)
  if (el !== hoveredElement.value) {
    hoveredElement.value = el
    draw()
  }
}

function handleClick(e: MouseEvent) {
  const el = getElementAt(e.clientX, e.clientY)
  if (el) {
    emit('elementClick', el)
  }
}

let resizeObserver: ResizeObserver | null = null

onMounted(() => {
  draw()

  if (containerRef.value) {
    resizeObserver = new ResizeObserver(() => draw())
    resizeObserver.observe(containerRef.value)
  }
})

onUnmounted(() => {
  resizeObserver?.disconnect()
})

watch(() => props.mapData, () => draw(), { deep: true })
</script>

<style scoped lang="scss">
.floor-2d-view {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: #0a1628;

  canvas {
    width: 100%;
    height: 100%;
    cursor: pointer;
  }
}

.tooltip {
  position: fixed;
  background: rgba(0, 20, 40, 0.95);
  border: 1px solid rgba(0, 200, 255, 0.5);
  border-radius: 6px;
  padding: 10px 14px;
  pointer-events: none;
  z-index: 1000;
  backdrop-filter: blur(10px);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);

  .tooltip-title {
    color: #ffffff;
    font-size: 14px;
    font-weight: 500;
    margin-bottom: 4px;
  }

  .tooltip-type {
    color: #88ccff;
    font-size: 12px;
  }

  .tooltip-device {
    color: #aaddff;
    font-size: 11px;
    margin-top: 2px;
  }

  .status {
    margin-top: 6px;
    padding: 2px 8px;
    border-radius: 3px;
    font-size: 11px;
    display: inline-block;

    &.normal {
      background: rgba(0, 200, 100, 0.3);
      color: #00ff88;
    }
    &.warning {
      background: rgba(255, 200, 0, 0.3);
      color: #ffcc00;
    }
    &.error {
      background: rgba(255, 50, 50, 0.3);
      color: #ff5555;
    }
    &.offline {
      background: rgba(100, 100, 100, 0.3);
      color: #888888;
    }
  }
}

.no-data {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
  color: #668899;

  .no-data-icon {
    font-size: 48px;
    margin-bottom: 16px;
    opacity: 0.5;
  }

  .no-data-text {
    font-size: 18px;
    margin-bottom: 8px;
  }

  .no-data-hint {
    font-size: 14px;
    opacity: 0.7;
  }
}
</style>
