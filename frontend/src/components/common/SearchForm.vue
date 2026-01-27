<template>
  <el-form
    ref="formRef"
    :model="modelValue"
    :inline="inline"
    :label-width="labelWidth"
    class="search-form"
    @submit.prevent="handleSearch"
  >
    <slot></slot>

    <el-form-item v-if="showButtons" class="search-form__buttons">
      <el-button type="primary" :icon="Search" @click="handleSearch">
        搜索
      </el-button>
      <el-button :icon="Refresh" @click="handleReset">
        重置
      </el-button>
      <el-button
        v-if="showExpand && $slots.expand"
        type="text"
        @click="expanded = !expanded"
      >
        {{ expanded ? '收起' : '展开' }}
        <el-icon class="expand-icon" :class="{ 'is-expanded': expanded }">
          <ArrowDown />
        </el-icon>
      </el-button>
    </el-form-item>

    <!-- 展开区域 -->
    <transition name="expand">
      <div v-if="expanded" class="search-form__expand">
        <slot name="expand"></slot>
      </div>
    </transition>
  </el-form>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Search, Refresh, ArrowDown } from '@element-plus/icons-vue'
import type { FormInstance } from 'element-plus'

interface Props {
  modelValue: Record<string, any>
  inline?: boolean
  labelWidth?: string
  showButtons?: boolean
  showExpand?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  inline: true,
  labelWidth: '80px',
  showButtons: true,
  showExpand: false
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: Record<string, any>): void
  (e: 'search', value: Record<string, any>): void
  (e: 'reset'): void
}>()

const formRef = ref<FormInstance>()
const expanded = ref(false)

const handleSearch = () => {
  emit('search', props.modelValue)
}

const handleReset = () => {
  formRef.value?.resetFields()
  emit('reset')
  emit('search', props.modelValue)
}

defineExpose({
  reset: handleReset,
  search: handleSearch,
  form: formRef
})
</script>

<style lang="scss" scoped>
.search-form {
  padding: 16px;
  background: var(--bg-card);
  border-radius: var(--radius-base);
  border: 1px solid var(--border-color);
  margin-bottom: 16px;

  &__buttons {
    margin-left: auto;
  }

  &__expand {
    width: 100%;
    padding-top: 16px;
    border-top: 1px dashed var(--border-color);
    margin-top: 16px;
  }

  .expand-icon {
    transition: transform 0.3s;

    &.is-expanded {
      transform: rotate(180deg);
    }
  }
}

.expand-enter-active,
.expand-leave-active {
  transition: all 0.3s ease;
  overflow: hidden;
}

.expand-enter-from,
.expand-leave-to {
  opacity: 0;
  max-height: 0;
}

.expand-enter-to,
.expand-leave-from {
  opacity: 1;
  max-height: 200px;
}
</style>
