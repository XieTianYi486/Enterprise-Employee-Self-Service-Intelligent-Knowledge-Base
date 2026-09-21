<template>
  <div class="page">
    <div class="page-header">
      <div class="header-left">
        <el-icon class="header-icon" :size="22"><Checked /></el-icon>
        <h2>知识审核</h2>
      </div>
      <div class="tabs">
        <el-radio-group v-model="reviewStatus" @change="() => { page = 1; selection = []; load() }">
          <el-radio-button :value="1">待审核</el-radio-button>
          <el-radio-button :value="2">已通过</el-radio-button>
          <el-radio-button :value="3">已驳回</el-radio-button>
          <el-radio-button :value="0">草稿</el-radio-button>
        </el-radio-group>
      </div>
    </div>

    <el-alert
      class="tip-alert"
      type="info"
      :closable="false"
      show-icon
      title="知识发布流：文档上传后默认进入「待审核」，审核通过后才会被检索与问答引用；被驳回的文档可修改后重新提交。"
    />

    <el-card class="table-card" shadow="never">
      <template #header>
        <div class="card-header">
          <span>审核队列（共 {{ total }} 条）</span>
          <div v-if="selection.length" class="batch-bar">
            <el-tag size="small" type="warning">已选 {{ selection.length }} 条</el-tag>
            <el-button size="small" type="primary" :icon="Select" @click="batchApprove">批量为通过</el-button>
            <el-button size="small" type="danger" :icon="Close" @click="batchReject">批量为驳回</el-button>
            <el-button size="small" text @click="selection = []">取消选择</el-button>
          </div>
        </div>
      </template>

      <el-table
        v-loading="loading"
        :data="list"
        style="width: 100%"
        @selection-change="(rows: any[]) => selection = rows"
      >
        <el-table-column v-if="reviewStatus === 1" type="selection" width="46" />
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="title" label="标题" min-width="170">
          <template #default="{ row }">
            <span class="doc-title">{{ row.title || row.file_name }}</span>
          </template>
        </el-table-column>
        <el-table-column label="分类" width="120">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ row.category_name || '未分类' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="security_level" label="密级" width="90">
          <template #default="{ row }">{{ levelText(row.security_level) }}</template>
        </el-table-column>
        <el-table-column prop="file_type" label="类型" width="80" />
        <el-table-column prop="chunk_count" label="切片" width="70" align="center" />
        <el-table-column prop="created_at" label="上传时间" width="160">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="审核意见" min-width="130">
          <template #default="{ row }">{{ row.review_comment || '—' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="230" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text type="info" :icon="View" @click="preview(row)">预览</el-button>
            <template v-if="row.review_status === 1">
              <el-button size="small" text type="success" @click="doReview(row, 'approve')">通过</el-button>
              <el-button size="small" text type="danger" @click="openReject(row)">驳回</el-button>
              <el-button size="small" text @click="doReview(row, 'recall')">撤回</el-button>
            </template>
            <template v-else-if="row.review_status === 3">
              <el-button size="small" text type="primary" @click="doReview(row, 'submit')">重新提交</el-button>
            </template>
            <template v-else-if="row.review_status === 0">
              <el-button size="small" text type="primary" @click="doReview(row, 'submit')">提交审核</el-button>
              <el-button size="small" text type="danger" @click="onDelete(row)">删除</el-button>
            </template>
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

    <!-- 驳回意见 -->
    <el-dialog v-model="rejectVisible" title="驳回文档" width="460px">
      <el-input
        v-model="rejectComment"
        type="textarea"
        :rows="4"
        placeholder="请填写驳回原因（可选）"
      />
      <template #footer>
        <el-button @click="rejectVisible = false">取消</el-button>
        <el-button type="danger" :loading="submitting" @click="confirmReject(rejectTarget, false)">确认驳回</el-button>
      </template>
    </el-dialog>

    <!-- 批量驳回意见 -->
    <el-dialog v-model="batchRejectVisible" title="批量驳回文档" width="460px">
      <el-input
        v-model="rejectComment"
        type="textarea"
        :rows="4"
        placeholder="请填写驳回原因（可选，将应用到所选文档）"
      />
      <template #footer>
        <el-button @click="batchRejectVisible = false">取消</el-button>
        <el-button type="danger" :loading="submitting" @click="confirmReject(null, true)">确认驳回 {{ selection.length }} 条</el-button>
      </template>
    </el-dialog>

    <!-- 预览抽屉 -->
    <el-drawer v-model="previewVisible" :title="previewTitle" size="60%">
      <div v-loading="previewLoading" class="preview-body">
        <el-empty v-if="!previewLoading && !previewContent" description="暂无法读取文档内容" />
        <pre v-if="previewContent" class="preview-text">{{ previewContent }}</pre>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Checked, Select, Close, View } from '@element-plus/icons-vue'
import { reviewApi } from '@/api/security'
import client from '@/api/client'

const loading = ref(false)
const list = ref<any[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const reviewStatus = ref(1)
const selection = ref<any[]>([])

const rejectVisible = ref(false)
const rejectComment = ref('')
const rejectTarget = ref<any>(null)
const batchRejectVisible = ref(false)
const submitting = ref(false)

const previewVisible = ref(false)
const previewLoading = ref(false)
const previewContent = ref('')
const previewTitle = ref('')

function levelText(l: number) {
  return { 1: '公开', 2: '内部', 3: '机密', 4: '绝密' }[l] || '内部'
}
function formatTime(t: string) {
  if (!t) return '—'
  const d = new Date(t.endsWith('Z') ? t : t + 'Z')
  return d.toLocaleString('zh-CN', { hour12: false })
}

async function load() {
  loading.value = true
  try {
    const res = await reviewApi.queue({
      page: page.value, page_size: pageSize, review_status: reviewStatus.value,
    })
    const data = res.data.data
    list.value = data.items || []
    total.value = data.total || 0
  } finally {
    loading.value = false
  }
}

async function doReview(row: any, action: 'approve' | 'reject' | 'submit' | 'recall') {
  if (action === 'approve') {
    await ElMessageBox.confirm(`确认通过文档「${row.title || row.file_name}」并发布？`, '审核确认', { type: 'warning' })
  }
  submitting.value = true
  try {
    const res = await reviewApi.review(row.id, { action })
    ElMessage.success(res.data.message || '操作成功')
    load()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.message || '操作失败')
  } finally {
    submitting.value = false
  }
}

function openReject(row: any) {
  rejectTarget.value = row
  rejectComment.value = ''
  rejectVisible.value = true
}

function batchReject() {
  if (!selection.value.length) {
    ElMessage.warning('请先选择文档')
    return
  }
  rejectComment.value = ''
  batchRejectVisible.value = true
}

function batchApprove() {
  if (!selection.value.length) {
    ElMessage.warning('请先选择文档')
    return
  }
  ElMessageBox.confirm(`确定通过所选 ${selection.value.length} 篇文档？`, '批量通过', { type: 'warning' })
    .then(async () => {
      subscribing()
      try {
        const res = await reviewApi.batchReview({
          action: 'approve',
          ids: selection.value.map((r) => r.id),
        })
        ElMessage.success(res.data.message || '已批量通过')
        selection.value = []
        load()
      } catch (e: any) {
        ElMessage.error(e?.response?.data?.message || '操作失败')
      } finally {
        subscribing()
      }
    })
    .catch(() => {})
}

function subscribing() { submitting.value = !submitting.value }

async function confirmReject(target: any, batch: boolean) {
  submitting.value = true
  try {
    if (batch) {
      await reviewApi.batchReview({
        action: 'reject',
        ids: selection.value.map((r) => r.id),
        comment: rejectComment.value || undefined,
      })
      selection.value = []
      batchRejectVisible.value = false
    } else {
      await reviewApi.review(target.id, { action: 'reject', comment: rejectComment.value || undefined })
      rejectVisible.value = false
    }
    ElMessage.success('已驳回')
    load()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.message || '操作失败')
  } finally {
    submitting.value = false
  }
}

async function preview(row: any) {
  previewTitle.value = row.title || row.file_name
  previewContent.value = ''
  previewVisible.value = true
  previewLoading.value = true
  try {
    const res = await client.get(`/documents/${row.id}/content`)
    previewContent.value = res.data.data?.content || ''
  } catch {
    previewContent.value = ''
  } finally {
    previewLoading.value = false
  }
}

async function onDelete(row: any) {
  await ElMessageBox.confirm(`确定删除草稿「${row.title || row.file_name}」？`, '删除草稿', { type: 'warning' })
  try {
    await client.delete(`/documents/${row.id}`)
    ElMessage.success('已删除')
    load()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.message || '删除失败')
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
.tip-alert {
  margin-bottom: 14px;
  border-radius: 8px;
}
.table-card {
  border-radius: 10px;
}
.doc-title {
  font-weight: 500;
}
.pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.batch-bar {
  display: flex;
  align-items: center;
  gap: 8px;
}
.preview-body {
  min-height: 60vh;
}
.preview-text {
  white-space: pre-wrap;
  word-break: break-word;
  font-family: inherit;
  font-size: 14px;
  line-height: 1.7;
  margin: 0;
}
</style>