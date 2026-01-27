<template>
  <div class="login-container">
    <div class="login-box">
      <div class="login-header">
        <el-icon :size="48" color="#00d4ff"><Monitor /></el-icon>
        <h2>算力中心智能监控系统</h2>
        <p>Smart Computing Center Monitoring System</p>
      </div>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        class="login-form"
        @submit.prevent="handleLogin"
      >
        <el-form-item prop="username">
          <el-input
            v-model="form.username"
            placeholder="用户名"
            :prefix-icon="User"
            size="large"
          />
        </el-form-item>

        <el-form-item prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="密码"
            :prefix-icon="Lock"
            size="large"
            show-password
            @keyup.enter="handleLogin"
          />
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            size="large"
            :loading="loading"
            class="login-btn"
            @click="handleLogin"
          >
            登 录
          </el-button>
        </el-form-item>
      </el-form>

      <div class="login-footer">
        <p>请使用管理员分配的账户登录</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Monitor, User, Lock } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores'

const router = useRouter()
const userStore = useUserStore()

const formRef = ref()
const loading = ref(false)

const form = reactive({
  username: '',
  password: ''
})

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

async function handleLogin() {
  const valid = await formRef.value?.validate()
  if (!valid) return

  loading.value = true
  try {
    await userStore.doLogin(form.username, form.password)
    ElMessage.success('登录成功')
    router.push('/')
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped lang="scss">
.login-container {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #0a1628 0%, #0d2137 50%, #0a1628 100%);
  position: relative;

  // 添加科技感网格背景
  &::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-image:
      linear-gradient(rgba(0, 212, 255, 0.03) 1px, transparent 1px),
      linear-gradient(90deg, rgba(0, 212, 255, 0.03) 1px, transparent 1px);
    background-size: 50px 50px;
    pointer-events: none;
  }
}

.login-box {
  width: 420px;
  padding: 40px;
  background: rgba(13, 33, 55, 0.9);
  border-radius: 12px;
  box-shadow:
    0 0 40px rgba(0, 212, 255, 0.1),
    0 0 80px rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(0, 212, 255, 0.2);
  position: relative;
  z-index: 1;
}

.login-header {
  text-align: center;
  margin-bottom: 30px;

  h2 {
    margin: 16px 0 8px;
    color: #00d4ff;
    font-size: 22px;
    font-weight: 600;
    text-shadow: 0 0 10px rgba(0, 212, 255, 0.5);
  }

  p {
    margin: 0;
    color: rgba(255, 255, 255, 0.5);
    font-size: 13px;
    letter-spacing: 1px;
  }
}

.login-form {
  :deep(.el-input__wrapper) {
    background-color: rgba(10, 22, 40, 0.8);
    border: 1px solid rgba(0, 212, 255, 0.2);
    box-shadow: none;

    &:hover {
      border-color: rgba(0, 212, 255, 0.4);
    }

    &.is-focus {
      border-color: #00d4ff;
      box-shadow: 0 0 0 1px rgba(0, 212, 255, 0.2);
    }
  }

  :deep(.el-input__inner) {
    color: #fff;

    &::placeholder {
      color: rgba(255, 255, 255, 0.4);
    }
  }

  :deep(.el-input__prefix) {
    color: rgba(0, 212, 255, 0.6);
  }

  .login-btn {
    width: 100%;
    background: linear-gradient(135deg, #1890ff 0%, #00d4ff 100%);
    border: none;
    font-size: 16px;
    font-weight: 500;
    letter-spacing: 8px;

    &:hover {
      background: linear-gradient(135deg, #40a9ff 0%, #36e5ff 100%);
    }
  }
}

.login-footer {
  text-align: center;
  color: rgba(255, 255, 255, 0.4);
  font-size: 12px;
  margin-top: 20px;

  p {
    margin: 0;
  }
}
</style>
