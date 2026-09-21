import client from './client'

export const sessionApi = {
  getSessions: () => client.get('/chat/sessions'),
  createSession: (data: { title?: string }) =>
    client.post('/chat/sessions', data),
  updateSession: (id: string, data: { title?: string }) =>
    client.patch(`/chat/sessions/${id}`, data),
  deleteSession: (id: string) =>
    client.delete(`/chat/sessions/${id}`),
  getMessages: (sessionId: string, page = 1, pageSize = 50) =>
    client.get(`/chat/sessions/${sessionId}/messages`, { params: { page, page_size: pageSize } }),
}
