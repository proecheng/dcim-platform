<template>
  <div class="pricing-timeline">
    <div class="timeline-header">
      <h4>24小时覆盖情况</h4>
      <div class="coverage-info">
        <el-tag :type="coverageType">
          覆盖率: {{ coverage.toFixed(1) }}/24小时
        </el-tag>
        <el-tag v-if="conflicts.length > 0" type="danger">
          冲突: {{ conflicts.length }}处
        </el-tag>
        <el-tag v-if="gaps.length > 0" type="warning">
          缺失: {{ gaps.length }}处
        </el-tag>
      </div>
    </div>

    <div class="timeline-container">
      <!-- 时间刻度 -->
      <div class="time-scale">
        <div
          v-for="hour in 24"
          :key="hour"
          class="time-mark"
          :style="{ left: `${(hour / 24) * 100}%` }"
        >
          {{ hour }}:00
        </div>
      </div>

      <!-- 时段条 -->
      <div class="timeline-bars">
        <div
          v-for="(period, index) in displayPeriods"
          :key="index"
          class="period-bar"
          :class="period.type"
          :style="{
            left: `${period.left}%`,
            width: `${period.width}%`
          }"
          :title="period.tooltip"
        >
          <span class="period-label">{{ period.label }}</span>
        </div>
      </div>

      <!-- 冲突标记 -->
      <div v-if="conflicts.length > 0" class="conflict-markers">
        <div
          v-for="(conflict, index) in conflicts"
          :key="`conflict-${index}`"
          class="conflict-marker"
          :style="{
            left: `${conflict.left}%`,
            width: `${conflict.width}%`
          }"
          title="时段冲突"
        />
      </div>

      <!-- 缺失标记 -->
      <div v-if="gaps.length > 0" class="gap-markers">
        <div
          v-for="(gap, index) in gaps"
          :key="`gap-${index}`"
          class="gap-marker"
          :style="{
            left: `${gap.left}%`,
            width: `${gap.width}%`
          }"
          title="时段缺失"
        />
      </div>
    </div>

    <!-- 图例 -->
    <div class="timeline-legend">
      <div class="legend-item">
        <span class="legend-color sharp"></span>
        <span>尖峰</span>
      </div>
      <div class="legend-item">
        <span class="legend-color peak"></span>
        <span>高峰</span>
      </div>
      <div class="legend-item">
        <span class="legend-color normal"></span>
        <span>平段</span>
      </div>
      <div class="legend-item">
        <span class="legend-color valley"></span>
        <span>低谷</span>
      </div>
      <div class="legend-item">
        <span class="legend-color deep_valley"></span>
        <span>深谷</span>
      </div>
      <div v-if="conflicts.length > 0" class="legend-item">
        <span class="legend-color conflict"></span>
        <span>冲突</span>
      </div>
      <div v-if="gaps.length > 0" class="legend-item">
        <span class="legend-color gap"></span>
        <span>缺失</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ElectricityPricing } from '@/api/modules/energy'

// Props
const props = defineProps<{
  pricingIds: number[]
  allPricings: ElectricityPricing[]
}>()

// 时段类型颜色映射
const periodTypeColors: Record<string, string> = {
  sharp: '#f56c6c',
  peak: '#e6a23c',
  normal: '#409eff',
  valley: '#67c23a',
  deep_valley: '#909399'
}

// 时间转分钟
const timeToMinutes = (timeStr: string): number => {
  const [h, m] = timeStr.split(':').map(Number)
  return h * 60 + m
}

// 分钟转百分比
const minutesToPercent = (minutes: number): number => {
  return (minutes / 1440) * 100
}

// 选中的时段
const selectedPricings = computed(() => {
  return props.allPricings.filter(p => props.pricingIds.includes(p.id))
})

// 转换为区间
interface Interval {
  start: number
  end: number
  pricing: ElectricityPricing
}

const intervals = computed<Interval[]>(() => {
  const result: Interval[] = []
  
  for (const pricing of selectedPricings.value) {
    const start = timeToMinutes(pricing.start_time)
    const end = timeToMinutes(pricing.end_time)
    
    // 处理跨日时段
    if (end < start) {
      result.push({ start, end: 1440, pricing })
      result.push({ start: 0, end, pricing })
    } else {
      result.push({ start, end, pricing })
    }
  }
  
  return result.sort((a, b) => a.start - b.start)
})

// 显示的时段条
interface DisplayPeriod {
  left: number
  width: number
  label: string
  type: string
  tooltip: string
}

const displayPeriods = computed<DisplayPeriod[]>(() => {
  return intervals.value.map(interval => {
    const left = minutesToPercent(interval.start)
    const width = minutesToPercent(interval.end - interval.start)
    
    return {
      left,
      width,
      label: interval.pricing.pricing_name,
      type: interval.pricing.period_type.toLowerCase(),
      tooltip: `${interval.pricing.pricing_name} (${interval.pricing.start_time}-${interval.pricing.end_time})`
    }
  })
})

// 检测冲突
interface Conflict {
  left: number
  width: number
}

const conflicts = computed<Conflict[]>(() => {
  const result: Conflict[] = []
  
  for (let i = 0; i < intervals.value.length; i++) {
    for (let j = i + 1; j < intervals.value.length; j++) {
      const a = intervals.value[i]
      const b = intervals.value[j]
      
      // 检查重叠（左闭右开）
      if (b.start < a.end) {
        const overlapStart = Math.max(a.start, b.start)
        const overlapEnd = Math.min(a.end, b.end)
        
        result.push({
          left: minutesToPercent(overlapStart),
          width: minutesToPercent(overlapEnd - overlapStart)
        })
      }
    }
  }
  
  return result
})

// 检测缺失
interface Gap {
  left: number
  width: number
}

const gaps = computed<Gap[]>(() => {
  if (intervals.value.length === 0) {
    return [{ left: 0, width: 100 }]
  }
  
  // 合并区间
  const merged: Array<[number, number]> = []
  let current = [intervals.value[0].start, intervals.value[0].end]
  
  for (let i = 1; i < intervals.value.length; i++) {
    const interval = intervals.value[i]
    
    if (interval.start <= current[1]) {
      // 重叠或相邻，合并
      current[1] = Math.max(current[1], interval.end)
    } else {
      // 不重叠，保存当前区间，开始新区间
      merged.push([current[0], current[1]])
      current = [interval.start, interval.end]
    }
  }
  merged.push([current[0], current[1]])
  
  // 找缺失
  const result: Gap[] = []
  
  // 检查开头
  if (merged[0][0] > 0) {
    result.push({
      left: 0,
      width: minutesToPercent(merged[0][0])
    })
  }
  
  // 检查中间
  for (let i = 0; i < merged.length - 1; i++) {
    const gapStart = merged[i][1]
    const gapEnd = merged[i + 1][0]
    
    if (gapStart < gapEnd) {
      result.push({
        left: minutesToPercent(gapStart),
        width: minutesToPercent(gapEnd - gapStart)
      })
    }
  }
  
  // 检查结尾
  if (merged[merged.length - 1][1] < 1440) {
    result.push({
      left: minutesToPercent(merged[merged.length - 1][1]),
      width: minutesToPercent(1440 - merged[merged.length - 1][1])
    })
  }
  
  return result
})

// 覆盖率
const coverage = computed(() => {
  if (intervals.value.length === 0) return 0
  
  // 合并区间计算总覆盖
  const merged: Array<[number, number]> = []
  let current = [intervals.value[0].start, intervals.value[0].end]
  
  for (let i = 1; i < intervals.value.length; i++) {
    const interval = intervals.value[i]
    
    if (interval.start <= current[1]) {
      current[1] = Math.max(current[1], interval.end)
    } else {
      merged.push([current[0], current[1]])
      current = [interval.start, interval.end]
    }
  }
  merged.push([current[0], current[1]])
  
  const totalMinutes = merged.reduce((sum, [start, end]) => sum + (end - start), 0)
  return totalMinutes / 60
})

// 覆盖率类型
const coverageType = computed(() => {
  if (coverage.value >= 24) return 'success'
  if (coverage.value >= 20) return 'warning'
  return 'danger'
})
</script>

<style scoped lang="scss">
.pricing-timeline {
  padding: 16px;
  background: #f5f7fa;
  border-radius: 4px;

  .timeline-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;

    h4 {
      margin: 0;
      font-size: 14px;
      font-weight: 500;
    }

    .coverage-info {
      display: flex;
      gap: 8px;
    }
  }

  .timeline-container {
    position: relative;
    height: 80px;
    background: white;
    border: 1px solid #dcdfe6;
    border-radius: 4px;
    margin-bottom: 12px;

    .time-scale {
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      height: 20px;
      border-bottom: 1px solid #e4e7ed;

      .time-mark {
        position: absolute;
        transform: translateX(-50%);
        font-size: 10px;
        color: #909399;
        white-space: nowrap;
      }
    }

    .timeline-bars {
      position: absolute;
      top: 20px;
      left: 0;
      right: 0;
      height: 40px;

      .period-bar {
        position: absolute;
        height: 100%;
        border-radius: 2px;
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-size: 12px;
        overflow: hidden;
        cursor: pointer;
        transition: all 0.3s;

        &:hover {
          opacity: 0.8;
          transform: translateY(-2px);
        }

        .period-label {
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          padding: 0 4px;
        }

        &.sharp { background: #f56c6c; }
        &.peak { background: #e6a23c; }
        &.normal { background: #409eff; }
        &.valley { background: #67c23a; }
        &.deep_valley { background: #909399; }
      }
    }

    .conflict-markers {
      position: absolute;
      top: 60px;
      left: 0;
      right: 0;
      height: 10px;

      .conflict-marker {
        position: absolute;
        height: 100%;
        background: repeating-linear-gradient(
          45deg,
          #f56c6c,
          #f56c6c 5px,
          #fef0f0 5px,
          #fef0f0 10px
        );
        border: 1px solid #f56c6c;
        border-radius: 2px;
      }
    }

    .gap-markers {
      position: absolute;
      top: 60px;
      left: 0;
      right: 0;
      height: 10px;

      .gap-marker {
        position: absolute;
        height: 100%;
        background: repeating-linear-gradient(
          45deg,
          #e6a23c,
          #e6a23c 5px,
          #fdf6ec 5px,
          #fdf6ec 10px
        );
        border: 1px solid #e6a23c;
        border-radius: 2px;
      }
    }
  }

  .timeline-legend {
    display: flex;
    gap: 16px;
    flex-wrap: wrap;

    .legend-item {
      display: flex;
      align-items: center;
      gap: 4px;
      font-size: 12px;
      color: #606266;

      .legend-color {
        width: 16px;
        height: 12px;
        border-radius: 2px;

        &.sharp { background: #f56c6c; }
        &.peak { background: #e6a23c; }
        &.normal { background: #409eff; }
        &.valley { background: #67c23a; }
        &.deep_valley { background: #909399; }
        &.conflict {
          background: repeating-linear-gradient(
            45deg,
            #f56c6c,
            #f56c6c 3px,
            #fef0f0 3px,
            #fef0f0 6px
          );
          border: 1px solid #f56c6c;
        }
        &.gap {
          background: repeating-linear-gradient(
            45deg,
            #e6a23c,
            #e6a23c 3px,
            #fdf6ec 3px,
            #fdf6ec 6px
          );
          border: 1px solid #e6a23c;
        }
      }
    }
  }
}
</style>
