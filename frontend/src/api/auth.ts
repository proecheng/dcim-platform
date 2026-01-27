import request from '@/utils/request'

export function login(username: string, password: string) {
  const formData = new FormData()
  formData.append('username', username)
  formData.append('password', password)
  return request.post('/v1/auth/login', formData)
}

export function logout() {
  return request.post('/v1/auth/logout')
}

export function getUserInfo() {
  return request.get('/v1/auth/me')
}

export function changePassword(oldPassword: string, newPassword: string) {
  return request.put('/v1/auth/password', {
    old_password: oldPassword,
    new_password: newPassword
  })
}
