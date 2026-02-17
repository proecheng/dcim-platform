<template>
  <div v-if="store.hasDegradation" class="degradation-banners">
    <el-alert
      v-if="store.redisDown"
      title="实时数据可能有延迟"
      type="warning"
      :closable="false"
      show-icon
    />
    <el-alert
      v-if="store.websocketDown"
      title="连接中断，正在重连..."
      type="warning"
      :closable="false"
      show-icon
    />
    <el-alert
      v-if="store.mqttDown"
      title="数据采集服务异常"
      type="error"
      :closable="false"
      show-icon
    />
  </div>
</template>

<script setup lang="ts">
import { useDegradationStore } from '@/stores/degradation'

const store = useDegradationStore()

// 启动时从全局标志同步一次
store.syncFromFlags()
</script>

<style scoped>
.degradation-banners {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 8px;
}
</style>
