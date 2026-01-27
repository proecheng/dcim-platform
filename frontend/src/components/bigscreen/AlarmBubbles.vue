<!-- frontend/src/components/bigscreen/AlarmBubbles.vue -->
<template>
  <div class="alarm-bubbles"></div>
</template>

<script setup lang="ts">
import { inject, watch, onMounted, onUnmounted, type ShallowRef } from 'vue'
import * as THREE from 'three'
import { CSS2DObject } from 'three/examples/jsm/renderers/CSS2DRenderer.js'
import { useBigscreenStore } from '@/stores/bigscreen'
import type { BigscreenAlarm } from '@/types/bigscreen'

const store = useBigscreenStore()
const scene = inject<ShallowRef<THREE.Scene | null>>('three-scene')

// 气泡映射
const bubbleMap = new Map<number | string, CSS2DObject>()

// 告警等级颜色
const ALARM_COLORS = {
  critical: '#ff3300',
  major: '#ff6600',
  minor: '#ffcc00',
  info: '#00ccff'
}

// 创建告警气泡
function createBubble(alarm: BigscreenAlarm): CSS2DObject {
  const color = ALARM_COLORS[alarm.level]

  const div = document.createElement('div')
  div.className = `alarm-bubble alarm-${alarm.level}`
  div.innerHTML = `
    <div class="bubble-icon">⚠</div>
    <div class="bubble-content">
      <div class="bubble-title">${alarm.message}</div>
      <div class="bubble-detail">
        ${alarm.value !== undefined ? `当前: ${alarm.value}` : ''}
        ${alarm.threshold !== undefined ? ` / 阈值: ${alarm.threshold}` : ''}
      </div>
      ${alarm.duration ? `<div class="bubble-duration">持续: ${alarm.duration}</div>` : ''}
    </div>
  `

  div.style.cssText = `
    background: rgba(20, 0, 0, 0.9);
    border: 2px solid ${color};
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 12px;
    color: #fff;
    max-width: 200px;
    pointer-events: auto;
    cursor: pointer;
    animation: alarmPulse 2s ease-in-out infinite;
    box-shadow: 0 0 20px ${color}40;
  `

  // 添加动画样式
  const style = document.createElement('style')
  style.textContent = `
    @keyframes alarmPulse {
      0%, 100% { transform: translateX(-50%) scale(1); opacity: 1; }
      50% { transform: translateX(-50%) scale(1.05); opacity: 0.9; }
    }
    .bubble-icon { font-size: 16px; color: ${color}; margin-bottom: 4px; }
    .bubble-title { font-weight: bold; margin-bottom: 2px; }
    .bubble-detail { font-size: 11px; color: #aaa; }
    .bubble-duration { font-size: 10px; color: #888; margin-top: 4px; }
  `
  div.appendChild(style)

  // 点击事件
  div.addEventListener('click', () => {
    store.selectDevice(alarm.deviceId)
  })

  const bubble = new CSS2DObject(div)
  bubble.name = `alarm_${alarm.id}`

  return bubble
}

// 获取设备位置
function getDevicePosition(deviceId: string): THREE.Vector3 | null {
  if (!store.layout) return null

  for (const module of store.layout.modules) {
    const cabinet = module.cabinets.find(c => c.id === deviceId)
    if (cabinet) {
      return new THREE.Vector3(
        module.position.x + cabinet.position.x,
        (cabinet.position.y || 0) + 2.5,
        module.position.z + cabinet.position.z
      )
    }
  }
  return null
}

// 更新告警气泡
function updateBubbles() {
  if (!scene?.value) return

  // 移除已解除的告警
  const activeAlarmIds = new Set(store.activeAlarms.map(a => a.id))
  bubbleMap.forEach((bubble, alarmId) => {
    if (!activeAlarmIds.has(alarmId)) {
      scene.value!.remove(bubble)
      if (bubble.element && bubble.element.parentNode) {
        bubble.element.parentNode.removeChild(bubble.element)
      }
      bubbleMap.delete(alarmId)
    }
  })

  // 添加新告警
  store.activeAlarms.forEach(alarm => {
    if (!bubbleMap.has(alarm.id)) {
      const position = getDevicePosition(alarm.deviceId)
      if (position) {
        const bubble = createBubble(alarm)
        bubble.position.copy(position)
        scene.value!.add(bubble)
        bubbleMap.set(alarm.id, bubble)
      }
    }
  })
}

// 清除所有气泡
function clearBubbles() {
  bubbleMap.forEach(bubble => {
    if (scene?.value) {
      scene.value.remove(bubble)
    }
    if (bubble.element && bubble.element.parentNode) {
      bubble.element.parentNode.removeChild(bubble.element)
    }
  })
  bubbleMap.clear()
}

// 监听告警变化
watch(() => store.activeAlarms, () => {
  updateBubbles()
}, { deep: true, immediate: true })

onMounted(() => {
  setTimeout(updateBubbles, 200)
})

onUnmounted(() => {
  clearBubbles()
})

defineExpose({
  updateBubbles,
  clearBubbles
})
</script>

<style scoped>
.alarm-bubbles {
  display: none;
}
</style>
