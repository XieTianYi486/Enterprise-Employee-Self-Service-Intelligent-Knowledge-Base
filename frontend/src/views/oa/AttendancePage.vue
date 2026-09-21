<template>
  <div class="oa-page">
    <div class="page-header">
      <div class="header-left">
        <el-icon class="header-icon" :size="24"><Clock /></el-icon>
        <h2>考勤打卡</h2>
        <el-tag size="small" round type="info">上班 {{ workRule }} · 下班 {{ offRule }}</el-tag>
      </div>
    </div>

    <!-- 打卡区 -->
    <el-card class="clock-card" shadow="never">
      <div class="clock-row">
        <div class="clock-time">
          <div class="now-time">{{ nowText }}</div>
          <div class="now-date">{{ todayText }}</div>
        </div>
        <el-button
          type="primary"
          size="large"
          :loading="clocking"
          :disabled="todayDone"
          class="clock-btn"
          @click="handleClock"
        >
          {{ todayDone ? '今日考勤已完成' : (todayClockIn ? '下班签退' : '上班打卡') }}
        </el-button>
      </div>
      <div v-if="todayStatus" class="clock-result">
        <el-tag :type="statusTagType(todayStatus)" size="small">{{ statusLabel(todayStatus) }}</el-tag>
        <span class="clock-tip">{{ lastClockMessage }}</span>
      </div>
    </el-card>

    <el-tabs v-model="activeTab">
      <!-- 我的考勤 -->
      <el-tab-pane label="我的考勤" name="mine">
        <el-card shadow="never">
          <div class="toolbar">
            <el-date-picker
              v-model="month"
              type="month"
              value-format="YYYY-MM"
              :clearable="false"
              @change="loadMine"
            />
            <el-button :icon="Download" plain :disabled="!records.length" @click="exportMine">导出</el-button>
          </div>
          <div class="att-stats">
            <div class="att-stat"><div class="att-num">{{ stats.days }}</div><div class="att-label">打卡天数</div></div>
            <div class="att-stat"><div class="att-num warn">{{ stats.late }}</div><div class="att-label">迟到次数</div></div>
            <div class="att-stat"><div class="att-num warn">{{ stats.early }}</div><div class="att-label">早退次数</div></div>
          </div>
          <el-table :data="records" stripe v-loading="loading" empty-text="本月暂无考勤记录">
            <el-table-column prop="work_date" label="日期" width="130" />
            <el-table-column label="上班打卡" min-width="160">
              <template #default="{ row }"><span class="time-text">{{ formatTime(row.clock_in) }}</span></template>
            </el-table-column>
            <el-table-column label="下班签退" min-width="160">
              <template #default="{ row }"><span class="time-text">{{ formatTime(row.clock_out) }}</span></template>
            </el-table-column>
            <el-table-column label="状态" width="120" align="center">
              <template #default="{ row }">
                <el-tag size="small" :type="statusTagType(row.status)">{{ statusLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <!-- 部门汇总（经理/总经理/超管） -->
      <el-tab-pane v-if="canViewDept" label="部门汇总" name="dept">
        <el-card shadow="never">
          <div class="toolbar">
            <el-date-picker
              v-model="month"
              type="month"
              value-format="YYYY-MM"
              :clearable="false"
              @change="loadDept"
            />
            <el-button :icon="Download" plain :disabled="!deptRecords.length" @click="exportDept">导出</el-button>
          </div>
          <el-table :data="deptRecords" stripe v-loading="loadingDept" empty-text="本月暂无考勤数据">
            <el-table-column prop="real_name" label="姓名" min-width="100" />
            <el-table-column prop="dept_name" label="部门" min-width="120">
              <template #default="{ row }">{{ row.dept_name || '未分配' }}</template>
            </el-table-column>
            <el-table-column prop="days" label="打卡天数" width="100" align="center" />
            <el-table-column label="迟到" width="80" align="center">
              <template #default="{ row }">
                <span :class="{ 'num-warn': row.late > 0 }">{{ row.late }}</span>
              </template>
            </el-table-column>
            <el-table-column label="早退" width="80" align="center">
              <template #default="{ row }">
                <span :class="{ 'num-warn': row.early > 0 }">{{ row.early }}</span>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { Clock, Download } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import client from '@/api/client'
import { useAuthStore } from '@/store/auth'
import { exportCsv } from '@/utils/export'

const authStore = useAuthStore()
const activeTab = ref('mine')
const clocking = ref(false)
const loading = ref(false)
const loadingDept = ref(false)
const month = ref(new Date().toISOString().slice(0, 7))
const records = ref<any[]>([])
const stats = ref({ days: 0, late: 0, early: 0 })
const deptRecords = ref<any[]>([])
const todayClockIn = ref(false)
const todayDone = ref(false)
const todayStatus = ref('')
const lastClockMessage = ref('')
const nowText = ref('')
const todayText = ref('')

let timer: number | undefined

const canViewDept = computed(() => {
  const r = authStore.user?.role_name || ''
  return r.includes('部门') || r.includes('总经理') || r.includes('超级')
})
const workRule = '09:00'
const offRule = '18:00'

function updateClockDisplay() {
  const d = new Date()
  nowText.value = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}:${String(d.getSeconds()).padStart(2, '0')}`
  todayText.value = d.toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' })
}

function statusLabel(s: string) {
  return ({ NORMAL: '正常', LATE: '迟到', EARLY: '早退', LATE_EARLY: '迟到且早退' } as any)[s] || s
}
function statusTagType(s: string) {
  return ({ NORMAL: 'success', LATE: 'warning', EARLY: 'warning', LATE_EARLY: 'danger' } as any)[s] || 'info'
}
function formatTime(t: string | null) {
  if (!t) return '—'
  return t.slice(11, 19)
}

async function handleClock() {
  clocking.value = true
  try {
    const res = await client.post('/attendance/clock')
    const d = res.data.data
    ElMessage.success(d.message)
    lastClockMessage.value = d.message
    todayStatus.value = d.status
    if (d.type === 'clock_in') todayClockIn.value = true
    if (d.type === 'clock_out') todayDone.value = true
    loadMine()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.message || '打卡失败')
  } finally {
    clocking.value = false
  }
}

async function loadMine() {
  loading.value = true
  try {
    const res = await client.get('/attendance/my', { params: { month: month.value } })
    const d = res.data.data
    records.value = d.items || []
    stats.value = d.stats || { days: 0, late: 0, early: 0 }
    // 今日状态回显
    const today = new Date().toISOString().slice(0, 10)
    const todayRec = records.value.find((r: any) => r.work_date === today)
    if (todayRec) {
      todayClockIn.value = !!todayRec.clock_in
      todayDone.value = !!todayRec.clock_out
      todayStatus.value = todayRec.status
    }
  } finally {
    loading.value = false
  }
}

async function loadDept() {
  loadingDept.value = true
  try {
    const res = await client.get('/admin/attendance', { params: { month: month.value } })
    deptRecords.value = res.data.data || []
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.message || '加载失败')
  } finally {
    loadingDept.value = false
  }
}

function exportMine() {
  exportCsv(
    `我的考勤-${month.value}`,
    ['日期', '上班打卡', '下班签退', '状态'],
    records.value.map((r: any) => [
      r.work_date,
      formatTime(r.clock_in),
      formatTime(r.clock_out),
      statusLabel(r.status),
    ])
  )
}

function exportDept() {
  exportCsv(
    `部门考勤汇总-${month.value}`,
    ['姓名', '部门', '打卡天数', '迟到', '早退'],
    deptRecords.value.map((r: any) => [
      r.real_name,
      r.dept_name || '未分配',
      r.days,
      r.late,
      r.early,
    ])
  )
}

onMounted(() => {
  updateClockDisplay()
  timer = window.setInterval(updateClockDisplay, 1000)
  loadMine()
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.oa-page { padding: 24px 32px; max-width: 1200px; margin: 0 auto; }
.page-header { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 20px; }
.header-left { display: flex; align-items: center; gap: 10px; }
.header-icon { color: var(--color-primary); }
.page-header h2 { font-size: 20px; font-weight: 700; color: var(--color-text-primary); margin: 0; }

.clock-card { border-radius: 12px; margin-bottom: 16px; }
.clock-row { display: flex; justify-content: space-between; align-items: center; }
.now-time { font-size: 40px; font-weight: 800; color: var(--color-text-primary); letter-spacing: 1px; }
.now-date { font-size: 13px; color: var(--color-text-secondary); margin-top: 2px; }
.clock-btn { min-width: 160px; height: 48px; font-size: 16px; font-weight: 700; border-radius: 12px; }
.clock-result { display: flex; align-items: center; gap: 10px; margin-top: 12px; }
.clock-tip { font-size: 13px; color: var(--color-text-secondary); }

.toolbar { display: flex; align-items: center; gap: 12px; margin-bottom: 14px; }

.att-stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 16px; }
.att-stat {
  text-align: center; padding: 14px; border-radius: 10px;
  border: 1px solid var(--color-border);
}
.att-num { font-size: 26px; font-weight: 800; color: var(--color-primary); }
.att-num.warn { color: #d97706; }
.att-label { font-size: 12px; color: var(--color-text-secondary); margin-top: 2px; }

.time-text { font-size: 13px; color: var(--color-text-body); }
.num-warn { color: #d97706; font-weight: 700; }
</style>
