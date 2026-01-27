<!-- frontend/src/components/bigscreen/ui/ContextMenu.vue -->
<template>
  <Teleport to="body">
    <Transition name="context-menu">
      <div
        v-if="visible"
        ref="menuRef"
        class="context-menu"
        :style="menuStyle"
        @contextmenu.prevent
      >
        <template v-for="(item, index) in items" :key="index">
          <div v-if="item.divider" class="menu-divider"></div>
          <div
            v-else
            class="menu-item"
            :class="{ disabled: item.disabled }"
            @click="handleItemClick(item)"
          >
            <el-icon v-if="item.icon" class="menu-icon">
              <component :is="item.icon" />
            </el-icon>
            <span class="menu-label">{{ item.label }}</span>
            <span v-if="item.shortcut" class="menu-shortcut">{{ item.shortcut }}</span>
          </div>
        </template>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'

export interface ContextMenuItem {
  label?: string
  icon?: string
  action?: string
  shortcut?: string
  disabled?: boolean
  divider?: boolean
  onClick?: () => void
}

const props = withDefaults(defineProps<{
  visible: boolean
  x: number
  y: number
  items: ContextMenuItem[]
}>(), {
  visible: false,
  x: 0,
  y: 0,
  items: () => []
})

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'select', item: ContextMenuItem): void
}>()

const menuRef = ref<HTMLElement | null>(null)

const menuStyle = computed(() => {
  let left = props.x
  let top = props.y

  // 防止超出屏幕右边界
  if (menuRef.value) {
    const menuWidth = menuRef.value.offsetWidth || 180
    const menuHeight = menuRef.value.offsetHeight || 200
    const windowWidth = window.innerWidth
    const windowHeight = window.innerHeight

    if (left + menuWidth > windowWidth) {
      left = windowWidth - menuWidth - 10
    }
    if (top + menuHeight > windowHeight) {
      top = windowHeight - menuHeight - 10
    }
  }

  return {
    left: `${left}px`,
    top: `${top}px`
  }
})

function handleItemClick(item: ContextMenuItem) {
  if (item.disabled) return

  if (item.onClick) {
    item.onClick()
  }

  emit('select', item)
  emit('update:visible', false)
}

function handleClickOutside(event: MouseEvent) {
  if (menuRef.value && !menuRef.value.contains(event.target as Node)) {
    emit('update:visible', false)
  }
}

function handleEscape(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    emit('update:visible', false)
  }
}

watch(() => props.visible, (visible) => {
  if (visible) {
    setTimeout(() => {
      document.addEventListener('click', handleClickOutside)
      document.addEventListener('keydown', handleEscape)
    }, 0)
  } else {
    document.removeEventListener('click', handleClickOutside)
    document.removeEventListener('keydown', handleEscape)
  }
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
  document.removeEventListener('keydown', handleEscape)
})
</script>

<style scoped lang="scss">
.context-menu {
  position: fixed;
  min-width: 180px;
  background: rgba(10, 20, 40, 0.95);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(0, 136, 255, 0.4);
  border-radius: 8px;
  padding: 6px 0;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
  z-index: 9999;
  overflow: hidden;
}

.menu-item {
  display: flex;
  align-items: center;
  padding: 10px 16px;
  color: #ccc;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s ease;

  &:hover:not(.disabled) {
    background: rgba(0, 136, 255, 0.2);
    color: #fff;
  }

  &.disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .menu-icon {
    margin-right: 10px;
    font-size: 16px;
    color: #00ccff;
  }

  .menu-label {
    flex: 1;
  }

  .menu-shortcut {
    margin-left: 20px;
    font-size: 11px;
    color: #666;
    font-family: monospace;
  }
}

.menu-divider {
  height: 1px;
  background: rgba(255, 255, 255, 0.1);
  margin: 6px 12px;
}

// 动画
.context-menu-enter-active,
.context-menu-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}

.context-menu-enter-from,
.context-menu-leave-to {
  opacity: 0;
  transform: scale(0.95);
}
</style>
