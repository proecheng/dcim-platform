// frontend/src/composables/bigscreen/useThreeScene.ts
import { ref, shallowRef, onMounted, onUnmounted, type Ref } from 'vue'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { CSS2DRenderer } from 'three/examples/jsm/renderers/CSS2DRenderer.js'
import { RGBELoader } from 'three/examples/jsm/loaders/RGBELoader.js'
import { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js'
import { RenderPass } from 'three/examples/jsm/postprocessing/RenderPass.js'
import { UnrealBloomPass } from 'three/examples/jsm/postprocessing/UnrealBloomPass.js'

export interface UseThreeSceneOptions {
  antialias?: boolean
  alpha?: boolean
  backgroundColor?: number
  enablePostProcessing?: boolean
  enableEnvMap?: boolean
}

export function useThreeScene(
  containerRef: Ref<HTMLElement | null>,
  options: UseThreeSceneOptions = {}
) {
  const {
    antialias = true,
    alpha = false,
    backgroundColor = 0x0a0a1a,
    enablePostProcessing = true,
    enableEnvMap = true
  } = options

  // 使用 shallowRef 避免深度响应式（Three.js 对象很大）
  const scene = shallowRef<THREE.Scene | null>(null)
  const camera = shallowRef<THREE.PerspectiveCamera | null>(null)
  const renderer = shallowRef<THREE.WebGLRenderer | null>(null)
  const controls = shallowRef<OrbitControls | null>(null)
  const labelRenderer = shallowRef<CSS2DRenderer | null>(null)
  const composer = shallowRef<EffectComposer | null>(null)

  const isInitialized = ref(false)
  let animationFrameId: number | null = null
  let needsRender = true // 按需渲染标志

  // 初始化场景
  function initScene() {
    if (!containerRef.value) return

    const container = containerRef.value
    const width = container.clientWidth
    const height = container.clientHeight

    // 创建场景
    const newScene = new THREE.Scene()
    newScene.background = new THREE.Color(backgroundColor)
    scene.value = newScene

    // 创建相机 - 使用更窄的FOV增强透视深度感
    const newCamera = new THREE.PerspectiveCamera(45, width / height, 0.1, 500)
    newCamera.position.set(0, 35, 40)
    newCamera.lookAt(0, 0, 0)
    camera.value = newCamera

    // 创建渲染器
    const newRenderer = new THREE.WebGLRenderer({ antialias, alpha })
    newRenderer.setSize(width, height)
    newRenderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    newRenderer.shadowMap.enabled = true
    newRenderer.shadowMap.type = THREE.PCFSoftShadowMap
    newRenderer.toneMapping = THREE.ACESFilmicToneMapping
    newRenderer.toneMappingExposure = 1.2
    newRenderer.outputColorSpace = THREE.SRGBColorSpace
    container.appendChild(newRenderer.domElement)
    renderer.value = newRenderer

    // 创建轨道控制器
    const newControls = new OrbitControls(newCamera, newRenderer.domElement)
    newControls.enableDamping = true
    newControls.dampingFactor = 0.05
    newControls.minDistance = 5
    newControls.maxDistance = 100
    newControls.maxPolarAngle = Math.PI / 2.1
    // 监听控制器变化以触发渲染
    newControls.addEventListener('change', requestRender)
    controls.value = newControls

    // 创建标签渲染器 (CSS2DRenderer)
    const newLabelRenderer = new CSS2DRenderer()
    newLabelRenderer.setSize(width, height)
    newLabelRenderer.domElement.style.position = 'absolute'
    newLabelRenderer.domElement.style.top = '0'
    newLabelRenderer.domElement.style.left = '0'
    newLabelRenderer.domElement.style.pointerEvents = 'none'
    container.appendChild(newLabelRenderer.domElement)
    labelRenderer.value = newLabelRenderer

    // 添加灯光
    setupLights(newScene)

    // 设置后处理效果（轻量级）
    if (enablePostProcessing) {
      setupPostProcessing(newScene, newCamera, newRenderer, width, height)
    }

    // 加载HDR环境贴图增强金属反射
    if (enableEnvMap) {
      setupEnvironmentMap(newScene, newRenderer)
    }

    isInitialized.value = true
  }

  // 设置灯光 - 优化光照增强立体感
  function setupLights(targetScene: THREE.Scene) {
    // 环境光 - 提供基础照明
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.4)
    targetScene.add(ambientLight)

    // 半球光 - 模拟天空和地面的自然光照
    const hemisphereLight = new THREE.HemisphereLight(0x88ccff, 0x444466, 0.5)
    targetScene.add(hemisphereLight)

    // 主方向光 - 优化阴影设置
    const directionalLight = new THREE.DirectionalLight(0xffffff, 1.2)
    directionalLight.position.set(30, 60, 30)
    directionalLight.castShadow = true
    directionalLight.shadow.mapSize.width = 1024
    directionalLight.shadow.mapSize.height = 1024
    directionalLight.shadow.camera.near = 1
    directionalLight.shadow.camera.far = 200
    directionalLight.shadow.camera.left = -50
    directionalLight.shadow.camera.right = 50
    directionalLight.shadow.camera.top = 50
    directionalLight.shadow.camera.bottom = -50
    directionalLight.shadow.bias = -0.001
    targetScene.add(directionalLight)

    // 强补光 - 从侧面打光增强立体感
    const fillLight = new THREE.DirectionalLight(0x4488ff, 0.6)
    fillLight.position.set(-40, 30, -30)
    targetScene.add(fillLight)

    // 边缘光 - 从背后打光强调物体轮廓
    const rimLight = new THREE.DirectionalLight(0xffffff, 0.4)
    rimLight.position.set(0, 20, -60)
    targetScene.add(rimLight)
  }

  // 设置HDR环境贴图
  function setupEnvironmentMap(targetScene: THREE.Scene, targetRenderer: THREE.WebGLRenderer) {
    // 创建一个简单的程序化环境贴图（避免加载外部文件）
    const pmremGenerator = new THREE.PMREMGenerator(targetRenderer)
    pmremGenerator.compileEquirectangularShader()

    // 创建渐变环境
    const envScene = new THREE.Scene()
    const envGeometry = new THREE.SphereGeometry(500, 32, 32)
    const envMaterial = new THREE.ShaderMaterial({
      uniforms: {
        topColor: { value: new THREE.Color(0x0a1628) },
        bottomColor: { value: new THREE.Color(0x1a2a4a) },
        offset: { value: 200 },
        exponent: { value: 0.6 }
      },
      vertexShader: `
        varying vec3 vWorldPosition;
        void main() {
          vec4 worldPosition = modelMatrix * vec4(position, 1.0);
          vWorldPosition = worldPosition.xyz;
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }
      `,
      fragmentShader: `
        uniform vec3 topColor;
        uniform vec3 bottomColor;
        uniform float offset;
        uniform float exponent;
        varying vec3 vWorldPosition;
        void main() {
          float h = normalize(vWorldPosition + offset).y;
          gl_FragColor = vec4(mix(bottomColor, topColor, max(pow(max(h, 0.0), exponent), 0.0)), 1.0);
        }
      `,
      side: THREE.BackSide
    })

    const envMesh = new THREE.Mesh(envGeometry, envMaterial)
    envScene.add(envMesh)

    // 添加一些光点模拟反射高光
    const pointLightGeometry = new THREE.SphereGeometry(5, 16, 16)
    const pointLightMaterial = new THREE.MeshBasicMaterial({ color: 0xffffff })
    const points = [
      { pos: [100, 100, 100], intensity: 1.0 },
      { pos: [-100, 80, 50], intensity: 0.7 },
      { pos: [50, 60, -100], intensity: 0.5 }
    ]

    points.forEach(p => {
      const pointMesh = new THREE.Mesh(pointLightGeometry, pointLightMaterial.clone())
      pointMesh.position.set(p.pos[0], p.pos[1], p.pos[2])
      ;(pointMesh.material as THREE.MeshBasicMaterial).color.multiplyScalar(p.intensity)
      envScene.add(pointMesh)
    })

    // 生成环境贴图
    const envMapRenderTarget = pmremGenerator.fromScene(envScene)
    targetScene.environment = envMapRenderTarget.texture

    // 清理
    pmremGenerator.dispose()
  }

  // 设置后处理效果 - 轻量级（移除SSAO）
  function setupPostProcessing(
    targetScene: THREE.Scene,
    targetCamera: THREE.PerspectiveCamera,
    targetRenderer: THREE.WebGLRenderer,
    width: number,
    height: number
  ) {
    const newComposer = new EffectComposer(targetRenderer)

    // 基础渲染通道
    const renderPass = new RenderPass(targetScene, targetCamera)
    newComposer.addPass(renderPass)

    // 轻量泛光效果 - 只增强发光物体
    const bloomPass = new UnrealBloomPass(
      new THREE.Vector2(width, height),
      0.2,   // strength - 降低强度
      0.3,   // radius
      0.9    // threshold - 提高阈值，只对高亮区域生效
    )
    newComposer.addPass(bloomPass)

    composer.value = newComposer
  }

  // 请求渲染（按需渲染）
  function requestRender() {
    needsRender = true
  }

  // 渲染循环 - 优化为按需渲染
  function animate() {
    animationFrameId = requestAnimationFrame(animate)

    if (controls.value) {
      controls.value.update()
    }

    // 只在需要时渲染
    if (needsRender || controls.value?.enabled) {
      if (composer.value) {
        composer.value.render()
      } else if (renderer.value && scene.value && camera.value) {
        renderer.value.render(scene.value, camera.value)
      }

      // 渲染 CSS2D 标签
      if (labelRenderer.value && scene.value && camera.value) {
        labelRenderer.value.render(scene.value, camera.value)
      }

      needsRender = false
    }
  }

  // 处理窗口大小变化
  function handleResize() {
    if (!containerRef.value || !camera.value || !renderer.value) return

    const width = containerRef.value.clientWidth
    const height = containerRef.value.clientHeight

    camera.value.aspect = width / height
    camera.value.updateProjectionMatrix()
    renderer.value.setSize(width, height)

    // 同步更新标签渲染器尺寸
    if (labelRenderer.value) {
      labelRenderer.value.setSize(width, height)
    }

    // 更新后处理效果尺寸
    if (composer.value) {
      composer.value.setSize(width, height)
    }

    requestRender()
  }

  // 启动渲染
  function startRendering() {
    if (!animationFrameId) {
      animate()
    }
  }

  // 停止渲染
  function stopRendering() {
    if (animationFrameId) {
      cancelAnimationFrame(animationFrameId)
      animationFrameId = null
    }
  }

  // 销毁场景
  function dispose() {
    stopRendering()

    if (controls.value) {
      controls.value.removeEventListener('change', requestRender)
      controls.value.dispose()
    }

    if (composer.value) {
      composer.value.dispose()
    }

    if (renderer.value) {
      renderer.value.dispose()
      renderer.value.domElement.remove()
    }

    // 清理标签渲染器
    if (labelRenderer.value) {
      labelRenderer.value.domElement.remove()
      labelRenderer.value = null
    }

    if (scene.value) {
      scene.value.traverse((object) => {
        if (object instanceof THREE.Mesh) {
          object.geometry.dispose()
          if (Array.isArray(object.material)) {
            object.material.forEach((m) => m.dispose())
          } else {
            object.material.dispose()
          }
        }
      })
      scene.value.clear()
    }

    scene.value = null
    camera.value = null
    renderer.value = null
    controls.value = null
    composer.value = null
    isInitialized.value = false
  }

  onMounted(() => {
    initScene()
    startRendering()
    window.addEventListener('resize', handleResize)
  })

  onUnmounted(() => {
    window.removeEventListener('resize', handleResize)
    dispose()
  })

  return {
    scene,
    camera,
    renderer,
    controls,
    labelRenderer,
    composer,
    isInitialized,
    handleResize,
    startRendering,
    stopRendering,
    requestRender,
    dispose
  }
}
