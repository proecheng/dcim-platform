<!-- frontend/src/components/bigscreen/ThreeScene.vue -->
<template>
  <div ref="containerRef" class="three-scene-container">
    <slot v-if="isInitialized" />
  </div>
</template>

<script setup lang="ts">
import { ref, provide } from 'vue'
import { useThreeScene } from '@/composables/bigscreen/useThreeScene'

const containerRef = ref<HTMLElement | null>(null)

const {
  scene,
  camera,
  renderer,
  controls,
  isInitialized
} = useThreeScene(containerRef, {
  backgroundColor: 0x0a0a1a
})

// 提供给子组件
provide('three-scene', scene)
provide('three-camera', camera)
provide('three-renderer', renderer)
provide('three-controls', controls)

// 暴露给父组件
defineExpose({
  scene,
  camera,
  renderer,
  controls,
  isInitialized
})
</script>

<style scoped>
.three-scene-container {
  width: 100%;
  height: 100%;
  position: absolute;
  top: 0;
  left: 0;
  overflow: hidden;
}

.three-scene-container :deep(canvas) {
  display: block;
}
</style>
