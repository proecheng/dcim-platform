<template>
  <el-tooltip :content="soundEnabled ? '告警声音：开' : '告警声音：关'" placement="bottom">
    <el-button
      :icon="soundEnabled ? Bell : MuteNotification"
      circle
      size="small"
      @click="toggleSound"
      :type="soundEnabled ? '' : 'info'"
    />
  </el-tooltip>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Bell, MuteNotification } from '@element-plus/icons-vue'
import { useAlarmStore } from '@/stores/alarm'

const alarmStore = useAlarmStore()
const soundEnabled = computed(() => alarmStore.soundEnabled)

function toggleSound() {
  alarmStore.toggleSound()
}
</script>
