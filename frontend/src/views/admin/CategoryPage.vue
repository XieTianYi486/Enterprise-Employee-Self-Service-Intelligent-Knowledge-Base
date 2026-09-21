<template>
  <div class="admin-page">
    <div class="page-header">
      <div class="header-left">
        <el-icon class="header-icon" :size="24"><FolderOpened /></el-icon>
        <h2>分类管理</h2>
        <el-tag size="small" round type="info">{{ flatCount }} 个分类</el-tag>
      </div>
      <el-button type="primary" :icon="Plus" @click="showCreateDialog">新建分类</el-button>
    </div>

    <div v-loading="loading" class="category-list">
      <template v-if="treeData.length > 0">
        <div v-for="(cat, idx) in treeData" :key="cat.id" class="category-card">
          <div class="card-main" :style="{ borderLeftColor: accentColors[idx % accentColors.length] }">
            <div class="card-icon" :style="{ color: accentColors[idx % accentColors.length] }"><el-icon :size="22"><Folder /></el-icon></div>
            <div class="card-body">
              <div class="card-title">{{ cat.name }}</div>
              <div class="card-desc">{{ cat.description || '暂无描述' }}</div>
            </div>
            <el-tag size="small" type="primary" round>{{ cat.document_count ?? 0 }} 篇文档</el-tag>
            <div class="card-actions">
              <el-button text size="small" :icon="FolderAdd" @click="showCreateDialog(cat.id)">子分类</el-button>
              <el-button text size="small" :icon="Edit" @click="showEditDialog(cat)">编辑</el-button>
              <el-popconfirm title="确定删除？子分类将一并删除" @confirm="handleDelete(cat.id)">
                <template #reference>
                  <el-button text type="danger" size="small" :icon="Delete">删除</el-button>
                </template>
              </el-popconfirm>
            </div>
          </div>
          <!-- 子分类 -->
          <div v-if="cat.children && cat.children.length > 0" class="sub-list">
            <div v-for="sub in cat.children" :key="sub.id" class="sub-card">
              <el-icon :size="16" class="sub-icon"><Document /></el-icon>
              <span class="sub-name">{{ sub.name }}</span>
              <span class="sub-desc" v-if="sub.description">— {{ sub.description }}</span>
              <el-tag size="small" type="info" round>{{ sub.document_count ?? 0 }} 篇</el-tag>
              <div class="sub-actions">
                <el-button text size="small" :icon="Edit" @click="showEditDialog(sub)">编辑</el-button>
                <el-popconfirm title="确定删除？" @confirm="handleDelete(sub.id)">
                  <template #reference>
                    <el-button text type="danger" size="small" :icon="Delete" />
                  </template>
                </el-popconfirm>
              </div>
            </div>
          </div>
        </div>
      </template>
      <el-empty v-else description="暂无分类，点击上方按钮创建第一个分类">
        <el-button type="primary" @click="showCreateDialog">新建分类</el-button>
      </el-empty>
    </div>

    <!-- 创建/编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑分类' : '新建分类'" width="460px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="72px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="分类名称" maxlength="20" show-word-limit />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" placeholder="分类描述（选填）" maxlength="100" show-word-limit />
        </el-form-item>
        <el-form-item label="排序号">
          <el-input-number v-model="form.sort_order" :min="0" :max="999" controls-position="right" style="width: 100%" />
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
import { ref, reactive, computed, onMounted } from 'vue'
import { Plus, Folder, FolderAdd, FolderOpened, Document, Edit, Delete } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import client from '@/api/client'

const loading = ref(false)
const saving = ref(false)
const treeData = ref<any[]>([])
const accentColors = ['#409eff', '#67c23a', '#e6a23c', '#f56c6c', '#9b59b6', '#1abc9c']
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const parentId = ref<number>(0)
const formRef = ref<FormInstance>()

const form = reactive({ name: '', description: '', sort_order: 0 })
const rules: FormRules = {
  name: [{ required: true, message: '请输入分类名称', trigger: 'blur' }],
}

function countFlat(nodes: any[]): number {
  let n = 0
  for (const node of nodes) {
    n++
    if (node.children) n += countFlat(node.children)
  }
  return n
}
const flatCount = computed(() => countFlat(treeData.value))

async function loadData() {
  loading.value = true
  try {
    const res = await client.get('/documents/categories/tree')
    treeData.value = res.data.data || []
  } catch { /* ignore */ } finally { loading.value = false }
}

function showCreateDialog(pid: number = 0) {
  editingId.value = null
  parentId.value = pid
  form.name = ''
  form.description = ''
  form.sort_order = 0
  dialogVisible.value = true
}

function showEditDialog(row: any) {
  editingId.value = row.id
  parentId.value = 0
  form.name = row.name
  form.description = row.description || ''
  form.sort_order = row.sort_order || 0
  dialogVisible.value = true
}

async function handleSave() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    if (editingId.value) {
      await client.put(`/documents/categories/${editingId.value}`, form)
      ElMessage.success('分类已更新')
    } else {
      await client.post('/documents/categories', { ...form, parent_id: parentId.value })
      ElMessage.success('分类已创建')
    }
    dialogVisible.value = false
    loadData()
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.message || '操作失败')
  } finally { saving.value = false }
}

async function handleDelete(id: number) {
  try {
    await client.delete(`/documents/categories/${id}`)
    ElMessage.success('分类已删除')
    loadData()
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.message || '删除失败')
  }
}

onMounted(loadData)
</script>

<style scoped>
.admin-page { padding: 24px 32px; max-width: 960px; margin: 0 auto; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
.header-left { display: flex; align-items: center; gap: 10px; }
.header-icon { color: var(--color-primary); }
.header-left h2 { font-size: 20px; font-weight: 700; color: var(--color-text-primary); margin: 0; }

.category-list { display: flex; flex-direction: column; gap: 12px; }

.category-card {
  background: var(--color-bg-card); border: 1px solid var(--color-border);
  border-radius: 10px; overflow: hidden; transition: box-shadow .2s;
  box-shadow: 0 1px 3px rgba(0,0,0,.04);
}
.category-card:hover { box-shadow: 0 2px 12px rgba(0,0,0,.08); }

.card-main {
  display: flex; align-items: center; gap: 14px; padding: 16px 20px;
  border-left: 4px solid var(--color-primary);
  background: var(--color-bg-hover);
}
.card-icon { flex-shrink: 0; }
.card-body { flex: 1; min-width: 0; }
.card-title { font-size: 15px; font-weight: 600; color: var(--color-text-primary); }
.card-desc { font-size: 13px; color: var(--color-text-placeholder); margin-top: 2px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.card-actions { display: flex; gap: 2px; flex-shrink: 0; }

.sub-list { border-top: 1px solid var(--color-border); padding: 6px 0; }
.sub-card {
  display: flex; align-items: center; gap: 8px; padding: 10px 20px 10px 54px;
  transition: background .15s;
}
.sub-card:nth-child(even) { background: rgba(128,128,128,.03); }
.sub-card:hover { background: var(--color-bg-hover); }
.sub-icon { color: var(--color-text-placeholder); flex-shrink: 0; }
.sub-name { font-size: 14px; font-weight: 500; color: var(--color-text-primary); white-space: nowrap; }
.sub-desc { font-size: 12px; color: var(--color-text-placeholder); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; min-width: 0; }
.sub-actions { display: flex; gap: 2px; flex-shrink: 0; opacity: 0; transition: opacity .15s; }
.sub-card:hover .sub-actions { opacity: 1; }
</style>