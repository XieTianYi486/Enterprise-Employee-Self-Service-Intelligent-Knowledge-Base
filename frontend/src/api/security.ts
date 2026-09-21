import client from './client'

// 敏感词管理
export const sensitiveApi = {
  list: (params: { page?: number; page_size?: number; keyword?: string; enabled?: number }) =>
    client.get('/admin/sensitive-words', { params }),
  create: (data: { word: string; level?: number; action?: string; replacement?: string; category?: string }) =>
    client.post('/admin/sensitive-words', data),
  update: (id: number, data: Record<string, any>) =>
    client.put(`/admin/sensitive-words/${id}`, data),
  remove: (id: number) => client.delete(`/admin/sensitive-words/${id}`),
}

// 审计日志
export const auditApi = {
  list: (params: { page?: number; page_size?: number; module?: string; action?: string; keyword?: string }) =>
    client.get('/admin/audit-logs', { params }),
}

// 知识审核
export const reviewApi = {
  queue: (params: { page?: number; page_size?: number; review_status?: number }) =>
    client.get('/admin/documents/review-queue', { params }),
  review: (id: number, data: { action: 'approve' | 'reject' | 'submit' | 'recall'; comment?: string }) =>
    client.post(`/admin/documents/${id}/review`, data),
  batchReview: (data: { action: 'approve' | 'reject'; ids: number[]; comment?: string }) =>
    client.post('/admin/documents/batch-review', data),
}

// 验证码与 SSO
export const authSecurity = {
  captcha: () => client.get('/auth/captcha'),
  ssoStatus: () => client.get('/auth/sso/status'),
}