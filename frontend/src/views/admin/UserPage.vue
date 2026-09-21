<template>
  <div class="admin-page">
    <div class="page-header">
      <div class="header-left">
        <el-icon class="header-icon" :size="24"><User /></el-icon>
        <h2>用户管理</h2>
        <el-tag size="small" round type="info">{{ total }} 人</el-tag>
      </div>
      <el-input
        v-model="searchKeyword"
        placeholder="搜索用户名 / 姓名 / 邮箱..."
        :prefix-icon="Search"
        clearable
        style="width: 240px"
        @clear="handlePageChange(1)"
        @keyup.enter="handlePageChange(1)"
      />
    </div>

    <el-card>
      <el-table :data="users" stripe class="user-table" v-loading="loading" empty-text="暂无用户">
        <el-table-column label="用户" min-width="180">
          <template #default="{ row }">
            <div class="user-cell">
              <el-avatar :size="34" :src="row.avatar_url || ''">
                {{ avatarChar(row.real_name || row.username) }}
              </el-avatar>
              <div class="user-meta">
                <div class="user-name">{{ row.real_name || row.username }}</div>
                <div class="user-username">@{{ row.username }}</div>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="email" label="邮箱" min-width="180" show-overflow-tooltip />
        <el-table-column label="部门" width="200">
          <template #default="{ row }">
            <div class="dept-cell">
              <span class="dept-name">{{ row.department || '未分配' }}</span>
              <el-popover
                :visible="editingRow === row.id"
                placement="bottom"
                :width="220"
                trigger="click"
              >
                <template #reference>
                  <el-button
                    text size="small" class="edit-btn"
                    @click="startEdit(row)"
                  >
                    <el-icon :size="14"><EditPen /></el-icon>
                  </el-button>
                </template>
                <div class="dept-popover">
                  <p class="dept-popover-title">修改部门 — {{ row.real_name || row.username }}</p>
                  <el-select
                    v-model="editDept"
                    placeholder="选择部门"
                    clearable
                    style="width:100%"
                  >
                    <el-option
                      v-for="d in departments"
                      :key="d.id"
                      :label="d.name"
                      :value="d.id"
                    />
                  </el-select>
                  <div class="dept-popover-actions">
                    <el-button size="small" @click="cancelEdit">取消</el-button>
                    <el-button size="small" type="primary" @click="saveDept(row)">保存</el-button>
                  </div>
                </div>
              </el-popover>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="角色" width="200">
          <template #default="{ row }">
            <div class="dept-cell">
              <el-tag
                :type="roleTagType(row.role_name)"
                size="small"
                effect="plain"
              >{{ row.role_name }}</el-tag>
              <el-popover
                :visible="editingRoleRow === row.id"
                placement="bottom"
                :width="220"
                trigger="click"
              >
                <template #reference>
                  <el-button
                    text size="small" class="edit-btn"
                    @click="startRoleEdit(row)"
                  >
                    <el-icon :size="14"><EditPen /></el-icon>
                  </el-button>
                </template>
                <div class="dept-popover">
                  <p class="dept-popover-title">修改角色 — {{ row.real_name || row.username }}</p>
                  <el-select v-model="editRoleId" placeholder="选择角色" style="width:100%">
                    <el-option
                      v-for="r in roles"
                      :key="r.id"
                      :label="r.name + ' (' + r.code + ')'"
                      :value="r.id"
                    />
                  </el-select>
                  <div class="dept-popover-actions">
                    <el-button size="small" @click="cancelRoleEdit">取消</el-button>
                    <el-button size="small" type="primary" @click="saveRole(row)">保存</el-button>
                  </div>
                </div>
              </el-popover>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'danger'" size="small" effect="plain">
              {{ row.status === 1 ? '正常' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="注册时间" width="170">
          <template #default="{ row }">
            <span class="time-text">{{ formatTime(row.created_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" align="center" fixed="right">
          <template #default="{ row }">
            <el-tooltip content="禁用 / 启用账号" placement="top">
              <el-button
                v-if="row.status === 1"
                text type="warning" size="small"
                @click="handleToggle(row)"
              >禁用</el-button>
              <el-button
                v-else
                text type="success" size="small"
                @click="handleToggle(row)"
              >启用</el-button>
            </el-tooltip>
            <el-tooltip content="删除用户账号" placement="top">
              <el-button
                v-if="row.id !== currentUserId"
                text type="danger" size="small"
                :icon="Delete"
                @click="handleDelete(row)"
              >删除</el-button>
            </el-tooltip>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        class="user-pager"
        background
        layout="total, prev, pager, next, sizes"
        :total="total"
        :page-sizes="[20, 50, 100]"
        :page-size="pageSize"
        :current-page="page"
        @current-change="handlePageChange"
        @size-change="handleSizeChange"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { EditPen, Delete, User, Search } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import client from '@/api/client'
import { useAuthStore } from '@/store/auth'

const authStore = useAuthStore()

const loading = ref(false)
const users = ref<any[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const departments = ref<any[]>([])
const roles = ref<any[]>([])
const editingRow = ref<number | null>(null)
const editDept = ref<number | null>(null)
const editingRoleRow = ref<number | null>(null)
const editRoleId = ref<number>(0)
const searchKeyword = ref('')
const currentUserId = ref(authStore.user?.id)

function avatarChar(name: string) {
  return (name || '?').charAt(0).toUpperCase()
}

async function loadData() {
  // 第一步：立即加载当前页用户数据并显示
  loading.value = true
  const userRes = await client.get('/admin/users', {
    params: {
      page: page.value,
      page_size: pageSize.value,
      keyword: searchKeyword.value || undefined,
    },
  })
  users.value = userRes.data.data?.items || []
  total.value = userRes.data.data?.total || 0
  loading.value = false

  // 第二步：后台补加载部门和角色（不阻塞用户列表显示）
  client.get('/admin/departments').then(r => { departments.value = r.data.data || [] }).catch(() => {})
  client.get('/admin/roles').then(r => { roles.value = r.data.data || [] }).catch(() => {})
}

function handlePageChange(p: number) {
  page.value = p
  loadData()
}

function handleSizeChange(size: number) {
  pageSize.value = size
  page.value = 1
  loadData()
}

// ---- 部门编辑 ----
function startEdit(row: any) {
  editingRow.value = row.id
  editDept.value = row.dept_id || null
}
function cancelEdit() { editingRow.value = null }
async function saveDept(row: any) {
  try {
    await client.patch(`/admin/users/${row.id}/department`, null, {
      params: { dept_id: editDept.value },
    })
    const newDept = departments.value.find(d => d.id === editDept.value)
    row.dept_id = editDept.value
    row.department = newDept?.name || null
    editingRow.value = null
    ElMessage.success('已更新')
  } catch { ElMessage.error('更新失败') }
}

// ---- 角色编辑 ----
function startRoleEdit(row: any) {
  editingRoleRow.value = row.id
  editRoleId.value = row.role_id
}
function cancelRoleEdit() { editingRoleRow.value = null }
async function saveRole(row: any) {
  try {
    await client.patch(`/admin/users/${row.id}/role`, null, {
      params: { role_id: editRoleId.value },
    })
    const newRole = roles.value.find(r => r.id === editRoleId.value)
    row.role_id = editRoleId.value
    row.role_name = newRole?.name || row.role_name
    editingRoleRow.value = null
    ElMessage.success('角色已更新')
  } catch { ElMessage.error('更新失败') }
}

function roleTagType(name: string) {
  if (!name) return 'info'
  if (name.includes('超级')) return ''
  if (name.includes('知识库')) return 'warning'
  if (name.includes('部门')) return 'primary'
  return 'info'
}

async function handleToggle(row: any) {
  const newStatus = row.status === 1 ? 0 : 1
  try {
    await client.patch(`/admin/users/${row.id}/status`, null, { params: { status: newStatus } })
    ElMessage.success(newStatus === 1 ? '已启用' : '已禁用')
    row.status = newStatus
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.message || '操作失败')
  }
}

async function handleDelete(row: any) {
  try {
    await ElMessageBox.confirm(
      `确定删除用户「${row.real_name || row.username}」吗？该用户的账号和关联数据将被永久删除，此操作不可恢复。`,
      '删除确认',
      {
        confirmButtonText: '确定删除',
        cancelButtonText: '取消',
        type: 'warning',
        confirmButtonClass: 'el-button--danger',
      },
    )
    await client.delete(`/admin/users/${row.id}`)
    ElMessage.success('用户已删除')
    loadData()
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e?.response?.data?.message || '删除失败')
    }
  }
}

function formatTime(t: string) {
  if (!t) return '-'
  const d = new Date(t.endsWith('Z') ? t : t + 'Z')
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

onMounted(loadData)
</script>

<style scoped>
.admin-page { padding: 24px 32px; max-width: 1200px; margin: 0 auto; }
.page-header { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 20px; }
.header-left { display: flex; align-items: center; gap: 10px; }
.header-icon { color: var(--color-primary); }
.page-header h2 { font-size: 20px; font-weight: 700; color: var(--color-text-primary); margin: 0; }

.user-cell { display: flex; align-items: center; gap: 12px; }
.user-meta { min-width: 0; }
.user-name { font-size: 14px; font-weight: 600; color: var(--color-text-primary); }
.user-username { font-size: 12px; color: var(--color-text-placeholder); margin-top: 1px; }

.user-table { --el-table-header-bg-color: var(--color-bg-page); }

/* 部门列 */
.dept-cell {
  display: flex; align-items: center; justify-content: space-between;
  gap: 4px; min-height: 32px;
}
.dept-name { font-size: 14px; color: var(--color-text-body); }
.edit-btn { opacity: 0; transition: opacity 0.15s; color: var(--color-text-secondary); }
.dept-cell:hover .edit-btn { opacity: 1; }

/* 弹出框 */
.dept-popover { padding: 4px 0; }
.dept-popover-title {
  font-size: 13px; font-weight: 600; color: var(--color-text-primary);
  margin: 0 0 12px; padding-bottom: 8px;
  border-bottom: 1px solid var(--color-border);
}
.dept-popover-actions {
  display: flex; justify-content: flex-end; gap: 8px; margin-top: 14px;
}

.time-text { font-size: 13px; color: var(--color-text-secondary); }

.user-pager {
  margin-top: 16px;
  justify-content: flex-end;
}
</style>
