<template>
  <div class="date-range-picker">
    <el-date-picker
      v-model="dateRange"
      type="datetimerange"
      :shortcuts="showShortcuts ? shortcuts : []"
      range-separator="至"
      start-placeholder="开始时间"
      end-placeholder="结束时间"
      :value-format="valueFormat"
      :default-time="defaultTime"
      :disabled-date="disabledDate"
      :clearable="clearable"
      :size="size"
      @change="handleChange"
    />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import dayjs from 'dayjs'

interface Props {
  startTime?: string
  endTime?: string
  valueFormat?: string
  showShortcuts?: boolean
  clearable?: boolean
  size?: 'large' | 'default' | 'small'
  maxDays?: number
}

const props = withDefaults(defineProps<Props>(), {
  valueFormat: 'YYYY-MM-DD HH:mm:ss',
  showShortcuts: true,
  clearable: true,
  size: 'default'
})

const emit = defineEmits<{
  (e: 'update:startTime', value: string | undefined): void
  (e: 'update:endTime', value: string | undefined): void
  (e: 'change', value: { startTime?: string; endTime?: string }): void
}>()

const dateRange = computed({
  get: () => {
    if (props.startTime && props.endTime) {
      return [props.startTime, props.endTime]
    }
    return null
  },
  set: (val) => {
    if (val) {
      emit('update:startTime', val[0])
      emit('update:endTime', val[1])
    } else {
      emit('update:startTime', undefined)
      emit('update:endTime', undefined)
    }
  }
})

const defaultTime: [Date, Date] = [
  new Date(2000, 1, 1, 0, 0, 0),
  new Date(2000, 2, 1, 23, 59, 59)
]

const shortcuts = [
  {
    text: '最近1小时',
    value: () => {
      const end = new Date()
      const start = new Date()
      start.setTime(start.getTime() - 3600 * 1000)
      return [start, end]
    }
  },
  {
    text: '最近6小时',
    value: () => {
      const end = new Date()
      const start = new Date()
      start.setTime(start.getTime() - 3600 * 1000 * 6)
      return [start, end]
    }
  },
  {
    text: '最近12小时',
    value: () => {
      const end = new Date()
      const start = new Date()
      start.setTime(start.getTime() - 3600 * 1000 * 12)
      return [start, end]
    }
  },
  {
    text: '今天',
    value: () => {
      const end = new Date()
      const start = dayjs().startOf('day').toDate()
      return [start, end]
    }
  },
  {
    text: '昨天',
    value: () => {
      const start = dayjs().subtract(1, 'day').startOf('day').toDate()
      const end = dayjs().subtract(1, 'day').endOf('day').toDate()
      return [start, end]
    }
  },
  {
    text: '最近7天',
    value: () => {
      const end = new Date()
      const start = dayjs().subtract(7, 'day').startOf('day').toDate()
      return [start, end]
    }
  },
  {
    text: '最近30天',
    value: () => {
      const end = new Date()
      const start = dayjs().subtract(30, 'day').startOf('day').toDate()
      return [start, end]
    }
  },
  {
    text: '本月',
    value: () => {
      const end = new Date()
      const start = dayjs().startOf('month').toDate()
      return [start, end]
    }
  },
  {
    text: '上月',
    value: () => {
      const start = dayjs().subtract(1, 'month').startOf('month').toDate()
      const end = dayjs().subtract(1, 'month').endOf('month').toDate()
      return [start, end]
    }
  }
]

const disabledDate = (date: Date) => {
  // 不能选择未来的日期
  if (date.getTime() > Date.now()) {
    return true
  }

  // 如果设置了最大天数限制
  if (props.maxDays) {
    const minDate = dayjs().subtract(props.maxDays, 'day').toDate()
    return date.getTime() < minDate.getTime()
  }

  return false
}

const handleChange = (val: any) => {
  if (val) {
    emit('change', { startTime: val[0], endTime: val[1] })
  } else {
    emit('change', { startTime: undefined, endTime: undefined })
  }
}
</script>

<style lang="scss" scoped>
.date-range-picker {
  display: inline-block;
}
</style>
