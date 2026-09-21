<template>
  <div class="register-page">
    <!-- 左侧：品牌视觉区（与登录页保持一致：背景图 + 中间靠左文案） -->
    <div class="register-left">
      <div class="left-shade"></div>
      <div class="left-copy">
        <h1 class="main-title">企业员工自助服务系统</h1>
        <p class="main-sub">Enterprise Employee Self-Service System</p>
        <div class="sub-list">
          <div class="sub-item">
            <span class="logo" v-html="logoKb"></span>
            <span>制度智能问答，双路检索、答案带出处</span>
          </div>
          <div class="sub-item">
            <span class="logo" v-html="logoFlow"></span>
            <span>请假报销两级审批，进度实时可查</span>
          </div>
          <div class="sub-item">
            <span class="logo" v-html="logoChart"></span>
            <span>工单公告工作台，事务一站式自助办理</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 右侧：注册表单区（与登录页同风格） -->
    <div class="register-right">
      <div class="right-decor" aria-hidden="true">
        <span class="orb orb-a"></span>
        <span class="orb orb-b"></span>
        <span class="glow-ring"></span>
      </div>

      <div class="form-card">
        <div class="form-head">
          <div class="badge">企业员工自助服务平台</div>
          <h2>创建账号</h2>
          <p>注册后即可自助办理日常事务</p>
        </div>

        <el-form
          ref="formRef"
          :model="form"
          :rules="rules"
          label-position="top"
          class="register-form"
          @submit.prevent="handleRegister"
        >
          <el-row :gutter="12">
            <el-col :span="12">
              <el-form-item label="用户名" prop="username">
                <el-input
                  v-model="form.username"
                  placeholder="请输入用户名"
                  :prefix-icon="User"
                  size="large"
                />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="真实姓名" prop="real_name">
                <el-input
                  v-model="form.real_name"
                  placeholder="请输入真实姓名"
                  :prefix-icon="UserFilled"
                  size="large"
                />
              </el-form-item>
            </el-col>
          </el-row>

          <el-form-item label="所属部门" prop="dept_id">
            <el-select
              v-model="form.dept_id"
              placeholder="请选择所属部门"
              size="large"
              style="width: 100%"
              clearable
            >
              <el-option
                v-for="dept in departments"
                :key="dept.id"
                :label="dept.name"
                :value="dept.id"
              />
            </el-select>
          </el-form-item>

          <el-form-item label="邮箱">
            <el-input
              v-model="form.email"
              placeholder="请输入邮箱（选填）"
              :prefix-icon="Message"
              size="large"
            />
          </el-form-item>

          <el-form-item label="密码" prop="password">
            <el-input
              v-model="form.password"
              type="password"
              placeholder="请输入6-20位密码"
              :prefix-icon="Lock"
              size="large"
              show-password
            />
          </el-form-item>

          <el-form-item label="确认密码" prop="confirmPassword">
            <el-input
              v-model="form.confirmPassword"
              type="password"
              placeholder="请再次输入密码"
              :prefix-icon="Lock"
              size="large"
              show-password
              @keyup.enter="handleRegister"
            />
          </el-form-item>

          <el-form-item label="安全验证" prop="captcha">
            <div class="captcha-row">
              <el-input
                v-model="form.captcha"
                placeholder="计算结果"
                size="large"
                class="captcha-input"
                @keyup.enter="handleRegister"
              />
              <button type="button" class="captcha-refresh" @click="loadCaptcha" title="点击刷新">
                <span>{{ captchaChallenge }}</span>
              </button>
            </div>
          </el-form-item>

          <el-button
            type="primary"
            size="large"
            :loading="loading"
            native-type="submit"
            class="register-btn"
          >
            {{ loading ? '正在注册...' : '创建账号' }}
          </el-button>

          <div class="form-footer">
            <span>已有账号？</span>
            <router-link to="/login" class="login-link">
              <el-button type="primary" plain size="default" class="goto-login-btn">
                立即登录 <el-icon><ArrowRight /></el-icon>
              </el-button>
            </router-link>
          </div>
        </el-form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  User, UserFilled, Lock, Message, ArrowRight,
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { authApi } from '@/api/auth'
import { authSecurity } from '@/api/security'

const router = useRouter()
const formRef = ref<FormInstance>()
const loading = ref(false)

// 注册页始终使用明亮模式
let wasDark = false
onMounted(() => {
  wasDark = document.documentElement.classList.contains('dark')
  document.documentElement.classList.remove('dark')
  loadCaptcha()
})
onUnmounted(() => {
  if (wasDark) document.documentElement.classList.add('dark')
})

// 左侧功能亮点图标（SVG，青绿色系，与登录页一致）
const logoKb = `<svg viewBox="0 0 48 48"><path d="M10 12h20a4 4 0 014 4v20H14a4 4 0 01-4-4V12z" fill="#5eead4"/><path d="M14 12V8h20a4 4 0 014 4v20" fill="#99f6e4"/><path d="M18 22h12M18 28h8" stroke="#0f766e" stroke-width="2"/></svg>`
const logoFlow = `<svg viewBox="0 0 48 48"><rect x="6" y="8" width="14" height="10" rx="3" fill="#0d9488"/><rect x="28" y="19" width="14" height="10" rx="3" fill="#2dd4bf"/><rect x="6" y="30" width="14" height="10" rx="3" fill="#5eead4"/><path d="M20 13h6c4 0 6 3 6 6" stroke="#134e4a" stroke-width="3" fill="none"/><path d="M20 35h6c4 0 6-3 6-6" stroke="#134e4a" stroke-width="3" fill="none"/></svg>`
const logoChart = `<svg viewBox="0 0 48 48"><rect x="8" y="26" width="8" height="14" rx="2" fill="#99f6e4"/><rect x="20" y="16" width="8" height="24" rx="2" fill="#2dd4bf"/><rect x="32" y="10" width="8" height="30" rx="2" fill="#0d9488"/></svg>`

// 算式验证码（与登录页一致，防止批量注册）
const captchaChallenge = ref('')
const captchaToken = ref('')

async function loadCaptcha() {
  try {
    const res = await authSecurity.captcha()
    const data = res.data.data
    captchaToken.value = data.token
    captchaChallenge.value = data.challenge
    form.captcha = ''
  } catch {
    ElMessage.error('验证码加载失败，请刷新页面重试')
  }
}

const departments = ref<any[]>([])

// 拉取部门列表
async function loadDepartments() {
  try {
    const res = await fetch('/api/v1/admin/departments/public')
    const data = await res.json()
    if (data.code === 0) departments.value = data.data || []
  } catch { /* public endpoint might not be accessible yet */ }
}
onMounted(loadDepartments)

const form = reactive({
  username: '',
  real_name: '',
  dept_id: null as number | null,
  email: '',
  password: '',
  confirmPassword: '',
  captcha: '',
})

const validateConfirm = (_rule: any, value: string, callback: any) => {
  if (value !== form.password) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

const rules: FormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 30, message: '用户名需3-30个字符', trigger: 'blur' },
  ],
  real_name: [
    { required: true, message: '请输入真实姓名', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 20, message: '密码需6-20个字符', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    { validator: validateConfirm, trigger: 'blur' },
  ],
  captcha: [
    { required: true, message: '请输入计算结果', trigger: 'blur' },
  ],
}

async function handleRegister() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    await authApi.register({
      username: form.username,
      password: form.password,
      real_name: form.real_name,
      email: form.email || undefined,
      dept_id: form.dept_id || undefined,
      captcha_token: captchaToken.value,
      captcha_code: form.captcha,
    })
    ElMessage.success('注册成功，请登录')
    router.push('/login')
  } catch (err: any) {
    const msg = err?.response?.data?.message || '注册失败'
    ElMessage.error(msg)
    // 失败后刷新验证码，防止脚本重复尝试
    loadCaptcha()
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.register-page {
  min-height: 100vh;
  display: flex;
  background: linear-gradient(160deg, #f2fbfa 0%, #e6f7f5 45%, #d9f1ee 100%);
}

/* ==================== 左侧品牌视觉区（与登录页一致） ==================== */
.register-left {
  flex: 1;
  position: relative;
  background: url('@/assets/login-bg.jpg') center/cover no-repeat;
  overflow: hidden;
}

/* 轻渐变：自左向右淡出，保证中间靠左的文字区可读 */
.left-shade {
  position: absolute;
  inset: 0;
  background: linear-gradient(
    to right,
    rgba(240, 253, 250, 0.96) 0%,
    rgba(240, 253, 250, 0.82) 26%,
    rgba(240, 253, 250, 0.42) 52%,
    rgba(255, 255, 255, 0) 74%
  );
}

.left-copy {
  position: absolute;
  left: 0;
  right: 0;
  top: 50%;
  transform: translateY(-50%);
  padding: 0 6% 0 7%;
  color: #134e4a;
}

.main-title {
  margin: 0 0 8px;
  font-size: 40px;
  line-height: 1.2;
  font-weight: 800;
  letter-spacing: 1px;
  color: #0f766e;
  text-shadow: 0 2px 10px rgba(255, 255, 255, 0.6);
}

.main-sub {
  margin: 0 0 20px;
  font-size: 15px;
  letter-spacing: 0.6px;
  color: #5f716f;
}

.sub-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  align-items: flex-start;
}

.sub-item {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 15px;
  line-height: 1.4;
  font-weight: 600;
  color: #334155;
  padding: 8px 16px 8px 10px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.8);
  border: 1px solid rgba(153, 246, 228, 0.9);
  box-shadow: 0 6px 16px rgba(148, 163, 184, 0.14);
  backdrop-filter: blur(8px);
}

.logo {
  width: 34px;
  height: 34px;
  flex: 0 0 34px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.logo :deep(svg) {
  width: 34px;
  height: 34px;
  display: block;
}

/* ==================== 右侧表单区（与登录页一致） ==================== */
.register-right {
  width: 620px;
  flex: 0 0 620px;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
  background:
    radial-gradient(ellipse 90% 70% at 12% 8%, rgba(94, 234, 212, 0.35), transparent 58%),
    radial-gradient(ellipse 70% 55% at 92% 88%, rgba(45, 212, 191, 0.18), transparent 52%),
    radial-gradient(ellipse 55% 45% at 78% 18%, rgba(153, 246, 228, 0.4), transparent 48%),
    linear-gradient(168deg, #f7fdfc 0%, #e9f7f5 42%, #d8f0ec 100%);
}

.register-right::before {
  content: "";
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(13, 148, 136, 0.06) 1px, transparent 1px),
    linear-gradient(90deg, rgba(13, 148, 136, 0.06) 1px, transparent 1px);
  background-size: 36px 36px;
  mask-image: radial-gradient(ellipse 80% 70% at 50% 50%, #000 18%, transparent 78%);
  pointer-events: none;
}

.right-decor {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 0;
}

.orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(18px);
}

.orb-a {
  width: 220px;
  height: 220px;
  left: -70px;
  top: 8%;
  background: radial-gradient(circle, rgba(94, 234, 212, 0.45), transparent 70%);
}

.orb-b {
  width: 180px;
  height: 180px;
  right: -40px;
  bottom: 12%;
  background: radial-gradient(circle, rgba(45, 212, 191, 0.35), transparent 70%);
}

.glow-ring {
  position: absolute;
  width: 280px;
  height: 280px;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  border-radius: 50%;
  border: 1px solid rgba(153, 246, 228, 0.4);
  box-shadow: 0 0 60px rgba(13, 148, 136, 0.1) inset;
}

.form-card {
  width: 540px;
  max-height: calc(100vh - 40px);
  overflow-y: auto;
  padding: 30px 32px 24px;
  border-radius: 24px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.9) 0%, rgba(248, 253, 252, 0.82) 100%);
  border: 1px solid rgba(255, 255, 255, 0.95);
  box-shadow:
    0 24px 60px rgba(13, 148, 136, 0.12),
    0 8px 24px rgba(148, 163, 184, 0.16),
    inset 0 1px 0 rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(22px);
  position: relative;
  z-index: 1;
}

.form-head {
  text-align: center;
  margin-bottom: 18px;
}

.badge {
  display: inline-block;
  padding: 4px 12px;
  border-radius: 999px;
  background: #f0fdfa;
  color: #0f766e;
  border: 1px solid #99f6e4;
  font-weight: 700;
  font-size: 12px;
  margin-bottom: 12px;
}

.form-head h2 {
  margin: 0 0 6px;
  font-size: 28px;
  color: #134e4a;
}

.form-head p {
  margin: 0;
  color: #64748b;
  font-size: 14px;
}

.register-form :deep(.el-input__wrapper) {
  border-radius: 12px;
  box-shadow: 0 0 0 1px #cceee8 inset;
  background: #f8fdfc;
  padding: 5px 14px;
  transition: all 0.2s;
}

.register-form :deep(.el-input__wrapper:hover),
.register-form :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px #0d9488 inset, 0 8px 18px rgba(13, 148, 136, 0.12);
}

.register-form :deep(.el-select__wrapper) {
  border-radius: 12px;
  box-shadow: 0 0 0 1px #cceee8 inset;
  background: #f8fdfc;
}

.register-form :deep(.el-form-item) {
  margin-bottom: 16px;
}

/* 验证码行（与登录页一致） */
.captcha-row {
  display: flex;
  gap: 8px;
  width: 100%;
}

.captcha-input {
  flex: 1;
}

.captcha-refresh {
  min-width: 118px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid #cceee8;
  border-radius: 10px;
  background: linear-gradient(135deg, #f0fdfa, #d9f5f0);
  color: #0f766e;
  font-weight: 600;
  font-size: 14px;
  cursor: pointer;
  padding: 0 10px;
  white-space: nowrap;
  transition: all 0.2s;
}

.captcha-refresh:hover {
  border-color: #0d9488;
  color: #0f766e;
  background: linear-gradient(135deg, #d9f5f0, #c9efe8);
}

.register-btn {
  width: 100%;
  margin-top: 4px;
  height: 46px;
  border: none;
  border-radius: 12px;
  font-size: 16px;
  font-weight: 700;
  letter-spacing: 2px;
  background: linear-gradient(90deg, #0d9488, #0f766e);
  color: #fff;
}

.register-btn:hover {
  filter: brightness(1.05);
  transform: translateY(-1px);
}

.form-footer {
  margin-top: 18px;
  padding-top: 16px;
  border-top: 1px solid #e2e8f0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  font-size: 14px;
  color: #64748b;
}

.login-link {
  text-decoration: none;
}

.goto-login-btn {
  border-color: #0d9488 !important;
  color: #0d9488 !important;
}

/* ==================== 响应式 ==================== */
@media (max-width: 1080px) {
  .register-left {
    display: none;
  }
  .register-right {
    width: 100%;
    flex-basis: 100%;
  }
}

@media (max-width: 640px) {
  .form-card {
    width: 92%;
    padding: 24px 20px;
  }
}
</style>
