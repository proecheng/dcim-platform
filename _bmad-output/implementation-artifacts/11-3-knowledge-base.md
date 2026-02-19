# Story 11-3: 知识库

## Story

As a 运维工程师,
I want 查阅和维护知识库,
So that 故障处理经验和操作规程可以积累和共享。

**FR 追溯:** FR71

---

## 状态: 已审查

## Brownfield 分析

### 已有代码（完整可用）

| 层级 | 文件 | 已有内容 |
|------|------|----------|
| Model | `models/operation.py` | KnowledgeBase (title, category, content, tags, view_count, is_published, author) |
| Schema | `schemas/operation.py` | KnowledgeBaseSchema/Create/Update/Response |
| API | `api/v1/operation.py` | GET/POST /knowledge, GET/PUT/DELETE /knowledge/{id} — 含分类过滤、关键词搜索、分页、浏览量自增 |
| Frontend API | `api/modules/operation.ts` | Knowledge 类型 + API 函数（需修正字段名） |
| Router | `router/index.ts` | /operation/knowledge 路由已定义 |

### 后端 API 状态: 完整，无需修改

GET /knowledge 已支持:
- `category` 分类过滤
- `keyword` 关键词搜索（搜索 title, content, tags）
- `page`/`page_size` 分页
- 返回 `{code, message, data: {items, total, skip, limit}}`

GET /knowledge/{id} 自动增加 view_count

### 需要修改的部分

#### 1. 前端 API 类型修正 (`api/modules/operation.ts`)

| 前端字段 | 后端字段 | 修正 |
|----------|----------|------|
| keywords | tags | 改为 tags: string |
| views | view_count | 改为 view_count: number |
| likes | (不存在) | 删除 |

#### 2. 前端页面 (`views/operation/knowledge.vue`)

新建知识库管理页面:
- 分类浏览（故障处理、操作规程、设备手册 + 自定义）
- 关键词搜索
- 文章列表（标题、分类、作者、浏览量、发布状态、创建时间）
- 创建/编辑文章对话框（标题、分类、内容textarea、标签、作者、是否发布）
- 删除文章

#### 3. 测试 (`tests/test_knowledge.py`)

测试用例（约 10 个）:
1. 创建知识库文章
2. 获取文章列表
3. 获取文章列表 - category 过滤
4. 获取文章列表 - keyword 搜索
5. 获取文章详情（验证 view_count 自增）
6. 更新文章
7. 删除文章
8. 删除不存在的文章返回 404
9. 分页参数验证
10. 获取不存在的文章返回 404

---

## 验收标准

1. ✅ 前端 API 类型与后端完全对齐
2. ✅ 知识库管理页面支持分类浏览和关键词搜索
3. ✅ 文章 CRUD 完整可用
4. ✅ 浏览量自动递增
5. ✅ 所有新增测试通过，回归测试 126+ 通过

## 技术约束

- 后端 API 无需修改
- Vue 3 auto-imports: 不需要 import ref/computed/onMounted/ElMessage
- SCSS: `@use '@/styles/_mixins-25d' as *;` + `@include page-list;`
- 知识库 GET /knowledge 返回格式与其他列表不同: `{code, message, data: {items, total, skip, limit}}`
