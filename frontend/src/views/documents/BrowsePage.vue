<template>
  <div class="browse-page">
    <div class="page-header">
      <h2>知识库文档</h2>
      <el-input
        v-model="keyword"
        placeholder="搜索文档标题..."
        clearable
        :prefix-icon="Search"
        class="search-input"
        @input="onSearch"
      />
    </div>

    <div class="browse-body">
      <!-- 分类侧边栏 -->
      <aside class="category-sidebar">
        <div class="category-title">
          <el-icon :size="16"><FolderOpened /></el-icon>
          <span>文档分类</span>
        </div>
        <div class="category-list">
          <div
            class="category-item"
            :class="{ active: selectedCategoryId === null }"
            @click="selectedCategoryId = null"
          >全部文档</div>
          <div
            v-for="cat in categories"
            :key="cat.id"
            class="category-item"
            :class="{ active: selectedCategoryId === cat.id }"
            @click="selectedCategoryId = cat.id"
          >
            <span>{{ cat.name }}</span>
            <el-tag size="small" effect="plain">{{ cat.document_count }}</el-tag>
          </div>
        </div>
      </aside>

      <!-- 文档列表 -->
      <div class="doc-list-area">
        <el-card v-loading="loading" class="doc-card">
          <div v-if="documents.length === 0 && !loading" class="empty-state">
            <el-empty description="暂无文档" />
          </div>

          <div v-for="doc in documents" :key="doc.id" class="doc-item" @click="openContent(doc)">
            <div class="doc-icon">
              <el-icon :size="28" :color="fileIconColor(doc.file_type)">
                <component :is="fileIcon(doc.file_type)" />
              </el-icon>
            </div>
            <div class="doc-info">
              <div class="doc-title">{{ doc.title }}</div>
              <div class="doc-meta">
                <el-tag size="small" effect="plain" v-if="doc.category_name">{{ doc.category_name }}</el-tag>
                <span class="meta-item">{{ doc.file_type.toUpperCase() }}</span>
                <span class="meta-item">{{ formatFileSize(doc.file_size) }}</span>
                <span class="meta-item">{{ doc.version }}</span>
                <span class="meta-item">{{ doc.publish_date || '' }}</span>
              </div>
            </div>
            <div class="doc-arrow">
              <el-icon :size="16"><ArrowRight /></el-icon>
            </div>
          </div>
        </el-card>

        <!-- 分页 -->
        <div class="pagination-wrap" v-if="total > 0">
          <el-pagination
            v-model:current-page="page"
            :page-size="pageSize"
            :total="total"
            layout="prev, pager, next"
            @current-change="loadDocuments"
          />
        </div>
      </div>
    </div>

    <!-- 文档内容弹窗 -->
    <el-dialog
      v-model="contentVisible"
      :title="contentDoc?.title || '文档内容'"
      width="80%"
      top="5vh"
      destroy-on-close
      class="content-dialog"
    >
      <div v-loading="contentLoading" class="content-body">
        <div v-if="contentError" class="content-error">
          <el-result icon="error" :title="contentError" />
        </div>
        <div v-else-if="contentText" class="content-text" v-html="renderedContent"></div>
        <el-empty v-else-if="!contentLoading" description="暂无内容" />
      </div>
      <template #footer>
        <el-button @click="contentVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { Search, FolderOpened, ArrowRight, Document, Grid, Tickets } from '@element-plus/icons-vue'
import client from '@/api/client'
import MarkdownIt from 'markdown-it'

// html: false（默认）——文档内容中嵌入的原始 HTML 会被转义渲染，防止存储型 XSS
const md = new MarkdownIt({ breaks: true })

const loading = ref(false)
const keyword = ref('')
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const documents = ref<any[]>([])
const categories = ref<any[]>([])
const selectedCategoryId = ref<number | null>(null)

// 文档内容弹窗
const contentVisible = ref(false)
const contentLoading = ref(false)
const contentDoc = ref<any>(null)
const contentText = ref('')
const contentError = ref('')

// Markdown 渲染
const renderedContent = computed(() => {
  if (!contentText.value) return ''
  try {
    return md.render(contentText.value)
  } catch {
    return contentText.value.replace(/\n/g, '<br>')
  }
})

let searchTimer: ReturnType<typeof setTimeout> | null = null

function fileIcon(type: string) {
  return type === 'pdf' ? 'Document' : type === 'xlsx' ? 'Grid' : 'Tickets'
}

function fileIconColor(type: string) {
  return type === 'pdf' ? '#E74C3C' : type === 'xlsx' ? '#27AE60' : '#3498DB'
}

function formatFileSize(bytes: number) {
  if (!bytes) return '0 B'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

async function loadCategories() {
  try {
    const res = await client.get('/documents/categories/tree')
    categories.value = flattenCategories(res.data.data || [])
  } catch { /* ignore */ }
}

function flattenCategories(tree: any[], result: any[] = []): any[] {
  for (const node of tree) {
    result.push(node)
    if (node.children?.length) flattenCategories(node.children, result)
  }
  return result
}

async function loadDocuments() {
  loading.value = true
  try {
    const params: any = { page: page.value, page_size: pageSize.value }
    if (keyword.value) params.keyword = keyword.value
    if (selectedCategoryId.value) params.category_id = selectedCategoryId.value
    const res = await client.get('/documents', { params })
    const data = res.data.data
    documents.value = data.items || []
    total.value = data.total || 0
  } catch { /* ignore */ } finally { loading.value = false }
}

function onSearch() {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    page.value = 1
    loadDocuments()
  }, 300)
}

async function openContent(doc: any) {
  contentDoc.value = doc
  contentVisible.value = true
  contentLoading.value = true
  contentText.value = ''
  contentError.value = ''
  try {
    const res = await client.get(`/documents/${doc.id}/content`)
    contentText.value = res.data.data?.content || ''
  } catch (e: any) {
    contentError.value = e.response?.data?.message || '加载失败'
  } finally {
    contentLoading.value = false
  }
}

watch(selectedCategoryId, () => {
  page.value = 1
  loadDocuments()
})

onMounted(() => {
  loadCategories()
  loadDocuments()
})
</script>

<style scoped>
.browse-page { padding: 24px 32px; height: 100%; display: flex; flex-direction: column; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.page-header h2 { font-size: 22px; font-weight: 700; color: var(--color-text-primary); margin: 0; white-space: nowrap; }
.search-input { width: 300px; }

.browse-body { display: flex; gap: 20px; flex: 1; min-height: 0; }

/* 分类侧边栏 */
.category-sidebar {
  width: 200px;
  flex-shrink: 0;
  background: var(--color-bg-card);
  border-radius: 8px;
  border: 1px solid var(--color-border);
  overflow-y: auto;
}
.category-title {
  display: flex; align-items: center; gap: 8px;
  padding: 14px 16px; font-weight: 600; font-size: 14px;
  color: var(--color-text-primary); border-bottom: 1px solid var(--color-border);
}
.category-list { padding: 8px; }
.category-item {
  display: flex; justify-content: space-between; align-items: center;
  padding: 8px 12px; border-radius: 6px; cursor: pointer;
  font-size: 13px; color: var(--color-text-secondary); transition: all 0.15s;
}
.category-item:hover { background: var(--color-primary-light); color: var(--color-primary); }
.category-item.active { background: var(--color-primary-light); color: var(--color-primary); font-weight: 600; }

/* 文档列表 */
.doc-list-area { flex: 1; display: flex; flex-direction: column; min-width: 0; }
.doc-card { flex: 1; overflow-y: auto; }
.empty-state { padding: 40px 0; }

.doc-item {
  display: flex; align-items: center; gap: 14px;
  padding: 14px 16px; border-bottom: 1px solid var(--color-border);
  cursor: pointer; transition: background 0.15s;
}
.doc-item:last-child { border-bottom: none; }
.doc-item:hover { background: var(--color-primary-light); }

.doc-icon { flex-shrink: 0; }
.doc-info { flex: 1; min-width: 0; }
.doc-title { font-size: 15px; font-weight: 600; color: var(--color-text-primary); margin-bottom: 6px; }
.doc-meta { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.meta-item { font-size: 12px; color: var(--color-text-placeholder); }
.doc-arrow { flex-shrink: 0; color: var(--color-text-placeholder); }

.pagination-wrap { display: flex; justify-content: center; padding: 16px 0; }

/* 内容弹窗 */
.content-body { max-height: 70vh; overflow-y: auto; }
.content-error { padding: 20px 0; }
.content-text {
  padding: 16px 20px; line-height: 1.8; font-size: 14px; color: var(--color-text-primary);
}
.content-text :deep(h1), .content-text :deep(h2), .content-text :deep(h3) {
  margin-top: 24px; margin-bottom: 12px; font-weight: 700;
}
.content-text :deep(p) { margin: 8px 0; }
.content-text :deep(table) { border-collapse: collapse; width: 100%; margin: 12px 0; }
.content-text :deep(th), .content-text :deep(td) { border: 1px solid var(--color-border); padding: 8px 12px; text-align: left; }
.content-text :deep(th) { background: var(--color-primary-light); font-weight: 600; }
.content-text :deep(code) { background: var(--color-primary-light); padding: 2px 6px; border-radius: 4px; font-size: 13px; }
.content-text :deep(pre) { background: #1e1e2e; color: #cdd6f4; padding: 16px; border-radius: 8px; overflow-x: auto; }
</style>