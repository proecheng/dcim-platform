<template>
  <el-card
    class="interactive-power-card"
    shadow="hover"
    @click="handleClick"
  >
    <div class="card-header">
      <div class="header-left">
        <el-icon :size="20" :color="iconColor"><component :is="icon" /></el-icon>
        <span class="title">{{ title }}</span>
      </div>
      <el-tooltip v-if="tooltip" :content="tooltip" placement="top">
        <el-icon :size="16" class="info-icon"><InfoFilled /></el-icon>
      </el-tooltip>
    </div>

    <div class="card-body">
      <div class="main-value">
        <span class="value" :style="{ color: valueColor }">{{ formattedValue }}</span>
        <span class="unit">{{ unit }}</span>
        <el-icon v-if="trendIcon" :size="16" :color="trendColor" class="trend-icon">
          <component :is="trendIcon" />
        </el-icon>
      </div>

      <div class="sparkline-container" v-if="trendData.length > 0">
        <Sparkline
          :data="trendData"
          :color="sparklineColor"
          height="32px"
        />
      </div>

      <div class="details" v-if="details.length > 0">
        <div v-for="(item, index) in details" :key="index" class="detail-item">
          <span class="label">{{ item.label }}</span>
          <span class="value">{{ item.value }}</span>
        </div>
      </div>

      <div class="footer" v-if="footerTag || footerText">
        <el-tag v-if="footerTag" :type="footerTag.type" size="small">
          {{ footerTag.text }}
        </el-tag>
        <span v-if="footerText" class="footer-text">{{ footerText }}</span>
      </div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { InfoFilled, Top, Bottom, Minus } from '@element-plus/icons-vue'
import Sparkline from '@/components/charts/Sparkline.vue'

interface DetailItem {
  label: string
  value: string | number
}

interface FooterTag {
  text: string
  type: 'success' | 'warning' | 'danger' | 'info'
}

const props = defineProps<{
  title: string
  value: number | string
  unit: string
  icon: any
  iconColor?: string
  valueColor?: string
  trend?: 'up' | 'down' | 'stable'
  trendData?: number[]
  sparklineColor?: string
  details?: DetailItem[]
  footerTag?: FooterTag
  footerText?: string
  tooltip?: string
  navigateTo?: string
}>()

const router = useRouter()

const formattedValue = computed(() => {
  if (typeof props.value === 'number') {
    return props.value.toFixed(1)
  }
  return props.value
})

const trendIcon = computed(() => {
  switch (props.trend) {
    case 'up': return Top
    case 'down': return Bottom
    default: return null
  }
})

const trendColor = computed(() => {
  switch (props.trend) {
    case 'up': return '#F56C6C'
    case 'down': return '#67C23A'
    default: return '#909399'
  }
})

const trendData = computed(() => props.trendData || [])

const handleClick = () => {
  if (props.navigateTo) {
    router.push(props.navigateTo)
  }
}
</script>

<style scoped lang="scss">
.interactive-power-card {
  cursor: pointer;
  transition: all 0.3s;

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  }

  :deep(.el-card__body) {
    padding: 16px;
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;

    .header-left {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .title {
      font-size: 14px;
      color: #606266;
    }

    .info-icon {
      color: #C0C4CC;
      cursor: help;
    }
  }

  .card-body {
    .main-value {
      display: flex;
      align-items: baseline;
      gap: 4px;
      margin-bottom: 8px;

      .value {
        font-size: 28px;
        font-weight: bold;
        color: #303133;
      }

      .unit {
        font-size: 14px;
        color: #909399;
      }

      .trend-icon {
        margin-left: 4px;
      }
    }

    .sparkline-container {
      margin: 8px 0;
    }

    .details {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin-top: 8px;

      .detail-item {
        display: flex;
        gap: 4px;
        font-size: 12px;

        .label {
          color: #909399;
        }

        .value {
          color: #606266;
        }
      }
    }

    .footer {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-top: 8px;

      .footer-text {
        font-size: 12px;
        color: #909399;
      }
    }
  }
}
</style>
