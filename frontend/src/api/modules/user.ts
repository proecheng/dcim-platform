/**
 * 用户管理 API
 */
import request from '@/utils/request'
import type { PageParams, PageResponse } from './types'

export interface UserInfo {
  id: number
  username: string
  real_name: string
  email: string
  phone: string
  role: string
  department: string
  avatar: string
  is_active: boolean
  last_login_at: string
  login_count: number
  created_at: string
  updated_at: string
}

export interface UserCreateParams {
  username: string
  password: string
  real_name?: string
  email?: string
  phone?: string
  role?: string
  department?: string
}

export interface UserUpdateParams {
  real_name?: string
  email?: string
  phone?: string
  role?: string
  department?: string
  avatar?: string
}

export interface LoginHistory {
  id: number
  user_id: number
  login_at: string
  login_ip: string
  user_agent: string
  status: string
  fail_reason?: string
}

/**
 * 获取用户列表
 */
export function getUserList(params: PageParams & {
  keyword?: string
  role?: string
  is_active?: boolean
}): Promise<PageResponse<UserInfo>> {
  return request.get('/v1/users', { params })
}

/**
 * 获取用户详情
 */
export function getUserById(id: number): Promise<UserInfo> {
  return request.get(`/v1/users/${id}`)
}

/**
 * 创建用户
 */
export function createUser(data: UserCreateParams): Promise<UserInfo> {
  return request.post('/v1/users', data)
}

/**
 * 更新用户
 */
export function updateUser(id: number, data: UserUpdateParams): Promise<UserInfo> {
  return request.put(`/v1/users/${id}`, data)
}

/**
 * 删除用户
 */
export function deleteUser(id: number): Promise<void> {
  return request.delete(`/v1/users/${id}`)
}

/**
 * 启用/禁用用户
 */
export function toggleUserStatus(id: number, is_active: boolean): Promise<void> {
  return request.put(`/v1/users/${id}/status`, { is_active })
}

/**
 * 重置密码
 */
export function resetPassword(id: number, new_password: string): Promise<void> {
  return request.put(`/v1/users/${id}/reset-password`, { new_password })
}

/**
 * 获取用户登录历史
 */
export function getLoginHistory(id: number, params?: PageParams): Promise<PageResponse<LoginHistory>> {
  return request.get(`/v1/users/${id}/login-history`, { params })
}
