<script setup lang="ts">
import { ref, computed, reactive, watch } from 'vue'
import type { TravelPlan, POIFeedbackType, POICategory, GeoEnrichedItinerary } from '../lib/api'
import { api } from '../lib/api'
import ItineraryDisplay from './ItineraryDisplay.vue'
import ItineraryMap from './ItineraryMap.vue'
import MapModal from './MapModal.vue'

const props = defineProps<{
  plan: TravelPlan
  userId?: string
}>()

const emit = defineEmits<{
  feedback: [feedback: string]
  'poi-feedback': [poiName: string, feedbackType: POIFeedbackType, learned: { category: string; tag: string; is_new: boolean } | null]
}>()

const isExpanded = ref(false)
const feedbackText = ref('')
const showFeedbackForm = ref(false)

// Track POI feedback state
const poiFeedback = reactive<Record<string, POIFeedbackType>>({})

// Map state
const geoData = ref<GeoEnrichedItinerary | null>(null)
const geoLoading = ref(false)
const geoError = ref(false)
const showMapModal = ref(false)

// Fetch geo data when plan becomes available
const fetchGeoData = async () => {
  if (geoData.value || geoLoading.value) return
  geoLoading.value = true
  geoError.value = false
  try {
    const destination = props.plan.itinerary.days?.[0]?.items?.[0]?.poi?.location || ''
    geoData.value = await api.enrichItineraryGeo(props.plan.itinerary, destination)
  } catch {
    geoError.value = true
  } finally {
    geoLoading.value = false
  }
}

watch(() => props.plan, () => {
  fetchGeoData()
}, { immediate: true })

const scorePercentage = computed(() => Math.round(props.plan.score * 100))

const scoreColor = computed(() => {
  if (props.plan.score >= 0.8) return '#48bb78'
  if (props.plan.score >= 0.6) return '#4299e1'
  if (props.plan.score >= 0.4) return '#ed8936'
  return '#f56565'
})

const daysCount = computed(() => props.plan.itinerary.days?.length || 0)

const submitFeedback = () => {
  if (feedbackText.value.trim()) {
    emit('feedback', feedbackText.value)
    feedbackText.value = ''
    showFeedbackForm.value = false
  }
}

const handlePOIFeedback = async (
  poiName: string,
  category: POICategory,
  feedbackType: POIFeedbackType,
  tags: string[]
) => {
  if (!props.userId) {
    console.error('User ID is required for POI feedback')
    return
  }

  // Optimistically update UI
  poiFeedback[poiName] = feedbackType

  try {
    const response = await api.sendPOIFeedback(
      props.userId,
      props.plan.id,
      poiName,
      category,
      feedbackType,
      tags
    )

    // Emit event for toast notification
    emit('poi-feedback', poiName, feedbackType, response.learned_preference)
  } catch (error) {
    console.error('Failed to send POI feedback:', error)
    // Revert on error
    delete poiFeedback[poiName]
  }
}
</script>

<template>
  <div class="plan-card">
    <div class="plan-header" @click="isExpanded = !isExpanded">
      <div class="plan-icon">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
          <circle cx="12" cy="10" r="3" />
        </svg>
      </div>
      <div class="plan-info">
        <h3 class="plan-title">{{ plan.itinerary.title || '旅行プラン' }}</h3>
        <p class="plan-subtitle">{{ daysCount }}日間の旅程</p>
      </div>
      <div class="plan-score" :style="{ backgroundColor: scoreColor }">
        {{ scorePercentage }}
      </div>
      <div class="expand-icon" :class="{ expanded: isExpanded }">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </div>
    </div>

    <div v-if="!isExpanded" class="plan-summary">
      <p>{{ plan.itinerary.summary }}</p>
      <div v-if="plan.itinerary.highlights && plan.itinerary.highlights.length > 0" class="quick-highlights">
        <span v-for="(h, i) in plan.itinerary.highlights.slice(0, 3)" :key="i" class="highlight-tag">
          {{ h }}
        </span>
      </div>
    </div>

    <Transition name="slide">
      <div v-if="isExpanded" class="plan-details">
        <div class="feedback-hint">
          各スポットの👍👎で好みを教えてください
        </div>

        <ItineraryDisplay
          :itinerary="plan.itinerary"
          :feedback-enabled="!!userId"
          :poi-feedback="poiFeedback"
          @poi-feedback="handlePOIFeedback"
        />

        <!-- Map section -->
        <div v-if="geoLoading" class="map-section map-loading">
          <div class="map-skeleton"></div>
          <span class="loading-text">地図を読み込み中...</span>
        </div>
        <div v-else-if="geoData && !geoError" class="map-section">
          <ItineraryMap
            :geo-data="geoData"
            :selected-day="0"
            height="250px"
          />
          <button class="map-expand-btn" @click.stop="showMapModal = true">
            地図を大きく見る
          </button>
        </div>

        <div v-if="plan.rationale" class="rationale">
          <h4>このプランについて</h4>
          <p>{{ plan.rationale }}</p>
        </div>

        <div class="score-breakdown" v-if="Object.keys(plan.score_breakdown).length > 0">
          <h4>スコア詳細</h4>
          <div class="score-bars">
            <div v-for="(value, key) in plan.score_breakdown" :key="key" class="score-bar-item">
              <span class="score-label">{{ key }}</span>
              <div class="score-bar">
                <div class="score-fill" :style="{ width: `${value * 100}%` }"></div>
              </div>
              <span class="score-value">{{ Math.round(value * 100) }}</span>
            </div>
          </div>
        </div>

        <div class="feedback-section">
          <button
            v-if="!showFeedbackForm"
            class="feedback-toggle"
            @click.stop="showFeedbackForm = true"
          >
            コメントを送る
          </button>
          <div v-else class="feedback-form" @click.stop>
            <textarea
              v-model="feedbackText"
              placeholder="このプランについてのご意見をお聞かせください..."
              rows="3"
            ></textarea>
            <div class="feedback-actions">
              <button class="cancel-btn" @click="showFeedbackForm = false">
                キャンセル
              </button>
              <button class="submit-btn" @click="submitFeedback" :disabled="!feedbackText.trim()">
                送信
              </button>
            </div>
          </div>
        </div>
      </div>
    </Transition>

    <!-- Full-screen map modal -->
    <MapModal
      v-if="geoData"
      :geo-data="geoData"
      :visible="showMapModal"
      @close="showMapModal = false"
    />
  </div>
</template>

<style scoped>
.plan-card {
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  overflow: hidden;
  margin: 0.5rem 0;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.plan-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  cursor: pointer;
  transition: background 0.2s;
}

.plan-header:hover {
  background: #f7fafc;
}

.plan-icon {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #ebf8ff;
  color: #3182ce;
  border-radius: 10px;
}

.plan-info {
  flex: 1;
}

.plan-title {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: #2d3748;
}

.plan-subtitle {
  margin: 2px 0 0;
  font-size: 0.85rem;
  color: #718096;
}

.plan-score {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  color: white;
  font-size: 0.85rem;
  font-weight: 600;
}

.expand-icon {
  color: #a0aec0;
  transition: transform 0.3s;
}

.expand-icon.expanded {
  transform: rotate(180deg);
}

.plan-summary {
  padding: 0 16px 16px;
}

.plan-summary p {
  margin: 0;
  font-size: 0.9rem;
  color: #4a5568;
  line-height: 1.5;
}

.quick-highlights {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
}

.highlight-tag {
  font-size: 0.75rem;
  padding: 4px 10px;
  background: #edf2f7;
  color: #4a5568;
  border-radius: 12px;
}

.plan-details {
  padding: 0 16px 16px;
  border-top: 1px solid #e2e8f0;
}

.feedback-hint {
  padding: 8px 12px;
  margin: 12px 0;
  background: #ebf8ff;
  color: #2b6cb0;
  border-radius: 6px;
  font-size: 0.8rem;
  text-align: center;
}

.rationale {
  margin-top: 16px;
  padding: 12px;
  background: #f7fafc;
  border-radius: 8px;
}

.rationale h4 {
  margin: 0 0 8px;
  font-size: 0.85rem;
  color: #2d3748;
}

.rationale p {
  margin: 0;
  font-size: 0.85rem;
  color: #4a5568;
  line-height: 1.5;
}

.score-breakdown {
  margin-top: 16px;
}

.score-breakdown h4 {
  margin: 0 0 10px;
  font-size: 0.85rem;
  color: #2d3748;
}

.score-bars {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.score-bar-item {
  display: flex;
  align-items: center;
  gap: 10px;
}

.score-label {
  width: 80px;
  font-size: 0.75rem;
  color: #718096;
}

.score-bar {
  flex: 1;
  height: 8px;
  background: #e2e8f0;
  border-radius: 4px;
  overflow: hidden;
}

.score-fill {
  height: 100%;
  background: #4299e1;
  border-radius: 4px;
  transition: width 0.3s;
}

.score-value {
  width: 30px;
  font-size: 0.75rem;
  color: #4a5568;
  text-align: right;
}

.feedback-section {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #e2e8f0;
}

.feedback-toggle {
  width: 100%;
  padding: 10px;
  background: #edf2f7;
  border: none;
  border-radius: 8px;
  color: #4a5568;
  font-size: 0.9rem;
  cursor: pointer;
  transition: background 0.2s;
}

.feedback-toggle:hover {
  background: #e2e8f0;
}

.feedback-form textarea {
  width: 100%;
  padding: 10px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 0.9rem;
  resize: vertical;
  font-family: inherit;
}

.feedback-form textarea:focus {
  outline: none;
  border-color: #4299e1;
}

.feedback-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 10px;
}

.cancel-btn {
  padding: 8px 16px;
  background: #edf2f7;
  border: none;
  border-radius: 6px;
  color: #4a5568;
  font-size: 0.85rem;
  cursor: pointer;
}

.submit-btn {
  padding: 8px 16px;
  background: #4299e1;
  border: none;
  border-radius: 6px;
  color: white;
  font-size: 0.85rem;
  cursor: pointer;
}

.submit-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.map-section {
  margin-top: 16px;
}

.map-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.map-skeleton {
  width: 100%;
  height: 250px;
  background: linear-gradient(110deg, #e2e8f0 8%, #edf2f7 18%, #e2e8f0 33%);
  background-size: 200% 100%;
  border-radius: 8px;
  animation: skeleton-shine 1.5s linear infinite;
}

@keyframes skeleton-shine {
  to {
    background-position-x: -200%;
  }
}

.loading-text {
  font-size: 0.8rem;
  color: #a0aec0;
}

.map-expand-btn {
  display: block;
  width: 100%;
  margin-top: 8px;
  padding: 8px;
  background: #edf2f7;
  border: none;
  border-radius: 6px;
  color: #4a5568;
  font-size: 0.85rem;
  cursor: pointer;
  transition: background 0.2s;
}

.map-expand-btn:hover {
  background: #e2e8f0;
}

/* Transition */
.slide-enter-active,
.slide-leave-active {
  transition: all 0.3s ease;
  overflow: hidden;
}

.slide-enter-from,
.slide-leave-to {
  opacity: 0;
  max-height: 0;
}

.slide-enter-to,
.slide-leave-from {
  opacity: 1;
  max-height: 2000px;
}
</style>
