<script setup lang="ts">
export type TabMode = 'preference' | 'planning'

interface Props {
  activeMode: TabMode
}

interface Emits {
  (e: 'change', mode: TabMode): void
}

defineProps<Props>()
defineEmits<Emits>()
</script>

<template>
  <div class="mode-tabs">
    <button
      :class="['tab', { active: activeMode === 'preference' }]"
      @click="$emit('change', 'preference')"
    >
      <span class="tab-icon">&#128218;</span>
      <span class="tab-label">嗜好学習</span>
      <span class="tab-desc">あなたの好みを教えてください</span>
    </button>
    <button
      :class="['tab', { active: activeMode === 'planning' }]"
      @click="$emit('change', 'planning')"
    >
      <span class="tab-icon">&#9992;</span>
      <span class="tab-label">旅行企画</span>
      <span class="tab-desc">旅行プランを作成</span>
    </button>
  </div>
</template>

<style scoped>
.mode-tabs {
  display: flex;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  background: #f7fafc;
  border-bottom: 1px solid #e2e8f0;
}

.tab {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.25rem;
  padding: 0.75rem 1rem;
  background: white;
  border: 2px solid transparent;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.tab:hover {
  background: #edf2f7;
}

.tab.active {
  border-color: #4299e1;
  background: #ebf8ff;
}

.tab-icon {
  font-size: 1.5rem;
}

.tab-label {
  font-size: 0.9rem;
  font-weight: 600;
  color: #2d3748;
}

.tab-desc {
  font-size: 0.7rem;
  color: #718096;
}

.tab.active .tab-label {
  color: #2b6cb0;
}

.tab.active .tab-desc {
  color: #4299e1;
}
</style>
