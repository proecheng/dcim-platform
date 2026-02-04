<!-- frontend/src/components/bigscreen/DataCenterModel.vue -->
<template>
  <div class="datacenter-model">
    <!-- 这是一个逻辑组件，不渲染DOM -->
  </div>
</template>

<script setup lang="ts">
import { inject, watch, onMounted, onUnmounted, shallowRef, type ShallowRef } from 'vue'
import * as THREE from 'three'
import { useBigscreenStore } from '@/stores/bigscreen'
import {
  createCabinet,
  createCoolingUnit,
  createUPSRoom,
  updateCabinetStatus
} from '@/utils/three/modelGenerator'
import type { DataCenterLayout, ModuleConfig } from '@/types/bigscreen'

const store = useBigscreenStore()

// 注入场景
const scene = inject<ShallowRef<THREE.Scene | null>>('three-scene')

// 数据中心模型组
const dataCenterGroup = shallowRef<THREE.Group | null>(null)

// 机柜映射 (id -> mesh)
const cabinetMap = new Map<string, THREE.Group>()

// 创建数据中心模型
function createDataCenter(layout: DataCenterLayout) {
  if (!scene?.value) return

  // 清除旧模型
  if (dataCenterGroup.value) {
    scene.value.remove(dataCenterGroup.value)
    dataCenterGroup.value = null
    cabinetMap.clear()
  }

  const group = new THREE.Group()
  group.name = 'datacenter'

  // 创建模块
  layout.modules.forEach((module) => {
    const moduleGroup = createModule(module)
    group.add(moduleGroup)
  })

  // 创建基础设施
  if (layout.infrastructure.upsRoom) {
    const ups = createUPSRoom(
      layout.infrastructure.upsRoom.position,
      layout.infrastructure.upsRoom.size
    )
    group.add(ups)
  }

  scene.value.add(group)
  dataCenterGroup.value = group
}

// 创建单个模块
function createModule(config: ModuleConfig): THREE.Group {
  const group = new THREE.Group()
  group.name = `module_${config.id}`
  group.position.set(config.position.x, 0, config.position.z)
  group.rotation.y = (config.rotation * Math.PI) / 180

  // 创建机柜
  config.cabinets.forEach((cabinetConfig) => {
    const cabinet = createCabinet(cabinetConfig)
    group.add(cabinet)
    cabinetMap.set(cabinetConfig.id, cabinet)
  })

  // 创建空调
  config.coolingUnits.forEach((cooling) => {
    const coolingUnit = createCoolingUnit(cooling.position)
    coolingUnit.name = `cooling_${cooling.id}`
    group.add(coolingUnit)
  })

  return group
}

// 生成默认布局 (演示用)
function generateDefaultLayout(): DataCenterLayout {
  const cabinets = []

  // 生成两排机柜
  for (let row = 0; row < 2; row++) {
    for (let i = 0; i < 8; i++) {
      cabinets.push({
        id: `cab_${row}_${i}`,
        name: `机柜 ${String.fromCharCode(65 + row)}-${i + 1}`,
        position: {
          x: -12 + i * 3,
          y: 0,
          z: -5 + row * 10
        },
        size: { width: 0.6, height: 2.0, depth: 1.0 },
        // 使用确定性状态（基于位置），避免随机
        status: ((row * 8 + i) % 11 === 0) ? 'alarm' : 'normal' as const
      })
    }
  }

  return {
    name: '演示数据中心',
    dimensions: { width: 50, length: 30, height: 5 },
    modules: [
      {
        id: 'module_a',
        name: '模块A',
        position: { x: 0, z: 0 },
        rotation: 0,
        cabinets,
        coolingUnits: [
          { id: 'ac_1', position: { x: -15, z: 0 } },
          { id: 'ac_2', position: { x: 15, z: 0 } }
        ]
      }
    ],
    infrastructure: {
      upsRoom: {
        position: { x: -20, z: -10 },
        size: { width: 8, length: 6 }
      }
    }
  }
}

// 更新机柜数据
function updateCabinets() {
  cabinetMap.forEach((cabinet, id) => {
    const data = store.deviceData[id]
    if (data) {
      updateCabinetStatus(cabinet, data.status)
    }
  })
}

// 监听布局变化
watch(
  () => store.layout,
  (layout) => {
    if (layout) {
      createDataCenter(layout)
    }
  },
  { immediate: true }
)

// 监听设备数据变化
watch(
  () => store.deviceData,
  () => {
    updateCabinets()
  },
  { deep: true }
)

onMounted(() => {
  // 如果没有布局，使用默认布局
  if (!store.layout) {
    const defaultLayout = generateDefaultLayout()
    store.setLayout(defaultLayout)
  }
})

onUnmounted(() => {
  if (scene?.value && dataCenterGroup.value) {
    scene.value.remove(dataCenterGroup.value)
  }
  cabinetMap.clear()
})

// 暴露方法
defineExpose({
  cabinetMap,
  updateCabinets
})
</script>

<style scoped>
.datacenter-model {
  display: none;
}
</style>
