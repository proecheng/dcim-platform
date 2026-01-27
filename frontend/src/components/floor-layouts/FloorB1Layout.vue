<template>
  <FloorLayoutBase
    :width="width"
    :height="height"
    :viewBoxWidth="400"
    :viewBoxHeight="280"
    :showGrid="showGrid"
    :showLegend="showLegend"
  >
    <!-- 楼层标题 -->
    <text x="200" y="18" text-anchor="middle" fill="#fff" font-size="14" font-weight="bold">
      B1 地下制冷机房
    </text>

    <!-- 冷却塔区域 -->
    <g class="cooling-towers">
      <!-- CT-1 -->
      <rect x="80" y="30" width="60" height="40" fill="#2a5a8a" stroke="#4a8aba" stroke-width="1" rx="2" />
      <text x="110" y="55" text-anchor="middle" fill="#fff" font-size="10">CT-1</text>
      <text x="110" y="65" text-anchor="middle" fill="#aaa" font-size="7">冷却塔</text>

      <!-- CT-2 -->
      <rect x="260" y="30" width="60" height="40" fill="#2a5a8a" stroke="#4a8aba" stroke-width="1" rx="2" />
      <text x="290" y="55" text-anchor="middle" fill="#fff" font-size="10">CT-2</text>
      <text x="290" y="65" text-anchor="middle" fill="#aaa" font-size="7">冷却塔</text>
    </g>

    <!-- 冷水机组 -->
    <g class="chillers">
      <!-- CH-1 -->
      <rect x="60" y="90" width="70" height="50" fill="#2a5a8a" stroke="#4a8aba" stroke-width="1" rx="2" />
      <text x="95" y="118" text-anchor="middle" fill="#fff" font-size="10">CH-1</text>
      <text x="95" y="130" text-anchor="middle" fill="#aaa" font-size="7">冷水机组</text>

      <!-- CH-2 -->
      <rect x="270" y="90" width="70" height="50" fill="#2a5a8a" stroke="#4a8aba" stroke-width="1" rx="2" />
      <text x="305" y="118" text-anchor="middle" fill="#fff" font-size="10">CH-2</text>
      <text x="305" y="130" text-anchor="middle" fill="#aaa" font-size="7">冷水机组</text>
    </g>

    <!-- 冷冻水泵 -->
    <g class="chilled-water-pumps">
      <!-- CHWP-1 -->
      <rect x="60" y="160" width="50" height="35" fill="#67C23A" stroke="#8ad16a" stroke-width="1" rx="2" />
      <text x="85" y="180" text-anchor="middle" fill="#fff" font-size="8">CHWP-1</text>
      <text x="85" y="190" text-anchor="middle" fill="#ddd" font-size="6">冷冻水泵</text>

      <!-- CHWP-2 -->
      <rect x="290" y="160" width="50" height="35" fill="#67C23A" stroke="#8ad16a" stroke-width="1" rx="2" />
      <text x="315" y="180" text-anchor="middle" fill="#fff" font-size="8">CHWP-2</text>
      <text x="315" y="190" text-anchor="middle" fill="#ddd" font-size="6">冷冻水泵</text>
    </g>

    <!-- 冷却水泵 -->
    <g class="cooling-water-pumps">
      <!-- CWP-1 -->
      <rect x="130" y="160" width="50" height="35" fill="#67C23A" stroke="#8ad16a" stroke-width="1" rx="2" />
      <text x="155" y="180" text-anchor="middle" fill="#fff" font-size="8">CWP-1</text>
      <text x="155" y="190" text-anchor="middle" fill="#ddd" font-size="6">冷却水泵</text>

      <!-- CWP-2 -->
      <rect x="220" y="160" width="50" height="35" fill="#67C23A" stroke="#8ad16a" stroke-width="1" rx="2" />
      <text x="245" y="180" text-anchor="middle" fill="#fff" font-size="8">CWP-2</text>
      <text x="245" y="190" text-anchor="middle" fill="#ddd" font-size="6">冷却水泵</text>
    </g>

    <!-- 配电与控制柜 -->
    <g class="power-distribution">
      <!-- 配电柜 -->
      <rect x="60" y="215" width="80" height="35" fill="#E6A23C" stroke="#f0c26a" stroke-width="1" rx="2" />
      <text x="100" y="235" text-anchor="middle" fill="#fff" font-size="9">配电柜</text>
      <text x="100" y="245" text-anchor="middle" fill="#ddd" font-size="6">PDU</text>

      <!-- 控制柜 -->
      <rect x="260" y="215" width="80" height="35" fill="#409EFF" stroke="#6eb8ff" stroke-width="1" rx="2" />
      <text x="300" y="235" text-anchor="middle" fill="#fff" font-size="9">控制柜</text>
      <text x="300" y="245" text-anchor="middle" fill="#ddd" font-size="6">PLC</text>
    </g>

    <!-- 管道连接线 -->
    <g class="pipe-connections">
      <!-- 冷却塔到冷水机组 -->
      <line x1="110" y1="70" x2="95" y2="90" stroke="#4a9aba" stroke-width="1.5" stroke-dasharray="4,2" />
      <line x1="290" y1="70" x2="305" y2="90" stroke="#4a9aba" stroke-width="1.5" stroke-dasharray="4,2" />

      <!-- 冷水机组到水泵 -->
      <line x1="95" y1="140" x2="85" y2="160" stroke="#4a9aba" stroke-width="1.5" stroke-dasharray="4,2" />
      <line x1="95" y1="140" x2="155" y2="160" stroke="#4a9aba" stroke-width="1.5" stroke-dasharray="4,2" />
      <line x1="305" y1="140" x2="315" y2="160" stroke="#4a9aba" stroke-width="1.5" stroke-dasharray="4,2" />
      <line x1="305" y1="140" x2="245" y2="160" stroke="#4a9aba" stroke-width="1.5" stroke-dasharray="4,2" />

      <!-- 横向连接 -->
      <line x1="130" y1="115" x2="270" y2="115" stroke="#4a9aba" stroke-width="1" stroke-dasharray="4,2" />
    </g>

    <template #legend>
      <div class="legend-item">
        <span class="legend-color" style="background: #2a5a8a;"></span>
        <span>制冷设备</span>
      </div>
      <div class="legend-item">
        <span class="legend-color" style="background: #67C23A;"></span>
        <span>水泵</span>
      </div>
      <div class="legend-item">
        <span class="legend-color" style="background: #E6A23C;"></span>
        <span>配电</span>
      </div>
      <div class="legend-item">
        <span class="legend-color" style="background: #409EFF;"></span>
        <span>控制</span>
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
