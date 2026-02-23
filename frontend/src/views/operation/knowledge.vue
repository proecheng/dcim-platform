<template>
  <div class="knowledge-page">
    <!-- 主内容区域 -->
    <el-card shadow="hover" class="main-card">
      <!-- 工具栏 -->
      <div class="toolbar">
        <div class="toolbar-left">
          <el-select v-model="filterCategory" placeholder="文章分类" clearable style="width: 140px;">
            <el-option label="全部" value="" />
            <el-option label="故障处理" value="故障处理" />
            <el-option label="操作规程" value="操作规程" />
            <el-option label="设备手册" value="设备手册" />
          </el-select>
          <el-input
            v-model="filterKeyword"
            placeholder="搜索文章..."
            clearable
            style="width: 220px;"
            @keyup.enter="handleSearch"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
          <el-button type="primary" @click="handleSearch">搜索</el-button>
        </div>
        <div class="toolbar-right">
          <el-button type="primary" :icon="Plus" @click="showCreateDialog">新建文章</el-button>
        </div>
      </div>

      <!-- 数据表格 -->
      <el-table :data="knowledgeList" stripe border v-loading="loading">
        <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
        <el-table-column prop="category" label="分类" width="120">
          <template #default="{ row }">
            {{ row.category || '--' }}
          </template>
        </el-table-column>
        <el-table-column prop="author" label="作者" width="100">
          <template #default="{ row }">
            {{ row.author || '--' }}
          </template>
        </el-table-column>
        <el-table-column prop="tags" label="标签" width="150" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.tags || '--' }}
          </template>
        </el-table-column>
        <el-table-column prop="view_count" label="浏览量" width="90" align="center" />
        <el-table-column prop="is_published" label="发布状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_published ? 'success' : 'info'" size="small">
              {{ row.is_published ? '已发布' : '草稿' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="170">
          <template #default="{ row }">
            {{ formatDateTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="showViewDialog(row)">查看</el-button>
            <el-button type="warning" link @click="showEditDialog(row)">编辑</el-button>
            <el-button type="danger" link @click="confirmDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="loadKnowledgeList"
          @current-change="loadKnowledgeList"
        />
      </div>
    </el-card>

    <!-- 新建/编辑对话框 -->
    <el-dialog append-to-body
      v-model="editDialogVisible"
      :title="isEdit ? '编辑文章' : '新建文章'"
      width="650px"
    >
      <el-form
        ref="editFormRef"
        :model="editForm"
        :rules="editRules"
        label-width="80px"
      >
        <el-form-item label="标题" prop="title">
          <el-input v-model="editForm.title" placeholder="请输入文章标题" />
        </el-form-item>
        <el-form-item label="分类" prop="category">
          <el-select v-model="editForm.category" placeholder="请选择分类" style="width: 100%;">
            <el-option label="故障处理" value="故障处理" />
            <el-option label="操作规程" value="操作规程" />
            <el-option label="设备手册" value="设备手册" />
          </el-select>
        </el-form-item>
        <el-form-item label="内容" prop="content">
          <el-input
            v-model="editForm.content"
            type="textarea"
            :rows="8"
            placeholder="请输入文章内容"
          />
        </el-form-item>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="标签" prop="tags">
              <el-input v-model="editForm.tags" placeholder="多个标签用逗号分隔" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="作者" prop="author">
              <el-input v-model="editForm.author" placeholder="请输入作者" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="发布">
          <el-switch v-model="editForm.is_published" active-text="已发布" inactive-text="草稿" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitEditForm" :loading="submitting">确定</el-button>
      </template>
    </el-dialog>

    <!-- 查看对话框 -->
    <el-dialog append-to-body
      v-model="viewDialogVisible"
      title="文章详情"
      width="700px"
    >
      <div class="article-view" v-if="currentArticle">
        <h2 class="article-title">{{ currentArticle.title }}</h2>
        <div class="article-meta">
          <el-tag v-if="currentArticle.category" size="small" type="primary">{{ currentArticle.category }}</el-tag>
          <span v-if="currentArticle.author">作者：{{ currentArticle.author }}</span>
          <span>浏览量：{{ currentArticle.view_count }}</span>
          <span>{{ formatDateTime(currentArticle.created_at) }}</span>
        </div>
        <el-divider />
        <div class="article-content">{{ currentArticle.content || '暂无内容' }}</div>
      </div>
      <template #footer>
        <el-button @click="viewDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { Plus, Search } from '@element-plus/icons-vue'
import {
  getKnowledgeList,
  getKnowledge,
  createKnowledge,
  updateKnowledge,
  deleteKnowledge
} from '@/api/modules/operation'
import type { Knowledge, KnowledgeCreate } from '@/api/modules/operation'

type FormInstance = InstanceType<typeof import('element-plus')['ElForm']>

// 数据状态
const loading = ref(false)
const submitting = ref(false)
const knowledgeList = ref<Knowledge[]>([])

// 分页
const currentPage = ref(1)
const pageSize = ref(10)
const total = ref(0)

// 筛选
const filterCategory = ref('')
const filterKeyword = ref('')

// 编辑对话框
const isEdit = ref(false)
const currentId = ref<number | null>(null)
const editDialogVisible = ref(false)
const editFormRef = ref<FormInstance>()
const editForm = reactive<KnowledgeCreate & { is_published: boolean }>({
  title: '',
  category: '',
  content: '',
  tags: '',
  author: '',
  is_published: false
})

const editRules = {
  title: [{ required: true, message: '请输入文章标题', trigger: 'blur' }]
}

// 查看对话框
const viewDialogVisible = ref(false)
const currentArticle = ref<Knowledge | null>(null)

// 初始化
onMounted(() => {
  loadKnowledgeList()
})

// 加载列表
async function loadKnowledgeList() {
  loading.value = true
  try {
    const res = await getKnowledgeList({
      page: currentPage.value,
      page_size: pageSize.value,
      category: filterCategory.value || undefined,
      keyword: filterKeyword.value || undefined
    })
    if (res.data) {
      const data = res.data as any
      knowledgeList.value = data.items || []
      total.value = data.total || 0
    }
  } catch (e) {
    console.error('加载知识库列表失败', e)
    ElMessage.error('加载知识库列表失败')
  } finally {
    loading.value = false
  }
}

// 搜索
function handleSearch() {
  currentPage.value = 1
  loadKnowledgeList()
}

// 新建
function showCreateDialog() {
  isEdit.value = false
  currentId.value = null
  Object.assign(editForm, {
    title: '',
    category: '',
    content: '',
    tags: '',
    author: '',
    is_published: false
  })
  editDialogVisible.value = true
}

// 编辑
async function showEditDialog(row: Knowledge) {
  isEdit.value = true
  currentId.value = row.id
  try {
    const res = await getKnowledge(row.id)
    if (res.data) {
      const detail = res.data as any
      Object.assign(editForm, {
        title: detail.title || '',
        category: detail.category || '',
        content: detail.content || '',
        tags: detail.tags || '',
        author: detail.author || '',
        is_published: detail.is_published ?? false
      })
    }
  } catch {
    Object.assign(editForm, {
      title: row.title || '',
      category: row.category || '',
      content: row.content || '',
      tags: row.tags || '',
      author: row.author || '',
      is_published: row.is_published ?? false
    })
  }
  editDialogVisible.value = true
}

// 提交表单
async function submitEditForm() {
  const valid = await editFormRef.value?.validate()
  if (!valid) return

  submitting.value = true
  try {
    const payload: KnowledgeCreate = {
      title: editForm.title,
      category: editForm.category || undefined,
      content: editForm.content || undefined,
      tags: editForm.tags || undefined,
      author: editForm.author || undefined,
      is_published: editForm.is_published
    }

    if (isEdit.value && currentId.value) {
      await updateKnowledge(currentId.value, payload)
      ElMessage.success('更新成功')
    } else {
      await createKnowledge(payload)
      ElMessage.success('创建成功')
    }
    editDialogVisible.value = false
    loadKnowledgeList()
  } catch (e) {
    console.error('操作失败', e)
    ElMessage.error('操作失败')
  } finally {
    submitting.value = false
  }
}

// 查看
async function showViewDialog(row: Knowledge) {
  try {
    const res = await getKnowledge(row.id)
    if (res.data) {
      currentArticle.value = res.data as any
    } else {
      currentArticle.value = row
    }
  } catch {
    currentArticle.value = row
  }
  viewDialogVisible.value = true
}

// 删除
function confirmDelete(row: Knowledge) {
  ElMessageBox.confirm(
    `确定要删除文章「${row.title}」吗？`,
    '删除确认',
    { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
  ).then(async () => {
    try {
      await deleteKnowledge(row.id)
      ElMessage.success('删除成功')
      loadKnowledgeList()
    } catch (e) {
      console.error('删除失败', e)
      ElMessage.error('删除失败')
    }
  }).catch(() => {})
}

// 格式化时间
function formatDateTime(dateStr?: string): string {
  if (!dateStr) return '--'
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}
</script>

<style scoped lang="scss">
@use '@/styles/_mixins-25d' as *;

.knowledge-page {
  @include page-list;

  .main-card {
    background: var(--bg-card);
    border-color: var(--border-color);
  }

  .toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;

    .toolbar-left {
      display: flex;
      gap: 12px;
      align-items: center;
    }

    .toolbar-right {
      display: flex;
      gap: 12px;
    }
  }

  .pagination-wrapper {
    display: flex;
    justify-content: flex-end;
    margin-top: 16px;
  }

  .article-view {
    .article-title {
      font-size: 22px;
      font-weight: 600;
      color: var(--text-primary);
      margin: 0 0 12px;
      line-height: 1.4;
    }

    .article-meta {
      display: flex;
      align-items: center;
      gap: 16px;
      font-size: 13px;
      color: var(--text-secondary);
    }

    .article-content {
      font-size: 14px;
      line-height: 1.8;
      color: var(--text-primary);
      white-space: pre-wrap;
      word-break: break-word;
    }
  }

  :deep(.el-table) {
    background: transparent;

    th.el-table__cell {
      background: var(--bg-card);
      color: var(--text-primary);
      border-color: var(--border-color);
    }

    td.el-table__cell {
      border-color: var(--border-color);
    }

    tr {
      background: var(--bg-card);

      &:hover > td.el-table__cell {
        background: rgba(255, 255, 255, 0.05);
      }
    }

    .el-table__body tr.el-table__row--striped td.el-table__cell {
      background: rgba(255, 255, 255, 0.02);
    }
  }

  :deep(.el-dialog) {
    background: var(--bg-card);
    border: 1px solid var(--border-color);

    .el-dialog__header {
      border-bottom: 1px solid var(--border-color);
    }

    .el-dialog__title {
      color: var(--text-primary);
    }

    .el-dialog__footer {
      border-top: 1px solid var(--border-color);
    }
  }

  :deep(.el-form-item__label) {
    color: var(--text-secondary);
  }

  :deep(.el-input__wrapper),
  :deep(.el-textarea__inner),
  :deep(.el-select .el-input__wrapper) {
    background: rgba(255, 255, 255, 0.05);
    border-color: var(--border-color);

    &:hover {
      border-color: var(--accent-color);
    }
  }

  :deep(.el-input__inner),
  :deep(.el-textarea__inner) {
    color: var(--text-primary);

    &::placeholder {
      color: var(--text-secondary);
    }
  }

  :deep(.el-divider) {
    border-color: var(--border-color);
  }
}
</style>
