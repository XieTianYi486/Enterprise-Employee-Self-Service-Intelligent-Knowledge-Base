/**
 * OA 办公流程 API 封装
 * 请假 / 报销 / 假期余额 / 审批中心（两级审批）
 */

import client from './client'

export interface LeaveBalance {
  year: number
  annual_total: number
  annual_used: number
  annual_left: number
  personal_used: number
  sick_used: number
  compensatory_total: number
  compensatory_used: number
  compensatory_left: number
}

export interface BillItem {
  id: number
  biz_type: 'LEAVE' | 'EXPENSE'
  user_id: number
  applicant_name: string | null
  dept_id: number | null
  // 请假字段
  leave_type: string | null
  start_date: string | null
  end_date: string | null
  days: number | null
  // 报销字段
  expense_type: string | null
  amount: number | null
  expense_date: string | null
  attachments: string[] | null
  // 公共
  reason: string | null
  status: 'PENDING' | 'APPROVED' | 'REJECTED' | 'CANCELLED'
  current_node: 'MANAGER' | 'BOSS' | 'NONE'
  create_time: string
}

export interface ApprovalRecordItem {
  node_name: string
  approver_name: string | null
  approver_role: string
  action_type: 'APPROVE' | 'REJECT'
  comment_text: string | null
  create_time: string
}

export interface BillDetail extends BillItem {
  records: ApprovalRecordItem[]
}

export const workflowApi = {
  // 假期余额
  getBalance: () => client.get('/leaves/balance'),

  // 请假
  submitLeave: (data: { leave_type: string; start_date: string; end_date: string; reason?: string }) =>
    client.post('/leaves', data),
  listLeaves: (params: { page?: number; page_size?: number; status?: string; pending_only?: boolean } = {}) =>
    client.get('/leaves', { params }),
  getLeave: (id: number) => client.get(`/leaves/${id}`),
  cancelLeave: (id: number) => client.post(`/leaves/${id}/cancel`),

  // 报销
  uploadExpenseAttachment: (file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return client.post('/expenses/attachments', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  submitExpense: (data: { expense_type: string; amount: number; expense_date: string; reason?: string; attachments?: string[] }) =>
    client.post('/expenses', data),
  listExpenses: (params: { page?: number; page_size?: number; status?: string; pending_only?: boolean } = {}) =>
    client.get('/expenses', { params }),
  getExpense: (id: number) => client.get(`/expenses/${id}`),
  cancelExpense: (id: number) => client.post(`/expenses/${id}/cancel`),

  // 审批中心
  getTodo: (params: { biz_type?: string; page?: number; page_size?: number } = {}) =>
    client.get('/approvals/todo', { params }),
  getDone: (params: { page?: number; page_size?: number } = {}) =>
    client.get('/approvals/done', { params }),
  approve: (bizType: string, billId: number, data: { action: 'APPROVE' | 'REJECT'; comment?: string }) =>
    client.post(`/approvals/${bizType}/${billId}`, data),
}

export const LEAVE_STATUS_LABELS: Record<string, { label: string; type: 'info' | 'warning' | 'success' | 'danger' }> = {
  PENDING: { label: '待审批', type: 'warning' },
  APPROVED: { label: '已通过', type: 'success' },
  REJECTED: { label: '已驳回', type: 'danger' },
  CANCELLED: { label: '已撤销', type: 'info' },
}

export const NODE_LABELS: Record<string, string> = {
  MANAGER: '部门经理',
  BOSS: '总经理',
  NONE: '—',
}

export const LEAVE_TYPE_TAG: Record<string, 'primary' | 'success' | 'warning' | 'danger' | 'info'> = {
  年假: 'primary',
  事假: 'warning',
  病假: 'danger',
  调休: 'success',
  婚假: 'info',
}
