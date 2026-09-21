<template>
  <div class="oa-page">
    <div class="page-header">
      <div class="header-left">
        <el-icon class="header-icon" :size="24"><Calendar /></el-icon>
        <h2>请假管理</h2>
      </div>
      <div class="header-actions">
        <el-button :icon="Download" plain :loading="exporting" @click="handleExport">导出</el-button>
        <el-button type="primary" :icon="Plus" @click="openSubmit">我要请假</el-button>
      </div>
    </div>

    <!-- 假期余额卡片 -->
    <div class="balance-row">
      <div class="balance-card" v-for="c in balanceCards" :key="c.label">
        <div class="balance-label">{{ c.label }}</div>
        <div class="balance-value">{{ c.value }}<span class="balance-unit">天</span></div>
        <div class="balance-sub">{{ c.sub }}</div>
      </div>
    </div>

    <el-card>
      <el-tabs v-model="statusFilter" @tab-change="loadList(1)">
        <el-tab-pane label="全部" name="" />
        <el-tab-pane label="待审批" name="PENDING" />
        <el-tab-pane label="已通过" name="APPROVED" />
        <el-tab-pane label="已驳回" name="REJECTED" />
        <el-tab-pane label="已撤销" name="CANCELLED" />
      </el-tabs>

      <el-table :data="bills" stripe v-loading="loading" empty-text="暂无请假记录">
        <el-table-column label="申请人" min-width="100">
          <template #default="{ row }">{{ row.applicant_name || '-' }}</template>
        </el-table-column>
        <el-table-column label="类型" width="90">
          <template #default="{ row }">
            <el-tag size="small" :type="LEAVE_TYPE_TAG[row.leave_type] || 'info'">{{ row.leave_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="起止日期" min-width="200">
          <template #default="{ row }">
            <span class="date-range">{{ row.start_date }} ~ {{ row.end_date }}</span>
          </template>
        </el-table-column>
        <el-table-column label="天数" width="80" align="center">
          <template #default="{ row }">{{ row.days }}</template>
        </el-table-column>
        <el-table-column prop="reason" label="事由" min-width="160" show-overflow-tooltip />
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="LEAVE_STATUS_LABELS[row.status]?.type || 'info'">
              {{ LEAVE_STATUS_LABELS[row.status]?.label || row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="当前节点" width="110" align="center">
          <template #default="{ row }">
            <span v-if="row.status === 'PENDING'">{{ NODE_LABELS[row.current_node] || row.current_node }}</span>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="申请时间" width="170">
          <template #default="{ row }"><span class="time-text">{{ formatTime(row.create_time) }}</span></template>
        </el-table-column>
        <el-table-column label="操作" width="180" align="center" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="openDetail(row)">详情</el-button>
            <el-button text type="primary" size="small" @click="printBill(row)">打印</el-button>
            <el-button
              v-if="row.status === 'PENDING' && row.user_id === authStore.user?.id"
              text type="danger" size="small"
              @click="handleCancel(row)"
            >撤销</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        class="oa-pager"
        background
        layout="total, prev, pager, next, sizes"
        :total="total"
        :page-sizes="[10, 20, 50]"
        :page-size="pageSize"
        :current-page="page"
        @current-change="loadList"
        @size-change="(s: number) => { pageSize = s; loadList(1) }"
      />
    </el-card>

    <!-- 提交请假对话框 -->
    <el-dialog v-model="submitVisible" title="我要请假" width="520px" destroy-on-close>
      <el-alert
        v-if="balance"
        type="info" :closable="false" class="balance-alert"
        :title="`当年余额：年假剩余 ${balance.annual_left} 天，调休剩余 ${balance.compensatory_left} 天，事假已用 ${balance.personal_used} 天`"
      />
      <el-form ref="submitFormRef" :model="submitForm" :rules="submitRules" label-width="90px">
        <el-form-item label="请假类型" prop="leave_type">
          <el-select v-model="submitForm.leave_type" placeholder="选择请假类型" style="width: 100%">
            <el-option v-for="t in LEAVE_TYPES" :key="t" :label="t" :value="t" />
          </el-select>
        </el-form-item>
        <el-form-item label="起止日期" prop="dates">
          <el-date-picker
            v-model="submitForm.dates"
            type="daterange"
            value-format="YYYY-MM-DD"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="请假事由">
          <el-input v-model="submitForm.reason" type="textarea" :rows="3" maxlength="500" show-word-limit placeholder="请假事由（选填）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="submitVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">提交申请</el-button>
      </template>
    </el-dialog>

    <!-- 详情对话框（含审批时间线） -->
    <el-dialog v-model="detailVisible" title="请假单详情" width="560px" destroy-on-close>
      <template v-if="detail">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="申请人">{{ detail.applicant_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="类型">{{ detail.leave_type }}</el-descriptions-item>
          <el-descriptions-item label="起止日期">{{ detail.start_date }} ~ {{ detail.end_date }}</el-descriptions-item>
          <el-descriptions-item label="天数">{{ detail.days }} 天</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag size="small" :type="LEAVE_STATUS_LABELS[detail.status]?.type || 'info'">
              {{ LEAVE_STATUS_LABELS[detail.status]?.label || detail.status }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="事由" :span="2">{{ detail.reason || '-' }}</el-descriptions-item>
        </el-descriptions>

        <div class="timeline-title">审批进度</div>
        <el-timeline v-if="detail.records?.length" class="oa-timeline">
          <el-timeline-item
            v-for="r in detail.records"
            :key="r.create_time + r.node_name"
            :type="r.action_type === 'APPROVE' ? 'success' : 'danger'"
            :hollow="false"
          >
            <div class="timeline-head">
              <span class="timeline-actor">{{ r.approver_name || r.approver_role }}</span>
              <el-tag size="small" :type="r.action_type === 'APPROVE' ? 'success' : 'danger'" effect="plain">
                {{ r.action_type === 'APPROVE' ? '通过' : '驳回' }}
              </el-tag>
              <span class="timeline-node">{{ NODE_LABELS[r.node_name] }}</span>
            </div>
            <div class="timeline-comment" v-if="r.comment_text">意见：{{ r.comment_text }}</div>
            <div class="timeline-time">{{ formatTime(r.create_time) }}</div>
          </el-timeline-item>
        </el-timeline>
        <el-empty v-else description="暂无审批记录" :image-size="60" />
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { Calendar, Plus, Download } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { workflowApi, LEAVE_STATUS_LABELS, NODE_LABELS, LEAVE_TYPE_TAG, type BillItem, type BillDetail, type LeaveBalance } from '@/api/workflow'
import { useAuthStore } from '@/store/auth'
import { exportCsv } from '@/utils/export'
import { printForm, escapeHtml } from '@/utils/print'

const authStore = useAuthStore()

const LEAVE_TYPES = ['年假', '事假', '病假', '调休', '婚假']

const loading = ref(false)
const exporting = ref(false)
const bills = ref<BillItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)
const statusFilter = ref('')

const balance = ref<LeaveBalance | null>(null)
const balanceCards = computed(() => {
  if (!balance.value) return []
  const b = balance.value
  return [
    { label: '年假剩余', value: b.annual_left, sub: `总额 ${b.annual_total} 天 · 已用 ${b.annual_used} 天` },
    { label: '调休剩余', value: b.compensatory_left, sub: `总额 ${b.compensatory_total} 天` },
    { label: '已用事假', value: b.personal_used, sub: '事假将扣薪' },
    { label: '已用病假', value: b.sick_used, sub: '按病假规定执行' },
  ]
})

// 提交表单
const submitVisible = ref(false)
const submitting = ref(false)
const submitFormRef = ref<FormInstance>()
const submitForm = reactive({
  leave_type: '',
  dates: [] as string[],
  reason: '',
})
const submitRules: FormRules = {
  leave_type: [{ required: true, message: '请选择请假类型', trigger: 'change' }],
  dates: [{ required: true, type: 'array', min: 2, message: '请选择起止日期', trigger: 'change' }],
}

// 详情
const detailVisible = ref(false)
const detail = ref<BillDetail | null>(null)

async function loadBalance() {
  try {
    const res = await workflowApi.getBalance()
    balance.value = res.data.data
  } catch { /* 余额加载失败不阻塞页面 */ }
}

async function loadList(p?: number) {
  if (typeof p === 'number') page.value = p
  loading.value = true
  try {
    const res = await workflowApi.listLeaves({
      page: page.value,
      page_size: pageSize.value,
      status: statusFilter.value || undefined,
    })
    bills.value = res.data.data?.items || []
    total.value = res.data.data?.total || 0
  } finally {
    loading.value = false
  }
}

async function handleExport() {
  exporting.value = true
  try {
    // 分页拉全量（按当前状态筛选、沿用后端按角色的数据范围）
    const size = 100
    let p = 1
    let all: BillItem[] = []
    while (true) {
      const res = await workflowApi.listLeaves({
        page: p,
        page_size: size,
        status: statusFilter.value || undefined,
      })
      const items: BillItem[] = res.data.data?.items || []
      all = all.concat(items)
      if (items.length < size) break
      p++
    }
    exportCsv(
      `请假记录-${new Date().toISOString().slice(0, 10)}`,
      ['申请人', '类型', '开始日期', '结束日期', '天数', '事由', '状态', '申请时间'],
      all.map((r) => [
        r.applicant_name || '-',
        r.leave_type || '',
        r.start_date || '',
        r.end_date || '',
        r.days ?? '',
        r.reason || '',
        LEAVE_STATUS_LABELS[r.status]?.label || r.status,
        formatTime(r.create_time),
      ])
    )
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.message || '导出失败')
  } finally {
    exporting.value = false
  }
}

function printBill(row: BillItem) {
  const days = row.days != null ? `${row.days} 天` : ''
  const body = `
    <div class="form-no">单据编号：NO.${row.id}</div>
    <table>
      <tr>
        <td class="label">申请人</td><td>${escapeHtml(row.applicant_name)}</td>
        <td class="label">所在部门</td><td class="blank"></td>
      </tr>
      <tr>
        <td class="label">请假类型</td><td>${escapeHtml(row.leave_type)}</td>
        <td class="label">请假天数</td><td>${days}</td>
      </tr>
      <tr>
        <td class="label">起止日期</td><td colspan="3">${escapeHtml(row.start_date)} 至 ${escapeHtml(row.end_date)}</td>
      </tr>
      <tr>
        <td class="label">请假事由</td><td colspan="3" class="fill">${escapeHtml(row.reason)}</td>
      </tr>
    </table>
    <table class="approval">
      <tr><td class="section" colspan="3">审批意见</td></tr>
      <tr><td class="label">部门经理</td><td>意见：</td><td class="sign">签字：<br>日期：　　年　　月　　日</td></tr>
      <tr><td class="label">总经理</td><td>意见：</td><td class="sign">签字：<br>日期：　　年　　月　　日</td></tr>
    </table>
    <div class="note">备注：1. 本单一式两联，第一联交人事行政存档，第二联由申请人留存。<br>　　　2. 请假应提前办理审批手续，获批后方可休假。</div>
  `
  printForm('员工请假申请单', body)
}

function openSubmit() {
  submitForm.leave_type = ''
  submitForm.dates = []
  submitForm.reason = ''
  submitVisible.value = true
}

async function handleSubmit() {
  await submitFormRef.value?.validate()
  submitting.value = true
  try {
    const res = await workflowApi.submitLeave({
      leave_type: submitForm.leave_type,
      start_date: submitForm.dates[0],
      end_date: submitForm.dates[1],
      reason: submitForm.reason || undefined,
    })
    const data = res.data.data
    ElMessage.success(data?.status === 'APPROVED' ? '申请已提交（免审直接通过）' : '申请已提交，等待审批')
    submitVisible.value = false
    loadList(1)
    loadBalance()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.message || '提交失败')
  } finally {
    submitting.value = false
  }
}

async function openDetail(row: BillItem) {
  try {
    const res = await workflowApi.getLeave(row.id)
    detail.value = res.data.data
    detailVisible.value = true
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.message || '加载失败')
  }
}

async function handleCancel(row: BillItem) {
  try {
    await ElMessageBox.confirm('确定撤销该请假申请吗？', '撤销确认', { type: 'warning' })
    await workflowApi.cancelLeave(row.id)
    ElMessage.success('已撤销')
    loadList()
    loadBalance()
  } catch (e: any) {
    if (e !== 'cancel') ElMessage.error(e?.response?.data?.message || '撤销失败')
  }
}

function formatTime(t: string) {
  if (!t) return '-'
  const d = new Date(t.endsWith('Z') ? t : t + 'Z')
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

onMounted(() => {
  loadList()
  loadBalance()
})
</script>

<style scoped>
.oa-page { padding: 24px 32px; max-width: 1200px; margin: 0 auto; }
.page-header { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 20px; }
.header-left { display: flex; align-items: center; gap: 10px; }
.header-actions { display: flex; align-items: center; gap: 12px; }
.header-icon { color: var(--color-primary); }
.page-header h2 { font-size: 20px; font-weight: 700; color: var(--color-text-primary); margin: 0; }

/* 余额卡片 */
.balance-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 16px; }
.balance-card {
  background: var(--color-bg-card, #fff);
  border: 1px solid var(--color-border);
  border-radius: 10px;
  padding: 14px 16px;
}
.balance-label { font-size: 13px; color: var(--color-text-secondary); }
.balance-value { font-size: 26px; font-weight: 700; color: var(--color-primary); margin: 4px 0; }
.balance-unit { font-size: 13px; font-weight: 400; margin-left: 2px; color: var(--color-text-secondary); }
.balance-sub { font-size: 12px; color: var(--color-text-placeholder); }

.date-range { font-size: 13px; color: var(--color-text-body); }
.time-text { font-size: 13px; color: var(--color-text-secondary); }
.muted { color: var(--color-text-placeholder); }

.oa-pager { margin-top: 16px; justify-content: flex-end; }

.balance-alert { margin-bottom: 14px; }

.timeline-title { font-size: 14px; font-weight: 600; color: var(--color-text-primary); margin: 18px 0 10px; }
.oa-timeline { padding-left: 4px; }
.timeline-head { display: flex; align-items: center; gap: 8px; }
.timeline-actor { font-weight: 600; font-size: 13px; color: var(--color-text-primary); }
.timeline-node { font-size: 12px; color: var(--color-text-secondary); }
.timeline-comment { font-size: 13px; color: var(--color-text-body); margin-top: 2px; }
.timeline-time { font-size: 12px; color: var(--color-text-placeholder); margin-top: 2px; }
</style>
