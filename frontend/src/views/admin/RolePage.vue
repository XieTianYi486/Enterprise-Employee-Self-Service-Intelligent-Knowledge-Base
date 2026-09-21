<template>
  <div class="admin-page">
    <div class="page-header">
      <div class="header-left">
        <el-icon class="header-icon" :size="24"><Avatar /></el-icon>
        <h2>角色管理</h2>
        <el-tag size="small" round type="info">{{ roles.length }} 个角色</el-tag>
      </div>
      <el-button type="primary" :icon="Plus" @click="openCreate">新增角色</el-button>
    </div>

    <div v-loading="loading" class="role-grid">
      <template v-if="roles.length > 0">
        <div v-for="role in roles" :key="role.id" class="role-card">
          <div class="role-head">
            <div class="role-avatar" :style="{ background: avatarBg(role.code) }">
              <el-icon :size="22"><UserFilled /></el-icon>
            </div>
            <div class="role-info">
              <div class="role-name">{{ role.name }}</div>
              <div class="role-code">{{ role.code }}</div>
            </div>
            <el-tag size="small" round>{{ role.user_count ?? 0 }} 人</el-tag>
          </div>
          <div class="role-body">
            <div class="role-desc">{{ role.description || '暂无描述' }}</div>
            <div class="perm-tags" v-if="(role.permission_labels || role.permissions || []).length">
              <el-tag
                v-for="label in (role.permission_labels || role.permissions || [])"
                :key="label"
                size="small"
                effect="plain"
                type="info"
              >{{ label }}</el-tag>
            </div>
            <span v-else class="empty-hint">无权限</span>
          </div>
          <div class="role-actions">
            <el-button size="small" :icon="Edit" @click="openEdit(role)">编辑</el-button>
            <el-button size="small" type="danger" :icon="Delete" @click="handleDelete(role)">删除</el-button>
          </div>
        </div>
      </template>
      <el-empty v-else description="暂无角色，点击上方按钮创建" class="empty-state">
        <el-button type="primary" @click="openCreate">新增角色</el-button>
      </el-empty>
    </div>

    <!-- 新建/编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEditing ? '编辑角色' : '新增角色'"
      width="520px"
      destroy-on-close
    >
      <el-form :model="form" label-width="80px" :rules="rules" ref="formRef">
        <el-form-item label="角色名称" prop="name">
          <el-input v-model="form.name" placeholder="如：部门管理员" maxlength="20" show-word-limit />
        </el-form-item>
        <el-form-item label="角色编码" prop="code">
          <el-input v-model="form.code" placeholder="如：dept_admin" :disabled="isEditing" maxlength="30" show-word-limit />
        </el-form-item>
        <el-form-item label="角色描述" prop="description">
          <el-input v-model="form.description" placeholder="如：管理部门文档和问答统计" type="textarea" :rows="2" maxlength="100" show-word-limit />
        </el-form-item>
        <el-form-item v-if="isEditing" label="权限配置">
          <el-checkbox-group v-model="form.permissions" class="perm-checkboxes">
            <el-checkbox
              v-for="perm in availablePermissions"
              :key="perm.value"
              :label="perm.value"
            >{{ perm.label }}</el-checkbox>
          </el-checkbox-group>
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
import { Plus, Avatar, UserFilled, Edit, Delete } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import client from '@/api/client'

const loading = ref(false)
const submitting = ref(false)
const dialogVisible = ref(false)
const isEditing = ref(false)
const editingRoleId = ref<number | null>(null)
const formRef = ref()
const roles = ref<any[]>([])

const form = ref({
  name: '',
  code: '',
  description: '',
  permissions: [] as string[],
})

const rules = {
  name: [{ required: true, message: '请输入角色名称', trigger: 'blur' }],
  code: [{ required: true, message: '请输入角色编码', trigger: 'blur' }],
}

const availablePermissions = [
  { value: 'documents:read', label: '查看文档' },
  { value: 'documents:*', label: '文档管理（上传/编辑/删除）' },
  { value: 'categories:*', label: '分类管理' },
  { value: 'chat:ask', label: '智能问答' },
  { value: 'logs:read', label: '查看问答日志' },
  { value: 'stats:read', label: '查看统计数据' },
  { value: '*', label: '全部权限' },
]

const avatarColors: Record<string, string> = {
  super_admin: 'linear-gradient(135deg, #fde8e8, #f8b4b4)',
  knowledge_admin: 'linear-gradient(135deg, #e8f4fd, #a0cfff)',
  dept_admin: 'linear-gradient(135deg, #e6f7e6, #9ce09c)',
  employee: 'linear-gradient(135deg, #fef0e6, #fcd4a0)',
}

function avatarBg(code: string) {
  return avatarColors[code] || 'linear-gradient(135deg, #f1f5f9, #cbd5e1)'
}

async function loadData() {
  loading.value = true
  try {
    const res = await client.get('/admin/roles')
    roles.value = res.data.data || []
  } catch { /* ignore */ } finally { loading.value = false }
}

function openCreate() {
  isEditing.value = false
  editingRoleId.value = null
  form.value = { name: '', code: '', description: '', permissions: [] }
  dialogVisible.value = true
}

function openEdit(row: any) {
  isEditing.value = true
  editingRoleId.value = row.id
  form.value = {
    name: row.name,
    code: row.code,
    description: row.description || '',
    permissions: row.permissions || [],
  }
  dialogVisible.value = true
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    if (isEditing.value) {
      const permStr = form.value.permissions.join(',')
      await client.put(`/admin/roles/${editingRoleId.value}`, null, {
        params: {
          name: form.value.name,
          description: form.value.description,
          permissions: permStr,
        },
      })
      ElMessage.success('角色更新成功')
    } else {
      await client.post('/admin/roles', null, {
        params: {
          name: form.value.name,
          code: form.value.code,
          description: form.value.description,
        },
      })
      ElMessage.success('角色创建成功')
    }
    dialogVisible.value = false
    loadData()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.message || '操作失败')
  } finally {
    submitting.value = false
  }
}

async function handleDelete(row: any) {
  try {
    await ElMessageBox.confirm(
      `确定删除角色「${row.name}」吗？该操作不可恢复。`,
      '删除确认',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
    await client.delete(`/admin/roles/${row.id}`)
    ElMessage.success('角色已删除')
    loadData()
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e.response?.data?.message || '删除失败')
    }
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

.role-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 14px; }
.empty-state { grid-column: 1 / -1; }

.role-card {
  background: var(--color-bg-card); border: 1px solid var(--color-border);
  border-radius: 10px; padding: 20px; display: flex; flex-direction: column; gap: 14px;
  transition: box-shadow .2s; box-shadow: 0 1px 3px rgba(0,0,0,.04);
}
.role-card:hover { box-shadow: 0 2px 12px rgba(0,0,0,.08); }

.role-head { display: flex; align-items: center; gap: 12px; }
.role-avatar {
  width: 40px; height: 40px; border-radius: 10px;
  display: flex; align-items: center; justify-content: center; color: #fff; flex-shrink: 0;
}
.role-info { flex: 1; min-width: 0; }
.role-name { font-size: 15px; font-weight: 600; color: var(--color-text-primary); }
.role-code { font-size: 12px; color: var(--color-text-placeholder); margin-top: 2px; font-family: monospace; }

.role-body { flex: 1; }
.role-desc { font-size: 13px; color: var(--color-text-secondary); margin-bottom: 8px; }
.perm-tags { display: flex; flex-wrap: wrap; gap: 6px; }
.empty-hint { font-size: 13px; color: var(--color-text-placeholder); }

.role-actions { display: flex; justify-content: flex-end; gap: 6px; border-top: 1px solid var(--color-border); padding-top: 12px; }

.perm-checkboxes { display: flex; flex-direction: column; gap: 8px; }
</style>