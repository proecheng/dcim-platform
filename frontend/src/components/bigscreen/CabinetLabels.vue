<!-- frontend/src/components/bigscreen/CabinetLabels.vue -->
<template>
  <div class="cabinet-labels">
    <!-- 逻辑组件，不渲染DOM -->
  </div>
</template>

<script setup lang="ts">
import { inject, watch, onMounted, onUnmounted, shallowRef, type ShallowRef } from 'vue'
import * as THREE from 'three'
import { CSS2DObject } from 'three/examples/jsm/renderers/CSS2DRenderer.js'
import { useBigscreenStore } from '@/stores/bigscreen'

const store = useBigscreenStore()
const scene = inject<ShallowRef<THREE.Scene | null>>('three-scene')

// 标签映射
const labelMap = new Map<string, CSS2DObject>()

// 创建紧凑型功率标签（不遮挡机柜）
function createLabel(cabinetId: string, name: string, power: number, position: THREE.Vector3): CSS2DObject {
  const div = document.createElement('div')
  div.className = 'cabinet-compact-label'
  updateLabelDiv(div, name, power)

  const label = new CSS2DObject(div)
  // 标签位置：机柜右前角上方，偏移避免遮挡
  label.position.copy(position)
  label.position.x += 0.35  // 偏移到右侧
  label.position.y += 2.15  // 略高于机柜顶部
  label.position.z += 0.3   // 偏移到前方
  label.name = `label_${cabinetId}`

  return label
}

// 更新标签内容 - 紧凑型设计
function updateLabelDiv(div: HTMLDivElement, name: string, power: number) {
  // 提取机柜编号（如 A-01 从 "A区1号柜" 中提取）
  const shortName = name.match(/([A-Z])[区]?(\d+)/i)
  const displayName = shortName ? `${shortName[1]}${shortName[2]}` : name.slice(0, 4)

  div.innerHTML = `
    <div class="compact-power">${power.toFixed(1)}<span class="unit">kW</span></div>
  `
  div.style.cssText = `
    background: rgba(0, 20, 40, 0.85);
    border: 1px solid rgba(0, 136, 255, 0.5);
    border-radius: 4px;
    padding: 3px 6px;
    font-size: 10px;
    color: #00ccff;
    font-weight: bold;
    text-align: center;
    pointer-events: none;
    white-space: nowrap;
    transform: translateX(-50%);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
  `
}

// 初始化所有标签
function initLabels() {
  if (!scene?.value || !store.layout) return

  // 清除旧标签
  clearLabels()

  // 为每个机柜创建标签
  store.layout.modules.forEach(module => {
    module.cabinets.forEach(cabinet => {
      const power = store.deviceData[cabinet.id]?.power || cabinet.power || 0
      const position = new THREE.Vector3(
        module.position.x + cabinet.position.x,
        cabinet.position.y || 0,
        module.position.z + cabinet.position.z
      )

      const label = createLabel(cabinet.id, cabinet.name, power, position)
      scene.value!.add(label)
      labelMap.set(cabinet.id, label)
    })
  })
}

// 更新标签数据
function updateLabels() {
  labelMap.forEach((label, cabinetId) => {
    const data = store.deviceData[cabinetId]
    const cabinet = store.layout?.modules
      .flatMap(m => m.cabinets)
      .find(c => c.id === cabinetId)

    if (cabinet && label.element) {
      const power = data?.power || cabinet.power || 0
      updateLabelDiv(label.element as HTMLDivElement, cabinet.name, power)
    }
  })
}

// 设置标签可见性
function setLabelsVisible(visible: boolean) {
  labelMap.forEach(label => {
    label.visible = visible
    if (label.element) {
      (label.element as HTMLDivElement).style.display = visible ? 'block' : 'none'
    }
  })
}

// 清除所有标签
function clearLabels() {
  labelMap.forEach(label => {
    if (scene?.value) {
      scene.value.remove(label)
    }
    if (label.element && label.element.parentNode) {
      label.element.parentNode.removeChild(label.element)
    }
  })
  labelMap.clear()
}

// 监听布局变化
watch(() => store.layout, () => {
  initLabels()
}, { immediate: true })

// 监听设备数据变化
watch(() => store.deviceData, () => {
  updateLabels()
}, { deep: true })

// 监听图层开关
watch(() => store.layers.power, (visible) => {
  setLabelsVisible(visible)
})

onMounted(() => {
  // 延迟初始化，确保场景已就绪
  setTimeout(initLabels, 100)
})

onUnmounted(() => {
  clearLabels()
})

defineExpose({
  initLabels,
  updateLabels,
  setLabelsVisible
})
</script>

<style scoped>
.cabinet-labels {
  display: none;
}
</style>
