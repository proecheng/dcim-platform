import { onMounted, onUnmounted } from 'vue'
import { systemWs } from '@/api/websocket'
import { ElNotification } from 'element-plus'

export function useDataQuality() {
  const handleQualityMessage = (message: any) => {
    const data = message.data
    if (!data || data.type !== 'data_quality_changed') return

    if (data.quality === 2) {
      ElNotification({
        title: '数据质量告警',
        message: data.message || `${data.affected_count}个点位数据质量变为不可靠`,
        type: 'warning',
        duration: 5000,
      })
    } else if (data.quality === 0) {
      ElNotification({
        title: '数据质量恢复',
        message: data.message || `数据源通信恢复，${data.affected_count}个点位数据质量已恢复正常`,
        type: 'success',
        duration: 3000,
      })
    }
  }

  onMounted(() => {
    systemWs.connect()
    systemWs.on('system', handleQualityMessage)
  })

  onUnmounted(() => {
    systemWs.off('system', handleQualityMessage)
  })
}
