<template>
  <div class="environment-overview">
    <el-card class="placeholder-card">
      <template #header>
        <div class="card-header">
          <el-icon :size="24"><Sunny /></el-icon>
          <span>环境监控总览</span>
        </div>
      </template>
      <el-empty description="环境监控功能开发中，敬请期待">
        <template #image>
          <el-icon :size="64" color="var(--text-disabled)"><Sunny /></el-icon>
        </template>
      </el-empty>
      <div class="planned-features">
        <h4>规划功能</h4>
        <ul>
          <li>温湿度监控 — 冷/热通道温湿度、空调回风温度</li>
          <li>水浸检测 — 漏水距离、漏水状态</li>
          <li>烟雾检测 — 烟雾浓度、传感器断线状态</li>
          <li>红外安防 — 人体移动探测、防拆报警</li>
        </ul>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { Sunny } from '@element-plus/icons-vue'
</script>

<style scoped lang="scss">
.environment-overview {
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
