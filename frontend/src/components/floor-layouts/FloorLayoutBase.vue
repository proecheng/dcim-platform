<template>
  <div class="floor-layout" :style="{ width: width + 'px', height: height + 'px' }">
    <svg
      :viewBox="`0 0 ${viewBoxWidth} ${viewBoxHeight}`"
      preserveAspectRatio="xMidYMid meet"
      xmlns="http://www.w3.org/2000/svg"
    >
      <!-- 背景 -->
      <rect
        x="0" y="0"
        :width="viewBoxWidth" :height="viewBoxHeight"
        fill="#1a2a4a"
        stroke="#2a4a6a"
        stroke-width="2"
      />

      <!-- 网格线 -->
      <g class="grid-lines" v-if="showGrid">
        <line
          v-for="i in Math.floor(viewBoxWidth / gridSize)"
          :key="'v' + i"
          :x1="i * gridSize" y1="0"
          :x2="i * gridSize" :y2="viewBoxHeight"
          stroke="#2a3a5a"
          stroke-width="0.5"
        />
        <line
          v-for="i in Math.floor(viewBoxHeight / gridSize)"
          :key="'h' + i"
          x1="0" :y1="i * gridSize"
          :x2="viewBoxWidth" :y2="i * gridSize"
          stroke="#2a3a5a"
          stroke-width="0.5"
        />
      </g>

      <!-- 楼层内容插槽 -->
      <slot></slot>

      <!-- 设备标注 -->
      <g class="device-labels">
        <slot name="labels"></slot>
      </g>
    </svg>

    <!-- 图例 -->
    <div class="layout-legend" v-if="showLegend">
      <slot name="legend">
        <div class="legend-item">
          <span class="legend-color cabinet"></span>
          <span>机柜</span>
        </div>
        <div class="legend-item">
          <span class="legend-color ac"></span>
          <span>空调</span>
        </div>
        <div class="legend-item">
          <span class="legend-color ups"></span>
          <span>UPS</span>
        </div>
      </slot>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps({
  width: { type: Number, default: 800 },
  height: { type: Number, default: 500 },
  viewBoxWidth: { type: Number, default: 400 },
  viewBoxHeight: { type: Number, default: 250 },
  showGrid: { type: Boolean, default: true },
  showLegend: { type: Boolean, default: true },
  gridSize: { type: Number, default: 20 }
})
</script>

<style scoped lang="scss">
.floor-layout {
  position: relative;
  background: var(--bg-primary, #0a1628);
  border-radius: 8px;
  overflow: hidden;

  svg {
    width: 100%;
    height: 100%;
  }

  .layout-legend {
    position: absolute;
    bottom: 10px;
    right: 10px;
    background: rgba(0, 0, 0, 0.6);
    padding: 8px 12px;
    border-radius: 4px;
    display: flex;
    gap: 12px;

    .legend-item {
      display: flex;
      align-items: center;
      gap: 4px;
      font-size: 12px;
      color: var(--text-primary, rgba(255, 255, 255, 0.95));

      .legend-color {
        width: 12px;
        height: 12px;
        border-radius: 2px;

        &.cabinet {
          background: var(--primary-color, #1890ff);
        }

        &.ac {
          background: var(--success-color, #52c41a);
        }

        &.ups {
          background: var(--warning-color, #faad14);
        }
      }
    }
  }
}
</style>
