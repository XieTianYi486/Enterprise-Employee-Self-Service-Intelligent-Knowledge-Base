<template>
  <div class="main-layout" :class="{ dark: themeStore.isDark }">
    <!-- 侧边栏 -->
    <aside class="sidebar" :class="{ collapsed: isCollapse }">
      <!-- Logo -->
      <div class="sidebar-logo">
        <el-icon :size="24" color="var(--color-primary)"><Reading /></el-icon>
        <span v-if="!isCollapse" class="logo-text">员工自助服务</span>
      </div>

      <!-- 菜单：日常功能平铺，管理后台收进二级菜单 -->
      <nav class="sidebar-nav">
        <el-menu
          class="sidebar-menu"
          :default-active="currentRoute"
          :collapse="isCollapse"
          :collapse-transition="false"
          @select="onMenuSelect"
        >
          <el-menu-item index="/workbench">
            <el-icon :size="20"><HomeFilled /></el-icon>
            <template #title>工作台</template>
          </el-menu-item>

          <el-menu-item v-if="authStore.can('chat:ask')" index="/chat">
            <el-icon :size="20"><ChatDotRound /></el-icon>
            <template #title>智能问答</template>
          </el-menu-item>

          <el-menu-item v-if="authStore.can('documents:read')" index="/documents">
            <el-icon :size="20"><FolderOpened /></el-icon>
            <template #title>知识库文档</template>
          </el-menu-item>

          <el-menu-item index="/tickets">
            <el-icon :size="20"><Tickets /></el-icon>
            <template #title>我的工单</template>
          </el-menu-item>

          <el-menu-item index="/contacts">
            <el-icon :size="20"><OfficeBuilding /></el-icon>
            <template #title>通讯录</template>
          </el-menu-item>

          <el-menu-item index="/attendance">
            <el-icon :size="20"><Clock /></el-icon>
            <template #title>考勤打卡</template>
          </el-menu-item>

          <el-menu-item index="/notifications">
            <el-icon :size="20"><Bell /></el-icon>
            <template #title>
              <span>消息中心</span>
              <span v-if="!isCollapse && unreadCount > 0" class="nav-badge">{{ unreadCount > 99 ? '99+' : unreadCount }}</span>
            </template>
          </el-menu-item>

          <el-menu-item v-if="authStore.can('leaves:read')" index="/leaves">
            <el-icon :size="20"><Calendar /></el-icon>
            <template #title>请假管理</template>
          </el-menu-item>

          <el-menu-item v-if="authStore.can('expenses:read')" index="/expenses">
            <el-icon :size="20"><Money /></el-icon>
            <template #title>报销管理</template>
          </el-menu-item>

          <el-menu-item v-if="authStore.can('approvals:read')" index="/approvals">
            <el-icon :size="20"><Stamp /></el-icon>
            <template #title>审批中心</template>
          </el-menu-item>

          <!-- 管理后台：知识运营 -->
          <el-sub-menu v-if="authStore.isAdmin()" index="kb-ops">
            <template #title>
              <el-icon :size="20"><Reading /></el-icon>
              <span>知识运营</span>
            </template>
            <el-menu-item index="/admin/documents">
              <el-icon :size="16"><Document /></el-icon>文档管理
            </el-menu-item>
            <el-menu-item index="/admin/categories">
              <el-icon :size="16"><CollectionTag /></el-icon>分类管理
            </el-menu-item>
            <el-menu-item index="/admin/review">
              <el-icon :size="16"><Finished /></el-icon>知识审核
              <span v-if="!isCollapse && reviewCount > 0" class="nav-badge">{{ reviewCount > 99 ? '99+' : reviewCount }}</span>
            </el-menu-item>
            <el-menu-item index="/admin/logs">
              <el-icon :size="16"><List /></el-icon>问答日志
            </el-menu-item>
            <el-menu-item index="/admin/stats">
              <el-icon :size="16"><DataAnalysis /></el-icon>统计分析
            </el-menu-item>
          </el-sub-menu>

          <!-- 管理后台：系统管理 -->
          <el-sub-menu v-if="authStore.isAdmin()" index="sys-mgmt">
            <template #title>
              <el-icon :size="20"><Setting /></el-icon>
              <span>系统管理</span>
            </template>
            <el-menu-item index="/admin/announcements">
              <el-icon :size="16"><Message /></el-icon>公告管理
            </el-menu-item>
            <el-menu-item index="/admin/tickets">
              <el-icon :size="16"><Tickets /></el-icon>工单管理
            </el-menu-item>
            <el-menu-item v-if="authStore.isSuperAdmin()" index="/admin/users">
              <el-icon :size="16"><User /></el-icon>用户管理
            </el-menu-item>
            <el-menu-item v-if="authStore.isSuperAdmin()" index="/admin/roles">
              <el-icon :size="16"><Avatar /></el-icon>角色管理
            </el-menu-item>
            <el-menu-item v-if="authStore.isSuperAdmin()" index="/admin/departments">
              <el-icon :size="16"><OfficeBuilding /></el-icon>部门管理
            </el-menu-item>
            <el-menu-item v-if="authStore.isSuperAdmin()" index="/admin/sensitive-words">
              <el-icon :size="16"><Lock /></el-icon>敏感词管理
            </el-menu-item>
            <el-menu-item v-if="authStore.isSuperAdmin()" index="/admin/audit-logs">
              <el-icon :size="16"><Memo /></el-icon>审计日志
            </el-menu-item>
          </el-sub-menu>

          <el-menu-item index="/profile">
            <el-icon :size="20"><UserFilled /></el-icon>
            <template #title>个人中心</template>
          </el-menu-item>
        </el-menu>
      </nav>

      <!-- 底部操作 -->
      <div class="sidebar-footer">
        <button class="footer-btn" @click="isCollapse = !isCollapse" title="收起/展开">
          <el-icon :size="18"><component :is="isCollapse ? 'Expand' : 'Fold'" /></el-icon>
        </button>
        <button class="footer-btn" @click="themeStore.toggle()" title="切换主题">
          <el-icon :size="18"><component :is="themeStore.isDark ? 'Sunny' : 'Moon'" /></el-icon>
        </button>
        <button v-if="!isCollapse" class="footer-btn logout-btn" @click="authStore.logout()" title="退出登录">
          <el-icon :size="18"><SwitchButton /></el-icon>
          <span class="nav-label">退出</span>
        </button>
      </div>
    </aside>

    <!-- 主内容 -->
    <main class="main-content">
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/store/auth'
import { useThemeStore } from '@/store/theme'
import { reviewApi } from '@/api/security'
import client from '@/api/client'
import {
  Expand, Fold, Sunny, Moon, Reading, SwitchButton,
  ChatDotRound, UserFilled, FolderOpened, OfficeBuilding, Bell,
  Tickets, Stamp, Calendar, Money, HomeFilled, Clock, Setting,
  Document, CollectionTag, Finished, List, DataAnalysis,
  Message, User, Avatar, Lock, Memo,
} from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const themeStore = useThemeStore()

// el-menu 点击回调：仅当 index 是路由路径时跳转（二级菜单分组 index 不是路径）
function onMenuSelect(index: string) {
  if (index.startsWith('/')) router.push(index)
}
const isCollapse = ref(false)
const reviewCount = ref(0)
const unreadCount = ref(0)

// 拉取待审核文档数量（侧边栏红色角标）
async function loadReviewCount() {
  try {
    const res = await reviewApi.queue({ review_status: 1, page: 1, page_size: 1 })
    reviewCount.value = res.data.data?.total || 0
  } catch {
    reviewCount.value = 0
  }
}

// 拉取站内消息未读数（侧边栏角标，60 秒轮询）
async function loadUnreadCount() {
  try {
    const res = await client.get('/notifications', { params: { page: 1, page_size: 1 } })
    unreadCount.value = res.data.data?.unread || 0
  } catch {
    unreadCount.value = 0
  }
}
onMounted(() => {
  loadReviewCount()
  loadUnreadCount()
  setInterval(loadUnreadCount, 60000)
})
// 进入消息中心后刷新未读数
watch(() => route.path, (p) => {
  if (p === '/notifications') loadUnreadCount()
})

const currentRoute = computed(() => {
  const path = route.path
  if (path === '/workbench') return '/workbench'
  if (path.startsWith('/admin/documents')) return '/admin/documents'
  if (path.startsWith('/admin/categories')) return '/admin/categories'
  if (path.startsWith('/admin/users')) return '/admin/users'
  if (path.startsWith('/admin/roles')) return '/admin/roles'
  if (path.startsWith('/admin/departments')) return '/admin/departments'
  if (path.startsWith('/admin/logs')) return '/admin/logs'
  if (path.startsWith('/admin/stats')) return '/admin/stats'
  if (path === '/leaves') return '/leaves'
  if (path === '/expenses') return '/expenses'
  if (path === '/approvals') return '/approvals'
  if (path === '/contacts') return '/contacts'
  if (path === '/attendance') return '/attendance'
  if (path === '/notifications') return '/notifications'
  if (path.startsWith('/admin/announcements')) return '/admin/announcements'
  if (path.startsWith('/admin/tickets')) return '/admin/tickets'
  if (path.startsWith('/admin/review')) return '/admin/review'
  if (path.startsWith('/admin/sensitive-words')) return '/admin/sensitive-words'
  if (path.startsWith('/admin/audit-logs')) return '/admin/audit-logs'
  if (path.startsWith('/documents')) return '/documents'
  if (path.startsWith('/tickets')) return '/tickets'
  if (path.startsWith('/chat')) return '/chat'
  if (path.startsWith('/profile')) return '/profile'
  return '/chat'
})
</script>

<style scoped>
/* ========== 布局 ========== */
.main-layout {
  display: flex;
  height: 100vh;
  background: var(--color-bg-page);
  color: var(--color-text-body);
}

/* ========== 侧边栏 ========== */
.sidebar {
  width: 220px;
  display: flex;
  flex-direction: column;
  background: var(--color-bg-card);
  border-right: 1px solid var(--color-border);
  transition: width 0.25s ease;
  flex-shrink: 0;
  overflow: hidden;
  z-index: 10;
}
.sidebar.collapsed { width: 64px; }

/* Logo */
.sidebar-logo {
  height: 56px;
  display: flex;
  align-items: center;
  padding: 0 20px;
  gap: 10px;
  border-bottom: 1px solid var(--color-border);
  flex-shrink: 0;
}
.sidebar.collapsed .sidebar-logo { justify-content: center; padding: 0; }

.logo-text {
  font-size: 16px;
  font-weight: 700;
  color: var(--color-text-primary);
  white-space: nowrap;
}

/* 导航 */
.sidebar-nav {
  flex: 1;
  padding: 12px 8px;
  overflow-y: auto;
  overflow-x: hidden;
}
.sidebar.collapsed .sidebar-nav { padding: 12px 0; }

/* el-menu 主题覆盖，与整体青绿风格保持一致 */
.sidebar-menu {
  border-right: none;
  background: transparent;
  width: 100%;
  --el-menu-bg-color: transparent;
  --el-menu-text-color: var(--color-text-secondary);
  --el-menu-hover-text-color: var(--color-primary);
  --el-menu-active-color: var(--color-primary);
  --el-menu-hover-bg-color: var(--color-primary-light);
  --el-menu-item-height: 40px;
  --el-menu-sub-item-height: 36px;
  --el-menu-base-level-padding: 12px;
  --el-menu-level-padding: 16px;
  --el-menu-collapse-width: 64px;
}
.sidebar-menu :deep(.el-menu-item),
.sidebar-menu :deep(.el-sub-menu__title) {
  border-radius: 8px;
  margin-bottom: 2px;
  font-size: 14px;
  gap: 12px;
}
.sidebar-menu :deep(.el-menu-item.is-active) {
  font-weight: 600;
}
.sidebar-menu :deep(.el-menu-item .el-icon),
.sidebar-menu :deep(.el-sub-menu__title .el-icon) {
  font-size: 20px;
}

.nav-badge {
  min-width: 18px;
  height: 18px;
  margin-left: auto;
  padding: 0 5px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 9px;
  background: #f56c6c;
  color: #fff;
  font-size: 11px;
  line-height: 18px;
  font-weight: 600;
}

/* 底部 */
.sidebar-footer {
  padding: 8px;
  border-top: 1px solid var(--color-border);
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  justify-content: center;
}

.sidebar.collapsed .sidebar-footer {
  flex-direction: column;
  align-items: center;
}

.footer-btn {
  width: 36px;
  height: 36px;
  border: none;
  background: transparent;
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-text-secondary);
  transition: all 0.15s;
}
.footer-btn:hover { background: var(--color-primary-light); color: var(--color-primary); }
.logout-btn {
  width: auto;
  padding: 0 12px;
  gap: 6px;
  font-size: 13px;
}
.logout-btn:hover { color: var(--color-danger) !important; background: #FEF2F2; }

/* ========== 主内容区 ========== */
.main-content {
  flex: 1;
  overflow-y: auto;
  background: var(--color-bg-page);
  min-width: 0;
}
</style>
