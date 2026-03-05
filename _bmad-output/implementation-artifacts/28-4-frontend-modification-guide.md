# 前端组件修改说明 - Story 28.4

## 文件: frontend/src/components/DemoDataLoader.vue

### 需要修改的部分

#### 1. 导入新的 API 方法
```typescript
import {
  getDemoStatus,
  loadDemoData,
  unloadDemoData,
  unloadDemoDataPreview,  // 新增
  getDemoDataStats,        // 新增
  getDemoProgress,
  refreshDemoDataDates
} from '@/api/modules/demo'
```

#### 2. 添加响应式数据
```typescript
const unloadStats = ref<Record<string, number>>({})
const showUnloadPreview = ref(false)
```

#### 3. 修改卸载方法
```typescript
// 原方法
const handleUnload = async () => {
  ElMessageBox.confirm('确定要卸载演示数据吗？此操作不可恢复！', '警告', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(async () => {
    // ... 执行卸载
  })
}

// 修改为
const handleUnload = async () => {
  try {
    // 1. 先获取删除预览
    const previewRes = await unloadDemoDataPreview()
    if (previewRes.code === 0) {
      unloadStats.value = previewRes.data.stats || {}
      showUnloadPreview.value = true
    }
  } catch (error) {
    ElMessage.error('获取删除预览失败')
  }
}

// 新增确认卸载方法
const confirmUnload = async () => {
  ElMessageBox.confirm(
    `即将删除以下 Demo 数据：\n${formatStats(unloadStats.value)}\n\n此操作不可恢复，确定继续吗？`,
    '确认卸载',
    {
      confirmButtonText: '确定卸载',
      cancelButtonText: '取消',
      type: 'warning',
      dangerouslyUseHTMLString: true
    }
  ).then(async () => {
    try {
      const res = await unloadDemoData()
      if (res.code === 0) {
        ElMessage.success('演示数据卸载成功')
        showUnloadPreview.value = false
        await checkStatus()
      } else {
        ElMessage.error(res.message || '卸载失败')
      }
    } catch (error) {
      ElMessage.error('卸载失败')
    }
  })
}

// 格式化统计信息
const formatStats = (stats: Record<string, number>) => {
  const labels: Record<string, string> = {
    devices: '设备',
    points: '点位',
    sites: '站点',
    floors: '楼层',
    rooms: '房间',
    rows: '机柜排',
    transformers: '变压器',
    meter_points: '计量点',
    distribution_panels: '配电柜',
    distribution_circuits: '配电回路',
    power_devices: '用电设备',
    cooling_groups: '空调群控组',
    cooling_units: '精密空调',
    cold_aisles: '冷通道',
    alarm_thresholds: '告警阈值',
    floor_maps: '楼层平面图',
    electricity_pricing: '电价配置'
  }

  return Object.entries(stats)
    .map(([key, count]) => `${labels[key] || key}: ${count} 条`)
    .join('<br/>')
}
```

#### 4. 添加预览对话框（可选）
```vue
<el-dialog
  v-model="showUnloadPreview"
  title="删除预览"
  width="500px"
>
  <div class="unload-preview">
    <el-alert
      title="以下 Demo 数据将被删除"
      type="warning"
      :closable="false"
      style="margin-bottom: 16px"
    />
    <el-descriptions :column="1" border>
      <el-descriptions-item
        v-for="(count, key) in unloadStats"
        :key="key"
        :label="getLabel(key)"
      >
        {{ count }} 条
      </el-descriptions-item>
    </el-descriptions>
    <el-alert
      title="用户自定义的数据将被保留"
      type="success"
      :closable="false"
      style="margin-top: 16px"
    />
  </div>
  <template #footer>
    <el-button @click="showUnloadPreview = false">取消</el-button>
    <el-button type="danger" @click="confirmUnload">确认卸载</el-button>
  </template>
</el-dialog>
```

---

## 简化实施方案（最小改动）

如果时间紧张，可以采用最小改动方案：

### 只修改 handleUnload 方法
```typescript
const handleUnload = async () => {
  try {
    // 获取删除预览
    const previewRes = await unloadDemoDataPreview()
    const stats = previewRes.data?.stats || {}
    const statsText = Object.entries(stats)
      .map(([key, count]) => `${key}: ${count}`)
      .join(', ')

    // 显示确认对话框
    await ElMessageBox.confirm(
      `将删除以下 Demo 数据：${statsText}。用户自定义数据将被保留。确定继续吗？`,
      '确认卸载',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    // 执行卸载
    const res = await unloadDemoData()
    if (res.code === 0) {
      ElMessage.success('演示数据卸载成功')
      await checkStatus()
    } else {
      ElMessage.error(res.message || '卸载失败')
    }
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('操作失败')
    }
  }
}
```

---

## 测试步骤

1. 启动前端开发服务器: `cd frontend && npm run dev`
2. 访问系统，加载 Demo 数据
3. 手动创建一些自定义数据（如新建站点、设备等）
4. 点击"卸载 Demo 数据"按钮
5. 验证预览对话框显示正确的统计信息
6. 确认卸载后，验证：
   - Demo 数据被删除
   - 用户自定义数据被保留
   - 系统仍然正常运行

---

**注意:** 由于前端组件较复杂，建议在实际修改前先备份文件。
