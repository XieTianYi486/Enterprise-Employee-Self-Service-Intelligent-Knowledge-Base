<template>
  <div class="ct-page">
    <div class="page-header">
      <div class="header-left">
        <el-icon class="header-icon" :size="24"><OfficeBuilding /></el-icon>
        <h2>通讯录</h2>
        <el-tag size="small" round type="info">{{ totalMembers }} 位同事</el-tag>
      </div>
      <el-input
        v-model="keyword"
        placeholder="搜索姓名 / 职位 / 邮箱..."
        :prefix-icon="Search"
        clearable
        style="width: 260px"
      />
    </div>

    <div class="ct-layout">
      <!-- 左侧组织树 -->
      <el-card class="ct-tree-card" shadow="never">
        <el-tree
          :data="treeData"
          :props="{ label: 'name', children: 'children' }"
          node-key="id"
          highlight-current
          :default-expanded-keys="expandedKeys"
          :expand-on-click-node="false"
          @node-click="onDeptClick"
        >
          <template #default="{ data }">
            <span class="tree-node">
              <el-icon :size="14"><FolderOpened v-if="data.children" /><UserFilled v-else /></el-icon>
              <span>{{ data.name }}</span>
              <span class="tree-count" v-if="data.members?.length">({{ data.members.length }})</span>
            </span>
          </template>
        </el-tree>
        <div class="tree-unassigned" v-if="unassigned.length" @click="showUnassigned = !showUnassigned">
          <el-icon :size="14"><QuestionFilled /></el-icon>
          <span>未分配部门（{{ unassigned.length }}）</span>
        </div>
      </el-card>

      <!-- 右侧成员区 -->
      <div class="ct-members">
        <div class="member-section-title">{{ currentDeptName }}</div>
        <div class="member-grid" v-loading="loading">
          <div v-for="m in filteredMembers" :key="m.id" class="member-card">
            <el-avatar :size="46" :src="m.avatar_url || ''">
              {{ (m.real_name || '?').charAt(0) }}
            </el-avatar>
            <div class="member-info">
              <div class="member-name">
                {{ m.real_name }}
                <el-tag size="small" effect="plain" :type="roleTagType(m.role_name)">{{ m.role_name }}</el-tag>
              </div>
              <div class="member-position" v-if="m.position">{{ m.position }}</div>
              <div class="member-contact">
                <span v-if="m.email"><el-icon :size="12"><Message /></el-icon>{{ m.email }}</span>
                <span v-if="m.phone"><el-icon :size="12"><Phone /></el-icon>{{ m.phone }}</span>
              </div>
              <div class="member-entry" v-if="m.entry_date">
                入职于 {{ m.entry_date }}
              </div>
            </div>
          </div>
          <el-empty v-if="!filteredMembers.length" description="暂无成员" :image-size="70" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { OfficeBuilding, Search, FolderOpened, UserFilled, QuestionFilled, Message, Phone } from '@element-plus/icons-vue'
import client from '@/api/client'

interface Member {
  id: number
  real_name: string
  username: string
  position: string | null
  email: string | null
  phone: string | null
  avatar_url: string | null
  role_name: string | null
  entry_date: string | null
}

interface DeptNode {
  id: number
  name: string
  members: Member[]
  children?: DeptNode[]
}

const loading = ref(true)
const treeData = ref<DeptNode[]>([])
const unassigned = ref<Member[]>([])
const expandedKeys = ref<number[]>([])
const currentDeptId = ref<number | null>(null)
const currentDeptName = ref('全体成员')
const showUnassigned = ref(false)
const keyword = ref('')

const totalMembers = computed(() => {
  const count = (nodes: DeptNode[]): number =>
    nodes.reduce((acc, n) => acc + n.members.length + count(n.children || []), 0)
  return count(treeData.value) + unassigned.value.length
})

const currentMembers = computed<Member[]>(() => {
  if (showUnassigned.value) return unassigned.value
  if (currentDeptId.value === null) {
    const flat = (nodes: DeptNode[]): Member[] =>
      nodes.flatMap(n => [...n.members, ...flat(n.children || [])])
    return flat(treeData.value)
  }
  const find = (nodes: DeptNode[]): DeptNode | null => {
    for (const n of nodes) {
      if (n.id === currentDeptId.value) return n
      const hit = find(n.children || [])
      if (hit) return hit
    }
    return null
  }
  return find(treeData.value)?.members || []
})

const filteredMembers = computed(() => {
  if (!keyword.value.trim()) return currentMembers.value
  const kw = keyword.value.trim().toLowerCase()
  return currentMembers.value.filter(m =>
    m.real_name.toLowerCase().includes(kw) ||
    (m.position || '').toLowerCase().includes(kw) ||
    (m.email || '').toLowerCase().includes(kw) ||
    (m.phone || '').includes(kw),
  )
})

function roleTagType(name: string | null) {
  if (!name) return 'info'
  if (name.includes('超级')) return ''
  if (name.includes('知识库')) return 'warning'
  if (name.includes('部门')) return 'primary'
  if (name.includes('总经理')) return 'success'
  return 'info'
}

function onDeptClick(data: DeptNode) {
  currentDeptId.value = data.id
  currentDeptName.value = `${data.name}（${data.members.length} 人）`
  showUnassigned.value = false
}

async function loadTree() {
  loading.value = true
  try {
    const res = await client.get('/contacts/tree')
    treeData.value = res.data.data?.tree || []
    unassigned.value = res.data.data?.unassigned || []
    expandedKeys.value = treeData.value.map(d => d.id)
  } finally {
    loading.value = false
  }
}

onMounted(loadTree)
</script>

<style scoped>
.ct-page { padding: 24px 32px; max-width: 1400px; margin: 0 auto; }
.page-header { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 20px; }
.header-left { display: flex; align-items: center; gap: 10px; }
.header-icon { color: var(--color-primary); }
.page-header h2 { font-size: 20px; font-weight: 700; color: var(--color-text-primary); margin: 0; }

.ct-layout { display: grid; grid-template-columns: 280px 1fr; gap: 16px; align-items: start; }

.ct-tree-card { border-radius: 12px; }
.tree-node { display: flex; align-items: center; gap: 6px; font-size: 14px; }
.tree-count { font-size: 12px; color: var(--color-text-placeholder); }
.tree-unassigned {
  margin-top: 10px; padding: 8px 10px; border-radius: 8px;
  display: flex; align-items: center; gap: 6px;
  font-size: 13px; color: var(--color-text-secondary);
  cursor: pointer; border: 1px dashed var(--color-border);
}
.tree-unassigned:hover { border-color: var(--color-primary); color: var(--color-primary); }

.member-section-title {
  font-size: 15px; font-weight: 700; color: var(--color-text-primary);
  margin-bottom: 14px;
}
.member-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 12px;
  min-height: 120px;
}
.member-card {
  display: flex; gap: 12px;
  background: var(--color-bg-card, #fff);
  border: 1px solid var(--color-border);
  border-radius: 12px;
  padding: 14px;
  transition: transform 0.15s, box-shadow 0.15s;
}
.member-card:hover { transform: translateY(-2px); box-shadow: 0 8px 20px rgba(13, 148, 136, 0.08); }
.member-info { min-width: 0; }
.member-name {
  display: flex; align-items: center; gap: 8px;
  font-size: 14px; font-weight: 700; color: var(--color-text-primary);
}
.member-position { font-size: 13px; color: var(--color-text-body); margin-top: 3px; }
.member-contact {
  display: flex; flex-wrap: wrap; gap: 12px;
  font-size: 12px; color: var(--color-text-secondary); margin-top: 6px;
}
.member-contact span { display: inline-flex; align-items: center; gap: 4px; }
.member-entry { font-size: 12px; color: var(--color-text-placeholder); margin-top: 4px; }

@media (max-width: 1000px) {
  .ct-layout { grid-template-columns: 1fr; }
}
</style>
