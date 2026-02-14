<template>
  <div class="cooling-overview">
    <el-card class="placeholder-card">
      <template #header>
        <div class="card-header">
          <el-icon :size="24"><IceCream /></el-icon>
          <span>制冷系统总览</span>
        </div>
      </template>
      <el-empty description="制冷系统监控功能开发中，敬请期待">
        <template #image>
          <el-icon :size="64" color="var(--text-disabled)"><IceCream /></el-icon>
        </template>
      </el-empty>
      <div class="planned-features">
        <h4>规划功能</h4>
        <ul>
          <li>精密空调（室内机）监控 — 制冷量、送回风温湿度、压缩机/风机状态</li>
          <li>精密空调（室外机）监控 — 环境温度、风机/压缩机状态</li>
          <li>冷通道天窗系统 — 天窗开闭状态</li>
          <li>群控状态展示</li>
        </ul>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { IceCream } from '@element-plus/icons-vue'
</script>

<style scoped lang="scss">
.cooling-overview {
  .placeholder-card {
    .card-header {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 18px;
      font-weight: 600;
    }
    .planned-features {
      margin-top: 20px;
      padding: 16px;
      background: var(--bg-primary);
      border-radius: 8px;
      h4 { margin-bottom: 12px; color: var(--text-regular); }
      ul {
        padding-left: 20px;
        li {
          margin-bottom: 8px;
          color: var(--text-secondary);
          line-height: 1.6;
        }
      }
    }
  }
}
</style>
