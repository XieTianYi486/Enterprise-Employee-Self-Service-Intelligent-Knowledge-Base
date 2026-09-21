import client from './client'

export interface Ticket {
  id: number
  title: string
  question: string
  detail: string | null
  status: string
  priority: string
  reply: string | null
  reply_count: number
  session_id: string | null
  created_by: number
  handler_id: number | null
  created_at: string
  updated_at: string | null
  resolved_at: string | null
  creator_name: string | null
  handler_name: string | null
}

export const ticketApi = {
  // 员工端
  create: (data: { title: string; question: string; detail?: string; session_id?: string; priority?: string }) =>
    client.post('/tickets', data),
  myTickets: (params: { page?: number; page_size?: number; status?: string } = {}) =>
    client.get('/tickets', { params }),
  getTicket: (id: number) => client.get(`/tickets/${id}`),

  // 管理端
  listAll: (params: { page?: number; page_size?: number; status?: string; priority?: string; keyword?: string } = {}) =>
    client.get('/admin/tickets', { params }),
  getStats: () => client.get('/admin/tickets/stats'),
  handle: (id: number, reply: string) => client.put(`/admin/tickets/${id}/handle`, { reply }),
  updateStatus: (id: number, status: string) => client.put(`/admin/tickets/${id}/status`, { status }),
}

export const TICKET_STATUS_LABELS: Record<string, { label: string; type: 'info' | 'warning' | 'success' | 'danger' }> = {
  pending: { label: '待处理', type: 'warning' },
  processing: { label: '处理中', type: 'info' },
  resolved: { label: '已解决', type: 'success' },
  closed: { label: '已关闭', type: 'danger' },
}

export const TICKET_PRIORITY_LABELS: Record<string, { label: string; type: 'danger' | 'warning' | 'success' }> = {
  high: { label: '高', type: 'danger' },
  medium: { label: '中', type: 'warning' },
  low: { label: '低', type: 'success' },
}