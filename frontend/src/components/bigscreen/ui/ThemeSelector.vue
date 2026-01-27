<!-- frontend/src/components/bigscreen/ui/ThemeSelector.vue -->
<template>
  <div class="theme-selector">
    <el-dropdown
      trigger="click"
      placement="bottom-end"
      @command="handleThemeChange"
    >
      <div class="theme-trigger">
        <el-icon><Brush /></el-icon>
        <span class="current-theme" v-if="showLabel">{{ currentDisplayName }}</span>
      </div>
      <template #dropdown>
        <el-dropdown-menu class="theme-dropdown">
          <el-dropdown-item
            v-for="theme in themeList"
            :key="theme.name"
            :command="theme.name"
            :class="{ active: theme.name === currentThemeName }"
          >
            <span class="theme-preview" :style="getPreviewStyle(theme.name)"></span>
            <span class="theme-name">{{ theme.displayName }}</span>
            <el-icon v-if="theme.name === currentThemeName" class="check-icon">
              <Check />
            </el-icon>
          </el-dropdown-item>
        </el-dropdown-menu>
      </template>
    </el-dropdown>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Brush, Check } from '@element-plus/icons-vue'
import { useTheme } from '@/composables/bigscreen/useTheme'
import type { ThemeName } from '@/types/theme'
import { themes } from '@/config/themes'

const props = withDefaults(defineProps<{
  showLabel?: boolean
}>(), {
  showLabel: true
})

const { currentThemeName, currentTheme, themeList, setTheme } = useTheme()

const currentDisplayName = computed(() => currentTheme.value.displayName)

function handleThemeChange(themeName: string) {
  setTheme(themeName as ThemeName)
}

function getPreviewStyle(themeName: string) {
  const theme = themes[themeName as ThemeName]
  if (!theme) return {}

  const bgColor = theme.scene.backgroundColor.toString(16).padStart(6, '0')
  const primaryColor = theme.ui.primaryColor

  return {
    background: `linear-gradient(135deg, #${bgColor} 50%, ${primaryColor} 50%)`
  }
}
</script>

<style scoped lang="scss">
.theme-selector {
  position: relative;
}

.theme-trigger {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: rgba(0, 136, 255, 0.15);
  border: 1px solid rgba(0, 136, 255, 0.3);
  border-radius: 6px;
  cursor: pointer;
  color: #ccc;
  font-size: 13px;
  transition: all 0.2s;

  &:hover {
    background: rgba(0, 136, 255, 0.25);
    color: #fff;
  }

  .el-icon {
    font-size: 16px;
    color: var(--bs-primary-color, #00ccff);
  }
}

:deep(.theme-dropdown) {
  background: rgba(10, 20, 40, 0.95) !important;
  backdrop-filter: blur(10px);
  border: 1px solid rgba(0, 136, 255, 0.3);

  .el-dropdown-menu__item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 16px;
    color: #ccc;

    &:hover {
      background: rgba(0, 136, 255, 0.2);
      color: #fff;
    }

    &.active {
      color: var(--bs-primary-color, #00ccff);

      .theme-name {
        font-weight: 600;
      }
    }

    .theme-preview {
      width: 20px;
      height: 20px;
      border-radius: 4px;
      border: 1px solid rgba(255, 255, 255, 0.2);
    }

    .theme-name {
      flex: 1;
    }

    .check-icon {
      color: var(--bs-primary-color, #00ccff);
      font-size: 14px;
    }
  }
}
</style>
