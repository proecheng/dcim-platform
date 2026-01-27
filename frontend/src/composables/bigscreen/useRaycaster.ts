// frontend/src/composables/bigscreen/useRaycaster.ts
import { ref, shallowRef, onMounted, onUnmounted, type Ref, type ShallowRef } from 'vue'
import * as THREE from 'three'
import { useBigscreenStore } from '@/stores/bigscreen'

export interface RaycasterOptions {
  recursive?: boolean
  filterTypes?: string[]
}

export function useRaycaster(
  containerRef: Ref<HTMLElement | null>,
  camera: ShallowRef<THREE.PerspectiveCamera | null>,
  scene: ShallowRef<THREE.Scene | null>,
  options: RaycasterOptions = {}
) {
  const { recursive = true, filterTypes = ['cabinet'] } = options

  const store = useBigscreenStore()
  const raycaster = new THREE.Raycaster()
  const mouse = new THREE.Vector2()

  const hoveredObject = shallowRef<THREE.Object3D | null>(null)
  const selectedObject = shallowRef<THREE.Object3D | null>(null)

  // 更新鼠标位置
  function updateMousePosition(event: MouseEvent) {
    if (!containerRef.value) return

    const rect = containerRef.value.getBoundingClientRect()
    mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
    mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1
  }

  // 执行射线检测
  function raycast(): THREE.Intersection[] {
    if (!camera.value || !scene.value) return []

    raycaster.setFromCamera(mouse, camera.value)
    const intersects = raycaster.intersectObjects(scene.value.children, recursive)

    // 过滤指定类型的对象
    return intersects.filter(intersect => {
      let obj: THREE.Object3D | null = intersect.object
      while (obj) {
        if (obj.userData?.type && filterTypes.includes(obj.userData.type)) {
          return true
        }
        obj = obj.parent
      }
      return false
    })
  }

  // 获取点击对象的根组
  function getObjectRoot(object: THREE.Object3D): THREE.Object3D | null {
    let current: THREE.Object3D | null = object
    while (current) {
      if (current.userData?.type && filterTypes.includes(current.userData.type)) {
        return current
      }
      current = current.parent
    }
    return null
  }

  // 处理鼠标移动（悬停检测）
  function handleMouseMove(event: MouseEvent) {
    updateMousePosition(event)
    const intersects = raycast()

    if (intersects.length > 0) {
      const root = getObjectRoot(intersects[0].object)
      if (root && root !== hoveredObject.value) {
        // 离开之前的对象
        if (hoveredObject.value) {
          onHoverLeave(hoveredObject.value)
        }
        // 进入新对象
        hoveredObject.value = root
        onHoverEnter(root)
      }
    } else if (hoveredObject.value) {
      onHoverLeave(hoveredObject.value)
      hoveredObject.value = null
    }
  }

  // 处理点击
  function handleClick(event: MouseEvent) {
    updateMousePosition(event)
    const intersects = raycast()

    if (intersects.length > 0) {
      const root = getObjectRoot(intersects[0].object)
      if (root) {
        // 取消之前选中
        if (selectedObject.value && selectedObject.value !== root) {
          onDeselect(selectedObject.value)
        }
        // 选中新对象
        selectedObject.value = root
        onSelect(root)

        // 更新 store
        const deviceId = root.userData?.config?.id
        if (deviceId) {
          store.selectDevice(deviceId)
        }
      }
    } else {
      // 点击空白处取消选中
      if (selectedObject.value) {
        onDeselect(selectedObject.value)
        selectedObject.value = null
        store.selectDevice(null)
      }
    }
  }

  // 悬停进入效果
  function onHoverEnter(object: THREE.Object3D) {
    if (containerRef.value) {
      containerRef.value.style.cursor = 'pointer'
    }
    // 高亮效果
    object.traverse((child) => {
      if (child instanceof THREE.Mesh && child.material) {
        const material = child.material as THREE.MeshStandardMaterial
        if (material.emissive) {
          child.userData.originalEmissive = material.emissive.getHex()
          material.emissive.setHex(0x333333)
        }
      }
    })
  }

  // 悬停离开效果
  function onHoverLeave(object: THREE.Object3D) {
    if (containerRef.value) {
      containerRef.value.style.cursor = 'default'
    }
    // 恢复原始效果
    object.traverse((child) => {
      if (child instanceof THREE.Mesh && child.material) {
        const material = child.material as THREE.MeshStandardMaterial
        if (material.emissive && child.userData.originalEmissive !== undefined) {
          material.emissive.setHex(child.userData.originalEmissive)
        }
      }
    })
  }

  // 选中效果
  function onSelect(object: THREE.Object3D) {
    object.traverse((child) => {
      if (child instanceof THREE.Mesh && child.material) {
        const material = child.material as THREE.MeshStandardMaterial
        if (material.emissive) {
          child.userData.selectedEmissive = material.emissive.getHex()
          material.emissive.setHex(0x0066ff)
        }
      }
    })
  }

  // 取消选中效果
  function onDeselect(object: THREE.Object3D) {
    object.traverse((child) => {
      if (child instanceof THREE.Mesh && child.material) {
        const material = child.material as THREE.MeshStandardMaterial
        if (material.emissive) {
          const original = child.userData.originalEmissive ?? 0x000000
          material.emissive.setHex(original)
        }
      }
    })
  }

  // 清除选中
  function clearSelection() {
    if (selectedObject.value) {
      onDeselect(selectedObject.value)
      selectedObject.value = null
      store.selectDevice(null)
    }
  }

  onMounted(() => {
    if (containerRef.value) {
      containerRef.value.addEventListener('mousemove', handleMouseMove)
      containerRef.value.addEventListener('click', handleClick)
    }
  })

  onUnmounted(() => {
    if (containerRef.value) {
      containerRef.value.removeEventListener('mousemove', handleMouseMove)
      containerRef.value.removeEventListener('click', handleClick)
    }
  })

  return {
    hoveredObject,
    selectedObject,
    clearSelection,
    raycast
  }
}
