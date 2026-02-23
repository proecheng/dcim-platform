/**
 * 网关配置对话框 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, computed } from 'vue'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }), useRoute: () => ({ params: {}, query: {} }), createRouter: vi.fn(), createWebHistory: vi.fn() }))

// ── 从 GatewayConfigDialog.vue 提取的辅助函数 ──
type TagType = 'info' | 'warning' | 'success' | 'danger' | 'primary'

function formatTime(t: string | null | undefined): string {
  if (!t) return '--'
  return t.replace('T', ' ').substring(0, 19)
}

function formatConfigSnapshot(snapshot: Record<string, unknown>): string {
  if (!snapshot) return '--'
  const keys = Object.keys(snapshot)
  if (keys.length === 0) return '--'
  const parts: string[] = []
  for (const key of keys.slice(0, 3)) {
    const val = snapshot[key]
    if (typeof val === 'object' && val !== null) {
      parts.push(`${key}: [${Object.keys(val as Record<string, unknown>).length}项]`)
    } else {
      parts.push(`${key}: ${val}`)
    }
  }
  if (keys.length > 3) parts.push(`...+${keys.length - 3}`)
  return parts.join(', ')
}

function statusTagType(status: string): TagType {
  const map: Record<string, TagType> = { pending: 'warning', delivered: 'success', failed: 'danger' }
  return map[status] || 'info'
}

function statusText(status: string): string {
  const map: Record<string, string> = { pending: '下发中', delivered: '已生效', failed: '失败' }
  return map[status] || status
}

interface GatewayDetail {
  gateway_id: string
  name: string
  ip_address: string | null
  version: string | null
  datasource_count: number
  point_count: number
  status: 'online' | 'offline'
  is_enabled: boolean
}

const GatewayConfigDialogTestable = defineComponent({
  name: 'GatewayConfigDialogTestable',
  setup() {
    const gatewayDetail = ref<GatewayDetail | null>({
      gateway_id: 'GW-001',
      name: '网关A',
      ip_address: '192.168.1.100',
      version: '2.1.0',
      datasource_count: 5,
      point_count: 120,
      status: 'online',
      is_enabled: true,
    })

    const activeTab = ref('push')
    const pushing = ref(false)
    const lastPushResult = ref<{ status: string; error_message?: string } | null>(null)

    const dialogTitle = computed(() => {
      return gatewayDetail.value ? `配置下发 — ${gatewayDetail.value.name}` : '配置下发'
    })

    const canPush = computed(() => {
      if (!gatewayDetail.value) return false
      return gatewayDetail.value.status === 'online' && gatewayDetail.value.is_enabled
    })

    const pushResultTitle = computed(() => {
      if (!lastPushResult.value) return ''
      const map: Record<string, string> = {
        pending: '配置下发中...',
        delivered: '配置已生效',
        failed: '配置下发失败',
      }
      return map[lastPushResult.value.status] || lastPushResult.value.status
    })

    const pushResultAlertType = computed<'info' | 'success' | 'warning' | 'error'>(() => {
      if (!lastPushResult.value) return 'info'
      const map: Record<string, 'info' | 'success' | 'warning' | 'error'> = {
        pending: 'info',
        delivered: 'success',
        failed: 'error',
      }
      return map[lastPushResult.value.status] || 'info'
    })

    function handleClose() {
      lastPushResult.value = null
      activeTab.value = 'push'
    }

    return {
      gatewayDetail, activeTab, pushing, lastPushResult,
      dialogTitle, canPush, pushResultTitle, pushResultAlertType, handleClose,
    }
  },
  template: `<div class="gateway-config-dialog">
    <div data-testid="dialog-title">{{ dialogTitle }}</div>
    <div data-testid="can-push">{{ canPush }}</div>
    <div data-testid="active-tab">{{ activeTab }}</div>
    <div v-if="gatewayDetail" data-testid="gateway-info">
      <span class="gateway-id">{{ gatewayDetail.gateway_id }}</span>
      <span class="name">{{ gatewayDetail.name }}</span>
      <span class="ip">{{ gatewayDetail.ip_address }}</span>
      <span class="status">{{ gatewayDetail.status }}</span>
    </div>
    <div v-if="lastPushResult" data-testid="push-result">
      <span class="title">{{ pushResultTitle }}</span>
      <span class="type">{{ pushResultAlertType }}</span>
    </div>
  </div>`,
})

describe('网关配置对话框', () => {
  beforeEach(() => { setActivePinia(createPinia()) })

  it('对话框标题包含网关名称', () => {
    expect(mount(GatewayConfigDialogTestable).find('[data-testid="dialog-title"]').text()).toBe('配置下发 — 网关A')
  })

  it('canPush: 在线且启用时可下发', () => {
    expect(mount(GatewayConfigDialogTestable).find('[data-testid="can-push"]').text()).toBe('true')
  })

  it('canPush: 离线时不可下发', () => {
    const w = mount(GatewayConfigDialogTestable)
    w.vm.gatewayDetail = { gateway_id: 'GW-002', name: '网关B', ip_address: null, version: null, datasource_count: 0, point_count: 0, status: 'offline', is_enabled: true }
    expect(w.vm.canPush).toBe(false)
  })

  it('canPush: 禁用时不可下发', () => {
    const w = mount(GatewayConfigDialogTestable)
    w.vm.gatewayDetail = { gateway_id: 'GW-003', name: '网关C', ip_address: null, version: null, datasource_count: 0, point_count: 0, status: 'online', is_enabled: false }
    expect(w.vm.canPush).toBe(false)
  })

  it('canPush: 无网关详情时不可下发', () => {
    const w = mount(GatewayConfigDialogTestable)
    w.vm.gatewayDetail = null
    expect(w.vm.canPush).toBe(false)
  })

  it('渲染网关信息', () => {
    const w = mount(GatewayConfigDialogTestable)
    expect(w.find('.gateway-id').text()).toBe('GW-001')
    expect(w.find('.name').text()).toBe('网关A')
    expect(w.find('.ip').text()).toBe('192.168.1.100')
  })

  it('handleClose 重置状态', () => {
    const w = mount(GatewayConfigDialogTestable)
    w.vm.lastPushResult = { status: 'delivered' }
    w.vm.activeTab = 'history'
    w.vm.handleClose()
    expect(w.vm.lastPushResult).toBeNull()
    expect(w.vm.activeTab).toBe('push')
  })

  it('pushResultTitle: 各状态映射', () => {
    const w = mount(GatewayConfigDialogTestable)
    w.vm.lastPushResult = { status: 'pending' }
    expect(w.vm.pushResultTitle).toBe('配置下发中...')
    w.vm.lastPushResult = { status: 'delivered' }
    expect(w.vm.pushResultTitle).toBe('配置已生效')
    w.vm.lastPushResult = { status: 'failed' }
    expect(w.vm.pushResultTitle).toBe('配置下发失败')
  })

  it('pushResultAlertType: 各状态映射', () => {
    const w = mount(GatewayConfigDialogTestable)
    w.vm.lastPushResult = { status: 'pending' }
    expect(w.vm.pushResultAlertType).toBe('info')
    w.vm.lastPushResult = { status: 'delivered' }
    expect(w.vm.pushResultAlertType).toBe('success')
    w.vm.lastPushResult = { status: 'failed' }
    expect(w.vm.pushResultAlertType).toBe('error')
  })
})

describe('网关配置 — 辅助函数', () => {
  it('formatTime: 正常格式化', () => {
    expect(formatTime('2026-02-01T10:30:00')).toBe('2026-02-01 10:30:00')
  })

  it('formatTime: 空值返回 --', () => {
    expect(formatTime(null)).toBe('--')
    expect(formatTime(undefined)).toBe('--')
  })

  it('formatConfigSnapshot: 简单键值', () => {
    expect(formatConfigSnapshot({ host: '192.168.1.1', port: 502 })).toBe('host: 192.168.1.1, port: 502')
  })

  it('formatConfigSnapshot: 对象值显示项数', () => {
    expect(formatConfigSnapshot({ devices: { a: 1, b: 2 } })).toBe('devices: [2项]')
  })

  it('formatConfigSnapshot: 超过3个键截断', () => {
    const result = formatConfigSnapshot({ a: 1, b: 2, c: 3, d: 4, e: 5 })
    expect(result).toContain('...+2')
  })

  it('formatConfigSnapshot: 空对象返回 --', () => {
    expect(formatConfigSnapshot({})).toBe('--')
  })

  it('statusTagType: 各状态映射', () => {
    expect(statusTagType('pending')).toBe('warning')
    expect(statusTagType('delivered')).toBe('success')
    expect(statusTagType('failed')).toBe('danger')
    expect(statusTagType('unknown')).toBe('info')
  })

  it('statusText: 各状态映射', () => {
    expect(statusText('pending')).toBe('下发中')
    expect(statusText('delivered')).toBe('已生效')
    expect(statusText('failed')).toBe('失败')
    expect(statusText('unknown')).toBe('unknown')
  })
})
