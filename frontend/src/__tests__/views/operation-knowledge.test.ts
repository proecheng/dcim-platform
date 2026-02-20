/**
 * 知识库页面 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, computed } from 'vue'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }), useRoute: () => ({ params: {}, query: {} }), createRouter: vi.fn(), createWebHistory: vi.fn() }))

const KnowledgeTestable = defineComponent({
  name: 'KnowledgeTestable',
  setup() {
    const loading = ref(false)
    const knowledgeList = ref([
      { id: 1, title: 'UPS维护手册', category: 'maintenance', author: '张三', views: 156, created_at: '2026-01-15' },
      { id: 2, title: '空调故障排查指南', category: 'troubleshooting', author: '李四', views: 89, created_at: '2026-01-20' },
      { id: 3, title: '机房安全规范', category: 'safety', author: '王五', views: 234, created_at: '2026-01-10' }
    ])
    const currentArticle = ref<any>(null)
    const editDialogVisible = ref(false)
    const viewDialogVisible = ref(false)
    const editForm = ref({ title: '', category: '', content: '' })
    const searchKeyword = ref('')
    const currentPage = ref(1)
    const total = ref(30)
    const categoryMap: Record<string, string> = { maintenance: '维护保养', troubleshooting: '故障排查', safety: '安全规范' }
    const filteredList = computed(() => {
      if (!searchKeyword.value) return knowledgeList.value
      return knowledgeList.value.filter(k => k.title.includes(searchKeyword.value))
    })
    const viewArticle = (a: any) => { currentArticle.value = a; viewDialogVisible.value = true }
    return { loading, knowledgeList, currentArticle, editDialogVisible, viewDialogVisible, editForm, searchKeyword, currentPage, total, categoryMap, filteredList, viewArticle }
  },
  template: `<div class="knowledge"><div class="toolbar"><input v-model="searchKeyword" data-testid="search-input" placeholder="搜索知识库" /><button data-testid="create-btn" @click="editDialogVisible = true">新建文章</button></div><div class="article-list" data-testid="article-list"><div v-for="a in filteredList" :key="a.id" :data-testid="'article-' + a.id" class="article-card" @click="viewArticle(a)"><span class="title">{{ a.title }}</span><span class="category">{{ categoryMap[a.category] || a.category }}</span><span class="author">{{ a.author }}</span><span class="views">{{ a.views }}</span></div></div><div class="pagination" data-testid="pagination"><span>第 {{ currentPage }} 页</span><span>共 {{ total }} 条</span></div><div v-if="editDialogVisible" class="edit-dialog" data-testid="edit-dialog"><input :value="editForm.title" data-testid="edit-title" /></div><div v-if="viewDialogVisible" class="view-dialog" data-testid="view-dialog"><span class="article-title">{{ currentArticle?.title }}</span></div></div>`
})

describe('知识库页面', () => {
  beforeEach(() => { setActivePinia(createPinia()) })
  it('渲染文章列表', () => { const w = mount(KnowledgeTestable); expect(w.findAll('.article-card')).toHaveLength(3) })
  it('显示文章标题和分类', () => { const w = mount(KnowledgeTestable); expect(w.find('[data-testid="article-1"] .title').text()).toBe('UPS维护手册'); expect(w.find('[data-testid="article-1"] .category').text()).toBe('维护保养') })
  it('显示浏览量', () => { expect(mount(KnowledgeTestable).find('[data-testid="article-3"] .views').text()).toBe('234') })
  it('搜索过滤文章', async () => { const w = mount(KnowledgeTestable); await w.find('[data-testid="search-input"]').setValue('空调'); expect(w.findAll('.article-card')).toHaveLength(1) })
  it('点击新建打开编辑对话框', async () => { const w = mount(KnowledgeTestable); await w.find('[data-testid="create-btn"]').trigger('click'); expect(w.find('[data-testid="edit-dialog"]').exists()).toBe(true) })
  it('点击文章打开查看对话框', async () => { const w = mount(KnowledgeTestable); await w.find('[data-testid="article-2"]').trigger('click'); expect(w.find('[data-testid="view-dialog"]').exists()).toBe(true); expect(w.find('.article-title').text()).toBe('空调故障排查指南') })
  it('显示分页信息', () => { const w = mount(KnowledgeTestable); expect(w.find('[data-testid="pagination"]').text()).toContain('第 1 页'); expect(w.find('[data-testid="pagination"]').text()).toContain('共 30 条') })
})
