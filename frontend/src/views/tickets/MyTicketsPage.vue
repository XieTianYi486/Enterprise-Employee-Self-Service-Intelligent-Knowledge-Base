<template>
  <div class="ticket-page">
    <div class="page-header">
      <div class="header-left">
        <el-icon class="header-icon" :size="22"><Tickets /></el-icon>
        <h2>我的工单</h2>
        <el-tag v-if="activeStatus" effect="plain">{{ total }} 条</el-tag>
      </div>
      <el-button type="primary" :icon="Plus" @click="openCreate">提交工单</el-button>
    </div>

    <!-- 状态筛选 -->
    <el-tabs v-model="activeStatus" @tab-change="loadTickets">
      <el-tab-pane label="全部" name="" />
      <el-tab-pane label="待处理" name="pending" />
      <el-tab-pane label="处理中" name="processing" />
      <el-tab-pane label="已解决" name="resolved" />
      <el-tab-pane label="已关闭" name="closed" />
    </el-tabs>

    <!-- 工单列表 -->
    <el-empty v-if="tickets.length === 0" description="暂无工单" />
    <div v-else class="ticket-list">
      <el-card v-for="t in tickets" :key="t.id" class="ticket-item" shadow="never" @click="openDetail(t)">
        <div class="ticket-main">
          <div class="ticket-title-row">
            <span class="ticket-no">#{{ t.id }}</span>
            <span class="ticket-title">{{ t.title }}</span>
            <el-tag size="small" :type="priorityMeta(t.priority).type" effect="light">{{ priorityMeta(t.priority).label }}优先级</el-tag>
          </div>
          <div class="ticket-question">{{ t.question }}</div>
          <div class="ticket-footer">
            <el-tag size="small" :type="statusMeta(t.status).type">{{ statusMeta(t.status).label }}</el-tag>
            <span class="ticket-time">{{ formatTime(t.created_at) }} 提交</span>
          </div>
        </div>
        <el-icon class="arrow"><ArrowRight /></el-icon>
      </el-card>
    </div>

    <!-- 分页 -->
    <div v-if="total > 0" class="pagination">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="loadTickets"
      />
    </div>

    <!-- 提交工单弹窗 -->
    <el-dialog v-model="createVisible" title="提交工单" width="520px">
      <el-form :model="createForm" :rules="createRules" ref="createFormRef" label-width="80px">
        <el-form-item label="标题" prop="title">
          <el-input v-model="createForm.title" maxlength="50" show-word-limit placeholder="一句话概括您的问题" />
        </el-form-item>
        <el-form-item label="问题描述" prop="question">
          <el-input v-model="createForm.question" type="textarea" :rows="4" maxlength="500" show-word-limit placeholder="详细描述您遇到的问题" />
        </el-form-item>
        <el-form-item label="优先级">
          <el-radio-group v-model="createForm.priority">
            <el-radio value="high">高</el-radio>
            <el-radio value="medium">中</el-radio>
            <el-radio value="low">低</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitCreate">提交</el-button>
      </template>
    </el-dialog>

    <!-- 工单详情弹窗 -->
    <el-dialog v-model="detailVisible" :title="'工单 #' + (current?.id ?? '')" width="600px">
      <div v-if="current" class="detail-body">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="状态">
            <el-tag size="small" :type="statusMeta(current.status).type">{{ statusMeta(current.status).label }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="优先级">
            <el-tag size="small" :type="priorityMeta(current.priority).type">{{ priorityMeta(current.priority).label }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="提交时间" :span="2">{{ formatTime(current.created_at) }}</el-descriptions-item>
        </el-descriptions>

        <div class="detail-block">
          <div class="detail-label">问题描述</div>
          <p class="detail-content">{{ current.question }}</p>
        </div>

        <div v-if="current.reply" class="detail-block" style="background: var(--color-bg-hover); border-radius: 8px; padding: 12px;">
          <div class="detail-label">· 人工回复（{{ current.handler_name || '管理员' }}）</div>
          <p class="detail-content">{{ current.reply }}</p>
        </div>
        <el-empty v-else description="暂无人工回复" :image-size="40" />
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { Tickets, Plus, ArrowRight } from '@element-plus/icons-vue'
import {
  ticketApi, TICKET_STATUS_LABELS, TICKET_PRIORITY_LABELS, type Ticket,
} from '@/api/ticket'

const tickets = ref<Ticket[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 10
const activeStatus = ref('')

const createVisible = ref(false)
const submitting = ref(false)
const createFormRef = ref<FormInstance>()
const createForm = reactive({ title: '', question: '', priority: 'medium' })
const createRules: FormRules = {
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
  question: [{ required: true, message: '请输入问题描述', trigger: 'blur' }],
}

const detailVisible = ref(false)
const current = ref<Ticket | null>(null)

function statusMeta(s: string) {
  return TICKET_STATUS_LABELS[s] || { label: s, type: 'info' as const }
}
function priorityMeta(p: string) {
  return TICKET_PRIORITY_LABELS[p] || { label: p, type: 'warning' as const }
}

function formatTime(t: string) {
  if (!t) return '-'
  const d = new Date(t.endsWith('Z') ? t : t + 'Z')
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

async function loadTickets() {
  try {
    const res = await ticketApi.myTickets({
      page: page.value,
      page_size: pageSize,
      status: activeStatus.value || undefined,
    })
    const data = res.data.data
    tickets.value = data.items || []
    total.value = data.total || 0
  } catch { /* ignore */ }
}

function openCreate() {
  createForm.title = ''
  createForm.question = ''
  createForm.priority = 'medium'
  createVisible.value = true
}

async function submitCreate() {
  const valid = await createFormRef.value?.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    await ticketApi.create({
      title: createForm.title,
      question: createForm.question,
      priority: createForm.priority,
    })
    ElMessage.success('工单已提交，等待人工处理')
    createVisible.value = false
    page.value = 1
    loadTickets()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.message || '提交失败')
  } finally {
    submitting.value = false
  }
}

async function openDetail(t: Ticket) {
  current.value = t
  detailVisible.value = true
}

onMounted(loadTickets)
</script>

<style scoped>
.ticket-page { padding: 24px 32px; max-width: 1100px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.header-left { display: flex; align-items: center; gap: 10px; }
.header-icon { color: var(--color-primary); }
.page-header h2 { font-size: 20px; font-weight: 700; color: var(--color-text-primary); margin: 0; }

.ticket-list { display: flex; flex-direction: column; gap: 12px; }
.ticket-item { border-radius: 12px; cursor: pointer; transition: box-shadow 0.2s, transform 0.2s; }
.ticket-item:hover { box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08); transform: translateY(-1px); }
.ticket-item :deep(.el-card__body) { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.ticket-main { flex: 1; min-width: 0; }
.ticket-title-row { display: flex; align-items: center; gap: 10px; }
.ticket-no { font-size: 12px; color: var(--color-text-placeholder); font-weight: 700; }
.ticket-title { font-size: 15px; font-weight: 600; color: var(--color-text-primary); flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ticket-question { margin: 6px 0; font-size: 13px; color: var(--color-text-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ticket-footer { display: flex; align-items: center; gap: 12px; }
.ticket-time { font-size: 12px; color: var(--color-text-placeholder); }
.arrow { color: var(--color-text-placeholder); }

.pagination { margin-top: 20px; display: flex; justify-content: center; }

.detail-body { display: flex; flex-direction: column; gap: 16px; }
.detail-block .detail-label { font-size: 13px; font-weight: 600; color: var(--color-text-secondary); margin-bottom: 6px; }
.detail-content { margin: 0; font-size: 14px; color: var(--color-text-primary); line-height: 1.6; white-space: pre-wrap; }
</style>