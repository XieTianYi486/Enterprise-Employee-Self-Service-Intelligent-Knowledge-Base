import { defineStore } from 'pinia'
import { ref } from 'vue'
import { authApi } from '@/api/auth'
import { useChatStore } from '@/store/chat'
import router from '@/router'

export interface UserInfo {
  id: number
  username: string
  real_name: string | null
  email: string | null
  phone: string | null
  position: string | null
  avatar_url: string | null
  department: string | null
  dept_id: number | null
  gender: string | null
  entry_date: string | null
  role_id: number
  role_name: string | null
  permissions: string[] | null
  status: number
  created_at: string
}

export const useAuthStore = defineStore('auth', () => {
  const user = ref<UserInfo | null>(null)
  const token = ref<string>(localStorage.getItem('access_token') || '')
  const loading = ref(false)

  /** 初始化：从 localStorage 恢复登录状态 */
  async function initialize() {
    if (!token.value) return
    try {
      const res = await authApi.getMe()
      user.value = res.data.data
    } catch {
      logout()
    }
  }

  /** 登录 */
  async function login(username: string, password: string, captcha?: { token?: string; code?: string }) {
    loading.value = true
    try {
      const res = await authApi.login({
        username,
        password,
        captcha_token: captcha?.token,
        captcha_code: captcha?.code,
      })
      const data = res.data.data
      token.value = data.access_token
      user.value = data.user
      localStorage.setItem('access_token', data.access_token)
      // 切换账号：清空上一账号留在内存中的会话/消息，避免串号看到他人聊天内容
      useChatStore().reset()
      localStorage.removeItem('chatClearedAt')
      router.push('/workbench')
    } finally {
      loading.value = false
    }
  }

  /** 退出 */
  function logout() {
    // 清空问答内存态并中止进行中的流式请求，防止下个账号看到本账号的会话/消息
    useChatStore().reset()
    token.value = ''
    user.value = null
    localStorage.removeItem('access_token')
    // 本账号的"清空对话"标记不应影响下个账号的会话列表过滤
    localStorage.removeItem('chatClearedAt')
    router.push('/login')
  }

  /** 检查是否为管理员 */
  const isAdmin = () => {
    return user.value?.role_name === '超级管理员' || user.value?.role_name === '知识库管理员'
  }

  const isSuperAdmin = () => {
    return user.value?.role_name === '超级管理员'
  }

  /** 是否拥有指定权限点（与后端 has_permission 规则一致：* 全部 / 精确匹配 / 模块:* 通配） */
  const can = (permission: string): boolean => {
    const perms = user.value?.permissions || []
    if (perms.includes('*')) return true
    if (perms.includes(permission)) return true
    const module = permission.split(':')[0]
    return perms.includes(`${module}:*`)
  }

  return { user, token, loading, initialize, login, logout, isAdmin, isSuperAdmin, can }
})
