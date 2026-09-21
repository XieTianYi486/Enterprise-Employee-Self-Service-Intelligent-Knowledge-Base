<template>
  <div class="admin-page">
    <div class="page-header">
      <div class="header-left">
        <el-icon class="header-icon" :size="24"><OfficeBuilding /></el-icon>
        <h2>部门管理</h2>
        <el-tag size="small" round type="info">{{ departments.length }} 个部门</el-tag>
      </div>
      <el-button type="primary" :icon="Plus" @click="showCreateDialog">新建部门</el-button>
    </div>

    <div v-loading="loading" class="dept-grid">
      <template v-if="departments.length > 0">
        <div v-for="dept in departments" :key="dept.id" class="dept-card">
          <div class="dept-avatar">
            <el-icon :size="24"><OfficeBuilding /></el-icon>
          </div>
          <div class="dept-body">
            <div class="dept-name">{{ dept.name }}</div>
            <div class="dept-desc">{{ dept.description || '暂无描述' }}</div>
            <div class="dept-meta">
              <span class="meta-item">
                <el-icon :size="14"><User /></el-icon>
                {{ dept.manager_name || '未设置' }}
              </span>
              <el-tag size="small" round>{{ dept.member_count ?? 0 }} 人</el-tag>
            </div>
          </div>
          <div class="dept-actions">
            <el-button text size="small" :icon="Edit" @click="showEditDialog(dept)">编辑</el-button>
            <el-popconfirm title="确定删除此部门？" @confirm="handleDelete(dept.id)">
              <template #reference>
                <el-button text type="danger" size="small" :icon="Delete">删除</el-button>
              </template>
            </el-popconfirm>
          </div>
        </div>
      </template>
      <el-empty v-else description="暂无部门，点击上方按钮创建" class="empty-state">
        <el-button type="primary" @click="showCreateDialog">新建部门</el-button>
      </el-empty>
    </div>

    <!-- 创建/编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑部门' : '新建部门'" width="460px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="72px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="部门名称" maxlength="20" show-word-limit />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" placeholder="部门描述（选填）" maxlength="100" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">
          {{ editingId ? '保存' : '创建' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { Plus, OfficeBuilding, User, Edit, Delete } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import client from '@/api/client'

const loading = ref(false)
const saving = ref(false)
const departments = ref<any[]>([])
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const formRef = ref<FormInstance>()

const form = reactive({ name: '', description: '' })
const rules: FormRules = {
  name: [{ required: true, message: '请输入部门名称', trigger: 'blur' }],
}

async function loadData() {
  loading.value = true
  try {
    const res = await client.get('/admin/departments')
    departments.value = res.data.data || []
  } catch { /* ignore */ } finally { loading.value = false }
}

function showCreateDialog() {
  editingId.value = null
  form.name = ''
  form.description = ''
  dialogVisible.value = true
}

function showEditDialog(row: any) {
  editingId.value = row.id
  form.name = row.name
  form.description = row.description || ''
  dialogVisible.value = true
}

async function handleSave() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    if (editingId.value) {
      await client.put(`/admin/departments/${editingId.value}`, null, {
        params: { name: form.name, description: form.description || undefined },
      })
      ElMessage.success('部门已更新')
    } else {
      await client.post('/admin/departments', null, {
        params: { name: form.name, description: form.description || undefined },
      })
      ElMessage.success('部门已创建')
    }
    dialogVisible.value = false
    loadData()
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.message || '操作失败')
  } finally { saving.value = false }
}

async function handleDelete(id: number) {
  try {
    await client.delete(`/admin/departments/${id}`)
    ElMessage.success('部门已删除')
    loadData()
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.message || '删除失败')
  }
}

onMounted(loadData)
</script>

<style scoped>
.admin-page { padding: 24px 32px; max-width: 1000px; margin: 0 auto; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
.header-left { display: flex; align-items: center; gap: 10px; }
.header-icon { color: var(--color-primary); }
.header-left h2 { font-size: 20px; font-weight: 700; color: var(--color-text-primary); margin: 0; }

.dept-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 14px; }
.empty-state { grid-column: 1 / -1; }

.dept-card {
  background: var(--color-bg-card); border: 1px solid var(--color-border);
  border-radius: 10px; padding: 20px; display: flex; flex-direction: column; gap: 14px;
  transition: box-shadow .2s; box-shadow: 0 1px 3px rgba(0,0,0,.04);
}
.dept-card:hover { box-shadow: 0 2px 12px rgba(0,0,0,.08); }

.dept-avatar {
  width: 44px; height: 44px; border-radius: 10px;
  background: linear-gradient(135deg, var(--color-primary-light-8, #d9ecff), var(--color-primary-light-5, #a0cfff));
  display: flex; align-items: center; justify-content: center; color: var(--color-primary);
}
.dept-body { flex: 1; }
.dept-name { font-size: 16px; font-weight: 600; color: var(--color-text-primary); }
.dept-desc { font-size: 13px; color: var(--color-text-placeholder); margin-top: 4px; min-height: 18px; }
.dept-meta { display: flex; align-items: center; justify-content: space-between; margin-top: 10px; }
.meta-item { display: flex; align-items: center; gap: 4px; font-size: 13px; color: var(--color-text-secondary); }
.dept-actions { display: flex; justify-content: flex-end; gap: 2px; border-top: 1px solid var(--color-border); padding-top: 12px; }
</style>