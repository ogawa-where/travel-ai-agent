<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { api, type LLMHealthResponse } from '../lib/api'

const healthData = ref<LLMHealthResponse | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const expanded = ref(false)

let refreshInterval: number | null = null

const fetchHealth = async (force: boolean = false) => {
  loading.value = true
  error.value = null
  try {
    healthData.value = await api.getLLMHealth(force)
  } catch (e) {
    error.value = 'ワーカー状態の取得に失敗しました'
    console.error('Health check failed:', e)
  } finally {
    loading.value = false
  }
}

const getRoleLabel = (role: string): string => {
  const labels: Record<string, string> = {
    heavy: '重量',
    light: '軽量',
    embed: '埋込',
  }
  return labels[role] || role
}

const getRoleColor = (role: string): string => {
  const colors: Record<string, string> = {
    heavy: '#e74c3c',
    light: '#3498db',
    embed: '#9b59b6',
  }
  return colors[role] || '#95a5a6'
}

onMounted(() => {
  fetchHealth()
  // 5秒ごとに更新
  refreshInterval = window.setInterval(() => fetchHealth(), 5000)
})

onUnmounted(() => {
  if (refreshInterval) {
    clearInterval(refreshInterval)
  }
})
</script>

<template>
  <div class="worker-status">
    <button
      class="status-toggle"
      @click="expanded = !expanded"
      :class="{ 'has-error': healthData && !healthData.all_healthy }"
    >
      <span class="status-indicator" :class="{
        'healthy': healthData?.all_healthy,
        'partial': healthData && !healthData.all_healthy && healthData.any_healthy,
        'unhealthy': healthData && !healthData.any_healthy,
        'loading': loading
      }"></span>
      <span class="status-text">
        LLM {{ healthData ? `${healthData.healthy}/${healthData.total}` : '-' }}
      </span>
      <svg
        class="chevron"
        :class="{ 'expanded': expanded }"
        width="12"
        height="12"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
      >
        <polyline points="6 9 12 15 18 9"></polyline>
      </svg>
    </button>

    <div v-if="expanded" class="status-panel">
      <div class="panel-header">
        <span>ワーカー状態</span>
        <button class="refresh-btn" @click="fetchHealth(true)" :disabled="loading">
          <svg
            class="refresh-icon"
            :class="{ 'spinning': loading }"
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
          >
            <path d="M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8" />
            <path d="M21 3v5h-5" />
          </svg>
        </button>
      </div>

      <div v-if="error" class="error-message">{{ error }}</div>

      <div v-else-if="healthData" class="workers-list">
        <div
          v-for="worker in healthData.workers"
          :key="worker.host"
          class="worker-item"
          :class="{ 'unhealthy': !worker.healthy }"
        >
          <span
            class="worker-indicator"
            :class="{ 'healthy': worker.healthy, 'unhealthy': !worker.healthy }"
          ></span>
          <span class="worker-host">{{ worker.host.split(':')[0] }}</span>
          <span
            class="worker-role"
            :style="{ backgroundColor: getRoleColor(worker.role) }"
          >
            {{ getRoleLabel(worker.role) }}
          </span>
          <span v-if="worker.consecutive_failures > 0" class="failure-count">
            {{ worker.consecutive_failures }}
          </span>
        </div>
      </div>

      <div v-else class="loading-message">読み込み中...</div>
    </div>
  </div>
</template>

<style scoped>
.worker-status {
  position: relative;
}

.status-toggle {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.4rem 0.75rem;
  border: 1px solid rgba(255, 255, 255, 0.2);
  background: transparent;
  color: rgba(255, 255, 255, 0.8);
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.8rem;
  transition: all 0.2s;
}

.status-toggle:hover {
  background: rgba(255, 255, 255, 0.1);
  border-color: rgba(255, 255, 255, 0.3);
}

.status-toggle.has-error {
  border-color: rgba(231, 76, 60, 0.5);
}

.status-indicator {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #95a5a6;
}

.status-indicator.healthy {
  background: #2ecc71;
  box-shadow: 0 0 6px rgba(46, 204, 113, 0.5);
}

.status-indicator.partial {
  background: #f39c12;
  box-shadow: 0 0 6px rgba(243, 156, 18, 0.5);
}

.status-indicator.unhealthy {
  background: #e74c3c;
  box-shadow: 0 0 6px rgba(231, 76, 60, 0.5);
}

.status-indicator.loading {
  animation: pulse 1s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.status-text {
  font-family: monospace;
}

.chevron {
  transition: transform 0.2s;
}

.chevron.expanded {
  transform: rotate(180deg);
}

.status-panel {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  min-width: 280px;
  background: #2c3e50;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
  z-index: 1000;
  overflow: hidden;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1rem;
  background: rgba(0, 0, 0, 0.2);
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  font-size: 0.85rem;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.9);
}

.refresh-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: none;
  background: rgba(255, 255, 255, 0.1);
  color: rgba(255, 255, 255, 0.7);
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}

.refresh-btn:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.2);
  color: white;
}

.refresh-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.refresh-icon.spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.workers-list {
  padding: 0.5rem;
}

.worker-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  border-radius: 4px;
  transition: background 0.2s;
}

.worker-item:hover {
  background: rgba(255, 255, 255, 0.05);
}

.worker-item.unhealthy {
  background: rgba(231, 76, 60, 0.1);
}

.worker-indicator {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.worker-indicator.healthy {
  background: #2ecc71;
}

.worker-indicator.unhealthy {
  background: #e74c3c;
}

.worker-host {
  flex: 1;
  font-family: monospace;
  font-size: 0.8rem;
  color: rgba(255, 255, 255, 0.9);
}

.worker-role {
  padding: 0.15rem 0.4rem;
  border-radius: 3px;
  font-size: 0.7rem;
  font-weight: 500;
  color: white;
}

.failure-count {
  padding: 0.1rem 0.35rem;
  background: rgba(231, 76, 60, 0.3);
  border-radius: 3px;
  font-size: 0.7rem;
  color: #e74c3c;
}

.error-message {
  padding: 1rem;
  color: #e74c3c;
  font-size: 0.85rem;
  text-align: center;
}

.loading-message {
  padding: 1rem;
  color: rgba(255, 255, 255, 0.6);
  font-size: 0.85rem;
  text-align: center;
}
</style>
