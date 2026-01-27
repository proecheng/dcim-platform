<template>
  <FloorLayoutBase
    :width="width"
    :height="height"
    :viewBoxWidth="400"
    :viewBoxHeight="300"
    :showGrid="showGrid"
    :showLegend="showLegend"
  >
    <!-- 楼层标题 -->
    <text x="200" y="18" text-anchor="middle" fill="#fff" font-size="14" font-weight="bold">
      F1 1楼机房区A
    </text>

    <!-- 精密空调 (4台) -->
    <g class="precision-acs">
      <g v-for="(ac, index) in 4" :key="'ac-' + index">
        <rect
          :x="60 + index * 80"
          y="30"
          width="50"
          height="30"
          fill="#67C23A"
          stroke="#8ad16a"
          stroke-width="1"
          rx="2"
        />
        <text
          :x="85 + index * 80"
          y="48"
          text-anchor="middle"
          fill="#fff"
          font-size="9"
        >AC-{{ index + 1 }}</text>
      </g>
    </g>

    <!-- 冷通道标签 -->
    <text x="200" y="78" text-anchor="middle" fill="#6cb8ff" font-size="8">↓ 冷通道 ↓</text>

    <!-- 机柜行 - 4行5列共20个机柜 -->
    <g class="cabinet-rows">
      <!-- 第1行 (01-05) -->
      <g v-for="col in 5" :key="'row1-' + col">
        <rect
          :x="50 + (col - 1) * 65"
          y="85"
          width="55"
          height="35"
          fill="#409EFF"
          stroke="#6eb8ff"
          stroke-width="1"
          rx="2"
        />
        <text
          :x="77.5 + (col - 1) * 65"
          y="105"
          text-anchor="middle"
          fill="#fff"
          font-size="9"
        >{{ String(col).padStart(2, '0') }}</text>
      </g>

      <!-- 热通道标签 -->
      <text x="200" y="133" text-anchor="middle" fill="#ffb86c" font-size="8">↑ 热通道 ↑</text>

      <!-- 第2行 (06-10) -->
      <g v-for="col in 5" :key="'row2-' + col">
        <rect
          :x="50 + (col - 1) * 65"
          y="140"
          width="55"
          height="35"
          fill="#409EFF"
          stroke="#6eb8ff"
          stroke-width="1"
          rx="2"
        />
        <text
          :x="77.5 + (col - 1) * 65"
          y="160"
          text-anchor="middle"
          fill="#fff"
          font-size="9"
        >{{ String(col + 5).padStart(2, '0') }}</text>
      </g>

      <!-- 冷通道标签 -->
      <text x="200" y="188" text-anchor="middle" fill="#6cb8ff" font-size="8">↓ 冷通道 ↓</text>

      <!-- 第3行 (11-15) -->
      <g v-for="col in 5" :key="'row3-' + col">
        <rect
          :x="50 + (col - 1) * 65"
          y="195"
          width="55"
          height="35"
          fill="#409EFF"
          stroke="#6eb8ff"
          stroke-width="1"
          rx="2"
        />
        <text
          :x="77.5 + (col - 1) * 65"
          y="215"
          text-anchor="middle"
          fill="#fff"
          font-size="9"
        >{{ String(col + 10).padStart(2, '0') }}</text>
      </g>

      <!-- 热通道标签 -->
      <text x="200" y="243" text-anchor="middle" fill="#ffb86c" font-size="8">↑ 热通道 ↑</text>

      <!-- 第4行 (16-20) -->
      <g v-for="col in 5" :key="'row4-' + col">
        <rect
          :x="50 + (col - 1) * 65"
          y="250"
          width="55"
          height="35"
          fill="#409EFF"
          stroke="#6eb8ff"
          stroke-width="1"
          rx="2"
        />
        <text
          :x="77.5 + (col - 1) * 65"
          y="270"
          text-anchor="middle"
          fill="#fff"
          font-size="9"
        >{{ String(col + 15).padStart(2, '0') }}</text>
      </g>
    </g>

    <!-- UPS和配电区域 (底部右侧) -->
    <g class="power-area">
      <!-- UPS-1 -->
      <rect x="360" y="100" width="35" height="50" fill="#E6A23C" stroke="#f0c26a" stroke-width="1" rx="2" />
      <text x="377.5" y="128" text-anchor="middle" fill="#fff" font-size="8">UPS-1</text>

      <!-- UPS-2 -->
      <rect x="360" y="160" width="35" height="50" fill="#E6A23C" stroke="#f0c26a" stroke-width="1" rx="2" />
      <text x="377.5" y="188" text-anchor="middle" fill="#fff" font-size="8">UPS-2</text>

      <!-- 配电柜 -->
      <rect x="360" y="220" width="35" height="35" fill="#E6A23C" stroke="#f0c26a" stroke-width="1" rx="2" />
      <text x="377.5" y="240" text-anchor="middle" fill="#fff" font-size="7">配电</text>

      <!-- 消防控制 -->
      <rect x="360" y="260" width="35" height="25" fill="#F56C6C" stroke="#f89898" stroke-width="1" rx="2" />
      <text x="377.5" y="276" text-anchor="middle" fill="#fff" font-size="7">消防</text>
    </g>

    <template #legend>
      <div class="legend-item">
        <span class="legend-color" style="background: #409EFF;"></span>
        <span>机柜</span>
      </div>
      <div class="legend-item">
        <span class="legend-color" style="background: #67C23A;"></span>
        <span>空调</span>
      </div>
      <div class="legend-item">
        <span class="legend-color" style="background: #E6A23C;"></span>
        <span>UPS/配电</span>
      </div>
      <div class="legend-item">
        <span class="legend-color" style="background: #F56C6C;"></span>
        <span>消防</span>
      </div>
    </template>
  </FloorLayoutBase>
</template>

<script setup lang="ts">
import FloorLayoutBase from './FloorLayoutBase.vue'

defineProps({
  width: { type: Number, default: 800 },
  height: { type: Number, default: 500 },
  showGrid: { type: Boolean, default: true },
  showLegend: { type: Boolean, default: true }
})
</script>

<style scoped lang="scss">
</style>
