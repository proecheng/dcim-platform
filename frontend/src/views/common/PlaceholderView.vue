<template>
  <div class="placeholder-view">
    <el-empty description="功能开发中">
      <template #image>
        <el-icon :size="64" style="color: var(--el-color-info)"><Setting /></el-icon>
      </template>
    </el-empty>
  </div>
</template>
<script setup lang="ts">
import { Setting } from '@element-plus/icons-vue'
</script>
<style scoped>
.placeholder-view {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 400px;
}
</style>
