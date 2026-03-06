/**
 * 站点切换事件总线 — 零依赖
 *
 * Story 27.6: 站点过滤贯穿数据链路
 * 各 Store 订阅站点变更事件，switchSite() 时自动重新加载数据。
 * 不引入 mitt（项目无此依赖），自定义实现 <30 行代码。
 */
type SiteChangeHandler = (siteId: number | null) => void

class SiteEventBus {
  private handlers = new Set<SiteChangeHandler>()

  /** 注册站点变更处理器，返回清理函数 */
  on(handler: SiteChangeHandler): () => void {
    this.handlers.add(handler)
    return () => this.handlers.delete(handler)
  }

  /** 发射站点变更事件 */
  emit(siteId: number | null): void {
    this.handlers.forEach(handler => {
      try {
        handler(siteId)
      } catch (e) {
        console.error('[SiteEventBus] handler error:', e)
      }
    })
  }

  /** 清除所有处理器（测试隔离用） */
  clear(): void {
    this.handlers.clear()
  }
}

export const siteEvents = new SiteEventBus()
