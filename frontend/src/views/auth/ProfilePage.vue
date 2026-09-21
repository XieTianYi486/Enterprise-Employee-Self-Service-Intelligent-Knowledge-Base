<template>
  <div class="profile-page">
    <div class="page-header">
      <div class="header-left">
        <el-icon class="header-icon" :size="22"><User /></el-icon>
        <h2>个人中心</h2>
      </div>
    </div>

    <div class="content-grid">
      <!-- 左侧：资料卡 -->
      <el-card class="profile-card" shadow="never">
        <div class="avatar-upload" @click="triggerUpload">
          <img v-if="avatarPreview" :src="avatarPreview" class="avatar-img" />
          <el-icon v-else :size="52" class="avatar-placeholder"><UserFilled /></el-icon>
          <div class="avatar-overlay">
            <el-icon :size="20"><Camera /></el-icon>
            <span>更换头像</span>
          </div>
        </div>
        <input ref="fileInputRef" type="file" accept="image/jpeg,image/png,image/gif,image/webp" hidden @change="handleAvatarChange" />

        <!-- 预设头像：点击即设为本人头像 -->
        <div class="preset-title">预设头像</div>
        <div class="preset-list">
          <div
            v-for="p in PRESET_AVATARS"
            :key="p.src"
            class="preset-item"
            :title="`使用${p.name}`"
            @click="applyPresetAvatar(p.src)"
          >
            <img :src="p.src" :alt="p.name" />
            <el-icon v-if="presetLoading === p.src" class="preset-loading is-loading"><Loading /></el-icon>
          </div>
        </div>

        <div class="profile-name">{{ authStore.user?.real_name || authStore.user?.username }}</div>
        <el-tag effect="plain" size="small">{{ authStore.user?.role_name || '-' }}</el-tag>

        <div class="profile-meta">
          <div class="meta-row">
            <el-icon :size="14"><User /></el-icon>
            <span>@{{ authStore.user?.username }}</span>
          </div>
          <div class="meta-row" v-if="authStore.user?.position">
            <el-icon :size="14"><Briefcase /></el-icon>
            <span>{{ authStore.user.position }}</span>
          </div>
          <div class="meta-row" v-if="authStore.user?.department">
            <el-icon :size="14"><OfficeBuilding /></el-icon>
            <span>{{ authStore.user.department }}</span>
          </div>
          <div class="meta-row">
            <el-icon :size="14"><Clock /></el-icon>
            <span>{{ formatTime(authStore.user?.created_at) }} 加入</span>
          </div>
        </div>
      </el-card>

      <!-- 右侧：标签页 -->
      <el-card class="settings-card" shadow="never">
        <el-tabs v-model="activeTab">
          <el-tab-pane label="编辑资料" name="profile">
            <el-form ref="profileFormRef" :model="form" :rules="profileRules" label-width="90px" label-position="left" class="profile-form">
              <el-form-item label="真实姓名" prop="real_name">
                <el-input v-model="form.real_name" placeholder="请输入真实姓名" clearable />
              </el-form-item>
              <el-form-item label="邮箱" prop="email">
                <el-input v-model="form.email" placeholder="请输入邮箱地址" clearable />
              </el-form-item>
              <el-form-item label="手机" prop="phone">
                <el-input v-model="form.phone" placeholder="请输入手机号码" clearable />
              </el-form-item>
              <el-form-item label="职位" prop="position">
                <el-input v-model="form.position" placeholder="例如：开发工程师" clearable />
              </el-form-item>
              <el-form-item label="部门">
                <el-input :model-value="authStore.user?.department || '未分配'" disabled placeholder="部门由管理员分配" />
              </el-form-item>
              <el-form-item label="性别" prop="gender">
                <el-select v-model="form.gender" placeholder="选择性别" clearable style="width: 100%">
                  <el-option label="男" value="男" />
                  <el-option label="女" value="女" />
                </el-select>
              </el-form-item>
              <el-form-item label="入职日期" prop="entry_date">
                <el-date-picker
                  v-model="form.entry_date"
                  type="date"
                  value-format="YYYY-MM-DD"
                  placeholder="选择入职日期"
                  style="width: 100%"
                />
              </el-form-item>
              <el-form-item>
                <el-button type="primary" :loading="saving" @click="handleSave">保存修改</el-button>
                <el-button @click="resetForm">重置</el-button>
              </el-form-item>
            </el-form>
          </el-tab-pane>

          <el-tab-pane label="修改密码" name="password">
            <el-form ref="pwdFormRef" :model="passwordForm" :rules="pwdRules" label-width="90px" label-position="left" class="profile-form">
              <el-form-item label="旧密码" prop="old_password" required>
                <el-input v-model="passwordForm.old_password" type="password" show-password placeholder="请输入旧密码" />
              </el-form-item>
              <el-form-item label="新密码" prop="new_password" required>
                <el-input v-model="passwordForm.new_password" type="password" show-password placeholder="长度不少于 6 位" />
              </el-form-item>
              <el-form-item label="确认密码" prop="confirm_password" required>
                <el-input v-model="passwordForm.confirm_password" type="password" show-password placeholder="再次输入新密码" />
              </el-form-item>
              <el-form-item>
                <el-button type="primary" @click="handleChangePassword">确认修改</el-button>
              </el-form-item>
            </el-form>
          </el-tab-pane>
        </el-tabs>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import {
  UserFilled, Camera, User, Briefcase, OfficeBuilding, Clock, Loading,
} from '@element-plus/icons-vue'
import { useAuthStore } from '@/store/auth'
import { authApi } from '@/api/auth'
// 预设头像（沿用参考项目个人中心的演示头像）
import avatar1 from '@/assets/avatars/avatar-1.jpg'
import avatar2 from '@/assets/avatars/avatar-2.jpg'
import avatar3 from '@/assets/avatars/avatar-3.jpg'
import avatar4 from '@/assets/avatars/avatar-4.jpg'

const PRESET_AVATARS = [
  { name: '头像 1', src: avatar1 },
  { name: '头像 2', src: avatar2 },
  { name: '头像 3', src: avatar3 },
  { name: '头像 4', src: avatar4 },
]

const authStore = useAuthStore()
const fileInputRef = ref<HTMLInputElement>()
const saving = ref(false)
const avatarPreview = ref<string | null>(null)
const presetLoading = ref<string | null>(null)
const activeTab = ref('profile')
const profileFormRef = ref<FormInstance>()
const pwdFormRef = ref<FormInstance>()

const form = reactive({
  real_name: '',
  email: '',
  phone: '',
  position: '',
  gender: '',
  entry_date: '',
})

const passwordForm = reactive({
  old_password: '',
  new_password: '',
  confirm_password: '',
})

const profileRules: FormRules = {
  email: [{ type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' }],
  phone: [{ pattern: /^1[3-9]\d{9}$/, message: '请输入正确的手机号', trigger: 'blur' }],
}

const pwdRules: FormRules = {
  old_password: [{ required: true, message: '请输入旧密码', trigger: 'blur' }],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '密码长度不能少于 6 位', trigger: 'blur' },
  ],
  confirm_password: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    {
      validator: (_rule, value, callback) => {
        if (value !== passwordForm.new_password) {
          callback(new Error('两次输入的新密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur',
    },
  ],
}

function formatTime(t: string | undefined) {
  if (!t) return '-'
  const d = new Date(t.endsWith('Z') ? t : t + 'Z')
  return d.toLocaleDateString('zh-CN')
}

function initForm() {
  const u = authStore.user
  if (!u) return
  form.real_name = u.real_name || ''
  form.email = u.email || ''
  form.phone = u.phone || ''
  form.position = u.position || ''
  form.gender = u.gender || ''
  form.entry_date = u.entry_date ? String(u.entry_date).slice(0, 10) : ''
  avatarPreview.value = u.avatar_url ? u.avatar_url : null
}

function resetForm() {
  initForm()
  profileFormRef.value?.clearValidate()
}

onMounted(initForm)

function triggerUpload() {
  fileInputRef.value?.click()
}

async function handleAvatarChange(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  try {
    const res = await authApi.uploadAvatar(file)
    const url = res.data.data.avatar_url
    avatarPreview.value = url
    if (authStore.user) {
      authStore.user.avatar_url = url
    }
    ElMessage.success('头像已更新')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.message || '上传失败')
  }
}

/** 应用预设头像：本地打包图片转 File 后走统一上传接口，保证服务端落库 */
async function applyPresetAvatar(src: string) {
  if (presetLoading.value) return
  presetLoading.value = src
  try {
    const resp = await fetch(src)
    const blob = await resp.blob()
    const ext = src.split('.').pop() || 'png'
    const file = new File([blob], `preset-avatar.${ext}`, { type: blob.type })
    const res = await authApi.uploadAvatar(file)
    const url = res.data.data.avatar_url
    avatarPreview.value = url
    if (authStore.user) {
      authStore.user.avatar_url = url
    }
    ElMessage.success('头像已更新')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.message || '头像设置失败')
  } finally {
    presetLoading.value = null
  }
}

async function handleSave() {
  const valid = await profileFormRef.value?.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    const res = await authApi.updateProfile({
      real_name: form.real_name || undefined,
      email: form.email || undefined,
      phone: form.phone || undefined,
      position: form.position || undefined,
      gender: form.gender || undefined,
      entry_date: form.entry_date || undefined,
    })
    if (authStore.user) {
      Object.assign(authStore.user, res.data.data)
    }
    ElMessage.success('个人信息已更新')
    initForm()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function handleChangePassword() {
  const valid = await pwdFormRef.value?.validate().catch(() => false)
  if (!valid) return
  try {
    await authApi.changePassword({
      old_password: passwordForm.old_password,
      new_password: passwordForm.new_password,
    })
    ElMessage.success('密码修改成功，请重新登录')
    authStore.logout()
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.message || '修改失败')
  }
}
</script>

<style scoped>
.profile-page {
  padding: 24px 32px;
  max-width: 1100px;
}
.page-header { margin-bottom: 20px; }
.header-left { display: flex; align-items: center; gap: 10px; }
.header-icon { color: var(--color-primary); }
.page-header h2 {
  font-size: 20px; font-weight: 700;
  color: var(--color-text-primary); margin: 0;
}
.content-grid {
  display: grid; grid-template-columns: 280px 1fr; gap: 24px;
  align-items: start;
}

/* 资料卡 */
.profile-card { border-radius: 12px; }
.profile-card :deep(.el-card__body) {
  display: flex; flex-direction: column; align-items: center; padding: 28px 20px;
}
.avatar-upload {
  width: 120px; height: 120px; border-radius: 50%;
  cursor: pointer; position: relative; overflow: hidden;
  border: 2px dashed var(--color-border);
  display: flex; align-items: center; justify-content: center;
  background: var(--color-bg-hover);
  transition: border-color .2s;
}
.avatar-upload:hover { border-color: var(--color-primary); }
.avatar-upload img.avatar-img { border: none; }
.avatar-img { width: 100%; height: 100%; object-fit: cover; }
.avatar-placeholder { color: var(--color-text-placeholder); }
.avatar-overlay {
  position: absolute; inset: 0; border-radius: 50%;
  background: rgba(0,0,0,.5); color: #fff;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 4px; font-size: 12px; opacity: 0; transition: opacity .2s;
}
.avatar-upload:hover .avatar-overlay { opacity: 1; }

/* 预设头像 */
.preset-title {
  margin-top: 16px;
  font-size: 12px;
  color: var(--color-text-secondary);
  align-self: flex-start;
}
.preset-list {
  margin-top: 8px;
  display: flex;
  gap: 10px;
  align-self: flex-start;
}
.preset-item {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  overflow: hidden;
  cursor: pointer;
  position: relative;
  border: 2px solid transparent;
  transition: border-color 0.15s, transform 0.15s;
}
.preset-item:hover {
  border-color: var(--color-primary);
  transform: translateY(-2px);
}
.preset-item img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.preset-loading {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
}

.profile-name { margin: 14px 0 6px; font-size: 17px; font-weight: 600; color: var(--color-text-primary); }
.profile-meta { margin-top: 20px; width: 100%; border-top: 1px solid var(--color-border); padding-top: 16px; display: flex; flex-direction: column; gap: 10px; }
.meta-row { display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--color-text-secondary); }

/* 设置卡 */
.settings-card { border-radius: 12px; }
.settings-card :deep(.el-tabs__header) { margin-bottom: 20px; }
.profile-form { max-width: 480px; }

@media (max-width: 900px) {
  .content-grid { grid-template-columns: 1fr; }
}
</style>