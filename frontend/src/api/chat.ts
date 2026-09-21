/**
 * SSE 流式查询
 * 向 /api/v1/chat/stream 发送请求，通过 Server-Sent Events 接收流式回答
 */

import type { CitationSource } from '@/store/chat'

export interface SuggestedAction {
  type: 'leave' | 'expense' | 'ticket'
  label: string
}

interface StreamCallbacks {
  onToken: (token: string) => void
  onSources: (sources: CitationSource[]) => void
  onSensitive?: (masked: string, hits: any[]) => void
  onDone: (result: { message_id: string; total_tokens: number; status?: string; suggested_actions?: SuggestedAction[] }) => void
  onError: (error: string) => void
}

export function streamQuery(
  sessionId: string,
  question: string,
  onToken: (token: string) => void,
  onSources: (sources: CitationSource[]) => void,
  onDone: (result: { message_id: string; total_tokens: number; status?: string; suggested_actions?: SuggestedAction[] }) => void,
  onError: (error: string) => void,
  onSensitive?: (masked: string, hits: any[]) => void,
): AbortController {
  const controller = new AbortController()
  const token = localStorage.getItem('access_token')

  fetch('/api/v1/chat/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
    },
    body: JSON.stringify({ question, session_id: sessionId }),
    signal: controller.signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      const reader = response.body?.getReader()
      if (!reader) throw new Error('No response body')

      const decoder = new TextDecoder()
      let buffer = ''
      let currentEvent = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            currentEvent = line.slice(7).trim()
          } else if (line.startsWith('data: ')) {
            const data = line.slice(6).trim()
            if (!data) continue

            try {
              const parsed = JSON.parse(data)
              switch (currentEvent) {
                case 'token':
                  onToken(parsed.token)
                  break
                case 'sources':
                  onSources(parsed)
                  break
                case 'sensitive':
                  onSensitive?.(parsed.full_answer, parsed.hits || [])
                  break
                case 'done':
                  onDone(parsed)
                  break
                case 'error':
                  onError(parsed.message || '未知错误')
                  break
              }
            } catch {
              // 非 JSON 数据，忽略
            }
          }
        }
      }
    })
    .catch((error) => {
      if (error.name === 'AbortError') return
      onError(error.message || '网络请求失败')
    })

  return controller
}
