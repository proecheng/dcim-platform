<template>
  <FloorLayoutBase
    :width="width"
    :height="height"
    :viewBoxWidth="400"
    :viewBoxHeight="260"
    :showGrid="showGrid"
    :showLegend="showLegend"
  >
    <!-- 楼层标题 -->
    <text x="200" y="18" text-anchor="middle" fill="#fff" font-size="14" font-weight="bold">
      F3 3楼办公监控
    </text>

    <!-- 监控中心 -->
    <g class="monitoring-center">
      <rect x="30" y="30" width="120" height="60" fill="#3a5a7a" stroke="#5a8aaa" stroke-width="1" rx="3" />
      <text x="90" y="55" text-anchor="middle" fill="#fff" font-size="10">监控中心</text>
      <text x="90" y="70" text-anchor="middle" fill="#aaa" font-size="7">NOC</text>

      <!-- 监控台图标 -->
      <rect x="45" y="75" width="15" height="8" fill="#5a7a9a" rx="1" />
      <rect x="70" y="75" width="15" height="8" fill="#5a7a9a" rx="1" />
      <rect x="95" y="75" width="15" height="8" fill="#5a7a9a" rx="1" />
      <rect x="120" y="75" width="15" height="8" fill="#5a7a9a" rx="1" />
    </g>

    <!-- 会议室 -->
    <g class="meeting-room">
      <rect x="170" y="30" width="90" height="60" fill="#3a5a7a" stroke="#5a8aaa" stroke-width="1" rx="3" />
      <text x="215" y="55" text-anchor="middle" fill="#fff" font-size="10">会议室</text>
      <text x="215" y="70" text-anchor="middle" fill="#aaa" font-size="7">Conference</text>
    </g>

    <!-- 精密空调 (2台) -->
    <g class="precision-acs">
      <g v-for="(ac, index) in 2" :key="'ac-' + index">
        <rect
          :x="290 + index * 55"
          y="30"
          width="45"
          height="30"
          fill="#67C23A"
          stroke="#8ad16a"
          stroke-width="1"
          rx="2"
        />
        <text
          :x="312.5 + index * 55"
          y="48"
          text-anchor="middle"
          fill="#fff"
          font-size="8"
        >AC-{{ index + 1 }}</text>
      </g>
    </g>

    <!-- 分隔线 -->
    <line x1="30" y1="105" x2="370" y2="105" stroke="#4a6a8a" stroke-width="1" stroke-dasharray="5,3" />
    <text x="200" y="115" text-anchor="middle" fill="#6a8aaa" font-size="7">机房区域</text>

    <!-- 机柜区 - 2行4列共8个机柜 -->
    <g class="cabinet-rows">
      <!-- 冷通道标签 -->
      <text x="160" y="135" text-anchor="middle" fill="#6cb8ff" font-size="8">↓ 冷通道 ↓</text>

      <!-- 第1行 (01-04) -->
      <g v-for="col in 4" :key="'row1-' + col">
        <rect
          :x="50 + (col - 1) * 70"
          y="145"
          width="55"
          height="35"
          fill="#409EFF"
          stroke="#6eb8ff"
          stroke-width="1"
          rx="2"
        />
        <text
          :x="77.5 + (col - 1) * 70"
          y="165"
          text-anchor="middle"
          fill="#fff"
          font-size="9"
        >{{ String(col).padStart(2, '0') }}</text>
      </g>

      <!-- 热通道标签 -->
      <text x="160" y="195" text-anchor="middle" fill="#ffb86c" font-size="8">↑ 热通道 ↑</text>

      <!-- 第2行 (05-08) -->
      <g v-for="col in 4" :key="'row2-' + col">
        <rect
          :x="50 + (col - 1) * 70"
          y="200"
          width="55"
          height="35"
          fill="#409EFF"
          stroke="#6eb8ff"
          stroke-width="1"
          rx="2"
        />
        <text
          :x="77.5 + (col - 1) * 70"
          y="220"
          text-anchor="middle"
          fill="#fff"
          font-size="9"
        >{{ String(col + 4).padStart(2, '0') }}</text>
      </g>
    </g>

    <!-- UPS和配电区域 (右侧) -->
    <g class="power-area">
      <!-- UPS-1 -->
      <rect x="320" y="130" width="45" height="50" fill="#E6A23C" stroke="#f0c26a" stroke-width="1" rx="2" />
      <text x="342.5" y="158" text-anchor="middle" fill="#fff" font-size="8">UPS-1</text>

      <!-- 配电柜 -->
      <rect x="320" y="190" width="45" height="40" fill="#E6A23C" stroke="#f0c26a" stroke-width="1" rx="2" />
      <text x="342.5" y="213" text-anchor="middle" fill="#fff" font-size="8">配电柜</text>
    </g>

    <template #legend>
      <div class="legend-item">
        <span class="legend-color" style="background: #3a5a7a;"></span>
        <span>办公区</span>
      </div>
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
