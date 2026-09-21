<template>
  <div class="admin-page">
    <div class="page-header">
      <div class="header-left">
        <el-icon class="header-icon" :size="24"><Document /></el-icon>
        <h2>文档管理</h2>
        <el-tag size="small" round type="info">{{ stats.total_documents }} 篇文档</el-tag>
      </div>
      <div class="header-right">
        <el-input
          v-model="searchKeyword"
          placeholder="搜索文档标题..."
          :prefix-icon="Search"
          clearable
          style="width: 220px"
        />
        <el-button type="primary" :icon="Upload" @click="openUploadDialog">上传文档</el-button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stats-row">
      <el-col :span="8">
        <div class="stat-card">
          <div class="stat-icon" style="background: #e8f4fd; color: #409eff;">
            <el-icon :size="20"><Files /></el-icon>
          </div>
          <div class="stat-body">
            <div class="stat-value">{{ stats.total_documents }}</div>
            <div class="stat-label">文档总数</div>
          </div>
        </div>
      </el-col>
      <el-col :span="8">
        <div class="stat-card">
          <div class="stat-icon" style="background: #e6f7e6; color: #67c23a;">
            <el-icon :size="20"><Grid /></el-icon>
          </div>
          <div class="stat-body">
            <div class="stat-value">{{ stats.total_chunks }}</div>
            <div class="stat-label">分块总数</div>
          </div>
        </div>
      </el-col>
      <el-col :span="8">
        <div class="stat-card">
          <div class="stat-icon" style="background: #fef0e6; color: #e6a23c;">
            <el-icon :size="20"><Coin /></el-icon>
          </div>
          <div class="stat-body">
            <div class="stat-value">{{ formatSize(stats.total_size_bytes) }}</div>
            <div class="stat-label">存储大小</div>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- 文档表格 -->
    <el-card style="margin-top: 16px;">
      <el-table :data="filteredDocuments" stripe v-loading="loading" empty-text="暂无文档，请上传">
        <el-table-column prop="title" label="标题" min-width="200">
          <template #default="{ row }">
            <div class="doc-title-cell">
              <el-icon :size="16" class="file-type-icon"><Document /></el-icon>
              <span>{{ row.title }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="category_name" label="分类" width="140">
          <template #default="{ row }">
            <el-tag v-if="row.category_name" size="small" effect="plain">{{ row.category_name }}</el-tag>
            <span v-else class="empty-hint">未分类</span>
          </template>
        </el-table-column>
        <el-table-column prop="file_type" label="类型" width="80" align="center">
          <template #default="{ row }">
            <el-tag size="small" type="info" effect="plain">{{ row.file_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="file_size" label="大小" width="100" :formatter="(r: any) => formatSize(r.file_size)" />
        <el-table-column prop="chunk_count" label="分块数" width="80" align="center" />
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small" effect="plain">{{ statusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="审核" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="reviewType(row.review_status)" size="small" effect="light">{{ reviewText(row.review_status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="上传时间" width="180" />
        <el-table-column label="操作" width="200" fixed="right" align="center">
          <template #default="{ row }">
            <div class="action-btns">
              <el-upload
                :before-upload="(file: File) => handleUploadVersion(file, row)"
                :show-file-list="false"
                accept=".pdf,.docx,.xlsx,.md,.txt"
              >
                <el-tooltip content="上传新版本替换当前文件" placement="top">
                  <el-button text size="small" :icon="Upload" class="action-btn">更新</el-button>
                </el-tooltip>
              </el-upload>
              <el-divider direction="vertical" />
              <el-tooltip content="删除此文档" placement="top">
                <el-button text type="danger" size="small" :icon="Delete" class="action-btn" @click="handleDelete(row)">删除</el-button>
              </el-tooltip>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 上传文档对话框（与分类联动） -->
    <el-dialog v-model="uploadDialogVisible" title="上传文档" width="560px" destroy-on-close>
      <el-form ref="uploadFormRef" :model="uploadForm" :rules="uploadRules" label-width="90px">
        <el-form-item label="文件" prop="file">
          <el-upload
            :auto-upload="false"
            :limit="1"
            :on-change="handleFileChange"
            :on-remove="handleFileRemove"
            accept=".pdf,.docx,.xlsx,.md,.txt"
            drag
          >
            <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
            <div class="el-upload__text">拖拽文件到此处，或 <em>点击选择</em></div>
            <template #tip>
              <div class="el-upload__tip">支持 PDF / DOCX / XLSX / MD / TXT</div>
            </template>
          </el-upload>
        </el-form-item>

        <el-form-item label="标题" prop="title">
          <el-input v-model="uploadForm.title" placeholder="文档标题（默认使用文件名）" />
        </el-form-item>

        <el-form-item label="所属分类">
          <div class="category-row">
            <el-tree-select
              v-model="uploadForm.category_id"
              :data="categoryTreeOptions"
              :props="{ label: 'label', children: 'children' }"
              node-key="value"
              value-key="value"
              clearable
              placeholder="选择分类（可留空）"
              style="flex: 1"
            />
            <el-button :icon="Plus" @click="openCreateCategory">新建分类</el-button>
          </div>
        </el-form-item>

        <el-form-item label="标签">
          <el-input v-model="uploadForm.tags" placeholder="多个标签用逗号分隔，如：考勤,请假" />
        </el-form-item>

        <el-form-item label="审核方式">
          <el-radio-group v-model="uploadForm.review_mode">
            <el-radio value="pending">提交审核</el-radio>
            <el-radio value="draft">保存草稿</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="uploadDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="submitUpload">开始上传</el-button>
      </template>
    </el-dialog>

    <!-- 快速新建分类对话框 -->
    <el-dialog v-model="createCatVisible" title="新建分类" width="420px" append-to-body>
      <el-form ref="createCatFormRef" :model="createCatForm" :rules="createCatRules" label-width="90px">
        <el-form-item label="分类名称" prop="name">
          <el-input v-model="createCatForm.name" placeholder="如：考勤管理" />
        </el-form-item>
        <el-form-item label="上级分类">
          <el-tree-select
            v-model="createCatForm.parent_id"
            :data="categoryTreeOptions"
            :props="{ label: 'label', children: 'children' }"
            node-key="value"
            value-key="value"
            clearable
            placeholder="不选则作为顶级分类"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="createCatForm.description" placeholder="分类描述（选填）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createCatVisible = false">取消</el-button>
        <el-button type="primary" :loading="creatingCat" @click="submitCreateCategory">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { Upload, UploadFilled, Plus, Document, Files, Grid, Coin, Search, Delete } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import client from '@/api/client'

const loading = ref(false)
const documents = ref<any[]>([])
const searchKeyword = ref('')
const stats = ref({ total_documents: 0, total_chunks: 0, total_size_bytes: 0 })

const filteredDocuments = computed(() => {
  if (!searchKeyword.value) return documents.value
  const kw = searchKeyword.value.toLowerCase()
  return documents.value.filter((d: any) => d.title?.toLowerCase().includes(kw))
})

// ==================== 分类树 ====================
const categoryTree = ref<any[]>([])
const categoryTreeOptions = ref<any[]>([])

function buildTreeOptions(nodes: any[]): any[] {
  return nodes.map((n) => ({
    value: n.id,
    label: n.name,
    children: n.children && n.children.length ? buildTreeOptions(n.children) : undefined,
  }))
}

async function loadCategories() {
  try {
    const res = await client.get('/documents/categories/tree')
    categoryTree.value = res.data.data || []
    categoryTreeOptions.value = buildTreeOptions(categoryTree.value)
  } catch { /* ignore */ }
}

// ==================== 上传对话框 ====================
const uploadDialogVisible = ref(false)
const uploading = ref(false)
const uploadFormRef = ref<FormInstance>()
const uploadForm = reactive({
  file: null as File | null,
  title: '',
  category_id: null as number | null,
  tags: '',
  review_mode: 'pending' as string,
})

const uploadRules: FormRules = {
  file: [{ required: true, message: '请选择要上传的文件', trigger: 'change' }],
}

function openUploadDialog() {
  uploadForm.file = null
  uploadForm.title = ''
  uploadForm.category_id = null
  uploadForm.tags = ''
  uploadForm.review_mode = 'pending'
  uploadDialogVisible.value = true
  loadCategories()
}

function handleFileChange(file: any) {
  uploadForm.file = file.raw || file
  if (!uploadForm.title) {
    // 默认标题：去掉扩展名的文件名
    uploadForm.title = (uploadForm.file?.name || '').replace(/\.[^.]+$/, '')
  }
}

function handleFileRemove() {
  uploadForm.file = null
}

async function submitUpload() {
  const valid = await uploadFormRef.value?.validate().catch(() => false)
  if (!valid || !uploadForm.file) return

  const formData = new FormData()
  formData.append('file', uploadForm.file)
  if (uploadForm.title) formData.append('title', uploadForm.title)
  if (uploadForm.category_id) formData.append('category_id', String(uploadForm.category_id))
  if (uploadForm.tags) {
    const tags = uploadForm.tags.split(/[,，]/).map((t) => t.trim()).filter(Boolean)
    formData.append('tags', JSON.stringify(tags))
  }
  formData.append('review_mode', uploadForm.review_mode)

  uploading.value = true
  try {
    await client.post('/documents/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    ElMessage.success(`文档 "${uploadForm.title || uploadForm.file.name}" 上传成功，后台处理中...`)
    uploadDialogVisible.value = false
    loadData()
    startPolling()
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.message || '上传失败')
  } finally {
    uploading.value = false
  }
}

// ==================== 快速新建分类 ====================
const createCatVisible = ref(false)
const creatingCat = ref(false)
const createCatFormRef = ref<FormInstance>()
const createCatForm = reactive({
  name: '',
  parent_id: null as number | null,
  description: '',
})

const createCatRules: FormRules = {
  name: [{ required: true, message: '请输入分类名称', trigger: 'blur' }],
}

function openCreateCategory() {
  createCatForm.name = ''
  createCatForm.parent_id = null
  createCatForm.description = ''
  createCatVisible.value = true
}

async function submitCreateCategory() {
  const valid = await createCatFormRef.value?.validate().catch(() => false)
  if (!valid) return
  creatingCat.value = true
  try {
    await client.post('/documents/categories', {
      name: createCatForm.name,
      parent_id: createCatForm.parent_id ?? 0,
      sort_order: 999,
      description: createCatForm.description || null,
    })
    ElMessage.success('分类创建成功')
    createCatVisible.value = false
    await loadCategories()
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.message || '创建失败')
  } finally {
    creatingCat.value = false
  }
}

// ==================== 通用工具 ====================
function formatSize(bytes: number): string {
  if (!bytes) return '0 B'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1048576).toFixed(1) + ' MB'
}

function statusType(status: number): string {
  return { 0: 'info', 1: 'success', 2: 'warning', 3: 'danger' }[status] || 'info'
}

function statusText(status: number): string {
  return { 0: '处理中', 1: '已发布', 2: '已归档', 3: '失败' }[status] || '未知'
}

function reviewType(s: number): string {
  return { 0: 'info', 1: 'warning', 2: 'success', 3: 'danger' }[s] || 'info'
}
function reviewText(s: number): string {
  return { 0: '草稿', 1: '待审核', 2: '已通过', 3: '已驳回' }[s] || '未知'
}

async function handleUploadVersion(file: File, row: any) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('changelog', `更新至新版本`)
  try {
    await client.post(`/documents/${row.id}/upload-version`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    ElMessage.success(`文档 "${row.title}" 新版本上传成功，后台处理中...`)
    loadData()
    startPolling()
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.message || '版本上传失败')
  }
  return false
}

// 自动轮询：有处理中的文档时每3秒刷新
let pollTimer: ReturnType<typeof setInterval> | null = null

function startPolling() {
  if (pollTimer) return
  pollTimer = setInterval(async () => {
    await loadData()
    const hasProcessing = documents.value.some((d: any) => d.status === 0)
    if (!hasProcessing) stopPolling()
  }, 3000)
}

function stopPolling() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
}

async function loadData() {
  try {
    const [docsRes, statsRes] = await Promise.all([
      client.get('/documents', { params: { page: 1, page_size: 100 } }),
      client.get('/documents/stats/overview'),
    ])
    documents.value = docsRes.data.data?.items || []
    stats.value = statsRes.data.data || stats.value
  } catch { /* ignore */ }
}

onMounted(() => {
  loadData()
  loadCategories()
  startPolling()
})

async function handleDelete(row: any) {
  try {
    await ElMessageBox.confirm(`确定删除 "${row.title}"？此操作不可逆`, '确认删除')
    await client.delete(`/documents/${row.id}`)
    ElMessage.success('文档已删除')
    loadData()
  } catch { /* 取消 */ }
}

</script>

<style scoped>
.admin-page { padding: 24px 32px; max-width: 1200px; margin: 0 auto; }

.page-header {
  display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px;
}
.header-left { display: flex; align-items: center; gap: 10px; }
.header-right { display: flex; align-items: center; gap: 10px; }
.header-icon { color: var(--color-primary); }
.header-left h2 { font-size: 20px; font-weight: 700; color: var(--color-text-primary); margin: 0; }

.stats-row { margin-bottom: 16px; }
.stat-card {
  display: flex; align-items: center; gap: 14px;
  background: var(--color-bg-card); border: 1px solid var(--color-border);
  border-radius: 10px; padding: 18px 20px;
}
.stat-icon {
  width: 42px; height: 42px; border-radius: 10px;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.stat-body { flex: 1; }
.stat-value { font-size: 22px; font-weight: 700; color: var(--color-text-primary); line-height: 1.2; }
.stat-label { font-size: 13px; color: var(--color-text-placeholder); margin-top: 2px; }

.doc-title-cell { display: flex; align-items: center; gap: 8px; }
.file-type-icon { color: var(--color-text-placeholder); flex-shrink: 0; }

.action-btns { display: flex; align-items: center; justify-content: center; gap: 0; }
.action-btn { font-size: 13px; }

.category-row { display: flex; gap: 8px; width: 100%; align-items: center; }
.empty-hint { color: var(--color-text-placeholder); font-size: 13px; }
</style>