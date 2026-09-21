<template>
  <div class="wb-page">
    <!-- 欢迎横幅 -->
    <div class="wb-header">
      <div class="wb-greeting">
        <h2>你好，{{ stats.user_name }} 👋</h2>
        <p>{{ todayText }} · 今天也要高效办公</p>
      </div>
      <el-tag size="large" effect="plain" type="success">{{ stats.role_name }}</el-tag>
    </div>

    <!-- 统计卡片：青绿渐变数字卡 -->
    <div class="wb-cards" v-loading="loading">
      <div
        class="wb-card"
        v-for="(c, i) in stats.cards"
        :key="c.label"
        :style="{ background: cardGradient(i) }"
      >
        <div class="wb-card-top">
          <span class="wb-card-icon">
            <el-icon :size="18"><component :is="cardIcon(c.label)" /></el-icon>
          </span>
          <span class="wb-card-label">{{ c.label }}</span>
        </div>
        <div class="wb-card-value">
          {{ c.value }}<span class="wb-card-unit">{{ c.unit }}</span>
        </div>
        <div class="wb-card-sub">{{ c.sub }}</div>
      </div>
    </div>

    <!-- 快捷入口：横排胶囊按钮条 -->
    <el-card class="panel quick-card" shadow="never">
      <div class="quick-strip">
        <span class="panel-title quick-head">⚡ 快捷入口</span>
        <div class="quick-items">
          <router-link v-if="authStore.can('leaves:submit')" to="/leaves" class="quick-item">
            <span class="quick-icon"><el-icon :size="18"><Calendar /></el-icon></span>我要请假
          </router-link>
          <router-link v-if="authStore.can('expenses:submit')" to="/expenses" class="quick-item">
            <span class="quick-icon"><el-icon :size="18"><Money /></el-icon></span>我要报销
          </router-link>
          <router-link v-if="authStore.can('approvals:read')" to="/approvals" class="quick-item">
            <span class="quick-icon"><el-icon :size="18"><Stamp /></el-icon></span>审批中心
          </router-link>
          <router-link to="/tickets" class="quick-item">
            <span class="quick-icon"><el-icon :size="18"><Tickets /></el-icon></span>我的工单
          </router-link>
          <router-link v-if="authStore.can('chat:ask')" to="/chat" class="quick-item">
            <span class="quick-icon"><el-icon :size="18"><ChatDotRound /></el-icon></span>制度问答
          </router-link>
        </div>
      </div>
    </el-card>

    <!-- 数据区：三列网格，趋势图整行，饼图/部门对比占一列，最近单据占两列 -->
    <div v-if="!showGuide" class="wb-grid">
      <!-- 趋势图（总经理/超管/知识库管理员）整行 -->
      <el-card v-if="stats.trend" class="panel trend-card" shadow="never">
        <div class="panel-title">
          <template v-if="stats.role === 'knowledge_admin'">近 6 月问答量趋势</template>
          <template v-else>近 6 月请假 / 报销趋势</template>
        </div>
        <div ref="trendRef" class="chart-box"></div>
      </el-card>

      <!-- 请假类型分布（员工/部门经理） -->
      <el-card v-if="stats.type_dist !== null" class="panel" shadow="never">
        <div class="panel-title">
          <template v-if="stats.role === 'dept_admin'">本部门请假类型分布</template>
          <template v-else>我的请假类型分布</template>
        </div>
        <div v-if="stats.type_dist?.length" ref="typeRef" class="chart-box"></div>
        <el-empty v-else description="暂无请假记录" :image-size="60" />
      </el-card>

      <!-- 部门对比（总经理/超管） -->
      <el-card v-if="stats.dept_dist !== null" class="panel" shadow="never">
        <div class="panel-title">各部门请假量对比</div>
        <div v-if="stats.dept_dist?.length" ref="deptRef" class="chart-box"></div>
        <el-empty v-else description="暂无数据" :image-size="60" />
      </el-card>

      <!-- 最近单据（请假+报销混合） -->
      <el-card v-if="stats.recent?.length" class="panel recent-card" shadow="never">
        <div class="panel-title">最近单据</div>
        <el-table :data="stats.recent" size="small" stripe>
          <el-table-column label="类型" width="70">
            <template #default="{ row }">
              <el-tag size="small" :type="row.biz_type === 'LEAVE' ? 'primary' : 'success'">
                {{ row.biz_type === 'LEAVE' ? '请假' : '报销' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="申请人" min-width="90">
            <template #default="{ row }">{{ row.applicant_name || '-' }}</template>
          </el-table-column>
          <el-table-column label="内容" min-width="170">
            <template #default="{ row }">
              <span v-if="row.biz_type === 'LEAVE'">{{ row.leave_type }} · {{ row.days }} 天</span>
              <span v-else>{{ row.expense_type }} · ¥{{ row.amount?.toFixed(2) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="90" align="center">
            <template #default="{ row }">
              <el-tag size="small" :type="LEAVE_STATUS_LABELS[row.status]?.type || 'info'">
                {{ LEAVE_STATUS_LABELS[row.status]?.label || row.status }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="提交时间" width="150">
            <template #default="{ row }"><span class="wb-time">{{ formatTime(row.create_time) }}</span></template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>

    <!-- 新用户引导卡：无任何图表与单据数据时展示 -->
    <el-card v-if="showGuide" class="panel guide-card" shadow="never">
      <div class="guide-body">
        <div class="guide-icon">👋</div>
        <div class="guide-title">欢迎使用员工自助服务</div>
        <div class="guide-sub">暂时还没有可展示的图表与单据数据，从下面的事务开始体验吧</div>
        <div class="guide-actions">
          <el-button v-if="authStore.can('leaves:submit')" type="primary" @click="$router.push('/leaves')">
            <el-icon><Calendar /></el-icon>我要请假
          </el-button>
          <el-button v-if="authStore.can('expenses:submit')" type="primary" plain @click="$router.push('/expenses')">
            <el-icon><Money /></el-icon>我要报销
          </el-button>
          <el-button v-if="authStore.can('chat:ask')" @click="$router.push('/chat')">
            <el-icon><ChatDotRound /></el-icon>问问制度问答
          </el-button>
        </div>
      </div>
    </el-card>

    <!-- 最新公告：整行卡片，双列排布 -->
    <el-card class="panel" shadow="never">
      <div class="panel-title">📢 最新公告</div>
      <el-empty v-if="!stats.announcements?.length" description="暂无公告" :image-size="50" />
      <div v-else class="ann-grid">
        <div v-for="a in stats.announcements" :key="a.id" class="ann-item">
          <span class="ann-dot"></span>
          <div class="ann-body">
            <div class="ann-title">{{ a.title }}</div>
            <div class="ann-time">{{ formatTime(a.publish_at) }}</div>
          </div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import {
  Calendar, Money, Stamp, Tickets, ChatDotRound,
  Timer, User, Document, CircleCheck,
} from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import client from '@/api/client'
import { useAuthStore } from '@/store/auth'
import { LEAVE_STATUS_LABELS } from '@/api/workflow'

const authStore = useAuthStore()

// 统计卡片：按标签关键词匹配图标
const CARD_ICONS: Array<[string, any]> = [
  ['待审批', Stamp],
  ['待办', Stamp],
  ['待终审', Stamp],
  ['待审核', Document],
  ['年假', Calendar],
  ['调休', Timer],
  ['请假', Calendar],
  ['报销', Money],
  ['人数', User],
  ['员工', User],
  ['文档', Document],
  ['问答', ChatDotRound],
]

function cardIcon(label: string) {
  const hit = CARD_ICONS.find(([k]) => label.includes(k))
  return hit ? hit[1] : CircleCheck
}

// 青绿系渐变（与项目主题一致）
const CARD_GRADIENTS = [
  'linear-gradient(135deg, #0d9488 0%, #14b8a6 100%)',
  'linear-gradient(135deg, #0f766e 0%, #0d9488 100%)',
  'linear-gradient(135deg, #0891b2 0%, #14b8a6 100%)',
  'linear-gradient(135deg, #134e4a 0%, #0f766e 100%)',
  'linear-gradient(135deg, #0ea5e9 0%, #0891b2 100%)',
  'linear-gradient(135deg, #115e59 0%, #0d9488 100%)',
]

// stats 为 any，v-for 索引在模板中可能被推断为 string | number，这里统一转 number
function cardGradient(i: number | string) {
  return CARD_GRADIENTS[Number(i) % CARD_GRADIENTS.length]
}

const loading = ref(true)
const stats = ref<any>({
  role: '',
  user_name: '',
  role_name: '',
  cards: [],
  trend: null,
  type_dist: null,
  dept_dist: null,
  announcements: [],
  recent: [],
})

const trendRef = ref<HTMLElement>()
const typeRef = ref<HTMLElement>()
const deptRef = ref<HTMLElement>()
const charts: echarts.ECharts[] = []

// 新用户引导卡：没有任何图表与单据数据时展示
const showGuide = computed(() => {
  const s = stats.value
  return !s.trend && !s.type_dist?.length && !s.dept_dist?.length && !s.recent?.length
})

const todayText = new Date().toLocaleDateString('zh-CN', {
  year: 'numeric', month: 'long', day: 'numeric', weekday: 'long',
})

const TEAL = ['#0d9488', '#2dd4bf', '#5eead4', '#0f766e', '#99f6e4', '#14b8a6']

function initTrendChart() {
  if (!trendRef.value || !stats.value.trend) return
  const t = stats.value.trend
  const isQa = stats.value.role === 'knowledge_admin'
  const chart = echarts.init(trendRef.value)
  chart.setOption({
    tooltip: { trigger: 'axis' },
    // 图例放在图表下方，避免遮挡绘图区
    legend: {
      data: isQa ? ['问答量'] : ['请假单数', '报销金额'],
      bottom: 0,
      icon: 'roundRect',
      itemWidth: 14,
      itemHeight: 8,
    },
    grid: { left: 52, right: 64, top: 42, bottom: 40 },
    xAxis: { type: 'category', data: t.months },
    // 轴名放在轴顶端（nameLocation: 'start'），避免与底部图例重叠；
    // 颜色与对应系列一致，一眼可辨左右轴各自归属
    yAxis: [
      {
        type: 'value',
        name: isQa ? '次数' : '单数',
        nameLocation: 'start',
        nameGap: 16,
        nameTextStyle: { fontSize: 12, color: TEAL[0] },
      },
      ...(isQa ? [] : [{
        type: 'value',
        name: '金额(元)',
        nameLocation: 'start',
        nameGap: 16,
        nameTextStyle: { fontSize: 12, color: TEAL[1] },
      }]),
    ],
    series: isQa
      ? [{ name: '问答量', type: 'bar', data: t.leave, itemStyle: { color: TEAL[0], borderRadius: [6, 6, 0, 0] }, barWidth: 26 }]
      : [
          { name: '请假单数', type: 'bar', data: t.leave, itemStyle: { color: TEAL[0], borderRadius: [6, 6, 0, 0] }, barWidth: 26 },
          { name: '报销金额', type: 'line', yAxisIndex: 1, data: t.expense, smooth: true, itemStyle: { color: TEAL[1] }, lineStyle: { width: 3 } },
        ],
  })
  charts.push(chart)
}

function initTypeChart() {
  if (!typeRef.value || !stats.value.type_dist?.length) return
  const chart = echarts.init(typeRef.value)
  chart.setOption({
    tooltip: { trigger: 'item' },
    legend: { bottom: 0 },
    color: TEAL,
    series: [{
      type: 'pie',
      radius: ['38%', '68%'],
      center: ['50%', '44%'],
      itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
      label: { formatter: '{b}: {c} 天' },
      data: stats.value.type_dist,
    }],
  })
  charts.push(chart)
}

function initDeptChart() {
  if (!deptRef.value || !stats.value.dept_dist?.length) return
  const chart = echarts.init(deptRef.value)
  chart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 20, top: 20, bottom: 50 },
    xAxis: { type: 'category', data: stats.value.dept_dist.map((d: any) => d.name), axisLabel: { rotate: 30 } },
    yAxis: { type: 'value' },
    series: [{
      type: 'bar',
      data: stats.value.dept_dist.map((d: any) => d.value),
      itemStyle: {
        borderRadius: [6, 6, 0, 0],
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: TEAL[3] },
          { offset: 1, color: TEAL[0] },
        ]),
      },
      barWidth: 24,
    }],
  })
  charts.push(chart)
}

async function loadStats() {
  loading.value = true
  try {
    const res = await client.get('/workbench/stats')
    stats.value = res.data.data || stats.value
    await nextTick()
    initTrendChart()
    initTypeChart()
    initDeptChart()
  } catch (e: any) {
    // 加载失败静默：页面保留空态
  } finally {
    loading.value = false
  }
}

function handleResize() {
  charts.forEach(c => c.resize())
}

function formatTime(t: string) {
  if (!t) return '-'
  const d = new Date(t.endsWith('Z') ? t : t + 'Z')
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

onMounted(() => {
  loadStats()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  charts.forEach(c => c.dispose())
})
</script>

<style scoped>
.wb-page { padding: 24px 32px; max-width: 1400px; margin: 0 auto; }

/* 欢迎横幅：浅青绿渐变卡片 */
.wb-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding: 18px 22px;
  border-radius: 16px;
  background: linear-gradient(120deg, rgba(13, 148, 136, 0.12), rgba(94, 234, 212, 0.16) 55%, rgba(13, 148, 136, 0.05));
  border: 1px solid rgba(13, 148, 136, 0.16);
}
.wb-greeting h2 { margin: 0 0 4px; font-size: 22px; font-weight: 700; color: var(--color-text-primary); }
.wb-greeting p { margin: 0; font-size: 13px; color: var(--color-text-secondary); }

/* 统计卡片：青绿渐变数字卡 */
.wb-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
  gap: 14px;
  margin-bottom: 16px;
  min-height: 60px;
}
.wb-card {
  color: #fff;
  border-radius: 16px;
  padding: 18px 20px 16px;
  border: none;
  position: relative;
  overflow: hidden;
  min-height: 100px;
  transition: transform 0.15s, box-shadow 0.15s;
}
.wb-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 12px 26px rgba(13, 148, 136, 0.28);
}
.wb-card-top { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
.wb-card-icon {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.22);
  flex: 0 0 34px;
}
.wb-card-label { font-size: 13px; font-weight: 600; color: rgba(255, 255, 255, 0.88); }
.wb-card-value { font-size: 30px; font-weight: 800; line-height: 1.1; }
.wb-card-unit { font-size: 13px; font-weight: 400; margin-left: 2px; color: rgba(255, 255, 255, 0.75); }
.wb-card-sub { font-size: 12px; color: rgba(255, 255, 255, 0.72); margin-top: 5px; }

/* 面板通用 */
.panel {
  border-radius: 14px;
  border: 1px solid var(--color-border);
  box-shadow: 0 2px 12px rgba(13, 148, 136, 0.05);
  margin-bottom: 16px;
}
.panel-title { font-size: 15px; font-weight: 700; color: var(--color-text-primary); margin-bottom: 8px; }
.chart-box { width: 100%; height: 280px; }
.trend-card .chart-box { height: 300px; }

/* 快捷入口：横排胶囊按钮条 */
.quick-strip { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }
.quick-head { margin-bottom: 0; white-space: nowrap; }
.quick-items { display: flex; gap: 10px; flex-wrap: wrap; }
.quick-item {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 7px 16px 7px 8px;
  border-radius: 999px;
  border: 1px solid var(--color-border);
  background: var(--color-bg-card, #fff);
  color: var(--color-text-body);
  text-decoration: none;
  font-size: 13px;
  transition: all 0.15s;
}
.quick-icon {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(13, 148, 136, 0.1);
  color: #0d9488;
  transition: all 0.15s;
}
.quick-item:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
  transform: translateY(-1px);
  box-shadow: 0 6px 14px rgba(13, 148, 136, 0.12);
}
.quick-item:hover .quick-icon { background: rgba(13, 148, 136, 0.18); }

/* 数据区三列网格：趋势整行、饼图/部门对比一列、最近单据两列 */
.wb-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 16px; }
.trend-card { grid-column: 1 / -1; }
.recent-card { grid-column: span 2; }

/* 新用户引导卡 */
.guide-body {
  min-height: 220px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 24px 16px;
}
.guide-icon { font-size: 44px; margin-bottom: 10px; }
.guide-title { font-size: 17px; font-weight: 700; color: var(--color-text-primary); margin-bottom: 6px; }
.guide-sub { font-size: 13px; color: var(--color-text-secondary); margin-bottom: 18px; }
.guide-actions { display: flex; flex-wrap: wrap; gap: 10px; justify-content: center; }
.guide-actions .el-button .el-icon { margin-right: 4px; }

/* 公告：双列排布 */
.ann-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 2px 28px; }
.ann-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 2px;
  border-bottom: 1px dashed var(--color-border);
}
.ann-dot {
  flex: 0 0 8px;
  width: 8px;
  height: 8px;
  margin-top: 5px;
  border-radius: 50%;
  background: #2dd4bf;
  box-shadow: 0 0 0 3px rgba(45, 212, 191, 0.15);
}
.ann-body { min-width: 0; }
.ann-title { font-size: 13px; font-weight: 600; color: var(--color-text-body); line-height: 1.4; }
.ann-time { font-size: 12px; color: var(--color-text-placeholder); margin-top: 2px; }

.wb-time { font-size: 12px; color: var(--color-text-secondary); }

@media (max-width: 1000px) {
  .wb-grid { grid-template-columns: 1fr; }
  .trend-card, .recent-card { grid-column: auto; }
  .ann-grid { grid-template-columns: 1fr; }
}
</style>
