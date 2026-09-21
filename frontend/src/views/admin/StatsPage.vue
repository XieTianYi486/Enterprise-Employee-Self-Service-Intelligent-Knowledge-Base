<template>
  <div class="stats-page">
    <div class="page-header">
      <div class="header-left">
        <el-icon class="header-icon" :size="22"><DataAnalysis /></el-icon>
        <h2>统计分析</h2>
      </div>
    </div>

    <!-- A. 概览 KPI 带 -->
    <el-card class="kpi-card" shadow="never">
      <div class="kpi-item" v-for="k in kpiList" :key="k.label">
        <div class="kpi-label">{{ k.label }}</div>
        <div class="kpi-value" :style="{ color: k.color }">{{ k.value }}</div>
        <div class="kpi-sub">{{ k.sub }}</div>
      </div>
    </el-card>

    <!-- B. 问答质量 + 高频问题 -->
    <div class="panel-grid">
      <el-card class="panel" shadow="never">
        <template #header>
          <div class="panel-header">
            <span>问答质量</span>
            <el-tag size="small" :type="answerRate >= 60 ? 'success' : 'warning'">回答率 {{ answerRate }}%</el-tag>
          </div>
        </template>
        <div ref="qaChartRef" class="chart"></div>
        <div class="mini-stats">
          <div class="mini-item">
            <el-icon :size="16" color="#67c23a"><CircleCheck /></el-icon>
            <span>点赞</span><b>{{ overview.like_count ?? 0 }}</b>
          </div>
          <div class="mini-item">
            <el-icon :size="16" color="#f56c6c"><CircleClose /></el-icon>
            <span>点踩</span><b>{{ overview.dislike_count ?? 0 }}</b>
          </div>
          <div class="mini-item">
            <el-icon :size="16" color="#9b59b6"><Star /></el-icon>
            <span>满意度</span><b>{{ overview.satisfaction_rate ?? 0 }}%</b>
          </div>
        </div>
      </el-card>

      <el-card class="panel" shadow="never">
        <template #header>
          <div class="panel-header"><span>高频问题 TOP 10</span></div>
        </template>
        <div ref="hotChartRef" class="chart hot-chart"></div>
      </el-card>
    </div>

    <!-- C. 文档数据 + 未命中问题 -->
    <div class="panel-grid">
      <el-card class="panel" shadow="never">
        <template #header>
          <div class="panel-header"><span>文档数据</span></div>
        </template>
        <div class="doc-kpis">
          <div class="doc-kpi">
            <div class="dg-label">文档总数</div>
            <div class="dg-value">{{ docStats.total_documents ?? 0 }}</div>
          </div>
          <div class="doc-kpi">
            <div class="dg-label">分块总数</div>
            <div class="dg-value">{{ docStats.total_chunks ?? 0 }}</div>
          </div>
          <div class="doc-kpi">
            <div class="dg-label">存储大小</div>
            <div class="dg-value">{{ formatSize(docStats.total_size_bytes) }}</div>
          </div>
        </div>
        <div class="type-title">文件类型分布</div>
        <div v-if="fileTypes.length > 0" class="type-list">
          <div class="type-row" v-for="ft in fileTypes" :key="ft.name">
            <span class="type-name">{{ ft.name }}</span>
            <div class="type-bar">
              <div class="type-fill" :style="{ width: ft.percent + '%', background: ft.color }"></div>
            </div>
            <span class="type-count">{{ ft.value }}</span>
          </div>
        </div>
        <el-empty v-else description="暂无文档" :image-size="50" />
      </el-card>

      <el-card class="panel" shadow="never">
        <template #header>
          <div class="panel-header"><span>未命中问题</span></div>
        </template>
        <el-table :data="unansweredQuestions" size="small" max-height="300">
          <el-table-column type="index" label="#" width="45" />
          <el-table-column prop="question" label="问题" show-overflow-tooltip />
          <el-table-column label="时间" width="120">
            <template #default="{ row }">
              <span class="time-text">{{ formatTime(row.created_at) }}</span>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="unansweredQuestions.length === 0" description="暂无未命中问题" :image-size="45" />
        <div v-if="unansweredQuestions.length > 0" class="unanswered-footer">
          <span class="hint">知识库缺少相关文档，可上传后补齐</span>
          <el-button size="small" type="primary" :icon="Upload" @click="goUpload">上传文档</el-button>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import * as echarts from 'echarts'
import { CircleCheck, CircleClose, Star, DataAnalysis, Upload } from '@element-plus/icons-vue'
import client from '@/api/client'

const router = useRouter()

const overview = ref<any>({})
const docStats = ref<any>({ total_documents: 0, total_chunks: 0, total_size_bytes: 0, by_file_type: {} })
const hotQuestions = ref<any[]>([])
const unansweredQuestions = ref<any[]>([])

const qaChartRef = ref<HTMLElement>()
const hotChartRef = ref<HTMLElement>()
let qaChart: echarts.ECharts | null = null
let hotChart: echarts.ECharts | null = null

const teal = getComputedStyle(document.documentElement).getPropertyValue('--color-primary').trim() || '#0D9488'

// KPI 概览带
const kpiList = computed(() => [
  { label: '注册用户', value: overview.value.user_count ?? 0, sub: '活跃账号', color: '#409eff' },
  { label: '总会话数', value: overview.value.session_count ?? 0, sub: '累计对话', color: '#0D9488' },
  { label: '问答总数', value: overview.value.total_queries ?? 0, sub: '全部提问', color: '#9b59b6' },
  { label: '回答率', value: (overview.value.answer_rate ?? 0) + '%', sub: '命中回答', color: '#e6a23c' },
])

const answerRate = computed(() => overview.value.answer_rate ?? 0)

// 文件类型分布（转成带百分比列表，按数量降序）
const fileTypes = computed(() => {
  const raw = docStats.value.by_file_type || {}
  const list = Object.entries(raw).map(([k, v]) => ({
    name: k.toUpperCase(),
    value: v as number,
    color: ['#409eff', '#67c23a', '#e6a23c', '#9b59b6', '#f56c6c', '#17a2b8'][Math.abs(k.length * 7) % 6],
  })).sort((a, b) => b.value - a.value)
  const max = Math.max(...list.map((i) => i.value), 1)
  return list.map((i) => ({ ...i, percent: Math.round((i.value / max) * 100) }))
})

function formatSize(bytes: number): string {
  if (!bytes) return '0 B'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1048576).toFixed(1) + ' MB'
}

function formatTime(t: string) {
  if (!t) return '-'
  const d = new Date(t.endsWith('Z') ? t : t + 'Z')
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getMonth() + 1}/${d.getDate()} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

async function loadStats() {
  try {
    const [sysRes, docRes, hotRes, unansweredRes] = await Promise.all([
      client.get('/admin/stats/overview'),
      client.get('/documents/stats/overview'),
      client.get('/admin/stats/hot-questions', { params: { limit: 10 } }),
      client.get('/admin/stats/unanswered', { params: { page: 1, page_size: 10 } }),
    ])
    overview.value = sysRes.data.data || {}
    docStats.value = docRes.data.data || docStats.value
    hotQuestions.value = hotRes.data.data || []
    unansweredQuestions.value = unansweredRes.data.data?.items || []
    await nextTick()
    renderCharts()
  } catch { /* ignore */ }
}

function renderCharts() {
  renderQaChart()
  renderHotChart()
}

function renderQaChart() {
  if (qaChartRef.value) {
    qaChart = echarts.init(qaChartRef.value)
    const s = overview.value
    qaChart.setOption({
      tooltip: { trigger: 'item' },
      legend: { bottom: 0, textStyle: { color: '#909399' } },
      series: [{
        type: 'pie', radius: ['52%', '76%'], center: ['50%', '44%'],
        itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
        label: { show: false },
        emphasis: { label: { show: true, fontWeight: 'bold' } },
        data: [
          { value: s.answered_queries ?? 0, name: '已回答', itemStyle: { color: '#67c23a' } },
          { value: s.unanswered_queries ?? 0, name: '未命中', itemStyle: { color: '#f56c6c' } },
          { value: Math.max((s.total_queries ?? 0) - (s.answered_queries ?? 0) - (s.unanswered_queries ?? 0), 0), name: '未答复', itemStyle: { color: '#e6a23c' } },
        ],
      }],
    })
  }
}

function renderHotChart() {
  if (hotChartRef.value) {
    hotChart = echarts.init(hotChartRef.value)
    const list = [...hotQuestions.value].slice(0, 10).reverse()
    hotChart.setOption({
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      grid: { left: 8, right: 30, bottom: 8, top: 10, containLabel: true },
      xAxis: { type: 'value', splitLine: { lineStyle: { color: 'rgba(128,128,128,.12)' } } },
      yAxis: {
        type: 'category',
        data: list.map((q: any) => q.question.length > 14 ? q.question.slice(0, 14) + '…' : q.question),
      },
      series: [{
        type: 'bar', barWidth: 14, itemStyle: { borderRadius: [0, 7, 7, 0], color: teal },
        label: { show: true, position: 'right', color: '#909399' },
        data: list.map((q: any) => q.count),
      }],
    })
  }
}

function resizeCharts() {
  qaChart?.resize()
  hotChart?.resize()
}

onMounted(() => {
  loadStats()
  window.addEventListener('resize', resizeCharts)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeCharts)
  qaChart?.dispose()
  hotChart?.dispose()
})

function goUpload() {
  router.push('/admin/documents')
}
</script>

<style scoped>
.stats-page { padding: 24px 32px; max-width: 1240px; }
.page-header { margin-bottom: 20px; }
.header-left { display: flex; align-items: center; gap: 10px; }
.header-icon { color: var(--color-primary); }
.page-header h2 { font-size: 20px; font-weight: 700; color: var(--color-text-primary); margin: 0; }

/* KPI 概览带 */
.kpi-card { border-radius: 12px; margin-bottom: 20px; }
.kpi-card :deep(.el-card__body) {
  display: grid; grid-template-columns: repeat(4, 1fr);
  padding: 8px 0;
}
.kpi-item {
  padding: 18px 24px; text-align: center;
  border-right: 1px solid var(--color-border);
}
.kpi-item:last-child { border-right: none; }
.kpi-label { font-size: 13px; color: var(--color-text-secondary); }
.kpi-value { font-size: 28px; font-weight: 700; margin: 4px 0; line-height: 1.2; }
.kpi-sub { font-size: 12px; color: var(--color-text-placeholder); }

/* 面板 */
.panel-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px; }
.panel { border-radius: 12px; }
.panel-header { display: flex; align-items: center; justify-content: space-between; font-weight: 600; color: var(--color-text-primary); }
.chart { width: 100%; height: 240px; }
.hot-chart { height: 360px; }

/* 问答质量 mini */
.mini-stats { display: flex; justify-content: space-around; border-top: 1px solid var(--color-border); padding-top: 14px; margin-top: 6px; }
.mini-item { display: flex; align-items: center; gap: 6px; font-size: 13px; color: var(--color-text-secondary); }
.mini-item b { font-size: 16px; color: var(--color-text-primary); }

/* 文档数据 */
.doc-kpis { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.doc-kpi { background: var(--color-bg-hover); border-radius: 10px; padding: 14px; text-align: center; }
.dg-label { font-size: 12px; color: var(--color-text-secondary); }
.dg-value { font-size: 20px; font-weight: 700; color: var(--color-text-primary); margin-top: 2px; }
.type-title { font-size: 13px; font-weight: 600; color: var(--color-text-primary); margin: 18px 0 10px; }
.type-list { display: flex; flex-direction: column; gap: 10px; }
.type-row { display: flex; align-items: center; gap: 10px; font-size: 13px; }
.type-name { width: 52px; color: var(--color-text-secondary); }
.type-bar { flex: 1; height: 8px; background: var(--color-bg-hover); border-radius: 4px; overflow: hidden; }
.type-fill { height: 100%; border-radius: 4px; transition: width 0.4s; }
.type-count { width: 32px; text-align: right; font-weight: 600; color: var(--color-text-primary); }

/* 未命中 */
.time-text { font-size: 12px; color: var(--color-text-placeholder); }
.unanswered-footer { display: flex; justify-content: space-between; align-items: center; padding-top: 12px; margin-top: 12px; border-top: 1px solid var(--color-border); }
.unanswered-footer .hint { font-size: 13px; color: var(--color-text-secondary); }

@media (max-width: 900px) {
  .kpi-card :deep(.el-card__body) { grid-template-columns: repeat(2, 1fr); }
  .kpi-item { border-bottom: 1px solid var(--color-border); border-right: none; }
  .panel-grid { grid-template-columns: 1fr; }
}
</style>