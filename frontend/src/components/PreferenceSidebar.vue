<script setup lang="ts">
import type { PreferenceSignal, UserProfile } from '../lib/api'
import SidebarSkeleton from './SidebarSkeleton.vue'

defineProps<{
  signals: PreferenceSignal[]
  isCompletingLearning: boolean
  profile: UserProfile | null
  isLoading: boolean
}>()

const emit = defineEmits<{
  completeLearning: []
}>()
</script>

<template>
  <div class="preference-sidebar">
    <SidebarSkeleton v-if="isLoading" variant="preference" />
    <template v-else>
      <div v-if="profile" class="profile-section">
        <h2>プロフィール</h2>
        <p class="profile-summary">{{ profile.summary }}</p>
      </div>

      <h2>学習した嗜好</h2>
      <div v-if="signals.length === 0" class="no-signals">
        まだ嗜好が学習されていません
      </div>
        <ul v-else class="signals-list">
        <li v-for="signal in signals" :key="signal.id" class="signal-item">
          <span class="signal-category">{{ signal.category }}</span>
          <span class="signal-tag">{{ signal.tag }}</span>
          <span class="signal-weight">({{ (signal.weight * 100).toFixed(0) }}%)</span>
        </li>
      </ul>
      <div class="learning-actions" v-if="signals.length > 0">
        <button
          class="complete-learning-btn"
          @click="emit('completeLearning')"
          :disabled="isCompletingLearning"
        >
          {{ isCompletingLearning ? '処理中...' : '学習を完了する' }}
        </button>
        <p class="action-hint">学習を完了すると、嗜好が整理・統合されます</p>
      </div>
    </template>
  </div>
</template>

<style scoped>
.preference-sidebar h2 {
  margin: 0 0 1rem;
  font-size: 1rem;
  color: #2c3e50;
}

.profile-section {
  margin-bottom: 1.5rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid #ecf0f1;
}

.profile-summary {
  margin: 0;
  font-size: 0.85rem;
  color: #34495e;
  line-height: 1.6;
  background: #f8f9fa;
  padding: 0.75rem;
  border-radius: 6px;
}

.no-signals {
  color: #7f8c8d;
  font-size: 0.9rem;
  line-height: 1.5;
}

.signals-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.signal-item {
  padding: 0.5rem 0;
  border-bottom: 1px solid #ecf0f1;
  font-size: 0.9rem;
}

.signal-item:last-child {
  border-bottom: none;
}

.signal-category {
  display: inline-block;
  background: #e74c3c;
  color: white;
  padding: 0.125rem 0.5rem;
  border-radius: 4px;
  font-size: 0.75rem;
  margin-right: 0.5rem;
}

.signal-tag {
  color: #2c3e50;
}

.signal-weight {
  color: #7f8c8d;
  font-size: 0.8rem;
}

.learning-actions {
  margin-top: 1.5rem;
  padding-top: 1rem;
  border-top: 1px solid #ecf0f1;
}

.complete-learning-btn {
  width: 100%;
  padding: 0.75rem 1rem;
  background: #27ae60;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.9rem;
  font-weight: 500;
  transition: background 0.2s;
}

.complete-learning-btn:hover:not(:disabled) {
  background: #219a52;
}

.complete-learning-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.action-hint {
  margin-top: 0.5rem;
  font-size: 0.75rem;
  color: #7f8c8d;
  text-align: center;
}
</style>
