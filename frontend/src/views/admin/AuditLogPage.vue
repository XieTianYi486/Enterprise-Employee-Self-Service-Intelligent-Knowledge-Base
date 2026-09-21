<template>
  <div class="page">
    <div class="page-header">
      <div class="header-left">
        <el-icon class="header-icon" :size="22"><Document /></el-icon>
        <h2>审计日志</h2>
        <el-tag effect="plain">{{ total }} 条</el-tag>
      </div>
      <div class="header-right">
        <el-select v-model="moduleFilter" placeholder="模块" clearable style="width: 130px" @change="() => { page = 1; load() }">
          <el-option v-for="m in modules" :key="m.value" :label="m.label" :value="m.value" />
        </el-select>
        <el-input v-model="keyword" placeholder="按用户名/详情搜索" clearable style="width: 220px" :prefix-icon="Search" @change="() => { page = 1; load() }" />
      </div>
    </div>

    <el-card class="table-card" shadow="never">
      <el-table v-loading="loading" :data="list" style="width: 100%">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="created_at" label="时间" width="170">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column prop="module" label="模块" width="110">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ moduleText(row.module) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="action" label="操作" min-width="150">
          <template #default="{ row }">
            {{ actionText(row.action) }}
          </template>
        </el-table-column>
        <el-table-column prop="username" label="用户" width="120">
          <template #default="{ row }">{{ row.username || '—' }}</template>
        </el-table-column>
        <el-table-column prop="status" label="结果" width="90">
          <template #default="{ row }">
            <el-tag size="small" :type="statusType(row.status)">{{ statusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="target_type" label="目标" width="120">
          <template #default="{ row }">
            <span v-if="row.target_type">{{ row.target_type }} #{{ row.target_id }}</span>
            <span v-else>—</span>
          </template>
        </el-table-column>
        <el-table-column prop="ip" label="IP" width="130">
          <template #default="{ row }">{{ row.ip || '—' }}</template>
        </el-table-column>
        <el-table-column label="详情" min-width="200">
          <template #default="{ row }">
            <span class="detail-text" v-if="row.detail">{{ JSON.stringify(row.detail) }}</span>
            <span v-else>—</span>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination">
        <el-pagination
          v-model:current-page="page"
          :page-size="pageSize"
          :total="total"
          layout="total, prev, pager, next"
          @current-change="load"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Search, Document } from '@element-plus/icons-vue'
import { auditApi } from '@/api/security'

const modules = [
  { value: 'login', label: '登录' },
  { value: 'sensitive', label: '敏感词' },
  { value: 'document', label: '文档' },
  { value: 'admin', label: '管理' },
  { value: 'chat', label: '问答' },
]

const loading = ref(false)
const list = ref<any[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const moduleFilter = ref('')
const keyword = ref('')

function formatTime(t: string) {
  if (!t) return '—'
  const d = new Date(t.endsWith('Z') ? t : t + 'Z')
  return d.toLocaleString('zh-CN', { hour12: false })
}
function moduleText(m: string) {
  const item = modules.find((i) => i.value === m)
  return item ? item.label : m
}
function actionText(a: string) {
  const map: Record<string, string> = {
    login_success: '登录成功', login_failed: '登录失败', login_locked: '账号锁定',
    login_blocked: '登录拦截', sensitive_hit: '敏感词命中', review_approve: '审核通过',
    review_reject: '审核驳回', document_delete: '删除文档', export: '导出数据',
  }
  return map[a] || a
}
function statusType(s: string) {
  return { success: 'success', failure: 'danger', blocked: 'warning', masked: 'warning' }[s] as any
}
function statusText(s: string) {
  return { success: '成功', failure: '失败', blocked: '拦截', masked: '脱敏' }[s] || s
}

async function load() {
  loading.value = true
  try {
    const res = await auditApi.list({
      page: page.value, page_size: pageSize,
      module: moduleFilter.value || undefined,
      keyword: keyword.value || undefined,
    })
    const data = res.data.data
    list.value = data.items || []
    total.value = data.total || 0
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.page {
  padding: 20px;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  flex-wrap: wrap;
  gap: 12px;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}
.header-left h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}
.header-icon {
  color: var(--el-color-primary);
}
.header-right {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
.table-card {
  border-radius: 10px;
}
.pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
.detail-text {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  word-break: break-all;
  font-family: monospace;
}
</style>