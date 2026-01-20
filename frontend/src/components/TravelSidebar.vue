<script setup lang="ts">
import { ref } from 'vue'
import type { TravelPlan } from '../lib/api'

const props = defineProps<{
  plan: TravelPlan | null
  isSendingFeedback: boolean
}>()

const emit = defineEmits<{
  sendFeedback: [feedback: string]
}>()

const feedbackText = ref('')

const handleSendFeedback = () => {
  if (!feedbackText.value.trim() || props.isSendingFeedback) return
  emit('sendFeedback', feedbackText.value.trim())
  feedbackText.value = ''
}
</script>

<template>
  <div class="travel-sidebar">
    <h2>旅行プラン</h2>
    <div v-if="!plan" class="no-plan">
      まだプランが作成されていません。<br>
      希望を入力して「プランを作って」と言ってみてください。
    </div>
    <div v-else class="plan-summary">
      <h3>{{ plan.itinerary.title || '旅程' }}</h3>
      <p class="plan-score">スコア: {{ (plan.score * 100).toFixed(0) }}%</p>
      <div class="score-breakdown">
        <div v-for="(score, key) in plan.score_breakdown" :key="key" class="score-item">
          <span class="score-label">{{ key }}</span>
          <span class="score-value">{{ (score * 100).toFixed(0) }}%</span>
        </div>
      </div>
      <div class="feedback-section">
        <h4>フィードバック</h4>
        <p class="feedback-hint">このプランへのご意見を教えてください</p>
        <textarea
          v-model="feedbackText"
          placeholder="良かった点、改善点など..."
          rows="3"
          class="feedback-input"
        />
        <button
          class="feedback-btn"
          @click="handleSendFeedback"
          :disabled="isSendingFeedback || !feedbackText.trim()"
        >
          {{ isSendingFeedback ? '送信中...' : 'フィードバックを送信' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.travel-sidebar h2 {
  margin: 0 0 1rem;
  font-size: 1rem;
  color: #2c3e50;
}

.no-plan {
  color: #7f8c8d;
  font-size: 0.9rem;
  line-height: 1.5;
}

.plan-summary h3 {
  margin: 0 0 0.5rem;
  font-size: 1rem;
  color: #2c3e50;
}

.plan-score {
  font-size: 0.9rem;
  color: #27ae60;
  margin: 0 0 1rem;
}

.score-breakdown {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.score-item {
  display: flex;
  justify-content: space-between;
  font-size: 0.85rem;
}

.score-label {
  color: #7f8c8d;
}

.score-value {
  color: #2c3e50;
  font-weight: 500;
}

.feedback-section {
  margin-top: 1.5rem;
  padding-top: 1rem;
  border-top: 1px solid #ecf0f1;
}

.feedback-section h4 {
  margin: 0 0 0.5rem;
  font-size: 0.9rem;
  color: #2c3e50;
}

.feedback-hint {
  margin: 0 0 0.5rem;
  font-size: 0.75rem;
  color: #7f8c8d;
}

.feedback-input {
  width: 100%;
  padding: 0.5rem;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-family: inherit;
  font-size: 0.85rem;
  resize: none;
  box-sizing: border-box;
}

.feedback-input:focus {
  outline: none;
  border-color: #3498db;
}

.feedback-btn {
  width: 100%;
  margin-top: 0.5rem;
  padding: 0.5rem 1rem;
  background: #3498db;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.85rem;
  transition: background 0.2s;
}

.feedback-btn:hover:not(:disabled) {
  background: #2980b9;
}

.feedback-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
