<template>
  <div class="chat-page">
    <!-- 会话侧边栏 -->
    <div class="chat-sidebar">
      <div class="sidebar-header">
        <el-button type="primary" @click="handleNewChat" :icon="Plus" class="new-chat-btn">
          新对话
        </el-button>
        <el-popconfirm
          title="确定清空所有对话？"
          @confirm="handleClearAll"
        >
          <template #reference>
            <el-button text :icon="Delete" class="clear-all-btn" title="清空所有对话" />
          </template>
        </el-popconfirm>
      </div>

      <div class="session-list">
        <div
          v-for="session in chatStore.sessions"
          :key="session.id"
          class="session-item"
          :class="{ active: session.id === chatStore.activeSessionId }"
          @click="chatStore.selectSession(session.id)"
        >
          <el-icon class="session-icon"><ChatLineRound /></el-icon>
          <div class="session-body">
            <span class="session-title">{{ session.title }}</span>
            <span class="session-time">{{ relativeTime(session.last_message_at || session.created_at) }}</span>
          </div>
          <el-popconfirm title="确定删除此对话？" @confirm="chatStore.deleteSession(session.id)">
            <template #reference>
              <el-button
                :icon="Delete"
                text
                size="small"
                class="delete-btn"
                @click.stop
              />
            </template>
          </el-popconfirm>
        </div>

        <el-empty v-if="chatStore.sessions.length === 0" description="暂无对话" :image-size="60" />
      </div>
    </div>

    <!-- 聊天主区域 -->
    <div class="chat-main">
      <!-- 公告栏 -->
      <div v-if="announcements.length > 0" class="announce-bar">
        <el-icon :size="16"><Bell /></el-icon>
        <span class="announce-title">{{ announcements[0].title }}</span>
        <el-button
          v-if="announcements.length > 0"
          size="small"
          text
          @click="showAnnounceDetail = true"
        >查看详情</el-button>
        <el-icon class="announce-close" :size="14" @click="announcements = []"><Close /></el-icon>
      </div>

      <!-- 消息列表 -->
      <div class="message-area" ref="messageAreaRef">
        <div v-if="chatStore.messages.length === 0 && !chatStore.streaming" class="welcome">
          <div class="welcome-inner">
            <div class="welcome-hero">
              <div class="welcome-bot">
                <el-icon :size="28"><Service /></el-icon>
              </div>
              <h2>制度智能问答</h2>
              <p>基于知识库为您解答公司制度、流程、政策相关问题，点击下方问题快速开始</p>
            </div>
            <div class="preset-section">
              <div class="category-bar">
                <button class="category-arrow" @click="scrollCategories(-1)" aria-label="上一页">
                  <el-icon :size="14"><ArrowLeft /></el-icon>
                </button>
                <div class="category-track" ref="categoryTrackRef">
                  <button
                    v-for="group in presetQuestions"
                    :key="group.category"
                    class="category-pill"
                    :class="{ active: activeCategory === group.category }"
                    @click="activeCategory = group.category"
                  >
                    <el-icon :size="14"><component :is="group.icon" /></el-icon>
                    <span>{{ group.category }}</span>
                  </button>
                </div>
                <button class="category-arrow" @click="scrollCategories(1)" aria-label="下一页">
                  <el-icon :size="14"><ArrowRight /></el-icon>
                </button>
              </div>

              <Transition name="panel" mode="out-in">
                <div :key="activeCategory" class="preset-panel">
                  <div class="preset-panel-hint">
                    <el-icon :size="14"><component :is="activeGroup?.icon" /></el-icon>
                    <span>{{ activeCategory }}相关问题，点击快速提问</span>
                  </div>
                  <div class="preset-panel-list">
                    <button
                      v-for="q in activeGroup?.questions"
                      :key="q"
                      class="preset-question-chip"
                      @click="quickAsk(q)"
                    >{{ q }}</button>
                  </div>
                </div>
              </Transition>
            </div>
          </div>
        </div>

        <div
          v-for="msg in chatStore.messages"
          :key="msg.id"
          class="message-row"
          :class="msg.role"
        >
          <div class="message-avatar">
            <img
              v-if="msg.role === 'user' && authStore.user?.avatar_url"
              :src="authStore.user.avatar_url"
              class="avatar-img"
            />
            <el-icon v-else-if="msg.role === 'assistant'" :size="20">
              <Service />
            </el-icon>
            <el-icon v-else :size="20"><UserFilled /></el-icon>
          </div>

          <div class="message-bubble">
            <div class="message-content" v-html="renderMarkdown(msg.content || '')"></div>

            <!-- 引用来源 -->
            <div v-if="msg.sources && msg.sources.length > 0" class="message-sources">
              <el-collapse>
                <el-collapse-item>
                  <template #title>查看来源 ({{ msg.sources.length }})</template>
                  <div
                    v-for="(src, i) in msg.sources"
                    :key="i"
                    class="source-item"
                  >
                    <el-tag
                      size="small" type="info"
                      style="cursor:pointer"
                      @click="viewDocument(src.document_id)"
                    >{{ src.document_name }}</el-tag>
                    <span v-if="src.chapter" class="source-chapter">{{ src.chapter }}</span>
                    <span v-if="src.page" class="source-page">第 {{ src.page }} 页</span>
                    <p class="source-snippet">{{ src.snippet }}</p>
                  </div>
                </el-collapse-item>
              </el-collapse>
            </div>

            <!-- 流程跳转建议（后端按问题关键词推荐） -->
            <div v-if="msg.role === 'assistant' && msg.suggested_actions?.length" class="action-row">
              <span class="action-hint">相关办理：</span>
              <el-button
                v-for="a in msg.suggested_actions"
                :key="a.type"
                size="small"
                type="primary"
                plain
                @click="goAction(a.type)"
              >{{ a.label }}</el-button>
            </div>

            <!-- 反馈按钮 (仅AI消息) -->
            <div v-if="msg.role === 'assistant'" class="feedback-row">
              <span
                class="feedback-btn"
                :class="{ active: feedbackState[msg.id] === 1 }"
                @click="handleFeedback(msg, 1)"
                title="有帮助"
              >👍</span>
              <span
                class="feedback-btn"
                :class="{ active: feedbackState[msg.id] === 2 }"
                @click="handleFeedback(msg, 2)"
                title="没帮助"
              >👎</span>
            </div>
          </div>

          <!-- 用户消息：转人工客服 -->
          <span v-if="msg.role === 'user'" class="escalate-btn" @click="openTicket(msg.content)">
            <el-icon :size="13"><Headset /></el-icon> 人工客服
          </span>
        </div>

        <!-- 流式输出 -->
        <div v-if="chatStore.streaming" class="message-row assistant">
          <div class="message-avatar">
            <el-icon :size="20"><Service /></el-icon>
          </div>
          <div class="message-bubble streaming">
            <span v-html="renderMarkdown(chatStore.streamContent)"></span>
            <span class="cursor-blink">|</span>
            <div v-if="chatStore.sensitiveNotice.length" class="sensitive-notice">
              已按合规要求对回答中敏感词进行了脱敏处理
            </div>
          </div>
        </div>
      </div>

      <!-- 输入区域 -->
      <div class="input-area">
        <el-input
          v-model="inputText"
          type="textarea"
          :rows="2"
          placeholder="输入您的问题，按 Enter 发送..."
          resize="none"
          :disabled="chatStore.streaming"
          @keydown.enter.exact.prevent="handleSend"
        />
        <div class="input-actions">
          <span class="input-hint">
            <el-icon :size="13"><Promotion /></el-icon>
            Enter 发送 · Shift + Enter 换行
          </span>
          <div class="input-btns">
            <span class="char-count">{{ inputText.length }}/2000</span>
            <el-button
              v-if="chatStore.streaming"
              type="danger"
              :icon="VideoPause"
              round
              @click="chatStore.cancelStreaming()"
            >
              停止
            </el-button>
            <el-button
              v-else
              type="primary"
              :icon="Promotion"
              :disabled="!inputText.trim()"
              round
              @click="handleSend"
            >
              发送
            </el-button>
          </div>
        </div>
      </div>
    </div>

    <!-- 文档查看弹窗 -->
    <el-dialog
      v-model="docDialogVisible"
      :title="docViewTitle"
      width="70%"
      top="5vh"
      destroy-on-close
      class="doc-dialog"
    >
      <div class="doc-content" v-html="renderMarkdown(docContent)"></div>
    </el-dialog>

    <!-- 公告详情弹窗 -->
    <el-dialog
      v-model="showAnnounceDetail"
      title="公告详情"
      width="600px"
      destroy-on-close
    >
      <div v-if="announcements.length > 0">
        <div
          v-for="ann in announcements"
          :key="ann.id"
          class="announce-detail-item"
        >
          <h4>{{ ann.title }}</h4>
          <div class="announce-content" v-html="renderMarkdown(ann.content)"></div>
          <div class="announce-time">{{ ann.publish_at ? new Date(ann.publish_at).toLocaleString('zh-CN') : '' }}</div>
        </div>
      </div>
    </el-dialog>

    <!-- 转人工工单弹窗 -->
    <el-dialog v-model="ticketVisible" title="转人工客服" width="520px">
      <div class="ticket-dialog-hint">
        <el-icon :size="16" color="#e6a23c"><Headset /></el-icon>
        <span>人工客服将尽快受理，您可在「我的工单」中查看处理进度。</span>
      </div>
      <el-form label-width="80px">
        <el-form-item label="标题">
          <el-input v-model="ticketForm.title" maxlength="50" show-word-limit />
        </el-form-item>
        <el-form-item label="问题描述">
          <el-input v-model="ticketForm.question" type="textarea" :rows="4" maxlength="500" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="ticketVisible = false">取消</el-button>
        <el-button type="primary" :loading="ticketSubmitting" @click="submitTicket">提交工单</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import {
  Plus, ChatLineRound, Delete, Promotion,
  Service, UserFilled, VideoPause,
  Clock, Coin, Lock, Monitor, List, Notebook, Tickets, ShoppingCart,
  Bell, Close, Headset, ArrowLeft, ArrowRight,
} from '@element-plus/icons-vue'
import { useChatStore } from '@/store/chat'
import { useAuthStore } from '@/store/auth'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import MarkdownIt from 'markdown-it'
import client from '@/api/client'
import { ticketApi } from '@/api/ticket'

const chatStore = useChatStore()
const authStore = useAuthStore()
const route = useRoute()
const router = useRouter()
const inputText = ref('')
const messageAreaRef = ref<HTMLElement>()

const md = new MarkdownIt({ breaks: true, linkify: true })

const announcements = ref<any[]>([])
const showAnnounceDetail = ref(false)

async function fetchAnnouncements() {
  try {
    const res = await client.get('/admin/announcements/active')
    announcements.value = res.data.data || []
  } catch { /* ignore */ }
}

/** 分类预设问题 */
const presetQuestions = [
  {
    category: '考勤与休假',
    icon: Clock,
    questions: [
      '年假可以休几天？怎么计算？',
      '病假需要什么证明材料？',
      '加班费怎么计算？',
    ],
  },
  {
    category: '薪酬与福利',
    icon: Coin,
    questions: [
      '工资每月几号发放？',
      '公司缴纳哪些社保和公积金？',
      '婚假和产假各多少天？',
    ],
  },
  {
    category: '差旅与报销',
    icon: Tickets,
    questions: [
      '出差住宿标准是多少？',
      '差旅报销需要什么票据？',
      '出差返回后多久提交报销？',
    ],
  },
  {
    category: '信息安全',
    icon: Lock,
    questions: [
      '公司信息分为哪几个密级？',
      '发现信息安全事件怎么报告？',
      '离职需要归还哪些公司设备？',
    ],
  },
  {
    category: 'IT与设备',
    icon: Monitor,
    questions: [
      'IT设备故障怎么报修？',
      '公司配发电脑多久更换一次？',
      '可以自己安装软件吗？',
    ],
  },
  {
    category: '考核与晋升',
    icon: Notebook,
    questions: [
      '绩效考核分为哪些等级？',
      '晋升需要满足什么条件？',
      '绩效申诉怎么申请？',
    ],
  },
  {
    category: '入职与离职',
    icon: List,
    questions: [
      '入职需要准备哪些材料？',
      '试用期一般是多久？',
      '主动辞职需要提前多久通知？',
    ],
  },
  {
    category: '财务与采购',
    icon: ShoppingCart,
    questions: [
      '采购审批的分级标准是什么？',
      '供应商评估有哪些维度？',
      '合同付款需要什么凭证？',
    ],
  },
]

/** 当前选中的预设问题分类标签 */
const activeCategory = ref(presetQuestions[0]?.category || '')

/** 当前选中分类的问题集合 */
const activeGroup = computed(() => presetQuestions.find(g => g.category === activeCategory.value))

/** 分类胶囊横向滚动 */
const categoryTrackRef = ref<HTMLElement>()
function scrollCategories(dir: number) {
  const el = categoryTrackRef.value
  if (!el) return
  el.scrollBy({ left: dir * 240, behavior: 'smooth' })
}

/** 反馈状态 */
const feedbackState = ref<Record<number, number>>({})

async function handleFeedback(msg: any, fb: number) {
  feedbackState.value[msg.id] = fb
  await chatStore.submitFeedback(fb)
}

/** 文档查看器 */
const docDialogVisible = ref(false)
const docViewTitle = ref('')
const docContent = ref('')

async function viewDocument(docId: number) {
  try {
    const token = localStorage.getItem('access_token')
    const res = await fetch(`/api/v1/documents/${docId}/content`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    const data = await res.json()
    if (data.code === 0) {
      docViewTitle.value = data.data.title
      docContent.value = data.data.content
      docDialogVisible.value = true
    } else {
      ElMessage.error(data.message || '获取文档内容失败')
    }
  } catch {
    ElMessage.error('获取文档内容失败，请检查网络连接')
  }
}

function renderMarkdown(text: string): string {
  return md.render(text || '')
}

/** 相对时间显示 */
function relativeTime(iso: string): string {
  if (!iso) return ''
  const d = new Date(iso.endsWith('Z') ? iso : iso + 'Z')
  if (isNaN(d.getTime())) return ''
  const now = new Date()
  const diffMs = now.getTime() - d.getTime()
  const min = Math.floor(diffMs / 60000)
  if (min < 1) return '刚刚'
  if (min < 60) return `${min} 分钟前`
  const hr = Math.floor(min / 60)
  if (hr < 24) return `${hr} 小时前`
  const day = Math.floor(hr / 24)
  if (day < 30) return `${day} 天前`
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

/** 滚动到底部 */
function scrollToBottom() {
  nextTick(() => {
    if (messageAreaRef.value) {
      messageAreaRef.value.scrollTop = messageAreaRef.value.scrollHeight
    }
  })
}

/** 发送消息 */
async function handleSend() {
  const text = inputText.value.trim()
  if (!text || chatStore.streaming) return
  inputText.value = ''
  await chatStore.sendMessage(text)
  scrollToBottom()
}

/** 快速提问 */
function quickAsk(question: string) {
  inputText.value = question
  handleSend()
}

/** 新对话 */
function handleNewChat() {
  chatStore.activeSessionId = null
  chatStore.messages = []
}

/** 转人工工单 */
const ticketVisible = ref(false)
const ticketSubmitting = ref(false)
const ticketForm = ref({ title: '', question: '', priority: 'medium' })

function openTicket(question: string) {
  const q = (question || '').trim()
  ticketForm.value = {
    title: q.length > 30 ? q.slice(0, 30) : q,
    question: q,
    priority: 'medium',
  }
  ticketVisible.value = true
}

/** 问答页流程跳转：请假 → 请假页；报销 → 报销页；工单 → 直接打开工单弹窗 */
function goAction(type: string) {
  if (type === 'leave') {
    router.push('/leaves')
  } else if (type === 'expense') {
    router.push('/expenses')
  } else if (type === 'ticket') {
    openTicket('')
  }
}

async function submitTicket() {
  const f = ticketForm.value
  if (!f.title.trim() || !f.question.trim()) {
    ElMessage.warning('请填写标题和问题描述')
    return
  }
  ticketSubmitting.value = true
  try {
    await ticketApi.create({
      title: f.title,
      question: f.question,
      priority: f.priority,
      session_id: chatStore.activeSessionId || undefined,
    })
    ElMessage.success('工单已提交，可在「我的工单」查看处理进度')
    ticketVisible.value = false
  } catch (e: any) {
    ElMessage.error(e.response?.data?.message || '提交失败')
  } finally {
    ticketSubmitting.value = false
  }
}

/** 清空所有对话（仅前端，后端数据保留） */
function handleClearAll() {
  chatStore.clearAllFrontend()
  ElMessage.success('全部对话已清空')
}

// 监听消息变化自动滚动
watch(() => chatStore.messages.length, scrollToBottom)
watch(() => chatStore.streamContent, scrollToBottom)

// 页面加载时获取会话列表
chatStore.loadSessions()

// URL 指定 sessionId 时加载对应会话
const sessionId = route.params.sessionId as string | undefined
if (sessionId) {
  chatStore.selectSession(sessionId)
}

onMounted(() => {
  fetchAnnouncements()
})
</script>

<style scoped>
.chat-page { display: flex; height: 100%; background: var(--color-bg-page); }

/* 侧边栏 */
.chat-sidebar {
  width: 280px; background: var(--color-bg-card);
  border-right: 1px solid var(--color-border);
  display: flex; flex-direction: column;
}
.sidebar-header {
  padding: 16px; border-bottom: 1px solid var(--color-border);
  display: flex; gap: 8px; align-items: center;
}
.new-chat-btn {
  flex: 1; background: var(--color-primary); border-color: var(--color-primary);
}
.clear-all-btn {
  flex-shrink: 0; font-size: 18px; color: var(--color-text-placeholder);
}
.clear-all-btn:hover { color: var(--color-danger); }
.session-list { flex: 1; overflow-y: auto; padding: 8px; }

.session-item {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 12px; border-radius: 8px; cursor: pointer;
  transition: background 0.2s; color: var(--color-text-body);
}
.session-item:hover { background: var(--color-bg-hover); }
.session-item.active { background: var(--color-primary-light); color: var(--color-primary); }

.session-icon { flex-shrink: 0; color: var(--color-text-placeholder); }
.session-item.active .session-icon { color: var(--color-primary); }
.session-body { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.session-title {
  overflow: hidden; text-overflow: ellipsis;
  white-space: nowrap; font-size: 14px; line-height: 1.3;
}
.session-time { font-size: 11px; color: var(--color-text-placeholder); margin-top: 2px; }
.session-item.active .session-time { color: var(--color-primary); opacity: .7; }
.delete-btn { opacity: 0; transition: opacity 0.2s; }
.session-item:hover .delete-btn { opacity: 1; }

/* 聊天主区域 */
.chat-main {
  flex: 1; display: flex; flex-direction: column;
  max-width: calc(100% - 280px);
}
.message-area { flex: 1; overflow-y: auto; padding: 24px 32px; }

.welcome {
  display: flex; align-items: center; justify-content: center;
  height: 100%; overflow-y: auto;
}
.welcome-inner {
  max-width: 800px; width: 100%;
  padding: 24px 0;
}
/* 欢迎页 Hero */
.welcome-hero { display: flex; flex-direction: column; align-items: center; margin-bottom: 28px; }
.welcome-bot {
  position: relative;
  width: 64px; height: 64px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  color: #fff;
  background: linear-gradient(135deg, #0D9488, #06B6D4);
  margin-bottom: 16px;
  animation: bot-breathe 3s ease-in-out infinite;
}
.welcome-bot::after {
  content: '';
  position: absolute;
  inset: -10px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(13,148,136,.3), transparent 65%);
  z-index: -1;
  animation: bot-glow 3s ease-in-out infinite;
}
.welcome h2 {
  font-size: 26px; font-weight: 700;
  color: var(--color-text-primary); margin: 0 0 6px;
  text-align: center; letter-spacing: .5px;
}
.welcome p {
  font-size: 14px; color: var(--color-text-secondary);
  margin: 0; text-align: center; max-width: 480px;
}

/* 预设问题 - 玻璃质感布局 */
.preset-section {
  position: relative;
  padding: 16px 18px;
  border-radius: 20px;
  background: linear-gradient(135deg, rgba(13,148,136,.06), rgba(6,182,212,.03));
  border: 1px solid rgba(13,148,136,.14);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  box-shadow: 0 10px 32px rgba(13,148,136,.08);
}
html.dark .preset-section {
  background: linear-gradient(135deg, rgba(13,148,136,.12), rgba(6,182,212,.06));
  border-color: rgba(13,148,136,.22);
}

/* 分类胶囊栏 */
.category-bar {
  display: flex;
  align-items: center;
  gap: 8px;
}
.category-track {
  flex: 1;
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding: 2px;
  scrollbar-width: none;
}
.category-track::-webkit-scrollbar { display: none; }
.category-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 999px;
  border: 1px solid transparent;
  background: var(--color-bg-hover);
  color: var(--color-text-secondary);
  font-size: 13px;
  cursor: pointer;
  white-space: nowrap;
  flex-shrink: 0;
  transition: all .25s ease;
}
.category-pill:hover {
  color: var(--color-primary);
  background: var(--color-primary-light);
  transform: translateY(-1px);
}
.category-pill.active {
  background: linear-gradient(135deg, #0D9488, #06B6D4);
  color: #fff;
  box-shadow: 0 4px 14px rgba(13,148,136,.35);
}
.category-arrow {
  width: 32px; height: 32px;
  border-radius: 50%;
  border: 1px solid var(--color-border);
  background: var(--color-bg-card);
  color: var(--color-text-secondary);
  display: flex; align-items: center; justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
  transition: all .2s;
}
.category-arrow:hover {
  color: var(--color-primary);
  border-color: var(--color-primary);
  background: var(--color-primary-light);
}

/* 问题面板 */
.preset-panel {
  margin-top: 14px;
}
.preset-panel-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--color-text-secondary);
  margin-bottom: 12px;
}
.preset-panel-hint .el-icon {
  color: var(--color-primary);
  flex-shrink: 0;
}
.preset-panel-list {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.preset-question-chip {
  font-size: 13px;
  color: var(--color-text-body);
  padding: 8px 16px;
  border-radius: 12px;
  border: 1px solid var(--color-border);
  background: linear-gradient(135deg, var(--color-bg-hover), var(--color-bg-card));
  cursor: pointer;
  transition: all .25s ease;
  white-space: nowrap;
}
.preset-question-chip:hover {
  color: var(--color-primary);
  border-color: var(--color-primary);
  background: linear-gradient(135deg, var(--color-primary-light), var(--color-bg-card));
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(13,148,136,.18);
}

/* 面板切换过渡 */
.panel-enter-active,
.panel-leave-active {
  transition: opacity .3s ease, transform .3s ease;
}
.panel-enter-from {
  opacity: 0;
  transform: translateY(8px);
}
.panel-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

/* 欢迎图标呼吸与光晕 */
@keyframes bot-breathe {
  0%, 100% { transform: translateY(0); box-shadow: 0 6px 20px rgba(13,148,136,.35); }
  50% { transform: translateY(-4px); box-shadow: 0 10px 30px rgba(13,148,136,.55); }
}
@keyframes bot-glow {
  0%, 100% { opacity: .5; transform: scale(1); }
  50% { opacity: 1; transform: scale(1.15); }
}

@media (max-width: 640px) {
  .preset-section { padding: 12px; }
  .category-pill { padding: 7px 12px; font-size: 12px; }
  .preset-question-chip { padding: 7px 12px; font-size: 12px; }
}

/* 消息 */
.message-row { display: flex; gap: 12px; margin-bottom: 24px; max-width: 85%; }
.message-row.user { margin-left: auto; flex-direction: row-reverse; }

.message-avatar {
  width: 36px; height: 36px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
  background: var(--color-bg-button);
  color: var(--color-text-secondary);
  overflow: hidden;
}
.avatar-img {
  width: 100%; height: 100%; object-fit: cover;
}

.message-bubble {
  padding: 12px 16px; border-radius: 16px;
  line-height: 1.7; font-size: 14px;
}
.message-row.user .message-bubble {
  background: linear-gradient(135deg, var(--color-primary), var(--color-primary-hover));
  color: #fff; border-bottom-right-radius: 4px;
}
.message-row.assistant .message-bubble {
  background: var(--color-bg-card); border: 1px solid var(--color-border);
  border-bottom-left-radius: 4px; color: var(--color-text-body);
}
.message-bubble.streaming { border-color: var(--color-primary); }

.cursor-blink { animation: blink 1s infinite; }
@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}
.sensitive-notice {
  margin-top: 8px;
  padding: 6px 10px;
  font-size: 12px;
  color: #d48806;
  background: #fffbe6;
  border: 1px dashed #d4b106;
  border-radius: 6px;
}

.message-sources { margin-top: 12px; font-size: 13px; }

/* 流程跳转建议按钮 */
.action-row {
  margin-top: 10px;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.action-hint { font-size: 13px; color: var(--color-text-secondary); }

.feedback-row { display: flex; gap: 8px; margin-top: 10px; }
.escalate-btn {
  align-self: flex-end;
  display: inline-flex; align-items: center; gap: 4px;
  font-size: 12px; color: var(--color-text-secondary);
  cursor: pointer; padding: 2px 6px; border-radius: 6px;
  white-space: nowrap; transition: all 0.15s;
  margin-top: 6px;
}
.escalate-btn:hover { color: #e6a23c; background: var(--color-bg-hover); }
.ticket-dialog-hint {
  display: flex; align-items: center; gap: 8px;
  font-size: 13px; color: var(--color-text-secondary);
  background: var(--color-bg-hover); border-radius: 8px;
  padding: 10px 12px; margin-bottom: 14px;
}
.feedback-btn {
  font-size: 16px; cursor: pointer; opacity: 0.4;
  padding: 2px 6px; border-radius: 6px; transition: all 0.15s;
}
.feedback-btn:hover { opacity: 0.8; background: var(--color-bg-hover); }
.feedback-btn.active { opacity: 1; }
.feedback-btn.active:hover { opacity: 1; }
.source-item {
  padding: 8px 0; border-bottom: 1px solid var(--color-border);
}
.source-item:last-child { border-bottom: none; }
.source-chapter { margin-left: 8px; color: var(--color-text-secondary); }
.source-page { margin-left: 8px; color: var(--color-text-placeholder); font-size: 12px; }
.source-snippet { margin: 4px 0 0; color: var(--color-text-body); font-size: 13px; }

/* 输入区域 */
.input-area {
  padding: 16px 24px; border-top: 1px solid var(--color-border);
  background: var(--color-bg-card);
}
.input-area :deep(.el-textarea__inner) {
  border-radius: 12px; background: var(--color-bg-page);
  border-color: var(--color-border) !important;
  color: var(--color-text-body) !important;
}
.input-area :deep(.el-textarea__inner:focus) {
  border-color: var(--color-primary) !important;
  box-shadow: 0 0 0 2px var(--color-primary-light) !important;
}

.input-actions {
  display: flex; justify-content: space-between;
  align-items: center; margin-top: 8px;
}
.input-hint {
  font-size: 12px; color: var(--color-text-placeholder);
  display: flex; align-items: center; gap: 4px;
}
.input-btns { display: flex; align-items: center; gap: 12px; }
.char-count { font-size: 12px; color: var(--color-text-placeholder); }

@media (max-width: 768px) {
  .chat-sidebar { display: none; }
  .chat-main { max-width: 100%; }
  .message-row { max-width: 95%; }
}

/* 文档查看弹窗 */
.doc-content {
  max-height: 70vh; overflow-y: auto;
  font-size: 14px; line-height: 1.8;
  color: var(--color-text-body);
  padding: 4px 0;
}
.doc-content :deep(h1) { font-size: 24px; border-bottom: 2px solid var(--color-border); padding-bottom: 8px; }
.doc-content :deep(h2) { font-size: 20px; margin-top: 24px; }
.doc-content :deep(h3) { font-size: 17px; margin-top: 20px; }
.doc-content :deep(table) { width: 100%; border-collapse: collapse; margin: 12px 0; }
.doc-content :deep(th), .doc-content :deep(td) {
  border: 1px solid var(--color-border); padding: 6px 10px; text-align: left;
}
.doc-content :deep(th) { background: var(--color-bg-hover); font-weight: 600; }

/* 公告栏 */
.announce-bar {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 20px; margin: 0 16px 8px;
  background: linear-gradient(135deg, #FFF7E6 0%, #FFF1CC 100%);
  border: 1px solid #FADB7F; border-radius: 8px;
  font-size: 14px; color: #8B6914;
}
.dark .announce-bar { background: linear-gradient(135deg, #3D2E0A 0%, #2E2206 100%); border-color: #6B5210; color: #E6C34A; }
.announce-title { flex: 1; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.announce-close { cursor: pointer; opacity: 0.6; }
.announce-close:hover { opacity: 1; }

.announce-detail-item { margin-bottom: 20px; padding-bottom: 16px; border-bottom: 1px solid var(--color-border); }
.announce-detail-item:last-child { border-bottom: none; margin-bottom: 0; }
.announce-detail-item h4 { margin: 0 0 8px; font-size: 16px; color: var(--color-text-primary); }
.announce-content { line-height: 1.8; color: var(--color-text-body); }
.announce-time { font-size: 12px; color: var(--color-text-placeholder); margin-top: 8px; }
</style>
