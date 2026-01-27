<template>
  <div class="data-table">
    <!-- 工具栏 -->
    <div v-if="$slots.toolbar || showRefresh" class="data-table__toolbar">
      <div class="data-table__toolbar-left">
        <slot name="toolbar"></slot>
      </div>
      <div class="data-table__toolbar-right">
        <el-button
          v-if="showRefresh"
          :icon="Refresh"
          circle
          @click="handleRefresh"
        />
      </div>
    </div>

    <!-- 表格 -->
    <el-table
      ref="tableRef"
      v-loading="loading"
      :data="data"
      :height="height"
      :max-height="maxHeight"
      :stripe="stripe"
      :border="border"
      :row-key="rowKey"
      :highlight-current-row="highlightCurrentRow"
      :default-sort="defaultSort"
      @selection-change="handleSelectionChange"
      @sort-change="handleSortChange"
      @row-click="handleRowClick"
    >
      <!-- 选择列 -->
      <el-table-column
        v-if="showSelection"
        type="selection"
        width="55"
        align="center"
        :reserve-selection="reserveSelection"
      />

      <!-- 索引列 -->
      <el-table-column
        v-if="showIndex"
        type="index"
        label="序号"
        width="60"
        align="center"
        :index="indexMethod"
      />

      <!-- 数据列 -->
      <slot></slot>

      <!-- 操作列 -->
      <el-table-column
        v-if="$slots.action"
        label="操作"
        :width="actionWidth"
        :fixed="actionFixed"
        align="center"
      >
        <template #default="scope">
          <slot name="action" v-bind="scope"></slot>
        </template>
      </el-table-column>

      <!-- 空状态 -->
      <template #empty>
        <slot name="empty">
          <el-empty description="暂无数据" />
        </slot>
      </template>
    </el-table>

    <!-- 分页 -->
    <div v-if="showPagination && total > 0" class="data-table__pagination">
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="currentPageSize"
        :page-sizes="pageSizes"
        :total="total"
        :layout="paginationLayout"
        background
        @size-change="handleSizeChange"
        @current-change="handleCurrentChange"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import type { TableInstance } from 'element-plus'

interface Props {
  data: any[]
  loading?: boolean
  height?: string | number
  maxHeight?: string | number
  stripe?: boolean
  border?: boolean
  rowKey?: string
  highlightCurrentRow?: boolean
  defaultSort?: { prop: string; order: 'ascending' | 'descending' }
  showSelection?: boolean
  reserveSelection?: boolean
  showIndex?: boolean
  showRefresh?: boolean
  showPagination?: boolean
  total?: number
  page?: number
  pageSize?: number
  pageSizes?: number[]
  paginationLayout?: string
  actionWidth?: string | number
  actionFixed?: 'left' | 'right' | boolean
}

const props = withDefaults(defineProps<Props>(), {
  loading: false,
  stripe: true,
  border: false,
  rowKey: 'id',
  highlightCurrentRow: false,
  showSelection: false,
  reserveSelection: false,
  showIndex: false,
  showRefresh: true,
  showPagination: true,
  total: 0,
  page: 1,
  pageSize: 20,
  pageSizes: () => [10, 20, 50, 100],
  paginationLayout: 'total, sizes, prev, pager, next, jumper',
  actionWidth: 150,
  actionFixed: 'right'
})

const emit = defineEmits<{
  (e: 'update:page', page: number): void
  (e: 'update:pageSize', pageSize: number): void
  (e: 'refresh'): void
  (e: 'selection-change', selection: any[]): void
  (e: 'sort-change', sort: { prop: string; order: string | null }): void
  (e: 'row-click', row: any, column: any, event: Event): void
  (e: 'page-change', params: { page: number; pageSize: number }): void
}>()

const tableRef = ref<TableInstance>()

const currentPage = computed({
  get: () => props.page,
  set: (val) => emit('update:page', val)
})

const currentPageSize = computed({
  get: () => props.pageSize,
  set: (val) => emit('update:pageSize', val)
})

// 计算索引
const indexMethod = (index: number) => {
  return (currentPage.value - 1) * currentPageSize.value + index + 1
}

// 事件处理
const handleRefresh = () => {
  emit('refresh')
}

const handleSelectionChange = (selection: any[]) => {
  emit('selection-change', selection)
}

const handleSortChange = (sort: { prop: string; order: string | null }) => {
  emit('sort-change', sort)
}

const handleRowClick = (row: any, column: any, event: Event) => {
  emit('row-click', row, column, event)
}

const handleSizeChange = (size: number) => {
  emit('page-change', { page: 1, pageSize: size })
}

const handleCurrentChange = (page: number) => {
  emit('page-change', { page, pageSize: currentPageSize.value })
}

// 暴露方法
defineExpose({
  clearSelection: () => tableRef.value?.clearSelection(),
  toggleRowSelection: (row: any, selected?: boolean) => tableRef.value?.toggleRowSelection(row, selected),
  toggleAllSelection: () => tableRef.value?.toggleAllSelection(),
  setCurrentRow: (row: any) => tableRef.value?.setCurrentRow(row),
  sort: (prop: string, order: string) => tableRef.value?.sort(prop, order)
})
</script>

<style lang="scss" scoped>
.data-table {
  &__toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;

    &-left {
      display: flex;
      gap: 8px;
    }

    &-right {
      display: flex;
      gap: 8px;
    }
  }

  &__pagination {
    display: flex;
    justify-content: flex-end;
    margin-top: 16px;
  }
}
</style>
