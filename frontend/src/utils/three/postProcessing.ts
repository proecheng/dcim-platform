// frontend/src/utils/three/postProcessing.ts
import * as THREE from 'three'
import { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js'
import { RenderPass } from 'three/examples/jsm/postprocessing/RenderPass.js'
import { UnrealBloomPass } from 'three/examples/jsm/postprocessing/UnrealBloomPass.js'
import { OutputPass } from 'three/examples/jsm/postprocessing/OutputPass.js'
import { OutlinePass } from 'three/examples/jsm/postprocessing/OutlinePass.js'

export interface PostProcessingOptions {
  bloom?: {
    enabled: boolean
    strength?: number
    radius?: number
    threshold?: number
  }
  outline?: {
    enabled: boolean
    edgeStrength?: number
    edgeGlow?: number
    edgeThickness?: number
    pulsePeriod?: number
    visibleEdgeColor?: number
    hiddenEdgeColor?: number
  }
}

export interface PostProcessingSetup {
  composer: EffectComposer
  bloomPass: UnrealBloomPass | null
  outlinePass: OutlinePass | null
  setBloomEnabled: (enabled: boolean) => void
  setBloomStrength: (strength: number) => void
  setOutlineEnabled: (enabled: boolean) => void
  setOutlineObjects: (objects: THREE.Object3D[]) => void
  setOutlineColor: (visible: number, hidden?: number) => void
  resize: (width: number, height: number) => void
  render: () => void
  dispose: () => void
}

export function setupPostProcessing(
  renderer: THREE.WebGLRenderer,
  scene: THREE.Scene,
  camera: THREE.Camera,
  options: PostProcessingOptions = {}
): PostProcessingSetup {
  const {
    bloom = { enabled: false },
    outline = { enabled: true }
  } = options

  // 创建 EffectComposer
  const composer = new EffectComposer(renderer)
  const resolution = new THREE.Vector2(window.innerWidth, window.innerHeight)

  // 渲染通道
  const renderPass = new RenderPass(scene, camera)
  composer.addPass(renderPass)

  // 轮廓高亮通道
  let outlinePass: OutlinePass | null = null
  if (outline.enabled) {
    outlinePass = new OutlinePass(resolution, scene, camera)
    outlinePass.edgeStrength = outline.edgeStrength ?? 3.0
    outlinePass.edgeGlow = outline.edgeGlow ?? 1.0
    outlinePass.edgeThickness = outline.edgeThickness ?? 2.0
    outlinePass.pulsePeriod = outline.pulsePeriod ?? 2
    outlinePass.visibleEdgeColor.setHex(outline.visibleEdgeColor ?? 0x00ccff)
    outlinePass.hiddenEdgeColor.setHex(outline.hiddenEdgeColor ?? 0x004466)
    composer.addPass(outlinePass)
  }

  // 泛光通道
  let bloomPass: UnrealBloomPass | null = null
  if (bloom.enabled) {
    bloomPass = new UnrealBloomPass(
      resolution,
      bloom.strength ?? 0.5,
      bloom.radius ?? 0.4,
      bloom.threshold ?? 0.85
    )
    composer.addPass(bloomPass)
  }

  // 输出通道
  const outputPass = new OutputPass()
  composer.addPass(outputPass)

  // 设置泛光开关
  function setBloomEnabled(enabled: boolean) {
    if (bloomPass) {
      bloomPass.enabled = enabled
    }
  }

  // 设置泛光强度
  function setBloomStrength(strength: number) {
    if (bloomPass) {
      bloomPass.strength = strength
    }
  }

  // 设置轮廓高亮开关
  function setOutlineEnabled(enabled: boolean) {
    if (outlinePass) {
      outlinePass.enabled = enabled
    }
  }

  // 设置要高亮的对象
  function setOutlineObjects(objects: THREE.Object3D[]) {
    if (outlinePass) {
      outlinePass.selectedObjects = objects
    }
  }

  // 设置轮廓颜色
  function setOutlineColor(visible: number, hidden?: number) {
    if (outlinePass) {
      outlinePass.visibleEdgeColor.setHex(visible)
      if (hidden !== undefined) {
        outlinePass.hiddenEdgeColor.setHex(hidden)
      }
    }
  }

  // 调整大小
  function resize(width: number, height: number) {
    composer.setSize(width, height)
    if (bloomPass) {
      bloomPass.resolution.set(width, height)
    }
    if (outlinePass) {
      outlinePass.resolution.set(width, height)
    }
  }

  // 渲染
  function render() {
    composer.render()
  }

  // 清理
  function dispose() {
    composer.dispose()
  }

  return {
    composer,
    bloomPass,
    outlinePass,
    setBloomEnabled,
    setBloomStrength,
    setOutlineEnabled,
    setOutlineObjects,
    setOutlineColor,
    resize,
    render,
    dispose
  }
}
