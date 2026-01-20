<script setup lang="ts">
import { ref } from 'vue'
import type { TravelPlan } from '../lib/api'
import ItineraryDisplay from './ItineraryDisplay.vue'

const props = defineProps<{
  plan: TravelPlan | null
  isSendingFeedback: boolean
}>()

const emit = defineEmits<{
  sendFeedback: [feedback: string]
}>()

const feedbackText = ref('')
const showItinerary = ref(false)

const handleSendFeedback = () => {
  if (!feedbackText.value.trim() || props.isSendingFeedback) return
  emit('sendFeedback', feedbackText.value.trim())
  feedbackText.value = ''
}

const toggleItinerary = () => {
  showItinerary.value = !showItinerary.value
}

const getScoreLabel = (key: string): string => {
  const labels: Record<string, string> = {
    completeness: '充実度',
    accommodation: '宿泊',
    meals: '食事',
    budget: '予算適合',
  }
  return labels[key] || key
}
</script>

<template>
  <div class="travel-sidebar">
    <h2>旅行プラン</h2>
    <div v-if="!plan" class="no-plan">
      まだプランが作成されていません。<br>
      希望を入力して「プランを作って」と言ってみてください。
    </div>
    <div v-else class="plan-container">
      <div class="plan-header">
        <h3>{{ plan.itinerary.title || '旅程' }}</h3>
        <p v-if="plan.itinerary.summary" class="plan-summary-text">
          {{ plan.itinerary.summary }}
        </p>
      </div>

      <div class="plan-score-section">
        <div class="overall-score">
          <span class="overall-label">総合スコア</span>
          <span class="overall-value">{{ (plan.score * 100).toFixed(0) }}%</span>
        </div>
        <div class="score-breakdown">
          <div v-for="(score, key) in plan.score_breakdown" :key="key" class="score-item">
            <span class="score-label">{{ getScoreLabel(String(key)) }}</span>
            <div class="score-bar-container">
              <div class="score-bar" :style="{ width: `${score * 100}%` }"></div>
            </div>
            <span class="score-percent">{{ (score * 100).toFixed(0) }}%</span>
          </div>
        </div>
      </div>

      <button class="toggle-itinerary-btn" @click="toggleItinerary">
        {{ showItinerary ? '旅程を閉じる' : '旅程を表示' }}
      </button>

      <div v-if="showItinerary" class="itinerary-section">
        <ItineraryDisplay :itinerary="plan.itinerary" />
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

.plan-container {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.plan-header h3 {
  margin: 0 0 0.25rem;
  font-size: 1rem;
  color: #2c3e50;
}

.plan-summary-text {
  margin: 0;
  font-size: 0.8rem;
  color: #7f8c8d;
  line-height: 1.4;
}

.plan-score-section {
  padding: 0.75rem;
  background: #f8f9fa;
  border-radius: 6px;
}

.overall-score {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.75rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid #e0e0e0;
}

.overall-label {
  font-size: 0.85rem;
  color: #2c3e50;
  font-weight: 500;
}

.overall-value {
  font-size: 1.1rem;
  font-weight: 600;
  color: #27ae60;
}

.score-breakdown {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.score-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.8rem;
}

.score-label {
  width: 60px;
  color: #7f8c8d;
}

.score-bar-container {
  flex: 1;
  height: 6px;
  background: #e0e0e0;
  border-radius: 3px;
  overflow: hidden;
}

.score-bar {
  height: 100%;
  background: #3498db;
  border-radius: 3px;
  transition: width 0.3s ease;
}

.score-percent {
  width: 35px;
  text-align: right;
  color: #2c3e50;
  font-weight: 500;
}

.toggle-itinerary-btn {
  width: 100%;
  padding: 0.6rem 1rem;
  background: #27ae60;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.85rem;
  transition: background 0.2s;
}

.toggle-itinerary-btn:hover {
  background: #219a52;
}

.itinerary-section {
  max-height: 400px;
  overflow-y: auto;
  border: 1px solid #e0e0e0;
  border-radius: 6px;
}

.feedback-section {
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
