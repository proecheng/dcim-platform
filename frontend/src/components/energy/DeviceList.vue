<template>
  <div class="device-list">
    <el-alert type="info" :closable="false" class="data-source-tip">
      <template #title>
        设备数据来源：power_devices表 + device_shift_configs表
      </template>
    </el-alert>

    <!-- 设备统计 -->
    <el-row :gutter="16" class="device-stats">
      <el-col :span="8">
        <el-statistic title="设备总数" :value="devices.length" />
      </el-col>
      <el-col :span="8">
        <el-statistic
          title="总可调节容量"
          :value="totalShiftablePower"
          :precision="1"
        >
          <template #suffix>kW</template>
        </el-statistic>
      </el-col>
      <el-col :span="8">
        <el-statistic
          title="平均转移比例"
          :value="avgShiftRatio * 100"
          :precision="1"
        >
          <template #suffix>%</template>
        </el-statistic>
      </el-col>
    </el-row>

    <!-- 设备表格 -->
    <el-table
      :data="devices"
      stripe
      border
      size="small"
      class="device-table"
      max-height="400"
      :row-style="{ height: '36px' }"
      :cell-style="{ padding: '4px 8px' }"
      :header-row-style="{ height: '32px' }"
      :header-cell-style="{ padding: '6px 8px' }"
    >
      <el-table-column prop="device_code" label="设备编码" width="120" fixed />
      <el-table-column prop="device_name" label="设备名称" min-width="150" />
      <el-table-column prop="device_type" label="设备类型" width="100">
        <template #default="{ row }">
          <el-tag size="small">{{ deviceTypeText[row.device_type] || row.device_type }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="rated_power" label="额定功率" width="100" align="right">
        <template #default="{ row }">
          {{ row.rated_power?.toFixed(1) || '-' }} kW
        </template>
      </el-table-column>
      <el-table-column prop="shiftable_power" label="可调节容量" width="110" align="right">
        <template #default="{ row }">
          <span class="highlight">{{ row.shiftable_power?.toFixed(1) || '-' }} kW</span>
        </template>
      </el-table-column>
      <el-table-column prop="regulation_method" label="调节方式" min-width="180">
        <template #default="{ row }">
          {{ row.regulation_method || '负荷转移' }}
        </template>
      </el-table-column>
      <el-table-column label="时段约束" width="180">
        <template #default="{ row }">
          <div v-if="row.constraints?.allowed_hours?.length">
            <el-tooltip>
              <template #content>
                <div>允许时段: {{ formatHours(row.constraints.allowed_hours) }}</div>
                <div v-if="row.constraints.forbidden_hours?.length">
                  禁止时段: {{ formatHours(row.constraints.forbidden_hours) }}
                </div>
                <div v-if="row.constraints.min_runtime">
                  最小运行时长: {{ row.constraints.min_runtime }}h
                </div>
              </template>
              <el-tag size="small" type="warning">
                {{ formatHoursShort(row.constraints.allowed_hours) }}
              </el-tag>
            </el-tooltip>
          </div>
          <span v-else class="no-constraint">无限制</span>
        </template>
      </el-table-column>
    </el-table>

    <!-- 无设备提示 -->
    <el-empty
      v-if="devices.length === 0"
      description="暂无可转移设备，请在系统设置中配置"
    />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { SuggestionDetail, DeviceInSuggestion, ShiftableDevice } from '@/api/modules/energy'

const props = defineProps<{
  suggestion: SuggestionDetail
}>()

// Device list can be either DeviceInSuggestion[] or ShiftableDevice[]
type DeviceItem = DeviceInSuggestion | ShiftableDevice

const devices = computed<DeviceItem[]>(() => {
  return props.suggestion.parameters?.devices || props.suggestion.shiftable_devices || []
})

const totalShiftablePower = computed(() => {
  return devices.value.reduce((sum, d) => sum + (d.shiftable_power || 0), 0)
})

const avgShiftRatio = computed(() => {
  if (devices.value.length === 0) return 0
  const totalRated = devices.value.reduce((sum, d) => sum + (d.rated_power || 0), 0)
  if (totalRated === 0) return 0
  return totalShiftablePower.value / totalRated
})

const deviceTypeText: Record<string, string> = {
  HVAC: '空调',
  AC: '空调',
  PUMP: '水泵',
  COMPRESSOR: '压缩机',
  CHILLER: '冷水机',
  COOLING_TOWER: '冷却塔',
  AHU: '空气处理机',
  LIGHTING: '照明',
  UPS: 'UPS',
  IT_SERVER: 'IT服务器',
  IT_STORAGE: 'IT存储'
}

function formatHours(hours: number[]): string {
  if (!hours || hours.length === 0) return '全天'
  const ranges: string[] = []
  let start = hours[0]
  let end = hours[0]

  for (let i = 1; i <= hours.length; i++) {
    if (i < hours.length && hours[i] === end + 1) {
      end = hours[i]
    } else {
      ranges.push(start === end ? `${start}:00` : `${start}:00-${end + 1}:00`)
      if (i < hours.length) {
        start = hours[i]
        end = hours[i]
      }
    }
  }
  return ranges.join(', ')
}

function formatHoursShort(hours: number[]): string {
  if (!hours || hours.length === 0) return '全天'
  if (hours.length <= 4) {
    return hours.map(h => `${h}:00`).join(',')
  }
  return `${hours.length}个时段`
}
</script>

<style scoped lang="scss">
.device-list {
  .data-source-tip {
    margin-bottom: 16px;
    background: rgba(24, 144, 255, 0.1);
    border-color: rgba(24, 144, 255, 0.3);
  }

  .device-stats {
    margin-bottom: 20px;
    text-align: center;
  }

  .device-table {
    :deep(.el-table__header th) {
      padding: 6px 0;
    }

    :deep(.el-table__body td) {
      padding: 4px 0;
    }

    :deep(.el-table__row) {
      height: 36px;
    }

    .highlight {
      color: var(--success-color, #52c41a);
      font-weight: bold;
    }

    .no-constraint {
      color: var(--text-secondary, rgba(255, 255, 255, 0.65));
    }
  }
}
</style>
