<template>
  <div class="energy-topology">
    <el-card class="summary-card">
      <div class="summary-items">
        <div class="summary-item">
          <span class="label">总容量</span>
          <span class="value">{{ topology?.total_capacity || 0 }} kVA</span>
        </div>
        <div class="summary-item">
          <span class="label">计量点</span>
          <span class="value">{{ topology?.total_meter_points || 0 }} 个</span>
        </div>
        <div class="summary-item">
          <span class="label">用电设备</span>
          <span class="value">{{ topology?.total_devices || 0 }} 台</span>
        </div>
        <el-button type="primary" @click="loadTopology" :loading="loading">
          <el-icon><Refresh /></el-icon>刷新
        </el-button>
      </div>
    </el-card>

    <el-card class="topology-card" v-loading="loading">
      <template #header>
        <span>配电系统拓扑</span>
      </template>
      <div class="topology-tree" v-if="topology?.transformers?.length">
        <el-tree
          :data="treeData"
          :props="{ children: 'children', label: 'label' }"
          default-expand-all
          :expand-on-click-node="false"
        >
          <template #default="{ node, data }">
            <div class="tree-node" :class="data.type">
              <el-icon class="node-icon">
                <component :is="getNodeIcon(data.type)" />
              </el-icon>
              <span class="node-label">{{ data.label }}</span>
              <span class="node-info" v-if="data.info">{{ data.info }}</span>
              <el-tag v-if="data.status" :type="getStatusType(data.status)" size="small">
                {{ getStatusText(data.status) }}
              </el-tag>
            </div>
          </template>
        </el-tree>
      </div>
      <el-empty v-else description="暂无配电拓扑数据" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Refresh, OfficeBuilding, Odometer, Box, Connection, Monitor } from '@element-plus/icons-vue'
import { getDistributionTopology, type DistributionTopology } from '@/api/modules/energy'

const loading = ref(false)
const topology = ref<DistributionTopology | null>(null)

const treeData = computed(() => {
  if (!topology.value?.transformers) return []
  return topology.value.transformers.map(t => ({
    label: t.transformer_name,
    type: 'transformer',
    info: `${t.rated_capacity} kVA`,
    children: t.meter_points.map(m => ({
      label: m.meter_name,
      type: 'meter',
      info: m.declared_demand ? `${m.declared_demand} kW` : '',
      children: m.panels.map(p => ({
        label: p.panel_name,
        type: 'panel',
        info: p.panel_type,
        children: p.circuits.map(c => ({
          label: c.circuit_name,
          type: 'circuit',
          info: c.load_type || '',
          children: c.devices.map(d => ({
            label: d.device_name,
            type: 'device',
            info: d.rated_power ? `${d.rated_power} kW` : ''
          }))
        }))
      }))
    }))
  }))
})

const getNodeIcon = (type: string) => {
  const icons: Record<string, any> = {
    transformer: OfficeBuilding,
    meter: Odometer,
    panel: Box,
    circuit: Connection,
    device: Monitor
  }
  return icons[type] || Box
}

type TagType = 'success' | 'warning' | 'danger' | 'info' | 'primary'

const getStatusType = (status: string): TagType => {
  const map: Record<string, TagType> = { normal: 'success', warning: 'warning', fault: 'danger', offline: 'info' }
  return map[status] || 'info'
}

const getStatusText = (status: string) => {
  const map: Record<string, string> = { normal: '正常', warning: '告警', fault: '故障', offline: '离线' }
  return map[status] || status
}

const loadTopology = async () => {
  loading.value = true
  try {
    const res = await getDistributionTopology()
    if (res.code === 0 && res.data) {
      topology.value = res.data
    }
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadTopology()
})
</script>

<style scoped lang="scss">
.energy-topology {
  padding: 20px;
}

.summary-card {
  margin-bottom: 20px;
  background-color: var(--bg-card-solid);
  border-color: var(--border-color);

  :deep(.el-card__body) {
    background-color: var(--bg-card-solid);
  }
}

.summary-items {
  display: flex;
  align-items: center;
  gap: 40px;
}

.summary-item {
  display: flex;
  flex-direction: column;

  .label {
    font-size: 12px;
    color: var(--text-secondary);
  }

  .value {
    font-size: 20px;
    font-weight: bold;
    color: var(--text-primary);
  }
}

.topology-card {
  min-height: 400px;
  background-color: var(--bg-card-solid);
  border-color: var(--border-color);

  :deep(.el-card__header) {
    background-color: var(--bg-tertiary);
    border-bottom-color: var(--border-color);
    color: var(--text-primary);
  }

  :deep(.el-card__body) {
    background-color: var(--bg-card-solid);
  }
}

.topology-tree {
  :deep(.el-tree) {
    background-color: transparent;

    .el-tree-node__content {
      background-color: transparent;

      &:hover {
        background-color: var(--bg-tertiary);
      }
    }

    .el-tree-node__expand-icon {
      color: var(--text-secondary);
    }

    // Connection lines for tree nodes
    .el-tree-node {
      &::before {
        border-color: var(--border-color);
      }

      &::after {
        border-color: var(--border-color);
      }
    }
  }
}

.tree-node {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
}

.node-icon {
  font-size: 16px;
}

.tree-node.transformer .node-icon {
  color: var(--error-color);
}

.tree-node.meter .node-icon {
  color: var(--warning-color);
}

.tree-node.panel .node-icon {
  color: var(--primary-color);
}

.tree-node.circuit .node-icon {
  color: var(--success-color);
}

.tree-node.device .node-icon {
  color: var(--info-color);
}

.node-label {
  font-weight: 500;
  color: var(--text-primary);
}

.node-info {
  color: var(--text-secondary);
  font-size: 12px;
}
</style>
