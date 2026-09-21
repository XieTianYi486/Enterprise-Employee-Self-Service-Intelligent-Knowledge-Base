import client from './client'

export const authApi = {
  login: (data: { username: string; password: string; captcha_token?: string; captcha_code?: string }) =>
    client.post('/auth/login', data),
  captcha: () => client.get('/auth/captcha'),
  register: (data: { username: string; password: string; email?: string; real_name?: string; dept_id?: number; captcha_token?: string; captcha_code?: string }) =>
    client.post('/auth/register', data),
  getMe: () => client.get('/auth/me'),
  changePassword: (data: { old_password: string; new_password: string }) =>
    client.post('/auth/change-password', data),
  updateProfile: (data: { real_name?: string; email?: string; phone?: string; position?: string; gender?: string; entry_date?: string }) =>
    client.put('/auth/profile', data),
  uploadAvatar: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return client.post('/auth/avatar', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
}
