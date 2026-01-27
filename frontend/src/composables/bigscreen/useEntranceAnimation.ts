// frontend/src/composables/bigscreen/useEntranceAnimation.ts
import { ref, onUnmounted } from 'vue'
import gsap from 'gsap'

export interface EntranceAnimationOptions {
  duration?: number
  staggerDelay?: number
  ease?: string
}

/**
 * 大屏入场动画 composable
 * 使用 GSAP 实现面板依次入场效果
 */
export function useEntranceAnimation(options: EntranceAnimationOptions = {}) {
  const {
    duration = 0.6,
    staggerDelay = 0.1,
    ease = 'power2.out'
  } = options

  const isAnimating = ref(false)
  const isComplete = ref(false)
  let timeline: gsap.core.Timeline | null = null

  /**
   * 播放入场动画
   * 按照时序表依次播放各元素动画
   */
  function playEntrance() {
    if (isAnimating.value) return

    isAnimating.value = true
    isComplete.value = false

    timeline = gsap.timeline({
      onComplete: () => {
        isAnimating.value = false
        isComplete.value = true
      }
    })

    // 阶段1: 背景层淡入 (0-0.5s)
    timeline.from('.bigscreen-container', {
      opacity: 0,
      duration: 0.5,
      ease: 'power1.inOut'
    })

    // 阶段2: 3D场景淡入并缩放 (0.3-1.1s)
    timeline.from('.three-scene-container', {
      opacity: 0,
      scale: 0.9,
      duration: 0.8,
      ease: 'power2.out'
    }, 0.3)

    // 阶段3: 顶部栏从上滑入 (0.5-1.0s)
    timeline.from('.top-bar', {
      y: -80,
      opacity: 0,
      duration: 0.5,
      ease
    }, 0.5)

    // 阶段4: 左侧面板从左滑入 (0.8-1.2s)
    timeline.from('.left-panel', {
      x: -300,
      opacity: 0,
      duration: 0.4,
      ease
    }, 0.8)

    // 阶段5: 右侧面板从右滑入 (0.8-1.2s)
    timeline.from('.right-panel', {
      x: 300,
      opacity: 0,
      duration: 0.4,
      ease
    }, 0.8)

    // 阶段6: 底部栏从下滑入 (1.0-1.3s)
    timeline.from('.bottom-bar', {
      y: 80,
      opacity: 0,
      duration: 0.3,
      ease
    }, 1.0)

    // 阶段7: 设备详情面板淡入 (1.1-1.4s)
    timeline.from('.device-detail-panel', {
      opacity: 0,
      scale: 0.95,
      duration: 0.3,
      ease
    }, 1.1)

    return timeline
  }

  /**
   * 播放机柜群升起动画
   * 适用于3D场景中的机柜模型
   */
  function playCabinetRise(cabinets: HTMLElement[] | NodeListOf<Element>) {
    if (!cabinets || cabinets.length === 0) return null

    return gsap.from(cabinets, {
      y: 50,
      opacity: 0,
      duration: 0.6,
      stagger: staggerDelay,
      ease: 'back.out(1.2)'
    })
  }

  /**
   * 播放数据面板内容动画
   * 面板出现后，内部元素依次显示
   */
  function playPanelContent(panelSelector: string) {
    const panel = document.querySelector(panelSelector)
    if (!panel) return null

    const items = panel.querySelectorAll('.panel-item, .chart-container, .data-row')
    if (items.length === 0) return null

    return gsap.from(items, {
      y: 20,
      opacity: 0,
      duration: 0.3,
      stagger: 0.05,
      ease: 'power1.out'
    })
  }

  /**
   * 播放KPI数字高亮动画
   */
  function playKpiHighlight(selector: string) {
    return gsap.fromTo(selector, {
      scale: 1,
      textShadow: '0 0 0 transparent'
    }, {
      scale: 1.1,
      textShadow: '0 0 20px rgba(0, 204, 255, 0.8)',
      duration: 0.3,
      yoyo: true,
      repeat: 1,
      ease: 'power2.inOut'
    })
  }

  /**
   * 播放边框光效流动动画
   */
  function playBorderGlow(selector: string) {
    return gsap.to(selector, {
      '--glow-position': '100%',
      duration: 2,
      repeat: -1,
      ease: 'none'
    })
  }

  /**
   * 停止所有动画
   */
  function stopAll() {
    if (timeline) {
      timeline.kill()
      timeline = null
    }
    gsap.killTweensOf('*')
    isAnimating.value = false
  }

  /**
   * 跳过入场动画，直接显示
   */
  function skipEntrance() {
    stopAll()

    // 重置所有元素到最终状态
    gsap.set([
      '.bigscreen-container',
      '.three-scene-container',
      '.top-bar',
      '.left-panel',
      '.right-panel',
      '.bottom-bar',
      '.device-detail-panel'
    ], {
      clearProps: 'all'
    })

    isComplete.value = true
  }

  /**
   * 播放退出动画
   */
  function playExit() {
    if (isAnimating.value) return

    isAnimating.value = true

    const exitTimeline = gsap.timeline({
      onComplete: () => {
        isAnimating.value = false
      }
    })

    exitTimeline.to('.bottom-bar', {
      y: 80,
      opacity: 0,
      duration: 0.3,
      ease: 'power2.in'
    })

    exitTimeline.to(['.left-panel', '.right-panel'], {
      x: (index) => index === 0 ? -300 : 300,
      opacity: 0,
      duration: 0.3,
      ease: 'power2.in'
    }, 0.1)

    exitTimeline.to('.top-bar', {
      y: -80,
      opacity: 0,
      duration: 0.3,
      ease: 'power2.in'
    }, 0.2)

    exitTimeline.to('.bigscreen-container', {
      opacity: 0,
      duration: 0.4,
      ease: 'power1.inOut'
    }, 0.3)

    return exitTimeline
  }

  // 清理
  onUnmounted(() => {
    stopAll()
  })

  return {
    isAnimating,
    isComplete,
    playEntrance,
    playCabinetRise,
    playPanelContent,
    playKpiHighlight,
    playBorderGlow,
    stopAll,
    skipEntrance,
    playExit
  }
}
