<template>
  <div class="oa-page">
    <div class="page-header">
      <div class="header-left">
        <el-icon class="header-icon" :size="24"><Stamp /></el-icon>
        <h2>审批中心</h2>
        <el-tag v-if="todoTotal > 0" size="small" round type="warning">{{ todoTotal }} 项待办</el-tag>
      </div>
    </div>

    <el-card>
      <el-tabs v-model="activeTab" @tab-change="onTabChange">
        <!-- 待办 Tab -->
        <el-tab-pane label="我的待办" name="todo">
          <el-table :data="todoItems" stripe v-loading="loading" empty-text="暂无待审批单据">
            <el-table-column label="类型" width="90" align="center">
              <template #default="{ row }">
                <el-tag size="small" :type="row.biz_type === 'LEAVE' ? 'primary' : 'success'">
                  {{ row.biz_type === 'LEAVE' ? '请假' : '报销' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="申请人" min-width="110">
              <template #default="{ row }">{{ row.applicant_name || '-' }}</template>
            </el-table-column>
            <el-table-column label="申请内容" min-width="220">
              <template #default="{ row }">
                <span v-if="row.biz_type === 'LEAVE'">
                  {{ row.leave_type }} · {{ row.start_date }} ~ {{ row.end_date }} · {{ row.days }} 天
                </span>
                <span v-else>
                  {{ row.expense_type }} · ¥{{ row.amount?.toFixed(2) }} · {{ row.expense_date }}
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="reason" label="事由" min-width="150" show-overflow-tooltip />
            <el-table-column label="当前节点" width="110" align="center">
              <template #default="{ row }">
                <el-tag size="small" type="warning" effect="plain">{{ NODE_LABELS[row.current_node] || row.current_node }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="提交时间" width="165">
              <template #default="{ row }"><span class="time-text">{{ formatTime(row.create_time) }}</span></template>
            </el-table-column>
            <el-table-column label="操作" width="170" align="center" fixed="right">
              <template #default="{ row }">
                <el-button text type="success" size="small" @click="openApprove(row, 'APPROVE')">通过</el-button>
                <el-button text type="danger" size="small" @click="openApprove(row, 'REJECT')">驳回</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- 已办 Tab -->
        <el-tab-pane label="我的已办" name="done">
          <el-table :data="doneItems" stripe v-loading="loadingDone" empty-text="暂无审批记录">
            <el-table-column label="业务类型" width="90" align="center">
              <template #default="{ row }">
                <el-tag size="small" :type="row.biz_type === 'LEAVE' ? 'primary' : 'success'">
                  {{ row.biz_type === 'LEAVE' ? '请假' : '报销' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="单据编号" width="100" align="center">
              <template #default="{ row }">#{{ row.biz_id }}</template>
            </el-table-column>
            <el-table-column label="节点" width="110" align="center">
              <template #default="{ row }">{{ NODE_LABELS[row.node_name] || row.node_name }}</template>
            </el-table-column>
            <el-table-column label="动作" width="90" align="center">
              <template #default="{ row }">
                <el-tag size="small" :type="row.action_type === 'APPROVE' ? 'success' : 'danger'">
                  {{ row.action_type === 'APPROVE' ? '通过' : '驳回' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="comment_text" label="审批意见" min-width="180" show-overflow-tooltip>
              <template #default="{ row }">{{ row.comment_text || '-' }}</template>
            </el-table-column>
            <el-table-column label="审批时间" width="165">
              <template #default="{ row }"><span class="time-text">{{ formatTime(row.create_time) }}</span></template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 审批对话框 -->
    <el-dialog v-model="approveVisible" :title="approveAction === 'APPROVE' ? '审批通过' : '审批驳回'" width="480px" destroy-on-close>
      <template v-if="currentBill">
        <el-alert
          v-if="approveAction === 'APPROVE' && currentBill.biz_type === 'LEAVE' && (currentBill.days || 0) > 3"
          type="warning" :closable="false" class="approve-alert"
          title="该请假超过 3 天，通过后将转交总经理终审"
        />
        <el-alert
          v-if="approveAction === 'APPROVE' && currentBill.biz_type === 'EXPENSE' && (currentBill.amount || 0) > 5000"
          type="warning" :closable="false" class="approve-alert"
          title="该报销超过 5000 元，通过后将转交总经理终审"
        />
        <el-form label-width="80px">
          <el-form-item label="审批意见">
            <el-input
              v-model="approveComment"
              type="textarea"
              :rows="3"
              maxlength="500"
              show-word-limit
              :placeholder="approveAction === 'APPROVE' ? '审批意见（选填）' : '请填写驳回原因（选填）'"
            />
          </el-form-item>
        </el-form>
      </template>
      <template #footer>
        <el-button @click="approveVisible = false">取消</el-button>
        <el-button :type="approveAction === 'APPROVE' ? 'success' : 'danger'" :loading="approving" @click="handleApprove">
          {{ approveAction === 'APPROVE' ? '确认通过' : '确认驳回' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Stamp } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { workflowApi, NODE_LABELS, type BillItem } from '@/api/workflow'

const activeTab = ref('todo')
const loading = ref(false)
const loadingDone = ref(false)
const todoItems = ref<BillItem[]>([])
const todoTotal = ref(0)
const doneItems = ref<any[]>([])
const doneTotal = ref(0)
const donePage = ref(1)
const donePageSize = ref(10)

const approveVisible = ref(false)
const approving = ref(false)
const approveAction = ref<'APPROVE' | 'REJECT'>('APPROVE')
const approveComment = ref('')
const currentBill = ref<BillItem | null>(null)

async function loadTodo() {
  loading.value = true
  try {
    const res = await workflowApi.getTodo({ page: 1, page_size: 100 })
    todoItems.value = res.data.data?.items || []
    todoTotal.value = todoItems.value.length
  } finally {
    loading.value = false
  }
}

async function loadDone() {
  loadingDone.value = true
  try {
    const res = await workflowApi.getDone({ page: donePage.value, page_size: donePageSize.value })
    doneItems.value = res.data.data?.items || []
    doneTotal.value = res.data.data?.total || 0
  } finally {
    loadingDone.value = false
  }
}

function onTabChange(name: string | number) {
  if (name === 'done') loadDone()
}

function openApprove(row: BillItem, action: 'APPROVE' | 'REJECT') {
  currentBill.value = row
  approveAction.value = action
  approveComment.value = ''
  approveVisible.value = true
}

async function handleApprove() {
  if (!currentBill.value) return
  approving.value = true
  try {
    const res = await workflowApi.approve(currentBill.value.biz_type, currentBill.value.id, {
      action: approveAction.value,
      comment: approveComment.value || undefined,
    })
    const data = res.data.data
    let msg = approveAction.value === 'APPROVE' ? '已通过' : '已驳回'
    if (approveAction.value === 'APPROVE' && data?.current_node === 'BOSS') {
      msg += '，已转交总经理终审'
    }
    ElMessage.success(msg)
    approveVisible.value = false
    loadTodo()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.message || '审批失败')
  } finally {
    approving.value = false
  }
}

function formatTime(t: string) {
  if (!t) return '-'
  const d = new Date(t.endsWith('Z') ? t : t + 'Z')
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

onMounted(loadTodo)
</script>

<style scoped>
.oa-page { padding: 24px 32px; max-width: 1200px; margin: 0 auto; }
.page-header { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 20px; }
.header-left { display: flex; align-items: center; gap: 10px; }
.header-icon { color: var(--color-primary); }
.page-header h2 { font-size: 20px; font-weight: 700; color: var(--color-text-primary); margin: 0; }

.time-text { font-size: 13px; color: var(--color-text-secondary); }
.approve-alert { margin-bottom: 14px; }
</style>
