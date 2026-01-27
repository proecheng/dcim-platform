<template>
  <el-dialog
    v-model="visible"
    :title="title"
    :width="width"
    :close-on-click-modal="closeOnClickModal"
    :close-on-press-escape="closeOnPressEscape"
    :show-close="showClose"
    :draggable="draggable"
    :destroy-on-close="destroyOnClose"
    :append-to-body="appendToBody"
    @close="handleClose"
  >
    <div class="confirm-dialog__content">
      <el-icon v-if="showIcon" :class="['confirm-dialog__icon', iconClass]" :size="40">
        <component :is="iconComponent" />
      </el-icon>
      <div class="confirm-dialog__message">
        <slot>{{ message }}</slot>
      </div>
    </div>

    <template #footer>
      <div class="confirm-dialog__footer">
        <el-button @click="handleCancel">
          {{ cancelText }}
        </el-button>
        <el-button
          :type="confirmType"
          :loading="loading"
          @click="handleConfirm"
        >
          {{ confirmText }}
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import {
  WarningFilled,
  CircleCheckFilled,
  CircleCloseFilled,
  InfoFilled,
  QuestionFilled
} from '@element-plus/icons-vue'

type DialogType = 'warning' | 'success' | 'error' | 'info' | 'confirm'

interface Props {
  modelValue?: boolean
  title?: string
  message?: string
  type?: DialogType
  width?: string | number
  showIcon?: boolean
  showClose?: boolean
  closeOnClickModal?: boolean
  closeOnPressEscape?: boolean
  draggable?: boolean
  destroyOnClose?: boolean
  appendToBody?: boolean
  confirmText?: string
  cancelText?: string
  confirmType?: 'primary' | 'success' | 'warning' | 'danger' | 'info'
  beforeClose?: () => Promise<boolean>
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: false,
  title: '提示',
  message: '',
  type: 'confirm',
  width: '420px',
  showIcon: true,
  showClose: true,
  closeOnClickModal: false,
  closeOnPressEscape: true,
  draggable: false,
  destroyOnClose: true,
  appendToBody: true,
  confirmText: '确定',
  cancelText: '取消',
  confirmType: 'primary'
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'confirm'): void
  (e: 'cancel'): void
  (e: 'close'): void
}>()

const loading = ref(false)

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const iconConfig = {
  warning: { component: WarningFilled, class: 'is-warning' },
  success: { component: CircleCheckFilled, class: 'is-success' },
  error: { component: CircleCloseFilled, class: 'is-error' },
  info: { component: InfoFilled, class: 'is-info' },
  confirm: { component: QuestionFilled, class: 'is-confirm' }
}

const iconComponent = computed(() => iconConfig[props.type].component)
const iconClass = computed(() => iconConfig[props.type].class)

const handleClose = () => {
  emit('close')
}

const handleCancel = () => {
  visible.value = false
  emit('cancel')
}

const handleConfirm = async () => {
  if (props.beforeClose) {
    loading.value = true
    try {
      const result = await props.beforeClose()
      if (result) {
        visible.value = false
        emit('confirm')
      }
    } finally {
      loading.value = false
    }
  } else {
    visible.value = false
    emit('confirm')
  }
}
</script>

<style lang="scss" scoped>
.confirm-dialog {
  &__content {
    display: flex;
    align-items: flex-start;
    padding: 10px 0;
  }

  &__icon {
    flex-shrink: 0;
    margin-right: 16px;

    &.is-warning {
      color: var(--el-color-warning);
    }

    &.is-success {
      color: var(--el-color-success);
    }

    &.is-error {
      color: var(--el-color-danger);
    }

    &.is-info {
      color: var(--el-color-info);
    }

    &.is-confirm {
      color: var(--el-color-primary);
    }
  }

  &__message {
    flex: 1;
    font-size: 14px;
    line-height: 1.6;
    color: var(--el-text-color-regular);
    word-break: break-word;
  }

  &__footer {
    display: flex;
    justify-content: flex-end;
    gap: 12px;
  }
}
</style>
