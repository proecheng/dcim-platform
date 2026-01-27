/**
 * 认证相关 API
 */
import request from '@/utils/request'

export interface LoginParams {
  username: string
  password: string
}

export interface LoginResult {
  access_token: string
  token_type: string
  expires_in: number
}

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
  permissions: string[]
}

export interface PasswordChangeParams {
  old_password: string
  new_password: string
}

/**
 * 用户登录
 */
export function login(data: LoginParams): Promise<LoginResult> {
  // OAuth2PasswordRequestForm 需要表单数据格式
  const formData = new URLSearchParams()
  formData.append('username', data.username)
  formData.append('password', data.password)
  return request.post('/v1/auth/login', formData, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
  })
}

/**
 * 用户登出
 */
export function logout(): Promise<void> {
  return request.post('/v1/auth/logout')
}

/**
 * 刷新 Token
 */
export function refreshToken(): Promise<LoginResult> {
  return request.post('/v1/auth/refresh')
}

/**
 * 获取当前用户信息
 */
export function getCurrentUser(): Promise<UserInfo> {
  return request.get('/v1/auth/me')
}

/**
 * 修改密码
 */
export function changePassword(data: PasswordChangeParams): Promise<void> {
  return request.put('/v1/auth/password', data)
}

/**
 * 获取当前用户权限
 */
export function getPermissions(): Promise<string[]> {
  return request.get('/v1/auth/permissions')
}
