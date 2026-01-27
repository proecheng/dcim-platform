// frontend/src/composables/bigscreen/useCameraAnimation.ts
import { type ShallowRef } from 'vue'
import * as THREE from 'three'
import gsap from 'gsap'
import type { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import type { CameraPreset } from '@/types/bigscreen'

export interface CameraAnimationOptions {
  duration?: number
  ease?: string
}

export function useCameraAnimation(
  camera: ShallowRef<THREE.PerspectiveCamera | null>,
  controls: ShallowRef<OrbitControls | null>
) {
  let currentTween: gsap.core.Tween | null = null

  // 飞行到预设视角
  function flyToPreset(preset: CameraPreset, options: CameraAnimationOptions = {}) {
    const { duration = 1.5, ease = 'power2.inOut' } = options

    if (!camera.value || !controls.value) return Promise.resolve()

    // 取消之前的动画
    if (currentTween) {
      currentTween.kill()
    }

    const cam = camera.value
    const ctrl = controls.value

    return new Promise<void>((resolve) => {
      // 同时动画相机位置和控制器目标
      const timeline = gsap.timeline({
        onComplete: () => {
          ctrl.update()
          resolve()
        },
        onUpdate: () => {
          ctrl.update()
        }
      })

      timeline.to(cam.position, {
        x: preset.position[0],
        y: preset.position[1],
        z: preset.position[2],
        duration,
        ease
      }, 0)

      timeline.to(ctrl.target, {
        x: preset.target[0],
        y: preset.target[1],
        z: preset.target[2],
        duration,
        ease
      }, 0)

      currentTween = timeline as unknown as gsap.core.Tween
    })
  }

  // 飞行到指定位置
  function flyTo(
    position: { x: number; y: number; z: number },
    target: { x: number; y: number; z: number },
    options: CameraAnimationOptions = {}
  ) {
    return flyToPreset(
      {
        position: [position.x, position.y, position.z],
        target: [target.x, target.y, target.z]
      },
      options
    )
  }

  // 飞行到对象
  function flyToObject(
    object: THREE.Object3D,
    options: CameraAnimationOptions & { distance?: number; height?: number } = {}
  ) {
    const { distance = 10, height = 5 } = options

    // 计算对象的包围盒中心
    const box = new THREE.Box3().setFromObject(object)
    const center = box.getCenter(new THREE.Vector3())

    // 计算相机位置（在对象前方）
    const position = {
      x: center.x + distance * 0.7,
      y: center.y + height,
      z: center.z + distance * 0.7
    }

    return flyTo(position, { x: center.x, y: center.y, z: center.z }, options)
  }

  // 飞行到设备（按ID查找）
  function flyToDevice(
    deviceId: string,
    scene: THREE.Scene,
    options: CameraAnimationOptions & { distance?: number; height?: number } = {}
  ) {
    const device = scene.getObjectByName(`cabinet_${deviceId}`)
    if (device) {
      return flyToObject(device, options)
    }
    return Promise.resolve()
  }

  // 环绕动画
  function orbitAround(
    center: { x: number; y: number; z: number },
    radius: number,
    options: { duration?: number; loops?: number } = {}
  ) {
    const { duration = 10, loops = 1 } = options

    if (!camera.value || !controls.value) return Promise.resolve()

    const cam = camera.value
    const ctrl = controls.value
    const startAngle = Math.atan2(cam.position.z - center.z, cam.position.x - center.x)

    return new Promise<void>((resolve) => {
      gsap.to({ angle: startAngle }, {
        angle: startAngle + Math.PI * 2 * loops,
        duration,
        ease: 'none',
        onUpdate: function() {
          const angle = this.targets()[0].angle
          cam.position.x = center.x + Math.cos(angle) * radius
          cam.position.z = center.z + Math.sin(angle) * radius
          ctrl.target.set(center.x, center.y, center.z)
          ctrl.update()
        },
        onComplete: resolve
      })
    })
  }

  // 停止当前动画
  function stopAnimation() {
    if (currentTween) {
      currentTween.kill()
      currentTween = null
    }
  }

  return {
    flyToPreset,
    flyTo,
    flyToObject,
    flyToDevice,
    orbitAround,
    stopAnimation
  }
}
