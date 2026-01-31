<script setup lang="ts">
import { ref } from 'vue'
import { api } from '../lib/api'
import type { LoginResponse } from '../lib/api'

const emit = defineEmits<{
  login: [response: LoginResponse]
}>()

const username = ref('')
const isLoading = ref(false)
const error = ref<string | null>(null)

const handleSubmit = async () => {
  const trimmedUsername = username.value.trim()

  if (!trimmedUsername) {
    error.value = 'ユーザー名を入力してください'
    return
  }

  if (trimmedUsername.length > 50) {
    error.value = 'ユーザー名は50文字以内にしてください'
    return
  }

  try {
    isLoading.value = true
    error.value = null
    const response = await api.login(trimmedUsername)
    emit('login', response)
  } catch (e) {
    console.error('Login failed:', e)
    error.value = 'ログインに失敗しました。もう一度お試しください。'
  } finally {
    isLoading.value = false
  }
}

const handleKeydown = (e: KeyboardEvent) => {
  // IME変換中はEnterで送信しない
  if (e.isComposing) return

  // Enter または Ctrl+Enter でログイン
  if (e.key === 'Enter' && !isLoading.value) {
    handleSubmit()
  }
}
</script>

<template>
  <div class="login-screen">
    <div class="login-container">
      <div class="login-header">
        <h1>Travel AI</h1>
        <p>あなたの旅をサポート</p>
      </div>

      <div class="login-form">
        <div class="form-group">
          <label for="username">ユーザー名</label>
          <input
            id="username"
            v-model="username"
            type="text"
            placeholder="ユーザー名を入力"
            :disabled="isLoading"
            @keydown="handleKeydown"
            autofocus
          />
          <p class="hint">既存のユーザー名でログイン、または新規作成されます</p>
        </div>

        <div v-if="error" class="error-message">
          {{ error }}
        </div>

        <button
          class="login-btn"
          :disabled="isLoading || !username.trim()"
          @click="handleSubmit"
        >
          <span v-if="isLoading" class="spinner"></span>
          <span v-else>ログイン</span>
        </button>
      </div>

      <div class="login-footer">
        <p>パスワードなしでログインできます</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.login-screen {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 1rem;
}

.login-container {
  background: white;
  border-radius: 16px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.2);
  width: 100%;
  max-width: 400px;
  overflow: hidden;
}

.login-header {
  background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%);
  color: white;
  padding: 2rem;
  text-align: center;
}

.login-header h1 {
  margin: 0;
  font-size: 2rem;
  font-weight: 700;
  letter-spacing: -0.5px;
}

.login-header p {
  margin: 0.5rem 0 0;
  opacity: 0.8;
  font-size: 0.95rem;
}

.login-form {
  padding: 2rem;
}

.form-group {
  margin-bottom: 1.5rem;
}

.form-group label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 500;
  color: #2d3748;
  font-size: 0.9rem;
}

.form-group input {
  width: 100%;
  padding: 0.875rem 1rem;
  border: 2px solid #e2e8f0;
  border-radius: 8px;
  font-size: 1rem;
  transition: border-color 0.2s, box-shadow 0.2s;
  box-sizing: border-box;
}

.form-group input:focus {
  outline: none;
  border-color: #667eea;
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
}

.form-group input:disabled {
  background: #f7fafc;
  cursor: not-allowed;
}

.form-group .hint {
  margin: 0.5rem 0 0;
  font-size: 0.8rem;
  color: #718096;
}

.error-message {
  margin-bottom: 1rem;
  padding: 0.75rem 1rem;
  background: rgba(245, 101, 101, 0.1);
  border: 1px solid rgba(245, 101, 101, 0.3);
  border-radius: 8px;
  color: #c53030;
  font-size: 0.875rem;
}

.login-btn {
  width: 100%;
  padding: 0.875rem 1.5rem;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
}

.login-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

.login-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  transform: none;
}

.spinner {
  width: 20px;
  height: 20px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.login-footer {
  padding: 1rem 2rem 1.5rem;
  text-align: center;
  border-top: 1px solid #e2e8f0;
}

.login-footer p {
  margin: 0;
  font-size: 0.8rem;
  color: #a0aec0;
}
</style>
