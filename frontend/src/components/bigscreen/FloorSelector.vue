<template>
  <DraggablePanel
    ref="panelRef"
    title="楼层选择"
    panelId="floorSelector"
    :initialX="panelState.x"
    :initialY="panelState.y"
    :initialCollapsed="panelState.collapsed"
    @positionChange="handlePositionChange"
    @collapseChange="handleCollapseChange"
  >
    <div class="floor-selector-content">
      <div class="floor-buttons">
        <button
          v-for="floor in floors"
          :key="floor.floor_code"
          :class="['floor-btn', { active: currentFloor === floor.floor_code }]"
          @click="selectFloor(floor.floor_code)"
        >
          {{ floor.floor_code }}
          <span class="floor-name">{{ floor.floor_name }}</span>
        </button>
      </div>

      <div class="view-toggle">
        <button
          :class="['view-btn', { active: viewMode === '2d' }]"
          @click="setViewMode('2d')"
        >
          2D 平面
        </button>
        <button
          :class="['view-btn', { active: viewMode === '3d' }]"
          @click="setViewMode('3d')"
        >
          3D 场景
        </button>
      </div>

      <div v-if="loading" class="loading-indicator">
        加载中...
      </div>
    </div>
  </DraggablePanel>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useBigscreenStore } from '@/stores/bigscreen'
import { DraggablePanel } from '@/components/bigscreen/ui'
import { getFloors, getFloorMap, type FloorInfo, type FloorMapData } from '@/api/modules/floorMap'

const props = defineProps<{
  modelValue?: string
  mode?: '2d' | '3d'
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', floor: string): void
  (e: 'update:mode', mode: '2d' | '3d'): void
  (e: 'floorChange', data: { floor: string; mode: '2d' | '3d'; mapData: any }): void
}>()

const store = useBigscreenStore()
const panelRef = ref()

// 从store获取面板状态
const panelState = computed(() => store.panelStates.floorSelector || { x: 20, y: 120, collapsed: false })

const floors = ref<FloorInfo[]>([])
const currentFloor = ref(props.modelValue || 'F1')
const viewMode = ref<'2d' | '3d'>(props.mode || '3d')
const loading = ref(false)

onMounted(async () => {
  // 加载面板状态
  store.loadPanelStates()

  try {
    const res = await getFloors()
    const data = (res as any).data || res
    floors.value = data.floors || []

    // 如果没有数据，使用默认楼层
    if (floors.value.length === 0) {
      floors.value = [
        { floor_code: 'B1', floor_name: '地下制冷机房', map_types: ['2d', '3d'] },
        { floor_code: 'F1', floor_name: '1楼机房区A', map_types: ['2d', '3d'] },
        { floor_code: 'F2', floor_name: '2楼机房区B', map_types: ['2d', '3d'] },
        { floor_code: 'F3', floor_name: '3楼办公监控', map_types: ['2d', '3d'] }
      ]
    }

    // 加载默认楼层
    await loadFloorMap()
  } catch (err) {
    console.error('Failed to load floors:', err)
    // 使用默认数据
    floors.value = [
      { floor_code: 'B1', floor_name: '地下制冷机房', map_types: ['2d', '3d'] },
      { floor_code: 'F1', floor_name: '1楼机房区A', map_types: ['2d', '3d'] },
      { floor_code: 'F2', floor_name: '2楼机房区B', map_types: ['2d', '3d'] },
      { floor_code: 'F3', floor_name: '3楼办公监控', map_types: ['2d', '3d'] }
    ]
  }
})

async function selectFloor(floorCode: string) {
  currentFloor.value = floorCode
  emit('update:modelValue', floorCode)
  await loadFloorMap()
}

async function setViewMode(mode: '2d' | '3d') {
  viewMode.value = mode
  emit('update:mode', mode)
  await loadFloorMap()
}

async function loadFloorMap() {
  if (loading.value) return
  loading.value = true

  try {
    const res = await getFloorMap(currentFloor.value, viewMode.value)
    const data = (res as any).data || res
    const mapData = data.map_data

    emit('floorChange', {
      floor: currentFloor.value,
      mode: viewMode.value,
      mapData
    })
  } catch (err) {
    console.error('Failed to load floor map:', err)
    // 发送空数据以便组件可以显示占位内容
    emit('floorChange', {
      floor: currentFloor.value,
      mode: viewMode.value,
      mapData: null
    })
  } finally {
    loading.value = false
  }
}

watch(() => props.modelValue, (val) => {
  if (val && val !== currentFloor.value) {
    currentFloor.value = val
    loadFloorMap()
  }
})

watch(() => props.mode, (val) => {
  if (val && val !== viewMode.value) {
    viewMode.value = val
    loadFloorMap()
  }
})

function handlePositionChange(data: { id: string; x: number; y: number }) {
  store.updatePanelPosition(data.id, data.x, data.y)
}

function handleCollapseChange(data: { id: string; collapsed: boolean }) {
  store.updatePanelCollapsed(data.id, data.collapsed)
}
</script>

<style scoped lang="scss">
.floor-selector-content {
  min-width: 130px;
  padding: 12px;
}

.floor-buttons {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 12px;
}

.floor-btn {
  background: rgba(0, 100, 150, 0.3);
  border: 1px solid rgba(0, 200, 255, 0.2);
  border-radius: 4px;
  color: #88ccff;
  padding: 8px 12px;
  cursor: pointer;
  transition: all 0.2s ease;
  text-align: left;
  font-size: 14px;
  font-weight: 500;

  .floor-name {
    display: block;
    font-size: 10px;
    font-weight: normal;
    color: #668899;
    margin-top: 2px;
  }

  &:hover {
    background: rgba(0, 150, 200, 0.4);
    border-color: rgba(0, 200, 255, 0.5);
    transform: translateX(2px);
  }

  &.active {
    background: rgba(0, 200, 255, 0.3);
    border-color: #00ccff;
    color: #ffffff;
    box-shadow: 0 0 10px rgba(0, 200, 255, 0.3);

    .floor-name {
      color: #aaddff;
    }
  }
}

.view-toggle {
  display: flex;
  gap: 4px;
  border-top: 1px solid rgba(0, 200, 255, 0.2);
  padding-top: 10px;
}

.view-btn {
  flex: 1;
  background: rgba(0, 100, 150, 0.3);
  border: 1px solid rgba(0, 200, 255, 0.2);
  border-radius: 4px;
  color: #88ccff;
  padding: 6px 8px;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.2s ease;

  &:hover {
    background: rgba(0, 150, 200, 0.4);
  }

  &.active {
    background: rgba(0, 200, 255, 0.3);
    border-color: #00ccff;
    color: #ffffff;
    box-shadow: 0 0 8px rgba(0, 200, 255, 0.3);
  }
}

.loading-indicator {
  text-align: center;
  color: #668899;
  font-size: 11px;
  margin-top: 8px;
  padding: 4px;
  background: rgba(0, 100, 150, 0.2);
  border-radius: 4px;
}
</style>
