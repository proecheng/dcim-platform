# Story 23.2: 大屏3D楼层场景加载

## Story

**As a** 运维工程师,
**I want to** 在大屏3D模式下切换楼层时加载对应的3D场景,
**So that** 我可以直观查看数据中心设备的空间分布和运行状态。

## 状态

- **状态**: 开发中
- **优先级**: 高
- **预估工作量**: Medium (4-6小时)

## 验收标准 (AC)

### AC 1: 程序化生成3D机柜场景
- **Given** 用户在大屏页面切换到3D模式
- **When** 选择特定楼层
- **Then** 基于空间拓扑数据（行/列号、冷热通道分配），用 Three.js BoxGeometry 生成机柜（按行列排列），PlaneGeometry 生成地板，不同颜色区分冷通道（蓝色半透明）和热通道（红色半透明）

### AC 2: 标准42U机柜比例
- **Given** 3D场景已生成
- **When** 场景渲染完成
- **Then** 机柜尺寸按标准42U比例（宽0.6m×深1.2m×高2.0m），间距基于冷热通道宽度（冷通道1.2m，热通道0.9m）

### AC 3: 拓扑数据获取与默认布局
- **Given** 用户切换楼层
- **When** 后端有空间拓扑数据（行/列号）
- **Then** 从 `/v1/spatial/tree` API 获取数据生成场景
- **When** 后端无数据
- **Then** 使用默认4×10机柜布局作为演示

### AC 4: 设备状态着色
- **Given** 3D场景已生成
- **When** 设备实时数据更新
- **Then** 机柜按状态着色：正常-绿色、告警-红色脉冲动画、离线-灰色

### AC 5: 鼠标/触摸交互
- **Given** 3D场景已显示
- **When** 用户操作鼠标
- **Then** 支持旋转（左键拖拽）、缩放（滚轮）、平移（右键拖拽）

### AC 6: 设备点击联动
- **Given** 3D场景已显示
- **When** 用户点击机柜模型
- **Then** 触发设备选择事件，联动右侧设备详情面板

### AC 7: WebGL降级
- **Given** 浏览器不支持WebGL或3D场景生成失败
- **When** 检测到异常
- **Then** 自动降级到2D平面图模式

### AC 8: 无拓扑数据处理
- **Given** 楼层没有对应空间拓扑数据
- **When** 切换到该楼层
- **Then** 保持当前2D平面图模式并 console 记录

## 技术设计

### 架构决策
- 创建独立子组件 `BigscreenFloor3D.vue` 放在 `components/bigscreen/` 目录
- 最小化修改 `bigscreen/index.vue`：替换 `handleFloorChange` 中的 TODO 注释
- 复用现有 API：`spatial.ts` 的 `getSpatialTree()` 获取拓扑数据
- 复用 `useBigscreenStore` 的 `deviceData` 获取设备实时状态
- 纯程序化生成，不加载外部3D模型文件

### 数据流
```
FloorSelector → handleFloorChange(3D模式) → BigscreenFloor3D
  → getSpatialTree() → 解析楼层拓扑 → 程序化生成场景
  → store.deviceData → 实时状态着色
  → 点击机柜 → store.selectDevice() → DeviceDetailPanel
```

### 3D场景结构
- 地板: PlaneGeometry, 灰色材质
- 机柜: BoxGeometry (0.6×2.0×1.2), MeshStandardMaterial
- 冷通道: PlaneGeometry, 蓝色半透明 (opacity: 0.15)
- 热通道: PlaneGeometry, 红色半透明 (opacity: 0.15)
- 光照: AmbientLight + DirectionalLight
- 控制: OrbitControls (旋转/缩放/平移)

### 修改文件清单
| 文件 | 修改类型 | 说明 |
|------|---------|------|
| `frontend/src/components/bigscreen/BigscreenFloor3D.vue` | 新增 | 3D楼层场景组件 |
| `frontend/src/views/bigscreen/index.vue` | 修改 | 集成3D组件，替换TODO |

## 对抗性审查

### 风险评估
1. **WebGL兼容性**: 部分旧浏览器不支持 → 已设计降级逻辑
2. **性能**: 大量机柜可能影响帧率 → 使用 InstancedMesh 或限制最大渲染数
3. **数据缺失**: 后端可能无拓扑数据 → 默认4×10布局兜底
4. **内存泄漏**: Three.js 对象需手动释放 → onUnmounted 中 dispose 所有资源

### 审查结论
- 方案可行，风险可控
- 降级策略完善
- 与现有架构融合度高
