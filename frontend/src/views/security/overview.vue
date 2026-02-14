<template>
  <div class="security-overview">
    <el-card class="placeholder-card">
      <template #header>
        <div class="card-header">
          <el-icon :size="24"><Lock /></el-icon>
          <span>安防消防总览</span>
        </div>
      </template>
      <el-empty description="安防消防功能开发中，敬请期待">
        <template #image>
          <el-icon :size="64" color="var(--text-disabled)"><Lock /></el-icon>
        </template>
      </el-empty>
      <div class="planned-features">
        <h4>规划功能</h4>
        <ul>
          <li>门禁管理 — 门状态、非法闯入、远程开门</li>
          <li>视频监控 — 摄像头状态、分屏显示（预留）</li>
          <li>消防联动 — 干接点信号状态、联动规则</li>
        </ul>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { Lock } from '@element-plus/icons-vue'
</script>

<style scoped lang="scss">
.security-overview {
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
