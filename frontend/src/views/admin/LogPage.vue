<template>
  <div class="admin-page">
    <div class="page-header">
      <h2>问答日志</h2>
      <div class="header-actions">
        <el-button :icon="Download" @click="exportCSV" :disabled="logs.length === 0">导出当前页</el-button>
        <el-button :icon="Download" type="primary" @click="exportAll" :loading="exportingAll">导出全部</el-button>
      </div>
    </div>

    <div class="stats-row">
      <div class="stat-card"><div class="stat-number">{{ stats.total_queries }}</div><div class="stat-label">总问答数</div></div>
      <div class="stat-card"><div class="stat-number">{{ stats.answer_rate }}%</div><div class="stat-label">命中率</div></div>
      <div class="stat-card"><div class="stat-number">{{ stats.satisfaction_rate }}%</div><div class="stat-label">满意度</div></div>
      <div class="stat-card"><div class="stat-number">{{ stats.unanswered_queries }}</div><div class="stat-label">未命中</div></div>
    </div>

    <el-card class="filter-card">
      <div class="filter-row">
        <el-input v-model="filters.keyword" placeholder="搜索问题或回答关键词..." :prefix-icon="Search" clearable style="width:280px" @clear="loadLogs(1)" @keyup.enter="loadLogs(1)" />
        <el-select v-model="filters.is_answered" placeholder="命中状态" clearable style="width:130px" @change="loadLogs(1)">
          <el-option label="全部" :value="null" /><el-option label="已命中" :value="1" /><el-option label="未命中" :value="0" />
        </el-select>
        <el-select v-model="filters.feedback" placeholder="用户反馈" clearable style="width:130px" @change="loadLogs(1)">
          <el-option label="全部" :value="null" /><el-option label="未反馈" :value="0" /><el-option label="👍 点赞" :value="1" /><el-option label="👎 点踩" :value="2" />
        </el-select>
        <el-date-picker v-model="filters.dateRange" type="daterange" range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期" format="YYYY-MM-DD" value-format="YYYY-MM-DD" style="width:260px" @change="loadLogs(1)" />
        <el-button :icon="Refresh" @click="resetFilters">重置</el-button>
      </div>
    </el-card>

    <el-card style="margin-top:16px">
      <el-table :data="logs" stripe v-loading="loading" :row-key="(row: any) => row.id">
        <el-table-column type="expand">
          <template #default="{ row }">
            <div class="expand-detail">
              <div class="detail-section"><h4>🙋 用户问题</h4><p>{{ row.question }}</p></div>
              <div class="detail-section"><h4>🤖 系统回答</h4><div class="answer-full" v-html="renderMD(row.answer_full || row.answer)"></div></div>
              <div class="detail-meta">
                <el-tag size="small">会话: {{ row.session_id }}</el-tag>
                <el-tag size="small" type="info">检索: {{ row.retrieval_ms || '-' }}ms</el-tag>
                <el-tag size="small" type="info">LLM: {{ row.llm_ms || '-' }}ms</el-tag>
                <el-tag size="small" type="info">总耗时: {{ row.total_ms || '-' }}ms</el-tag>
                <el-tag size="small" v-if="row.prompt_tokens">Token: {{ row.prompt_tokens }}+{{ row.completion_tokens }}</el-tag>
                <el-tag v-if="row.feedback_reason" size="small" :type="row.feedback === 1 ? 'success' : 'danger'">{{ row.feedback === 1 ? '👍' : '👎' }} {{ row.feedback_reason }}</el-tag>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="question" label="问题" min-width="220" show-overflow-tooltip />
        <el-table-column label="回答" min-width="280" show-overflow-tooltip>
          <template #default="{ row }">{{ row.answer || '(拒答)' }}</template>
        </el-table-column>
        <el-table-column label="命中" width="80" align="center">
          <template #default="{ row }"><el-tag :type="row.is_answered ? 'success' : 'danger'" size="small">{{ row.is_answered ? '是' : '否' }}</el-tag></template>
        </el-table-column>
        <el-table-column label="反馈" width="80" align="center">
          <template #default="{ row }">
            <span v-if="row.feedback === 1" style="color:var(--color-success)">👍</span>
            <span v-else-if="row.feedback === 2" style="color:var(--color-danger)">👎</span>
            <span v-else style="color:var(--color-text-placeholder)">-</span>
          </template>
        </el-table-column>
        <el-table-column label="耗时" width="90" align="center">
          <template #default="{ row }">{{ row.total_ms ? row.total_ms + 'ms' : '-' }}</template>
        </el-table-column>
        <el-table-column prop="created_at" label="时间" width="170">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
      </el-table>
      <div class="pagination-wrap">
        <el-pagination v-model:current-page="pagination.page" :page-size="pagination.page_size" :total="pagination.total" layout="total, prev, pager, next, sizes" :page-sizes="[20, 50, 100]" @current-change="loadLogs" @size-change="(v: number) => { pagination.page_size = v; loadLogs(1) }" />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { Search, Refresh, Download } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import client from '@/api/client'
import MarkdownIt from 'markdown-it'

const loading = ref(false)
const exportingAll = ref(false)
const logs = ref<any[]>([])
const pagination = reactive({ page: 1, page_size: 20, total: 0 })
const filters = reactive({ keyword: '', is_answered: null as number | null, feedback: null as number | null, dateRange: null as [string, string] | null })
const stats = reactive({ total_queries: 0, answer_rate: 0, satisfaction_rate: 0, unanswered_queries: 0 })
const md = new MarkdownIt({ breaks: true, linkify: true })
function renderMD(text: string) { return md.render(text || '') }

async function loadLogs(page?: number) {
  if (page) pagination.page = page
  loading.value = true
  try {
    const params: any = { page: pagination.page, page_size: pagination.page_size }
    if (filters.keyword) params.keyword = filters.keyword
    if (filters.is_answered !== null) params.is_answered = filters.is_answered
    if (filters.feedback !== null) params.feedback = filters.feedback
    if (filters.dateRange && filters.dateRange.length === 2) { params.date_from = filters.dateRange[0]; params.date_to = filters.dateRange[1] }
    const res = await client.get('/admin/logs', { params })
    logs.value = res.data.data?.items || []
    pagination.total = res.data.data?.total || 0
    loadStats()
  } catch { /* ignore */ } finally { loading.value = false }
}

async function loadStats() {
  try {
    const res = await client.get('/admin/stats/overview')
    const d = res.data.data
    if (d) { stats.total_queries = d.total_queries || 0; stats.answer_rate = d.answer_rate || 0; stats.satisfaction_rate = d.satisfaction_rate || 0; stats.unanswered_queries = d.unanswered_queries || 0 }
  } catch { /* ignore */ }
}

function resetFilters() { filters.keyword = ''; filters.is_answered = null; filters.feedback = null; filters.dateRange = null; loadLogs(1) }
function formatTime(t: string) { if (!t) return '-'; const d = new Date(t.endsWith('Z') ? t : t + 'Z'); const pad = (n: number) => String(n).padStart(2, '0'); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}` }

function exportCSV() {
  const header = '问题,回答,命中,反馈,耗时(ms),时间\n'
  const rows = logs.value.map(row => { const answer = (row.answer || '').replace(/"/g, '""'); const question = (row.question || '').replace(/"/g, '""'); const fb = row.feedback === 1 ? '点赞' : row.feedback === 2 ? '点踩' : '无'; return `"${question}","${answer}","${row.is_answered ? '是' : '否'}","${fb}","${row.total_ms || ''}","${row.created_at}"` }).join('\n')
  const blob = new Blob(['﻿' + header + rows], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = `问答日志_${new Date().toISOString().slice(0, 10)}.csv`; a.click(); URL.revokeObjectURL(url)
  ElMessage.success('导出成功')
}

async function exportAll() {
  exportingAll.value = true
  try {
    const params: any = {}
    if (filters.dateRange && filters.dateRange.length === 2) {
      params.date_from = filters.dateRange[0]
      params.date_to = filters.dateRange[1]
    }
    const res = await client.get('/admin/export/logs', { params, responseType: 'blob' })
    const blob = new Blob([res.data], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `问答日志全部_${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('全部日志导出成功（最多5000条）')
  } catch {
    ElMessage.error('导出失败')
  } finally {
    exportingAll.value = false
  }
}

onMounted(() => loadLogs())
</script>

<style scoped>
.admin-page { padding: 24px 32px; max-width: 1400px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.page-header h2 { font-size: 22px; font-weight: 700; color: var(--color-text-primary); margin: 0; }
.header-actions { display: flex; gap: 8px; }
.stats-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 16px; }
.stat-card { background: var(--color-bg-card); border-radius: 10px; padding: 16px 20px; border: 1px solid var(--color-border); text-align: center; }
.stat-number { font-size: 28px; font-weight: 700; color: var(--color-primary); }
.stat-label { font-size: 13px; color: var(--color-text-secondary); margin-top: 4px; }
.filter-row { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
.pagination-wrap { display: flex; justify-content: flex-end; margin-top: 16px; }
.expand-detail { padding: 12px 20px; max-width: 800px; }
.detail-section { margin-bottom: 16px; }
.detail-section h4 { font-size: 14px; font-weight: 600; margin: 0 0 8px; color: var(--color-text-primary); }
.detail-section p { margin: 0; line-height: 1.7; white-space: pre-wrap; color: var(--color-text-body); font-size: 14px; }
.answer-full { line-height: 1.8; color: var(--color-text-body); }
.answer-full :deep(p) { margin: 4px 0; }
.detail-meta { display: flex; gap: 8px; flex-wrap: wrap; }
@media (max-width: 900px) { .stats-row { grid-template-columns: repeat(2, 1fr); } .filter-row { flex-direction: column; align-items: stretch; } }
</style>
