<template>
  <div class="admin-page">
    <div class="page-header">
      <h2>公告管理</h2>
      <el-button type="primary" @click="openCreate">发布公告</el-button>
    </div>

    <el-card>
      <el-table :data="announcements" stripe v-loading="loading">
        <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
        <el-table-column prop="content" label="内容" min-width="300" show-overflow-tooltip />
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_published ? 'success' : 'info'" size="small">
              {{ row.is_published ? '已发布' : '草稿' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="发布时间" width="170">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="togglePublish(row)">
              {{ row.is_published ? '下架' : '发布' }}
            </el-button>
            <el-button size="small" @click="openEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && announcements.length === 0" description="暂无公告" />
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      :title="isEditing ? '编辑公告' : '发布公告'"
      width="600px"
      destroy-on-close
    >
      <el-form :model="form" label-width="80px" ref="formRef" :rules="rules">
        <el-form-item label="标题" prop="title">
          <el-input v-model="form.title" placeholder="公告标题" />
        </el-form-item>
        <el-form-item label="内容" prop="content">
          <el-input v-model="form.content" type="textarea" :rows="6" placeholder="公告内容（支持 Markdown）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitting">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import client from '@/api/client'

const loading = ref(false)
const submitting = ref(false)
const dialogVisible = ref(false)
const isEditing = ref(false)
const editingId = ref<number | null>(null)
const formRef = ref()
const announcements = ref<any[]>([])

const form = ref({ title: '', content: '' })
const rules = {
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
  content: [{ required: true, message: '请输入内容', trigger: 'blur' }],
}

function formatTime(t: string) {
  if (!t) return '-'
  const d = new Date(t.endsWith('Z') ? t : t + 'Z')
  return d.toLocaleString('zh-CN')
}

async function loadData() {
  loading.value = true
  try {
    const res = await client.get('/admin/announcements', { params: { page: 1, page_size: 50 } })
    announcements.value = res.data.data?.items || []
  } catch { /* ignore */ } finally { loading.value = false }
}

function openCreate() {
  isEditing.value = false
  editingId.value = null
  form.value = { title: '', content: '' }
  dialogVisible.value = true
}

function openEdit(row: any) {
  isEditing.value = true
  editingId.value = row.id
  form.value = { title: row.title, content: row.content }
  dialogVisible.value = true
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    if (isEditing.value) {
      await client.put(`/admin/announcements/${editingId.value}`, null, {
        params: { title: form.value.title, content: form.value.content },
      })
      ElMessage.success('公告更新成功')
    } else {
      await client.post('/admin/announcements', null, {
        params: { title: form.value.title, content: form.value.content },
      })
      ElMessage.success('公告发布成功')
    }
    dialogVisible.value = false
    loadData()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.message || '操作失败')
  } finally { submitting.value = false }
}

async function togglePublish(row: any) {
  try {
    await client.put(`/admin/announcements/${row.id}`, null, {
      params: { is_published: !row.is_published },
    })
    row.is_published = !row.is_published
    ElMessage.success(row.is_published ? '已发布' : '已下架')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.message || '操作失败')
  }
}

async function handleDelete(row: any) {
  try {
    await ElMessageBox.confirm(`确定删除公告「${row.title}」？`, '删除确认', {
      confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning',
    })
    await client.delete(`/admin/announcements/${row.id}`)
    ElMessage.success('已删除')
    loadData()
  } catch (e: any) {
    if (e !== 'cancel') ElMessage.error(e.response?.data?.message || '删除失败')
  }
}

onMounted(loadData)
</script>

<style scoped>
.admin-page { padding: 24px 32px; max-width: 1100px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.page-header h2 { font-size: 22px; font-weight: 700; color: var(--color-text-primary); margin: 0; }
</style>