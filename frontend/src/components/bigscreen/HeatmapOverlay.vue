<!-- frontend/src/components/bigscreen/HeatmapOverlay.vue -->
<template>
  <div class="heatmap-overlay"></div>
</template>

<script setup lang="ts">
import { inject, watch, onMounted, onUnmounted, shallowRef, type ShallowRef } from 'vue'
import * as THREE from 'three'
import { useBigscreenStore } from '@/stores/bigscreen'
import { createHeatmapPlane, updateHeatmapColors } from '@/utils/three/heatmapHelper'

const store = useBigscreenStore()
const scene = inject<ShallowRef<THREE.Scene | null>>('three-scene')

const heatmapMesh = shallowRef<THREE.Mesh | null>(null)

// 初始化热力图
function initHeatmap() {
  if (!scene?.value || !store.layout) return

  // 清除旧热力图
  if (heatmapMesh.value) {
    scene.value.remove(heatmapMesh.value)
  }

  const { width, length } = store.layout.dimensions
  const mesh = createHeatmapPlane(width, length, 30)
  mesh.visible = store.layers.heatmap

  scene.value.add(mesh)
  heatmapMesh.value = mesh

  // 初始更新
  updateHeatmap()
}

// 更新热力图数据
function updateHeatmap() {
  if (!heatmapMesh.value || !store.layout) return

  // 收集温度数据点
  const temperatureData: Array<{ x: number; z: number; temp: number }> = []

  store.layout.modules.forEach(module => {
    module.cabinets.forEach(cabinet => {
      const data = store.deviceData[cabinet.id]
      const temp = data?.temperature || cabinet.temperature || 24
      temperatureData.push({
        x: module.position.x + cabinet.position.x,
        z: module.position.z + cabinet.position.z,
        temp
      })
    })
  })

  const { width, length } = store.layout.dimensions
  updateHeatmapColors(heatmapMesh.value, temperatureData, width, length)
}

// 设置可见性
function setVisible(visible: boolean) {
  if (heatmapMesh.value) {
    heatmapMesh.value.visible = visible
  }
}

// 监听布局变化
watch(() => store.layout, () => {
  initHeatmap()
}, { immediate: true })

// 监听设备数据变化
watch(() => store.deviceData, () => {
  updateHeatmap()
}, { deep: true })

// 监听图层开关
watch(() => store.layers.heatmap, (visible) => {
  setVisible(visible)
})

onMounted(() => {
  setTimeout(initHeatmap, 150)
})

onUnmounted(() => {
  if (scene?.value && heatmapMesh.value) {
    scene.value.remove(heatmapMesh.value)
  }
})

defineExpose({
  updateHeatmap,
  setVisible
})
</script>

<style scoped>
.heatmap-overlay {
  display: none;
}
</style>
