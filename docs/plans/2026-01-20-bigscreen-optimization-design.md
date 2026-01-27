# 数字孪生大屏性能与视觉优化设计方案

**日期:** 2026-01-20
**状态:** 已实施
**目标:** 解决大屏响应慢、卡顿严重、3D效果不足、功率标签遮挡机柜等问题

---

## 实施状态

| 优化项 | 状态 |
|--------|------|
| 移除SSAO后处理 | ✅ 已完成 |
| 简化机柜几何体 | ✅ 已完成 |
| 材质缓存共享 | ✅ 已完成 |
| 几何体缓存共享 | ✅ 已完成 |
| 添加程序化环境贴图 | ✅ 已完成 |
| 调整相机FOV (60°→45°) | ✅ 已完成 |
| 优化材质参数 | ✅ 已完成 |
| 紧凑型功率标签 | ✅ 已完成 |

---

## 问题诊断

### 1. 性能问题根因

| 问题 | 详情 | 影响程度 |
|------|------|----------|
| **SSAOPass** | 全屏多次采样计算环境光遮蔽 | 严重 - GPU消耗最大 |
| **几何体过于复杂** | 每个机柜~30个mesh（槽位、LED、通风孔等） | 严重 - 16柜=480+网格 |
| **ExtrudeGeometry** | 圆角几何体顶点数是BoxGeometry的10倍+ | 中等 |
| **材质未共享** | 每个小部件独立材质实例 | 中等 |
| **深度监听器** | `watch(..., { deep: true })` 频繁触发 | 轻微 |
| **持续渲染** | 即使场景无变化也在渲染 | 轻微（已部分优化） |

### 2. 3D效果不足根因

| 问题 | 详情 |
|------|------|
| **无环境贴图** | 材质缺少反射，金属感不足 |
| **无法线贴图** | 表面过于光滑，缺少纹理细节 |
| **光照单一** | 虽有多光源，但缺少对比和层次 |
| **相机FOV过大** | FOV=60导致透视变形，立体感弱 |

### 3. UI布局问题

- **功率标签** (CabinetLabels.vue): 显示为长条形，遮挡机柜主体
- 标签位置在机柜正上方 (y+2.3)，从俯视角度看会覆盖机柜

---

## 优化方案

### Phase 1: 性能优化（立即修复卡顿）

#### 1.1 移除SSAO，使用轻量替代方案

```typescript
// 移除 SSAOPass
// 替代方案：通过材质的 envMapIntensity 和边缘光模拟深度感
```

**理由**: SSAO是性能杀手，但其效果可以通过其他方式部分模拟：
- 使用预烘焙的环境遮蔽纹理
- 增强边缘光和补光
- 使用雾效模拟远距离衰减

#### 1.2 简化几何体

**当前状态 (每个机柜):**
- 主体 (ExtrudeGeometry) ~200顶点
- 顶框 (BoxGeometry) ~24顶点
- 底座 (BoxGeometry) ~24顶点
- 前面板 (PlaneGeometry) ~4顶点
- 8个槽位 (BoxGeometry) ~192顶点
- 8个LED (BoxGeometry) ~192顶点
- 10个通风孔 (PlaneGeometry) ~40顶点
- 指示灯 (SphereGeometry) ~360顶点
- 光晕 (RingGeometry) ~64顶点
- **总计: ~1100顶点/机柜**

**优化后 (每个机柜):**
- 主体 (BoxGeometry) ~24顶点
- 顶框+底座 (合并) ~48顶点
- 前面板纹理 (单一PlaneGeometry) ~4顶点
- 指示灯 (SphereGeometry低精度) ~96顶点
- **总计: ~172顶点/机柜**

**优化方法:**
1. 使用简单BoxGeometry替代ExtrudeGeometry
2. 用纹理代替槽位和通风孔的几何体
3. 共享材质实例

#### 1.3 材质共享与合批

```typescript
// 创建共享材质池
const MaterialPool = {
  cabinetBody: new THREE.MeshStandardMaterial({...}),
  cabinetFrame: new THREE.MeshStandardMaterial({...}),
  led: {
    green: new THREE.MeshStandardMaterial({...}),
    blue: new THREE.MeshStandardMaterial({...})
  }
}

// 所有机柜使用相同材质引用
const body = new THREE.Mesh(geometry, MaterialPool.cabinetBody)
```

#### 1.4 使用InstancedMesh合批渲染

```typescript
// 所有相同类型的机柜使用InstancedMesh
const cabinetGeometry = new THREE.BoxGeometry(0.6, 2.0, 1.0)
const cabinetMaterial = MaterialPool.cabinetBody
const instancedCabinets = new THREE.InstancedMesh(
  cabinetGeometry,
  cabinetMaterial,
  cabinetCount // 16个机柜 = 1次绘制调用
)
```

**性能提升**: 从16次Draw Call减少到1次

### Phase 2: 视觉增强（不影响性能）

#### 2.1 添加HDR环境贴图

```typescript
import { RGBELoader } from 'three/examples/jsm/loaders/RGBELoader.js'

const pmremGenerator = new THREE.PMREMGenerator(renderer)
new RGBELoader().load('/textures/studio_small.hdr', (texture) => {
  const envMap = pmremGenerator.fromEquirectangular(texture).texture
  scene.environment = envMap
  scene.background = new THREE.Color(0x0a0a1a) // 保持深色背景
})
```

**效果**: 金属材质自动获得真实反射，增强3D感

#### 2.2 调整相机参数

```typescript
// 当前
const camera = new THREE.PerspectiveCamera(60, width/height, 0.1, 1000)

// 优化后 - 更窄的FOV增强透视深度感
const camera = new THREE.PerspectiveCamera(45, width/height, 0.1, 500)
camera.position.set(0, 35, 40) // 调整位置保持视野范围
```

#### 2.3 增强材质设置

```typescript
const cabinetMaterial = new THREE.MeshStandardMaterial({
  color: 0x2a2a3a,
  roughness: 0.3,      // 降低粗糙度，增加反射
  metalness: 0.7,      // 增加金属感
  envMapIntensity: 1.0 // 环境反射强度
})
```

### Phase 3: UI布局优化

#### 3.1 功率标签重新设计

**当前问题**: 长条标签遮挡机柜

**解决方案1 - 缩小标签并改为角标形式:**

```typescript
function updateLabelDiv(div: HTMLDivElement, name: string, power: number) {
  div.innerHTML = `
    <div class="compact-label">
      <span class="power">${power.toFixed(1)}</span>
      <span class="unit">kW</span>
    </div>
  `
  div.style.cssText = `
    background: rgba(0, 20, 40, 0.85);
    border: 1px solid rgba(0, 136, 255, 0.5);
    border-radius: 3px;
    padding: 2px 5px;
    font-size: 10px;
    color: #fff;
    white-space: nowrap;
    transform: translateX(-50%);
  `
}
```

**解决方案2 - 将标签放置在机柜侧面而非上方:**

```typescript
// 修改标签位置，放在机柜右前角
label.position.copy(position)
label.position.x += 0.4  // 偏移到右侧
label.position.y += 2.5  // 稍微高于机柜
label.position.z += 0.3  // 偏移到前方
```

**解决方案3 - 只显示名称，功率集成到机柜模型上:**

用3D文字或贴图直接显示在机柜表面，悬停时才显示详细信息。

#### 3.2 信息分层显示

```typescript
// 根据相机距离动态调整标签显示
function updateLabelVisibility(camera: THREE.Camera) {
  const distance = camera.position.distanceTo(new THREE.Vector3(0, 0, 0))

  labelMap.forEach((label, id) => {
    if (distance > 50) {
      // 远距离只显示告警设备标签
      const data = store.deviceData[id]
      label.visible = data?.status === 'alarm'
    } else if (distance > 30) {
      // 中距离显示简化标签
      showCompactLabel(label)
    } else {
      // 近距离显示完整信息
      showDetailedLabel(label)
    }
  })
}
```

---

## 推荐实施顺序

### 第一步: 紧急性能修复
1. 移除SSAOPass
2. 简化机柜几何体（移除槽位、通风孔等细节）
3. 共享材质实例

**预期效果**: 帧率从~15fps提升到~60fps

### 第二步: 视觉增强
1. 添加HDR环境贴图
2. 调整相机FOV
3. 优化材质参数

**预期效果**: 3D立体感显著增强

### 第三步: UI优化
1. 缩小功率标签
2. 调整标签位置
3. 添加距离自适应显示

**预期效果**: 标签不再遮挡机柜

---

## 技术细节

### 移除的代码

```typescript
// useThreeScene.ts - 移除这些
import { SSAOPass } from 'three/examples/jsm/postprocessing/SSAOPass.js'

// 删除 SSAOPass 相关配置
const ssaoPass = new SSAOPass(...)  // 删除
newComposer.addPass(ssaoPass)       // 删除
```

### 简化的机柜生成函数

```typescript
// modelGenerator.ts - 简化版
export function createCabinetSimple(config: CabinetConfig): THREE.Mesh {
  const size = config.size || DEFAULT_CABINET_SIZE

  // 单一BoxGeometry
  const geometry = new THREE.BoxGeometry(size.width, size.height, size.depth)

  // 使用共享材质
  const material = getCabinetMaterial(config.status)

  const cabinet = new THREE.Mesh(geometry, material)
  cabinet.position.set(
    config.position.x,
    size.height / 2,
    config.position.z
  )
  cabinet.castShadow = true
  cabinet.receiveShadow = true
  cabinet.name = `cabinet_${config.id}`
  cabinet.userData = { type: 'cabinet', config }

  return cabinet
}

// 材质缓存
const materialCache = new Map<string, THREE.Material>()

function getCabinetMaterial(status: string): THREE.Material {
  if (!materialCache.has(status)) {
    materialCache.set(status, new THREE.MeshStandardMaterial({
      color: status === 'alarm' ? 0x3a2020 : 0x2a2a3a,
      roughness: 0.3,
      metalness: 0.7
    }))
  }
  return materialCache.get(status)!
}
```

---

## 验证标准

| 指标 | 当前值 | 目标值 |
|------|--------|--------|
| FPS | ~15fps | 60fps |
| Draw Calls | 500+ | <100 |
| 三角形数 | 50,000+ | <10,000 |
| 首次加载时间 | 5-8秒 | <2秒 |
| 标签遮挡 | 严重 | 无 |
| 3D立体感 | 弱 | 强 |

---

## 备选方案

如果InstancedMesh方案复杂度过高，可采用渐进式优化：

1. **Level 1**: 只移除SSAO，保留其他（最小改动）
2. **Level 2**: 简化几何体 + 移除SSAO
3. **Level 3**: 完整优化（InstancedMesh + HDR环境贴图）

---

*本方案将显著提升大屏性能和视觉效果，同时解决UI遮挡问题。*
