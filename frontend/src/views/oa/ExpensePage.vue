<template>
  <div class="oa-page">
    <div class="page-header">
      <div class="header-left">
        <el-icon class="header-icon" :size="24"><Money /></el-icon>
        <h2>报销管理</h2>
      </div>
      <div class="header-actions">
        <el-button :icon="Download" plain :loading="exporting" @click="handleExport">导出</el-button>
        <el-button type="primary" :icon="Plus" @click="openSubmit">我要报销</el-button>
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

      <el-table :data="bills" stripe v-loading="loading" empty-text="暂无报销记录">
        <el-table-column label="申请人" min-width="100">
          <template #default="{ row }">{{ row.applicant_name || '-' }}</template>
        </el-table-column>
        <el-table-column label="类型" width="100">
          <template #default="{ row }">{{ row.expense_type }}</template>
        </el-table-column>
        <el-table-column label="金额（元）" width="120" align="right">
          <template #default="{ row }">
            <span class="amount-text">¥{{ row.amount?.toFixed(2) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="发生日期" width="120">
          <template #default="{ row }">{{ row.expense_date }}</template>
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

    <!-- 提交报销对话框 -->
    <el-dialog v-model="submitVisible" title="我要报销" width="560px" destroy-on-close>
      <el-form ref="submitFormRef" :model="submitForm" :rules="submitRules" label-width="90px">
        <el-form-item label="报销类型" prop="expense_type">
          <el-select v-model="submitForm.expense_type" placeholder="选择报销类型" style="width: 100%">
            <el-option v-for="t in EXPENSE_TYPES" :key="t" :label="t" :value="t" />
          </el-select>
        </el-form-item>
        <el-form-item label="报销金额" prop="amount">
          <el-input-number
            v-model="submitForm.amount"
            :min="0.01" :max="999999" :precision="2" :step="100"
            controls-position="right"
            style="width: 100%"
            placeholder="报销金额（元）"
          />
        </el-form-item>
        <el-form-item label="发生日期" prop="expense_date">
          <el-date-picker
            v-model="submitForm.expense_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="费用发生日期"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="报销事由">
          <el-input v-model="submitForm.reason" type="textarea" :rows="3" maxlength="500" show-word-limit placeholder="报销事由（选填）" />
        </el-form-item>
        <el-form-item label="发票凭证">
          <el-upload
            :auto-upload="true"
            :show-file-list="true"
            :limit="6"
            :http-request="doUpload"
            :before-upload="beforeUpload"
            list-type="picture-card"
            accept=".jpg,.jpeg,.png,.webp,.pdf"
            class="expense-upload"
          >
            <el-icon :size="22"><Plus /></el-icon>
            <div class="upload-text">上传凭证</div>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="submitVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">提交申请</el-button>
      </template>
    </el-dialog>

    <!-- 详情对话框（含审批时间线与凭证） -->
    <el-dialog v-model="detailVisible" title="报销单详情" width="560px" destroy-on-close>
      <template v-if="detail">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="申请人">{{ detail.applicant_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="类型">{{ detail.expense_type }}</el-descriptions-item>
          <el-descriptions-item label="金额">¥{{ detail.amount?.toFixed(2) }}</el-descriptions-item>
          <el-descriptions-item label="发生日期">{{ detail.expense_date }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag size="small" :type="LEAVE_STATUS_LABELS[detail.status]?.type || 'info'">
              {{ LEAVE_STATUS_LABELS[detail.status]?.label || detail.status }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="事由" :span="2">{{ detail.reason || '-' }}</el-descriptions-item>
        </el-descriptions>

        <div v-if="attachUrls.length" class="attach-title">发票凭证</div>
        <div v-if="attachUrls.length" class="attach-row">
          <el-image
            v-for="(a, i) in attachUrls"
            :key="i"
            :src="a"
            :preview-src-list="attachUrls"
            :initial-index="i"
            fit="cover"
            class="attach-thumb"
          />
        </div>

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
import { ref, reactive, onMounted } from 'vue'
import { Money, Plus, Download } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules, type UploadRequestOptions } from 'element-plus'
import { workflowApi, LEAVE_STATUS_LABELS, NODE_LABELS, type BillItem, type BillDetail } from '@/api/workflow'
import { useAuthStore } from '@/store/auth'
import { exportCsv } from '@/utils/export'
import { printForm, escapeHtml, amountInChinese } from '@/utils/print'
import client from '@/api/client'

const authStore = useAuthStore()

const EXPENSE_TYPES = ['差旅费', '办公用品', '招待费', '交通费', '其他']

const loading = ref(false)
const exporting = ref(false)
const bills = ref<BillItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)
const statusFilter = ref('')

// 提交表单
const submitVisible = ref(false)
const submitting = ref(false)
const submitFormRef = ref<FormInstance>()
const submitForm = reactive({
  expense_type: '',
  amount: 0,
  expense_date: '',
  reason: '',
})
const uploadedPaths = ref<string[]>([])
const submitRules: FormRules = {
  expense_type: [{ required: true, message: '请选择报销类型', trigger: 'change' }],
  amount: [{ required: true, message: '请输入报销金额', trigger: 'blur' }],
  expense_date: [{ required: true, message: '请选择费用发生日期', trigger: 'change' }],
}

// 详情
const detailVisible = ref(false)
const detail = ref<BillDetail | null>(null)
const attachUrls = ref<string[]>([])

// 凭证经鉴权接口下载：用 axios（携带 Token）取 blob 后转 objectURL 展示
async function loadAttachments(paths: string[]) {
  attachUrls.value = []
  for (const p of paths) {
    if (p.startsWith('/static/')) {
      // 历史数据：旧路径仍在 /static 公开挂载下，直接引用
      attachUrls.value.push(p)
      continue
    }
    try {
      const res = await client.get(p, { responseType: 'blob' })
      attachUrls.value.push(URL.createObjectURL(res.data))
    } catch {
      attachUrls.value.push('')
    }
  }
}

function beforeUpload(file: File) {
  const ext = file.name.split('.').pop()?.toLowerCase() || ''
  if (!['jpg', 'jpeg', 'png', 'webp', 'pdf'].includes(ext)) {
    ElMessage.error('仅支持 jpg/png/webp/pdf 格式')
    return false
  }
  if (file.size > 5 * 1024 * 1024) {
    ElMessage.error('凭证大小不能超过 5MB')
    return false
  }
  return true
}

async function doUpload(options: UploadRequestOptions) {
  try {
    const res = await workflowApi.uploadExpenseAttachment(options.file as File)
    uploadedPaths.value.push(res.data.data?.path || '')
    options.onSuccess?.(res)
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.message || '上传失败')
    options.onError?.(e)
  }
}

async function loadList(p?: number) {
  if (typeof p === 'number') page.value = p
  loading.value = true
  try {
    const res = await workflowApi.listExpenses({
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
      const res = await workflowApi.listExpenses({
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
      `报销记录-${new Date().toISOString().slice(0, 10)}`,
      ['申请人', '类型', '金额（元）', '发生日期', '事由', '状态', '申请时间'],
      all.map((r) => [
        r.applicant_name || '-',
        r.expense_type || '',
        r.amount != null ? r.amount.toFixed(2) : '',
        r.expense_date || '',
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
  const amount = row.amount != null ? `¥${row.amount.toFixed(2)}` : ''
  const amountUpper = row.amount != null ? amountInChinese(row.amount) : ''
  const body = `
    <div class="form-no">单据编号：NO.${row.id}</div>
    <table>
      <tr>
        <td class="label">报销人</td><td>${escapeHtml(row.applicant_name)}</td>
        <td class="label">所在部门</td><td class="blank"></td>
      </tr>
      <tr>
        <td class="label">报销类型</td><td>${escapeHtml(row.expense_type)}</td>
        <td class="label">发生日期</td><td>${escapeHtml(row.expense_date)}</td>
      </tr>
      <tr>
        <td class="label">报销金额</td><td colspan="3">小写：${amount}　　大写：${amountUpper}</td>
      </tr>
      <tr>
        <td class="label">报销事由</td><td colspan="3" class="fill">${escapeHtml(row.reason)}</td>
      </tr>
    </table>
    <table class="approval">
      <tr><td class="section" colspan="6">审批意见</td></tr>
      <tr>
        <td class="label">部门经理</td><td>意见：</td><td class="sign">签字：<br>日期：　　年　　月　　日</td>
        <td class="label">财务审核</td><td>意见：</td><td class="sign">签字：<br>日期：　　年　　月　　日</td>
      </tr>
      <tr>
        <td class="label">总经理</td><td colspan="2">意见：</td><td class="sign" colspan="3">签字：<br>日期：　　年　　月　　日</td>
      </tr>
    </table>
    <div class="note">备注：1. 本单一式两联，报账时须附原始发票及相关凭证。<br>　　　2. 经审批通过并交财务审核后，方可办理报销付款。</div>
  `
  printForm('费用报销单', body)
}

function openSubmit() {
  submitForm.expense_type = ''
  submitForm.amount = 0
  submitForm.expense_date = ''
  submitForm.reason = ''
  uploadedPaths.value = []
  submitVisible.value = true
}

async function handleSubmit() {
  await submitFormRef.value?.validate()
  submitting.value = true
  try {
    const res = await workflowApi.submitExpense({
      expense_type: submitForm.expense_type,
      amount: submitForm.amount,
      expense_date: submitForm.expense_date,
      reason: submitForm.reason || undefined,
      attachments: uploadedPaths.value.length ? uploadedPaths.value : undefined,
    })
    const data = res.data.data
    ElMessage.success(data?.status === 'APPROVED' ? '申请已提交（免审直接通过）' : '申请已提交，等待审批')
    submitVisible.value = false
    loadList(1)
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.message || '提交失败')
  } finally {
    submitting.value = false
  }
}

async function openDetail(row: BillItem) {
  try {
    const res = await workflowApi.getExpense(row.id)
    const data: BillDetail = res.data.data
    detail.value = data
    detailVisible.value = true
    if (data.attachments?.length) {
      loadAttachments(data.attachments)
    } else {
      attachUrls.value = []
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.message || '加载失败')
  }
}

async function handleCancel(row: BillItem) {
  try {
    await ElMessageBox.confirm('确定撤销该报销申请吗？', '撤销确认', { type: 'warning' })
    await workflowApi.cancelExpense(row.id)
    ElMessage.success('已撤销')
    loadList()
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

onMounted(loadList)
</script>

<style scoped>
.oa-page { padding: 24px 32px; max-width: 1200px; margin: 0 auto; }
.page-header { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 20px; }
.header-left { display: flex; align-items: center; gap: 10px; }
.header-actions { display: flex; align-items: center; gap: 12px; }
.header-icon { color: var(--color-primary); }
.page-header h2 { font-size: 20px; font-weight: 700; color: var(--color-text-primary); margin: 0; }

.amount-text { font-weight: 600; color: var(--color-primary); font-size: 14px; }
.time-text { font-size: 13px; color: var(--color-text-secondary); }
.muted { color: var(--color-text-placeholder); }

.oa-pager { margin-top: 16px; justify-content: flex-end; }

.expense-upload :deep(.el-upload--picture-card) { width: 86px; height: 86px; }
.upload-text { font-size: 11px; color: var(--color-text-secondary); }

.attach-title { font-size: 14px; font-weight: 600; color: var(--color-text-primary); margin: 18px 0 10px; }
.attach-row { display: flex; flex-wrap: wrap; gap: 10px; }
.attach-thumb { width: 96px; height: 96px; border-radius: 8px; border: 1px solid var(--color-border); }

.timeline-title { font-size: 14px; font-weight: 600; color: var(--color-text-primary); margin: 18px 0 10px; }
.oa-timeline { padding-left: 4px; }
.timeline-head { display: flex; align-items: center; gap: 8px; }
.timeline-actor { font-weight: 600; font-size: 13px; color: var(--color-text-primary); }
.timeline-node { font-size: 12px; color: var(--color-text-secondary); }
.timeline-comment { font-size: 13px; color: var(--color-text-body); margin-top: 2px; }
.timeline-time { font-size: 12px; color: var(--color-text-placeholder); margin-top: 2px; }
</style>
