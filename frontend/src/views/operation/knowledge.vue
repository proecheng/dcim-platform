<template>
  <div class="knowledge-page">
    <!-- 工具栏 -->
    <el-card shadow="hover" class="toolbar-card">
      <div class="toolbar">
        <div class="toolbar-left">
          <el-select v-model="filterCategory" placeholder="选择分类" clearable style="width: 160px;">
            <el-option label="故障处理" value="故障处理" />
            <el-option label="操作指南" value="操作指南" />
            <el-option label="维护规范" value="维护规范" />
            <el-option label="安全规程" value="安全规程" />
            <el-option label="设备手册" value="设备手册" />
            <el-option label="最佳实践" value="最佳实践" />
            <el-option label="其他" value="其他" />
          </el-select>
          <el-input
            v-model="filterKeyword"
            placeholder="搜索知识..."
            clearable
            style="width: 200px;"
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
    </el-card>

    <!-- 文章卡片网格 -->
    <div class="article-grid" v-loading="loading">
      <el-card
        v-for="article in knowledgeList"
        :key="article.id"
        shadow="hover"
        class="article-card"
        @click="showDetailDialog(article)"
      >
        <div class="article-header">
          <h3 class="article-title">{{ article.title }}</h3>
          <el-tag :type="getCategoryType(article.category)" size="small">
            {{ article.category }}
          </el-tag>
        </div>
        <div class="article-content">
          {{ truncateContent(article.content) }}
        </div>
        <div class="article-footer">
          <div class="article-meta">
            <span class="meta-item">
              <el-icon><View /></el-icon>
              {{ article.views || 0 }}
            </span>
            <span class="meta-item">
              <el-icon><Star /></el-icon>
              {{ article.likes || 0 }}
            </span>
          </div>
          <div class="article-date">
            {{ formatDate(article.created_at) }}
          </div>
        </div>
        <div class="article-tags" v-if="article.keywords?.length">
          <el-tag
            v-for="tag in article.keywords.slice(0, 3)"
            :key="tag"
            type="info"
            size="small"
            class="keyword-tag"
          >
            {{ tag }}
          </el-tag>
        </div>
      </el-card>

      <!-- 空状态 -->
      <el-empty
        v-if="!loading && knowledgeList.length === 0"
        description="暂无知识文章"
        class="empty-state"
      />
    </div>

    <!-- 分页 -->
    <div class="pagination-wrapper" v-if="total > pageSize">
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :page-sizes="[12, 24, 48]"
        :total="total"
        layout="total, sizes, prev, pager, next"
        @size-change="loadKnowledgeList"
        @current-change="loadKnowledgeList"
      />
    </div>

    <!-- 新建/编辑文章对话框 -->
    <el-dialog
      v-model="createDialogVisible"
      :title="isEdit ? '编辑文章' : '新建文章'"
      width="700px"
      destroy-on-close
    >
      <el-form
        ref="createFormRef"
        :model="createForm"
        :rules="createRules"
        label-width="80px"
      >
        <el-form-item label="标题" prop="title">
          <el-input v-model="createForm.title" placeholder="请输入文章标题" />
        </el-form-item>
        <el-form-item label="分类" prop="category">
          <el-select v-model="createForm.category" placeholder="请选择分类" style="width: 100%;">
            <el-option label="故障处理" value="故障处理" />
            <el-option label="操作指南" value="操作指南" />
            <el-option label="维护规范" value="维护规范" />
            <el-option label="安全规程" value="安全规程" />
            <el-option label="设备手册" value="设备手册" />
            <el-option label="最佳实践" value="最佳实践" />
            <el-option label="其他" value="其他" />
          </el-select>
        </el-form-item>
        <el-form-item label="内容" prop="content">
          <el-input
            v-model="createForm.content"
            type="textarea"
            :rows="12"
            placeholder="请输入文章内容"
          />
        </el-form-item>
        <el-form-item label="标签" prop="tags">
          <el-input v-model="createForm.tags" placeholder="请输入标签（多个用逗号分隔）" />
        </el-form-item>
        <el-form-item label="发布状态" prop="is_published">
          <el-switch
            v-model="createForm.is_published"
            active-text="已发布"
            inactive-text="草稿"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitCreateForm" :loading="submitting">确定</el-button>
      </template>
    </el-dialog>

    <!-- 文章详情对话框 -->
    <el-dialog
      v-model="detailDialogVisible"
      :title="currentArticle?.title"
      width="800px"
      destroy-on-close
      class="detail-dialog"
    >
      <div class="detail-header">
        <div class="detail-meta">
          <el-tag :type="getCategoryType(currentArticle?.category)" size="small">
            {{ currentArticle?.category }}
          </el-tag>
          <span class="meta-item">
            <el-icon><User /></el-icon>
            {{ currentArticle?.author || '匿名' }}
          </span>
          <span class="meta-item">
            <el-icon><Calendar /></el-icon>
            {{ formatDateTime(currentArticle?.created_at) }}
          </span>
          <span class="meta-item">
            <el-icon><View /></el-icon>
            {{ currentArticle?.views || 0 }} 阅读
          </span>
          <span class="meta-item">
            <el-icon><Star /></el-icon>
            {{ currentArticle?.likes || 0 }} 点赞
          </span>
        </div>
        <div class="detail-tags" v-if="currentArticle?.keywords?.length">
          <el-tag
            v-for="tag in currentArticle.keywords"
            :key="tag"
            type="info"
            size="small"
            class="keyword-tag"
          >
            {{ tag }}
          </el-tag>
        </div>
      </div>

      <el-divider />

      <div class="detail-content markdown-body" v-html="renderedContent"></div>

      <template #footer>
        <el-button @click="handleEdit(currentArticle!)">编辑</el-button>
        <el-button type="danger" @click="confirmDelete(currentArticle!)">删除</el-button>
        <el-button type="primary" @click="detailDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance } from 'element-plus'
import { Plus, Search, View, Star, User, Calendar } from '@element-plus/icons-vue'
import { marked } from 'marked'
import hljs from 'highlight.js'
import 'highlight.js/styles/atom-one-dark.css'
import {
  getKnowledgeList,
  createKnowledge,
  updateKnowledge,
  deleteKnowledge,
  type Knowledge
} from '@/api/modules/operation'

// 配置 marked
marked.setOptions({
  gfm: true,
  breaks: true,
  highlight: function(code, lang) {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return hljs.highlight(code, { language: lang }).value
      } catch (_) {}
    }
    return hljs.highlightAuto(code).value
  }
})

// Markdown 渲染
function renderMarkdown(content: string): string {
  if (!content) return ''
  return marked(content) as string
}

// 从 Markdown 中提取纯文本（用于卡片摘要）
function stripMarkdown(content: string): string {
  if (!content) return ''
  return content
    .replace(/^#+\s+.+$/gm, '')  // 移除标题
    .replace(/\*\*(.+?)\*\*/g, '$1')  // 粗体
    .replace(/\*(.+?)\*/g, '$1')  // 斜体
    .replace(/`(.+?)`/g, '$1')  // 行内代码
    .replace(/```[\s\S]*?```/g, '')  // 代码块
    .replace(/\[(.+?)\]\(.+?\)/g, '$1')  // 链接
    .replace(/>\s+.+$/gm, '')  // 引用
    .replace(/^[-*+]\s+/gm, '')  // 列表
    .replace(/^\d+\.\s+/gm, '')  // 有序列表
    .replace(/^---$/gm, '')  // 分隔线
    .replace(/\|.+\|/g, '')  // 表格
    .replace(/\n{2,}/g, '\n')  // 多余换行
    .trim()
}

// 类型定义
type TagType = 'success' | 'warning' | 'danger' | 'info' | 'primary'

// 数据状态
const loading = ref(false)
const submitting = ref(false)
const knowledgeList = ref<Knowledge[]>([])

// 分页
const currentPage = ref(1)
const pageSize = ref(12)
const total = ref(0)

// 筛选条件
const filterCategory = ref('')
const filterKeyword = ref('')

// 对话框状态
const isEdit = ref(false)
const currentId = ref<number | null>(null)
const currentArticle = ref<Knowledge | null>(null)

// 新建/编辑对话框
const createDialogVisible = ref(false)
const createFormRef = ref<FormInstance>()
const createForm = reactive({
  title: '',
  category: '',
  content: '',
  tags: '',
  is_published: true
})

const createRules = {
  title: [{ required: true, message: '请输入文章标题', trigger: 'blur' }],
  category: [{ required: true, message: '请选择分类', trigger: 'change' }],
  content: [{ required: true, message: '请输入文章内容', trigger: 'blur' }]
}

// 详情对话框
const detailDialogVisible = ref(false)

// 渲染后的 Markdown 内容
const renderedContent = computed(() => {
  return currentArticle.value ? renderMarkdown(currentArticle.value.content) : ''
})

// 初始化加载
onMounted(() => {
  loadKnowledgeList()
})

// 加载知识库列表
async function loadKnowledgeList() {
  loading.value = true
  try {
    const res = await getKnowledgeList({
      page: currentPage.value,
      page_size: pageSize.value,
      category: filterCategory.value || undefined,
      keyword: filterKeyword.value || undefined
    })
    // 兼容两种返回格式：
    // 1. 统一格式 {code, message, data: {items, total}}
    // 2. 原始列表 [{...}, ...]
    const raw = res as any
    if (Array.isArray(raw)) {
      // 后端直接返回列表
      knowledgeList.value = raw
      total.value = raw.length
    } else if (raw?.data) {
      // 统一格式
      const data = raw.data
      knowledgeList.value = Array.isArray(data) ? data : data.items || []
      total.value = data.total || knowledgeList.value.length
    } else if (raw?.items) {
      knowledgeList.value = raw.items
      total.value = raw.total || raw.items.length
    } else {
      knowledgeList.value = []
      total.value = 0
    }

    // 字段映射: 后端 view_count/tags -> 前端 views/keywords
    knowledgeList.value = knowledgeList.value.map((item: any) => ({
      ...item,
      views: item.views ?? item.view_count ?? 0,
      likes: item.likes ?? 0,
      keywords: item.keywords ?? (item.tags ? item.tags.split(',').map((s: string) => s.trim()).filter(Boolean) : [])
    }))
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

// 显示新建对话框
function showCreateDialog() {
  isEdit.value = false
  currentId.value = null
  Object.assign(createForm, {
    title: '',
    category: '',
    content: '',
    tags: '',
    is_published: true
  })
  createDialogVisible.value = true
}

// 显示详情对话框
function showDetailDialog(article: Knowledge) {
  currentArticle.value = article
  detailDialogVisible.value = true
}

// 编辑文章
function handleEdit(article: Knowledge) {
  isEdit.value = true
  currentId.value = article.id
  Object.assign(createForm, {
    title: article.title,
    category: article.category,
    content: article.content,
    tags: article.keywords?.join(', ') || '',
    is_published: article.is_published
  })
  detailDialogVisible.value = false
  createDialogVisible.value = true
}

// 提交新建/编辑表单
async function submitCreateForm() {
  const valid = await createFormRef.value?.validate()
  if (!valid) return

  submitting.value = true
  try {
    const keywords = createForm.tags
      ? createForm.tags.split(/[,，]/).map(s => s.trim()).filter(Boolean)
      : []

    const data = {
      title: createForm.title,
      category: createForm.category,
      content: createForm.content,
      keywords: keywords.length > 0 ? keywords : undefined,
      is_published: createForm.is_published
    }

    if (isEdit.value && currentId.value) {
      await updateKnowledge(currentId.value, data)
      ElMessage.success('更新成功')
    } else {
      await createKnowledge(data)
      ElMessage.success('创建成功')
    }
    createDialogVisible.value = false
    loadKnowledgeList()
  } catch (e) {
    console.error('操作失败', e)
    ElMessage.error('操作失败')
  } finally {
    submitting.value = false
  }
}

// 确认删除
function confirmDelete(article: Knowledge) {
  ElMessageBox.confirm(
    `确定要删除文章 "${article.title}" 吗？`,
    '删除确认',
    { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
  ).then(async () => {
    try {
      await deleteKnowledge(article.id)
      ElMessage.success('删除成功')
      detailDialogVisible.value = false
      loadKnowledgeList()
    } catch (e) {
      console.error('删除失败', e)
      ElMessage.error('删除失败')
    }
  }).catch(() => {})
}

// 辅助函数
function getCategoryType(category?: string): TagType {
  const map: Record<string, TagType> = {
    '故障处理': 'danger',
    '操作指南': 'primary',
    '维护规范': 'warning',
    '安全规程': 'danger',
    '设备手册': 'info',
    '最佳实践': 'success',
    '其他': 'info'
  }
  return category ? map[category] || 'info' : 'info'
}

function truncateContent(content: string): string {
  if (!content) return ''
  const plainText = stripMarkdown(content)
  const maxLength = 100
  return plainText.length > maxLength ? plainText.substring(0, maxLength) + '...' : plainText
}

function formatDate(dateStr?: string): string {
  if (!dateStr) return '--'
  const date = new Date(dateStr)
  return date.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
  })
}

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
.knowledge-page {
  .toolbar-card {
    background: var(--bg-card);
    border-color: var(--border-color);
    margin-bottom: 20px;
  }

  .toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;

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

  .article-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 20px;
    min-height: 200px;
  }

  .article-card {
    background: var(--bg-card);
    border-color: var(--border-color);
    cursor: pointer;
    transition: all 0.3s ease;

    &:hover {
      transform: translateY(-4px);
      border-color: var(--accent-color);
      box-shadow: 0 4px 20px rgba(64, 158, 255, 0.2);
    }

    .article-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 12px;

      .article-title {
        font-size: 16px;
        font-weight: bold;
        color: var(--text-primary);
        margin: 0;
        flex: 1;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        margin-right: 12px;
      }
    }

    .article-content {
      font-size: 14px;
      color: var(--text-secondary);
      line-height: 1.6;
      margin-bottom: 16px;
      min-height: 48px;
    }

    .article-footer {
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 12px;
      color: var(--text-secondary);

      .article-meta {
        display: flex;
        gap: 16px;

        .meta-item {
          display: flex;
          align-items: center;
          gap: 4px;
        }
      }
    }

    .article-tags {
      margin-top: 12px;
      display: flex;
      gap: 8px;
      flex-wrap: wrap;

      .keyword-tag {
        font-size: 12px;
      }
    }
  }

  .empty-state {
    grid-column: 1 / -1;
    padding: 40px 0;
  }

  .pagination-wrapper {
    display: flex;
    justify-content: center;
    margin-top: 24px;
  }

  .detail-dialog {
    :deep(.el-dialog__body) {
      padding-top: 16px;
    }
  }

  .detail-header {
    .detail-meta {
      display: flex;
      align-items: center;
      gap: 16px;
      flex-wrap: wrap;
      margin-bottom: 12px;

      .meta-item {
        display: flex;
        align-items: center;
        gap: 4px;
        font-size: 14px;
        color: var(--text-secondary);
      }
    }

    .detail-tags {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;

      .keyword-tag {
        font-size: 12px;
      }
    }
  }

  .detail-content {
    max-height: 60vh;
    overflow-y: auto;

    &.markdown-body {
      font-size: 14px;
      color: var(--text-primary);
      line-height: 1.8;

      h1, h2, h3, h4, h5, h6 {
        color: var(--text-primary);
        margin-top: 1.5em;
        margin-bottom: 0.5em;
        font-weight: 600;
        border-bottom: 1px solid var(--border-color);
        padding-bottom: 0.3em;
      }

      h1 { font-size: 1.8em; }
      h2 { font-size: 1.5em; }
      h3 { font-size: 1.25em; }
      h4 { font-size: 1.1em; border-bottom: none; }

      p {
        margin: 0.8em 0;
      }

      a {
        color: var(--accent-color);
        text-decoration: none;
        &:hover {
          text-decoration: underline;
        }
      }

      code {
        background: rgba(0, 0, 0, 0.3);
        padding: 0.2em 0.4em;
        border-radius: 4px;
        font-family: 'Consolas', 'Monaco', monospace;
        font-size: 0.9em;
      }

      pre {
        background: #1e1e1e;
        border-radius: 8px;
        padding: 16px;
        overflow-x: auto;
        margin: 1em 0;

        code {
          background: transparent;
          padding: 0;
          font-size: 13px;
          line-height: 1.6;
        }
      }

      blockquote {
        margin: 1em 0;
        padding: 0.5em 1em;
        border-left: 4px solid var(--accent-color);
        background: rgba(64, 158, 255, 0.1);
        border-radius: 0 4px 4px 0;

        p {
          margin: 0;
        }
      }

      ul, ol {
        padding-left: 2em;
        margin: 0.8em 0;

        li {
          margin: 0.3em 0;
        }
      }

      table {
        width: 100%;
        border-collapse: collapse;
        margin: 1em 0;

        th, td {
          border: 1px solid var(--border-color);
          padding: 8px 12px;
          text-align: left;
        }

        th {
          background: rgba(64, 158, 255, 0.1);
          font-weight: 600;
        }

        tr:nth-child(even) {
          background: rgba(255, 255, 255, 0.02);
        }
      }

      hr {
        border: none;
        border-top: 1px solid var(--border-color);
        margin: 1.5em 0;
      }

      img {
        max-width: 100%;
        border-radius: 8px;
      }

      // details/summary 折叠样式
      details {
        margin: 1em 0;
        padding: 0.5em 1em;
        background: rgba(255, 255, 255, 0.02);
        border: 1px solid var(--border-color);
        border-radius: 8px;

        summary {
          cursor: pointer;
          font-weight: 500;
          outline: none;

          &:hover {
            color: var(--accent-color);
          }

          strong {
            font-weight: 600;
          }
        }
      }
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

  :deep(.el-divider) {
    border-color: var(--border-color);
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

  :deep(.el-switch) {
    --el-switch-on-color: var(--accent-color);
  }
}
</style>
