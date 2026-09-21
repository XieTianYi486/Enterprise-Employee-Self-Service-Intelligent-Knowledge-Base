<template>
  <div class="nt-page">
    <div class="page-header">
      <div class="header-left">
        <el-icon class="header-icon" :size="24"><Bell /></el-icon>
        <h2>消息中心</h2>
        <el-tag v-if="unread > 0" size="small" round type="warning">{{ unread }} 条未读</el-tag>
      </div>
      <div class="header-actions">
        <el-checkbox v-model="unreadOnly" @change="loadList(1)">仅看未读</el-checkbox>
        <el-button text type="primary" :disabled="unread === 0" @click="handleReadAll">全部已读</el-button>
      </div>
    </div>

    <el-card shadow="never" v-loading="loading">
      <div v-if="items.length" class="nt-list">
        <div
          v-for="n in items"
          :key="n.id"
          class="nt-item"
          :class="{ unread: !n.is_read }"
          @click="openItem(n)"
        >
          <div class="nt-dot" v-if="!n.is_read"></div>
          <div class="nt-body">
            <div class="nt-title">
              <el-tag size="small" effect="plain" :type="typeTag(n.type)">{{ typeLabel(n.type) }}</el-tag>
              <span class="nt-title-text">{{ n.title }}</span>
            </div>
            <div class="nt-content" v-if="n.content">{{ n.content }}</div>
            <div class="nt-time">{{ formatTime(n.create_time) }}</div>
          </div>
        </div>
      </div>
      <el-empty v-else description="暂无消息" />

      <el-pagination
        v-if="total > pageSize"
        class="nt-pager"
        background
        layout="total, prev, pager, next"
        :total="total"
        :page-size="pageSize"
        :current-page="page"
        @current-change="loadList"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Bell } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import client from '@/api/client'
import router from '@/router'

const loading = ref(false)
const items = ref<any[]>([])
const total = ref(0)
const unread = ref(0)
const page = ref(1)
const pageSize = ref(10)
const unreadOnly = ref(false)

function typeLabel(t: string) {
  return ({ APPROVAL: '审批通知', TICKET: '工单通知', ANNOUNCEMENT: '公告', SYSTEM: '系统通知' } as any)[t] || t
}
function typeTag(t: string) {
  return ({ APPROVAL: 'primary', TICKET: 'success', ANNOUNCEMENT: 'warning', SYSTEM: 'info' } as any)[t] || 'info'
}
function formatTime(t: string) {
  if (!t) return '-'
  const d = new Date(t.endsWith('Z') ? t : t + 'Z')
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

async function loadList(p?: number) {
  if (typeof p === 'number') page.value = p
  loading.value = true
  try {
    const res = await client.get('/notifications', {
      params: { page: page.value, page_size: pageSize.value, unread_only: unreadOnly.value },
    })
    items.value = res.data.data?.items || []
    total.value = res.data.data?.total || 0
    unread.value = res.data.data?.unread || 0
  } finally {
    loading.value = false
  }
}

async function openItem(n: any) {
  if (!n.is_read) {
    try {
      await client.post(`/notifications/${n.id}/read`)
      n.is_read = true
      unread.value = Math.max(0, unread.value - 1)
    } catch { /* ignore */ }
  }
  // 按业务类型跳转
  if (n.biz_type === 'LEAVE' || n.biz_type === 'EXPENSE') {
    router.push(n.biz_type === 'LEAVE' ? '/leaves' : '/expenses')
  } else if (n.biz_type === 'TICKET') {
    router.push('/tickets')
  }
}

async function handleReadAll() {
  try {
    await client.post('/notifications/read-all')
    ElMessage.success('已全部标记为已读')
    loadList(1)
  } catch { /* ignore */ }
}

onMounted(() => loadList())
</script>

<style scoped>
.nt-page { padding: 24px 32px; max-width: 900px; margin: 0 auto; }
.page-header { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 20px; }
.header-left { display: flex; align-items: center; gap: 10px; }
.header-icon { color: var(--color-primary); }
.page-header h2 { font-size: 20px; font-weight: 700; color: var(--color-text-primary); margin: 0; }
.header-actions { display: flex; align-items: center; gap: 14px; }

.nt-list { display: flex; flex-direction: column; }
.nt-item {
  display: flex; gap: 10px; align-items: flex-start;
  padding: 14px 12px; border-radius: 10px; cursor: pointer;
  border-bottom: 1px solid var(--color-border);
  transition: background 0.15s;
}
.nt-item:hover { background: rgba(13, 148, 136, 0.04); }
.nt-item.unread { background: rgba(13, 148, 136, 0.06); }
.nt-dot { width: 8px; height: 8px; border-radius: 50%; background: #f59e0b; margin-top: 6px; flex-shrink: 0; }
.nt-body { flex: 1; min-width: 0; }
.nt-title { display: flex; align-items: center; gap: 8px; }
.nt-title-text { font-size: 14px; font-weight: 600; color: var(--color-text-primary); }
.nt-content { font-size: 13px; color: var(--color-text-body); margin-top: 4px; }
.nt-time { font-size: 12px; color: var(--color-text-placeholder); margin-top: 4px; }

.nt-pager { margin-top: 16px; justify-content: flex-end; }
</style>
