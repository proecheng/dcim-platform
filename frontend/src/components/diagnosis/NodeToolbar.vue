<template>
  <div class="node-toolbar">
    <div class="toolbar-title">节点工具</div>

    <div class="toolbar-items">
      <div
        class="toolbar-item"
        draggable="true"
        @dragstart="handleDragStart('AND')"
        title="AND 门节点"
      >
        <div class="node-icon and-gate">AND</div>
        <div class="node-label">AND 门</div>
      </div>

      <div
        class="toolbar-item"
        draggable="true"
        @dragstart="handleDragStart('OR')"
        title="OR 门节点"
      >
        <div class="node-icon or-gate">OR</div>
        <div class="node-label">OR 门</div>
      </div>

      <div
        class="toolbar-item"
        draggable="true"
        @dragstart="handleDragStart('leaf')"
        title="叶节点"
      >
        <div class="node-icon leaf-node">叶</div>
        <div class="node-label">叶节点</div>
      </div>
    </div>

    <div class="toolbar-divider"></div>

    <div class="toolbar-actions">
      <el-button size="small" @click="$emit('fit-view')">
        <el-icon><FullScreen /></el-icon>
        适应视图
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { FullScreen } from '@element-plus/icons-vue'

const emit = defineEmits<{
  (e: 'add-node', nodeType: string): void
  (e: 'fit-view'): void
}>()

function handleDragStart(nodeType: string) {
  // 将节点类型存储到 dataTransfer 中
  // 实际的拖拽处理在 FaultTreeCanvas 组件中
  emit('add-node', nodeType)
}
</script>

<style scoped lang="scss">
.node-toolbar {
  width: 200px;
  background: #fff;
  border-right: 1px solid #e4e7ed;
  display: flex;
  flex-direction: column;
  padding: 16px;

  .toolbar-title {
    font-size: 16px;
    font-weight: 600;
    margin-bottom: 16px;
    color: #303133;
  }

  .toolbar-items {
    display: flex;
    flex-direction: column;
    gap: 12px;

    .toolbar-item {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 12px;
      border: 1px solid #dcdfe6;
      border-radius: 4px;
      cursor: move;
      transition: all 0.3s;

      &:hover {
        border-color: #409eff;
        background: #ecf5ff;
      }

      .node-icon {
        width: 40px;
        height: 40px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 4px;
        font-size: 12px;
        font-weight: 600;
        color: #fff;

        &.and-gate {
          background: #4ecdc4;
        }

        &.or-gate {
          background: #ffe66d;
          color: #333;
        }

        &.leaf-node {
          background: #95e1d3;
          color: #333;
        }
      }

      .node-label {
        font-size: 14px;
        color: #606266;
      }
    }
  }

  .toolbar-divider {
    height: 1px;
    background: #e4e7ed;
    margin: 16px 0;
  }

  .toolbar-actions {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
}
</style>
