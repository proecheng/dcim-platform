# Story 13-1: 用户管理前端页面

## 状态: 就绪

## Story

As a 系统管理员,
I want 通过前端页面完成用户管理全部操作,
So that 我不需要直接操作数据库来管理用户。

## 验收标准 (AC)

1. 用户管理页面显示用户列表（用户名、真实姓名、角色、部门、状态、最后登录时间）
2. 支持按关键词搜索、按角色筛选、按状态筛选
3. 支持创建用户（用户名、密码、真实姓名、邮箱、手机、角色、部门）
4. 支持编辑用户信息
5. 支持删除用户（不能删除自己）
6. 支持启用/禁用用户
7. 支持重置密码
8. 仅 admin 角色可访问此页面
9. 角色选项：管理员(admin)、操作员(operator)、只读(viewer)

## 棕地分析

### 已有代码
- **后端 API**: `api/v1/user.py` — 完整 CRUD（GET列表、GET详情、POST创建、PUT更新、DELETE删除、PUT启用禁用、PUT重置密码、GET登录历史）
- **后端 Schema**: `schemas/user.py` — UserCreate, UserUpdate, UserInfo, UserListResponse
- **前端 API**: `api/modules/user.ts` — getUserList, getUserById, createUser, updateUser, deleteUser, toggleUserStatus, resetPassword, getLoginHistory
- **路由**: `/settings` 已存在，需要添加 `/system/users` 路由

### 需要新增
- 前端路由: `/system/users`
- 前端页面: `views/system/user.vue`
- 后端 API 增强: 批量删除端点 `DELETE /users/batch`

## 技术方案

### 后端增强
在 `api/v1/user.py` 添加批量删除端点:
```python
@router.delete("/batch", summary="批量删除用户")
async def batch_delete_users(user_ids: List[int], ...)
```

### 前端页面
- 使用 Element Plus 的 Table + Pagination + Dialog
- 搜索栏: 关键词输入框 + 角色下拉 + 状态下拉
- 操作列: 编辑、重置密码、启用/禁用、删除
- 新建/编辑弹窗: 表单验证
- 角色显示: admin=管理员, operator=操作员, viewer=只读

### 路由配置
在 `router/index.ts` 添加:
```typescript
{
  path: 'system',
  name: 'System',
  meta: { title: '系统管理', icon: 'Setting' },
  children: [
    {
      path: 'users',
      name: 'UserManagement',
      component: () => import('@/views/system/user.vue'),
      meta: { title: '用户管理', icon: 'User' }
    }
  ]
}
```

## 测试计划
- 后端: 8 个测试（CRUD + 批量删除 + 权限检查）
- 测试文件: `tests/test_user_management.py`

## 依赖
- 无外部依赖，所有后端 API 已存在
