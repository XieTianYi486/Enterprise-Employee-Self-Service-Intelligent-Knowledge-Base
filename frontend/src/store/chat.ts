import { defineStore } from 'pinia'
import { ref } from 'vue'
import { sessionApi } from '@/api/session'
import { streamQuery } from '@/api/chat'

export interface ChatMessage {
  id: number
  session_id: string
  role: 'user' | 'assistant'
  content: string
  sources: CitationSource[] | null
  token_count: number | null
  created_at: string
  /** 后端按问题关键词给出的流程跳转建议（请假/报销/工单） */
  suggested_actions?: { type: 'leave' | 'expense' | 'ticket'; label: string }[]
}

export interface CitationSource {
  document_id: number
  document_name: string
  chapter: string | null
  page: number | null
  snippet: string
  score: number
}

export interface ChatSession {
  id: string
  title: string
  message_count: number
  last_message_at: string | null
  created_at: string
}

export const useChatStore = defineStore('chat', () => {
  const sessions = ref<ChatSession[]>([])
  const activeSessionId = ref<string | null>(null)
  const messages = ref<ChatMessage[]>([])
  const streaming = ref(false)
  const streamContent = ref('')
  const streamSources = ref<CitationSource[]>([])
  const sensitiveNotice = ref<{ word: string }[]>([])
  let abortController: AbortController | null = null

  /** 加载会话列表 */
  async function loadSessions() {
    try {
      const res = await sessionApi.getSessions()
      let all = res.data.data || []
      // 过滤清空时间之前的会话（created_at 为后端 UTC 时间，需补 Z 避免本地时区偏移）
      const clearedAt = localStorage.getItem('chatClearedAt')
      if (clearedAt) {
        const threshold = parseInt(clearedAt)
        all = all.filter((s: ChatSession) => {
          const t = s.created_at
          const ts = t ? new Date(t.endsWith('Z') ? t : t + 'Z').getTime() : 0
          return ts > threshold
        })
      }
      sessions.value = all
    } catch { /* ignore */ }
  }

  /** 创建新会话 */
  async function createSession(): Promise<string> {
    const res = await sessionApi.createSession({ title: '新对话' })
    const session = res.data.data
    sessions.value.unshift({
      id: session.session_id,
      title: session.title,
      message_count: 0,
      last_message_at: null,
      created_at: new Date().toISOString(),
    })
    return session.session_id
  }

  /** 选择会话 */
  async function selectSession(sessionId: string) {
    if (streaming.value) cancelStreaming()
    activeSessionId.value = sessionId
    try {
      const res = await sessionApi.getMessages(sessionId)
      messages.value = res.data.data?.items || []
    } catch {
      messages.value = []
    }
  }

  /** 删除会话 */
  async function deleteSession(sessionId: string) {
    await sessionApi.deleteSession(sessionId)
    sessions.value = sessions.value.filter(s => s.id !== sessionId)
    if (activeSessionId.value === sessionId) {
      activeSessionId.value = null
      messages.value = []
    }
  }

  /** 发送消息 */
  async function sendMessage(question: string) {
    const isNewSession = !activeSessionId.value
    if (isNewSession) {
      activeSessionId.value = await createSession()
    }
    // 此刻会话已保证存在，取非空引用供后续使用
    const sessionId = activeSessionId.value!

    // 若为新会话，用首条提问自动生成标题，便于列表识别
    if (isNewSession) {
      const title = question.replace(/\s+/g, ' ').trim()
      const shortTitle = title.length > 20 ? title.slice(0, 20) + '…' : title
      const item = sessions.value.find(s => s.id === activeSessionId.value)
      if (item) {
        item.title = shortTitle
        item.last_message_at = new Date().toISOString()
        item.message_count = 1
      }
      // 异步同步到后端，失败不影响前端体验
      if (shortTitle) {
        sessionApi.updateSession(sessionId, { title: shortTitle }).catch(() => {})
      }
    }

    // 乐观添加用户消息
    messages.value.push({
      id: Date.now(),
      session_id: sessionId,
      role: 'user',
      content: question,
      sources: null,
      token_count: null,
      created_at: new Date().toISOString(),
    })

    // 流式获取回答
    streaming.value = true
    streamContent.value = ''
    streamSources.value = []

    // 各回调先校验会话是否仍是当前会话：
    // 退出登录/切换账号会 reset()（activeSessionId 置空），
    // 过期回调直接丢弃，避免上一账号的回答串进新账号界面
    const isCurrentSession = () => activeSessionId.value === sessionId

    abortController = streamQuery(
      sessionId,
      question,
      (token) => { if (isCurrentSession()) streamContent.value += token },
      (sources) => { if (isCurrentSession()) streamSources.value = sources },
      (result) => {
        if (!isCurrentSession()) return
        // 完成
        messages.value.push({
          id: Date.now(),
          session_id: activeSessionId.value!,
          role: 'assistant',
          content: streamContent.value,
          sources: streamSources.value,
          token_count: result.total_tokens || 0,
          created_at: new Date().toISOString(),
          suggested_actions: result.suggested_actions || [],
        })
        streamContent.value = ''
        sensitiveNotice.value = []
        streaming.value = false
        loadSessions()
      },
      (error) => {
        if (!isCurrentSession()) return
        messages.value.push({
          id: Date.now(),
          session_id: activeSessionId.value!,
          role: 'assistant',
          content: `抱歉，请求出错了：${error}`,
          sources: null,
          token_count: null,
          created_at: new Date().toISOString(),
        })
        streaming.value = false
      },
      (masked, hits) => {
        if (!isCurrentSession()) return
        // 后端完成敏感词脱敏，用脱敏后的完整回答覆盖流式内容，并提示用户
        streamContent.value = masked
        sensitiveNotice.value = hits
      }
    )
  }

  /** 取消流式输出 */
  function cancelStreaming() {
    abortController?.abort()
    if (streamContent.value) {
      messages.value.push({
        id: Date.now(),
        session_id: activeSessionId.value!,
        role: 'assistant',
        content: streamContent.value + ' [已停止]',
        sources: streamSources.value,
        token_count: null,
        created_at: new Date().toISOString(),
      })
    }
    streamContent.value = ''
    streaming.value = false
  }

  /** 提交反馈 */
  async function submitFeedback(feedback: number, reason?: string) {
    try {
      const token = localStorage.getItem('access_token')
      await fetch('/api/v1/chat/feedback', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          session_id: activeSessionId.value,
          feedback,
          reason: reason || null,
        }),
      })
    } catch { /* ignore */ }
  }

  /** 重置（退出登录/切换账号时调用）：清空全部问答内存态并中止进行中的流式请求 */
  function reset() {
    abortController?.abort()
    abortController = null
    sessions.value = []
    activeSessionId.value = null
    messages.value = []
    streaming.value = false
    streamContent.value = ''
    streamSources.value = []
    sensitiveNotice.value = []
  }

  /** 一键清空所有对话（仅清前端，后端数据保留，刷新不恢复） */
  function clearAllFrontend() {
    if (streaming.value) cancelStreaming()
    sessions.value = []
    activeSessionId.value = null
    messages.value = []
    streamContent.value = ''
    localStorage.setItem('chatClearedAt', String(Date.now()))
  }

  return {
    sessions, activeSessionId, messages, streaming, streamContent, streamSources,
    sensitiveNotice,
    loadSessions, createSession, selectSession, deleteSession,
    sendMessage, cancelStreaming, submitFeedback, reset, clearAllFrontend,
  }
})
