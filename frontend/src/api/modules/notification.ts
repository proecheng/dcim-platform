/**
 * 通知管理 API 模块
 * Story 34.7 — 通知管理前端
 */

import request from '@/utils/request'

// ===== 类型定义 =====

export interface NotificationPolicyItem {
  id: number
  name: string
  site_id: number | null
  alarm_level: string
  time_range_start: string | null
  time_range_end: string | null
  channels: string[]
  notify_user_ids: number[]
  is_enabled: boolean
  channel_escalation_enabled: boolean
  escalation_timeout_minutes: number | null
  escalation_channel_order: string[] | null
  is_default: boolean
  created_at: string
}

export interface NotificationPolicyForm {
  name: string
  site_id: number | null
  alarm_level: string
  time_range_start: string | null
  time_range_end: string | null
  channels: string[]
  notify_user_ids: number[]
  is_enabled: boolean
  channel_escalation_enabled: boolean
  escalation_timeout_minutes: number | null
  escalation_channel_order: string[] | null
}

export interface NotificationRecordItem {
  id: number
  alarm_id: number | null
  alarm_level: string | null
  user_id: number | null
  policy_id: number | null
  channel_type: string
  platform: string | null
  contact_value: string
  content_summary: string | null
  status: string
  retry_count: number
  error_message: string | null
  sent_at: string | null
  created_at: string | null
}

export interface NotificationRecordQuery {
  channel_type?: string
  status?: string
  alarm_level?: string
  start_time?: string
  end_time?: string
  page?: number
  page_size?: number
}

export interface ChannelStatusItem {
  channel_type: string
  enabled: boolean
  healthy: boolean
}

export interface ContactItem {
  id: number
  user_id: number
  channel_type: string
  platform: string | null
  contact_value: string
  is_enabled: boolean
}

export interface ContactForm {
  channel_type: string
  platform: string | null
  contact_value: string
  is_enabled: boolean
}

// ===== 通知策略 =====

export function getPolicies(params?: { site_id?: number; alarm_level?: string }) {
  return request.get('/v1/notification/policies', { params })
}

export function createPolicy(data: NotificationPolicyForm) {
  return request.post('/v1/notification/policies', data)
}

export function updatePolicy(id: number, data: Partial<NotificationPolicyForm>) {
  return request.put(`/v1/notification/policies/${id}`, data)
}

export function deletePolicy(id: number) {
  return request.delete(`/v1/notification/policies/${id}`)
}

// ===== 通知记录 =====

export function getRecords(params?: NotificationRecordQuery) {
  return request.get('/v1/notification/records', { params })
}

// ===== 渠道状态 =====

export function getChannelStatus() {
  return request.get('/v1/notification/channels')
}

export function testChannel(data: { channel_type: string; contact_value: string }) {
  return request.post('/v1/notification/channels/test', data)
}

// ===== 用户联系方式 =====

export function getUserContacts(userId: number) {
  return request.get(`/v1/users/${userId}/notification-contacts`)
}

export function createContact(userId: number, data: ContactForm) {
  return request.post(`/v1/users/${userId}/notification-contacts`, data)
}

export function updateContact(userId: number, contactId: number, data: Partial<ContactForm>) {
  return request.put(`/v1/users/${userId}/notification-contacts/${contactId}`, data)
}

export function deleteContact(userId: number, contactId: number) {
  return request.delete(`/v1/users/${userId}/notification-contacts/${contactId}`)
}

export function importFromProfile(userId: number) {
  return request.post(`/v1/users/${userId}/notification-contacts/import-from-profile`)
}
