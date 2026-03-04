<template>
  <div class="condition-group" :class="{ nested: depth > 0 }">
    <!-- 组头部: 逻辑选择 + 操作按钮 -->
    <div class="group-header">
      <el-select
        :model-value="group.logic"
        style="width: 90px"
        size="small"
        @change="(val: string) => updateLogic(val as 'AND' | 'OR')"
      >
        <el-option label="AND" value="AND" />
        <el-option label="OR" value="OR" />
      </el-select>
      <span class="group-label">条件组</span>
      <div class="group-actions">
        <el-button size="small" @click="addCondition">
          <el-icon><Plus /></el-icon> 条件
        </el-button>
        <el-tooltip
          :content="depth >= maxDepth ? '已达最大嵌套层数' : ''"
          :disabled="depth < maxDepth"
          placement="top"
        >
          <el-button
            size="small"
            type="warning"
            plain
            :disabled="depth >= maxDepth"
            @click="addSubGroup"
          >
            <el-icon><FolderAdd /></el-icon> 子组
          </el-button>
        </el-tooltip>
        <el-button
          v-if="depth > 0"
          size="small"
          type="danger"
          plain
          @click="$emit('remove')"
        >
          <el-icon><Delete /></el-icon>
        </el-button>
      </div>
    </div>

    <!-- 子节点列表 -->
    <div class="group-children">
      <div
        v-for="(child, idx) in group.children"
        :key="child.id"
        class="child-item"
      >
        <!-- 逻辑连接符 -->
        <div v-if="idx > 0" class="logic-connector">
          <span class="logic-tag" :class="group.logic.toLowerCase()">
            {{ group.logic }}
          </span>
        </div>

        <!-- 条件行 -->
        <div v-if="child.type === 'condition'" class="condition-row">
          <el-select
            :model-value="child.pointId"
            placeholder="选择点位"
            filterable
            size="small"
            style="width: 200px"
            @change="(val: number) => updateChildCondition(idx, 'pointId', val)"
          >
            <el-option
              v-for="p in pointOptions"
              :key="p.id"
              :label="`${p.point_name} (${p.point_code})`"
              :value="p.id"
            />
          </el-select>
          <el-select
            :model-value="child.operator"
            size="small"
            style="width: 80px"
            @change="(val: string) => updateChildCondition(idx, 'operator', val)"
          >
            <el-option label=">" value=">" />
            <el-option label="<" value="<" />
            <el-option label="=" value="=" />
            <el-option label=">=" value=">=" />
            <el-option label="<=" value="<=" />
          </el-select>
          <el-input-number
            :model-value="child.threshold"
            :precision="2"
            size="small"
            style="width: 140px"
            placeholder="阈值"
            @change="(val: number | undefined) => updateChildCondition(idx, 'threshold', val)"
          />
          <el-button
            size="small"
            type="danger"
            plain
            circle
            @click="removeChild(idx)"
          >
            <el-icon><Close /></el-icon>
          </el-button>
        </div>

        <!-- 嵌套条件组 -->
        <ConditionGroupEditor
          v-else
          :group="child"
          :point-options="pointOptions"
          :depth="depth + 1"
          :max-depth="maxDepth"
          @update:group="(val: ConditionGroup) => updateChildGroup(idx, val)"
          @remove="removeChild(idx)"
        />
      </div>

      <!-- 空状态 -->
      <div v-if="!group.children.length" class="empty-hint">
        点击上方按钮添加条件或子条件组
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Plus, FolderAdd, Delete, Close } from '@element-plus/icons-vue'
import type { PointInfo } from '@/api/modules/point'
import { generateUUID } from '@/utils/uuid'

// ==================== 条件树类型 ====================
interface ConditionItem {
  id: string
  type: 'condition'
  pointId: number | undefined
  pointName: string
  operator: '>' | '<' | '=' | '>=' | '<='
  threshold: number | undefined
}

interface ConditionGroup {
  id: string
  type: 'group'
  logic: 'AND' | 'OR'
  children: (ConditionItem | ConditionGroup)[]
}


const props = withDefaults(defineProps<{
  group: ConditionGroup
  pointOptions: PointInfo[]
  depth: number
  maxDepth?: number
}>(), {
  maxDepth: 2
})

const emit = defineEmits<{
  remove: []
  'update:group': [value: ConditionGroup]
}>()

// ==================== 辅助: 不可变更新 ====================
function emitUpdate(patch: Partial<ConditionGroup>) {
  emit('update:group', { ...props.group, ...patch } as ConditionGroup)
}

// ==================== 操作方法 ====================
function updateLogic(val: 'AND' | 'OR') {
  emitUpdate({ logic: val })
}

function addCondition() {
  emitUpdate({
    children: [
      ...props.group.children,
      {
        id: generateUUID(),
        type: 'condition',
        pointId: undefined,
        pointName: '',
        operator: '>',
        threshold: undefined
      }
    ]
  })
}

function addSubGroup() {
  if (props.depth >= props.maxDepth) return
  emitUpdate({
    children: [
      ...props.group.children,
      {
        id: generateUUID(),
        type: 'group',
        logic: 'AND',
        children: []
      }
    ]
  })
}

function removeChild(idx: number) {
  emitUpdate({
    children: props.group.children.filter((_, i) => i !== idx)
  })
}

function updateChildGroup(idx: number, updated: ConditionGroup) {
  const newChildren = [...props.group.children]
  newChildren[idx] = updated
  emitUpdate({ children: newChildren })
}

function updateChildCondition(idx: number, field: string, val: unknown) {
  const child = props.group.children[idx]
  if (child.type !== 'condition') return

  const updated = { ...child }
  if (field === 'pointId') {
    updated.pointId = val as number
    const point = props.pointOptions.find(p => p.id === val)
    updated.pointName = point?.point_name || ''
  } else if (field === 'operator') {
    updated.operator = val as ConditionItem['operator']
  } else if (field === 'threshold') {
    updated.threshold = val as number | undefined
  }

  const newChildren = [...props.group.children]
  newChildren[idx] = updated
  emitUpdate({ children: newChildren })
}
</script>

<style lang="scss" scoped>
.condition-group {
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  padding: 10px;
  background: var(--el-bg-color);

  &.nested {
    background: var(--el-fill-color-light);
    border-style: dashed;
    margin-top: 4px;
  }
}

.group-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--el-border-color-lighter);

  .group-label {
    font-size: 12px;
    color: var(--el-text-color-secondary);
  }

  .group-actions {
    margin-left: auto;
    display: flex;
    gap: 4px;
  }
}

.group-children {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.child-item {
  position: relative;
}

.logic-connector {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2px 0;

  .logic-tag {
    font-size: 11px;
    font-weight: 700;
    padding: 1px 8px;
    border-radius: 4px;
    letter-spacing: 1px;

    &.and {
      background: rgba(64, 158, 255, 0.1);
      color: #409EFF;
    }
    &.or {
      background: rgba(230, 162, 60, 0.1);
      color: #E6A23C;
    }
  }
}

.condition-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  transition: border-color 0.2s;

  &:hover {
    border-color: var(--el-color-primary-light-5);
  }
}

.empty-hint {
  text-align: center;
  color: var(--el-text-color-placeholder);
  font-size: 13px;
  padding: 20px 0;
}
</style>
