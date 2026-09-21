import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/store/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'Login',
      component: () => import('@/views/auth/LoginPage.vue'),
      meta: { guest: true },
    },
    {
      path: '/register',
      name: 'Register',
      component: () => import('@/views/auth/RegisterPage.vue'),
      meta: { guest: true },
    },
    {
      path: '/',
      component: () => import('@/components/layout/MainLayout.vue'),
      children: [
        {
          path: '',
          redirect: '/workbench',
        },
        {
          path: 'workbench',
          name: 'Workbench',
          component: () => import('@/views/WorkbenchPage.vue'),
          meta: { title: '工作台' },
        },
        {
          path: 'chat',
          name: 'Chat',
          component: () => import('@/views/chat/ChatPage.vue'),
          meta: { title: '智能问答', permission: 'chat:ask' },
        },
        {
          path: 'chat/:sessionId',
          name: 'ChatSession',
          component: () => import('@/views/chat/ChatPage.vue'),
          meta: { title: '智能问答', permission: 'chat:ask' },
        },
        {
          path: 'documents',
          name: 'Documents',
          component: () => import('@/views/documents/BrowsePage.vue'),
          meta: { title: '知识库文档', permission: 'documents:read' },
        },
        {
          path: 'tickets',
          name: 'MyTickets',
          component: () => import('@/views/tickets/MyTicketsPage.vue'),
          meta: { title: '我的工单' },
        },
        {
          path: 'contacts',
          name: 'Contacts',
          component: () => import('@/views/ContactsPage.vue'),
          meta: { title: '通讯录' },
        },
        {
          path: 'attendance',
          name: 'Attendance',
          component: () => import('@/views/oa/AttendancePage.vue'),
          meta: { title: '考勤打卡' },
        },
        {
          path: 'notifications',
          name: 'Notifications',
          component: () => import('@/views/NotificationsPage.vue'),
          meta: { title: '消息中心' },
        },
        {
          path: 'leaves',
          name: 'Leaves',
          component: () => import('@/views/oa/LeavePage.vue'),
          meta: { title: '请假管理', permission: 'leaves:read' },
        },
        {
          path: 'expenses',
          name: 'Expenses',
          component: () => import('@/views/oa/ExpensePage.vue'),
          meta: { title: '报销管理', permission: 'expenses:read' },
        },
        {
          path: 'approvals',
          name: 'Approvals',
          component: () => import('@/views/oa/ApprovalPage.vue'),
          meta: { title: '审批中心', permission: 'approvals:read' },
        },
        {
          path: 'admin',
          redirect: '/admin/documents',
        },
        {
          path: 'admin/documents',
          name: 'AdminDocuments',
          component: () => import('@/views/admin/DocumentPage.vue'),
          meta: { title: '文档管理', admin: true },
        },
        {
          path: 'admin/categories',
          name: 'AdminCategories',
          component: () => import('@/views/admin/CategoryPage.vue'),
          meta: { title: '分类管理', admin: true },
        },
        {
          path: 'admin/users',
          name: 'AdminUsers',
          component: () => import('@/views/admin/UserPage.vue'),
          meta: { title: '用户管理', admin: true, superAdmin: true },
        },
        {
          path: 'admin/roles',
          name: 'AdminRoles',
          component: () => import('@/views/admin/RolePage.vue'),
          meta: { title: '角色管理', admin: true, superAdmin: true },
        },
        {
          path: 'admin/departments',
          name: 'AdminDepartments',
          component: () => import('@/views/admin/DeptPage.vue'),
          meta: { title: '部门管理', admin: true, superAdmin: true },
        },
        {
          path: 'admin/logs',
          name: 'AdminLogs',
          component: () => import('@/views/admin/LogPage.vue'),
          meta: { title: '问答日志', admin: true },
        },
        {
          path: 'admin/stats',
          name: 'AdminStats',
          component: () => import('@/views/admin/StatsPage.vue'),
          meta: { title: '统计分析', admin: true },
        },
        {
          path: 'admin/announcements',
          name: 'AdminAnnouncements',
          component: () => import('@/views/admin/AnnouncePage.vue'),
          meta: { title: '公告管理', admin: true },
        },
        {
          path: 'admin/tickets',
          name: 'AdminTickets',
          component: () => import('@/views/admin/TicketAdminPage.vue'),
          meta: { title: '工单管理', admin: true },
        },
        {
          path: 'admin/review',
          name: 'Review',
          component: () => import('@/views/admin/ReviewPage.vue'),
          meta: { title: '知识审核', admin: true },
        },
        {
          path: 'admin/sensitive-words',
          name: 'SensitiveWords',
          component: () => import('@/views/admin/SensitiveWordPage.vue'),
          meta: { title: '敏感词管理', admin: true },
        },
        {
          path: 'admin/audit-logs',
          name: 'AuditLogs',
          component: () => import('@/views/admin/AuditLogPage.vue'),
          meta: { title: '审计日志', admin: true },
        },
        {
          path: 'profile',
          name: 'Profile',
          component: () => import('@/views/auth/ProfilePage.vue'),
          meta: { title: '个人中心' },
        },
      ],
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'NotFound',
      component: () => import('@/views/auth/NotFoundPage.vue'),
    },
  ],
})

// 路由守卫
router.beforeEach(async (to, _from, next) => {
  const token = localStorage.getItem('access_token')
  const authStore = useAuthStore()

  // 已登录用户访问登录/注册页 → 跳转到聊天页
  if (to.meta.guest && token) {
    next('/chat')
    return
  }

  // 未登录用户访问需要认证的页面 → 跳转到登录页
  if (!to.meta.guest && !token) {
    next('/login')
    return
  }

  // 管理员页面权限检查
  if (to.meta.admin && token) {
    try {
      // 从 JWT payload 解析角色（不发起网络请求）
      // 注意：必须使用 ASCII 的 role 声明（super_admin 等），
      // atob 会把中文 role_name 按 Latin-1 解码成乱码导致比较恒为 false
      const payload = JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')))
      const role = payload.role || ''
      const isAdminUser = role === 'super_admin' || role === 'knowledge_admin'
      const isSuperAdminUser = role === 'super_admin'

      if (to.meta.superAdmin && !isSuperAdminUser) {
        next('/chat')
        return
      }
      if (!isAdminUser) {
        next('/chat')
        return
      }
    } catch {
      next('/chat')
      return
    }
  }

  // 业务功能权限检查（角色管理页可配置的权限点：chat:ask / documents:read）
  if (to.meta.permission && token) {
    try {
      // 页面刷新后首次导航时用户信息尚未加载，先初始化（含权限列表）
      if (!authStore.user) {
        await authStore.initialize()
      }
      if (!authStore.can(to.meta.permission as string)) {
        // 无权限：跳到第一个有权限的功能页；都没有则去个人中心
        if (authStore.can('chat:ask')) {
          next('/chat')
        } else if (authStore.can('leaves:read')) {
          next('/leaves')
        } else if (authStore.can('documents:read')) {
          next('/documents')
        } else {
          next('/profile')
        }
        return
      }
    } catch {
      next('/login')
      return
    }
  }

  next()
})

export default router
