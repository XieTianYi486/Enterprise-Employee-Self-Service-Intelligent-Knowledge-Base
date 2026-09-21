<template>
  <div class="ticket-admin">
    <div class="page-header">
      <div class="header-left">
        <el-icon class="header-icon" :size="22"><List /></el-icon>
        <h2>工单管理</h2>
        <el-tag v-if="total" effect="plain">{{ total }} 条</el-tag>
      </div>
      <el-input
        v-model="keyword"
        placeholder="搜索标题或问题"
        clearable
        style="width: 240px"
        :prefix-icon="Search"
        @change="() => { page = 1; loadTickets() }"
      />
    </div>

    <!-- 状态标签页（带角标数量） -->
    <el-tabs v-model="activeStatus" @tab-change="() => { page = 1; loadTickets() }">
      <el-tab-pane name="">
        <template #label>全部 <el-badge v-if="stats.total" :value="stats.total" :max="999" /></template>
      </el-tab-pane>
      <el-tab-pane name="pending">
        <template #label>待处理 <el-badge v-if="stats.pending" :value="stats.pending" :max="999" type="warning" /></template>
      </el-tab-pane>
      <el-tab-pane name="processing">
        <template #label>处理中 <el-badge v-if="stats.processing" :value="stats.processing" :max="999" type="info" /></template>
      </el-tab-pane>
      <el-tab-pane name="resolved">
        <template #label>已解决 <el-badge v-if="stats.resolved" :value="stats.resolved" :max="999" type="success" /></template>
      </el-tab-pane>
      <el-tab-pane name="closed">
        <template #label>已关闭 <el-badge v-if="stats.closed" :value="stats.closed" :max="999" type="danger" /></template>
      </el-tab-pane>
    </el-tabs>

    <el-card shadow="never" class="table-card">
      <el-table :data="tickets" v-loading="loading">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="title" label="标题" min-width="180" show-overflow-tooltip />
        <el-table-column prop="creator_name" label="提交人" width="100">
          <template #default="{ row }">{{ row.creator_name || row.created_by }}</template>
        </el-table-column>
        <el-table-column label="优先级" width="90">
          <template #default="{ row }">
            <el-tag size="small" :type="priorityMeta(row.priority).type">{{ priorityMeta(row.priority).label }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag size="small" :type="statusMeta(row.status).type">{{ statusMeta(row.status).label }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="时间" width="150">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="170" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" link :icon="Edit" @click="openHandle(row)">处理</el-button>
            <el-button size="small" type="warning" link :icon="View" @click="openView(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination">
        <el-pagination
          v-model:current-page="page"
          :page-size="pageSize"
          :total="total"
          layout="total, prev, pager, next"
          @current-change="loadTickets"
        />
      </div>
    </el-card>

    <!-- 处理工单弹窗 -->
    <el-dialog v-model="handleVisible" :title="'处理工单 #' + (current?.id ?? '')" width="560px">
      <div v-if="current" class="handle-body">
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="标题">{{ current.title }}</el-descriptions-item>
          <el-descriptions-item label="提交人">{{ current.creator_name || current.created_by }}（{{ formatTime(current.created_at) }}）</el-descriptions-item>
          <el-descriptions-item label="问题">{{ current.question }}</el-descriptions-item>
        </el-descriptions>
        <el-form :model="handleForm" label-width="70px" class="handle-form">
          <el-form-item label="回复">
            <el-input v-model="handleForm.reply" type="textarea" :rows="5" maxlength="2000" show-word-limit placeholder="填写处理结果，提交后工单将标记为「已解决」" />
          </el-form-item>
        </el-form>
      </div>
      <template #footer>
        <el-button @click="closeTicket">关闭工单</el-button>
        <el-button type="primary" :loading="submitting" @click="submitHandle">提交并解决</el-button>
      </template>
    </el-dialog>

    <!-- 详情弹窗（只看不回） -->
    <el-dialog v-model="viewVisible" :title="'工单 #' + (current?.id ?? '')" width="560px">
      <div v-if="current" class="handle-body">
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="标题">{{ current.title }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag size="small" :type="statusMeta(current.status).type">{{ statusMeta(current.status).label }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="提交人">{{ current.creator_name || current.created_by }}</el-descriptions-item>
          <el-descriptions-item label="处理人">{{ current.handler_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="问题">{{ current.question }}</el-descriptions-item>
        </el-descriptions>
        <div v-if="current.reply" class="reply-box">
          <div class="reply-label">处理人回复</div>
          <p class="reply-content">{{ current.reply }}</p>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { List, Search, Edit, View } from '@element-plus/icons-vue'
import {
  ticketApi, TICKET_STATUS_LABELS, TICKET_PRIORITY_LABELS, type Ticket,
} from '@/api/ticket'

const tickets = ref<Ticket[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 10
const keyword = ref('')
const activeStatus = ref('')
const loading = ref(false)
const stats = ref<any>({})

const handleVisible = ref(false)
const viewVisible = ref(false)
const current = ref<Ticket | null>(null)
const submitting = ref(false)
const handleForm = reactive({ reply: '' })

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

async function loadStats() {
  try {
    const res = await ticketApi.getStats()
    stats.value = res.data.data || {}
  } catch { /* ignore */ }
}

async function loadTickets() {
  loading.value = true
  try {
    const res = await ticketApi.listAll({
      page: page.value,
      page_size: pageSize,
      status: activeStatus.value || undefined,
      keyword: keyword.value || undefined,
    })
    const data = res.data.data
    tickets.value = data.items || []
    total.value = data.total || 0
  } finally {
    loading.value = false
  }
}

function openHandle(t: Ticket) {
  current.value = t
  handleForm.reply = t.reply || ''
  handleVisible.value = true
}

function openView(t: Ticket) {
  current.value = t
  viewVisible.value = true
}

async function submitHandle() {
  if (!handleForm.reply.trim()) {
    ElMessage.warning('请填写处理回复')
    return
  }
  if (!current.value) return
  submitting.value = true
  try {
    await ticketApi.handle(current.value.id, handleForm.reply)
    ElMessage.success('工单已处理')
    handleVisible.value = false
    loadTickets()
    loadStats()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.message || '处理失败')
  } finally {
    submitting.value = false
  }
}

async function closeTicket() {
  if (!current.value) return
  try {
    await ticketApi.updateStatus(current.value.id, 'closed')
    ElMessage.success('工单已关闭')
    handleVisible.value = false
    loadTickets()
    loadStats()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.message || '关闭失败')
  }
}

onMounted(() => {
  loadTickets()
  loadStats()
})
</script>

<style scoped>
.ticket-admin { padding: 24px 32px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.header-left { display: flex; align-items: center; gap: 10px; }
.header-icon { color: var(--color-primary); }
.page-header h2 { font-size: 20px; font-weight: 700; color: var(--color-text-primary); margin: 0; }

.table-card { border-radius: 12px; }
.pagination { margin-top: 16px; display: flex; justify-content: center; }

.handle-body { display: flex; flex-direction: column; gap: 14px; }
.handle-form { margin-top: 8px; }
.reply-box { background: var(--color-bg-hover); border-radius: 8px; padding: 12px; }
.reply-label { font-size: 12px; color: var(--color-text-secondary); margin-bottom: 6px; }
.reply-content { margin: 0; font-size: 14px; color: var(--color-text-primary); white-space: pre-wrap; }
</style>