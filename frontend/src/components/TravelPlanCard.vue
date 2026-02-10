<script setup lang="ts">
import { ref, computed, reactive, watch } from 'vue'
import type { TravelPlan, POIFeedbackType, POICategory, GeoEnrichedItinerary, POIDetail } from '../lib/api'
import { api } from '../lib/api'
import ItineraryDisplay from './ItineraryDisplay.vue'
import ItineraryMap from './ItineraryMap.vue'
import MapModal from './MapModal.vue'
import POIDetailModal from './POIDetailModal.vue'

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

// POI Detail modal state
const showPOIDetail = ref(false)
const poiDetail = ref<POIDetail | null>(null)
const poiDetailLoading = ref(false)
const poiDetailError = ref<string | null>(null)

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

// Handle POI click to show detail modal
const handlePOIClick = async (poiName: string, category: POICategory) => {
  showPOIDetail.value = true
  poiDetailLoading.value = true
  poiDetailError.value = null
  poiDetail.value = null

  try {
    // Get destination from plan
    const destination = props.plan.itinerary.days?.[0]?.items?.[0]?.poi?.location || ''
    poiDetail.value = await api.getPOIDetail(poiName, destination, category)
  } catch (error) {
    console.error('Failed to fetch POI detail:', error)
    poiDetailError.value = 'POI情報の取得に失敗しました'
  } finally {
    poiDetailLoading.value = false
  }
}

const closePOIDetail = () => {
  showPOIDetail.value = false
  poiDetail.value = null
  poiDetailError.value = null
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
          @poi-click="handlePOIClick"
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

    <!-- POI Detail modal -->
    <POIDetailModal
      :visible="showPOIDetail"
      :poi="poiDetail"
      :loading="poiDetailLoading"
      :error="poiDetailError"
      @close="closePOIDetail"
    />
  </div>
</template>

<style scoped>
.plan-card {
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(102, 126, 234, 0.12);
  border-radius: 16px;
  overflow: hidden;
  margin: 0.5rem 0;
  box-shadow:
    0 2px 8px rgba(102, 126, 234, 0.06),
    0 8px 32px rgba(102, 126, 234, 0.04);
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
  background: rgba(102, 126, 234, 0.04);
}

.plan-icon {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.12) 0%, rgba(118, 75, 162, 0.12) 100%);
  color: #667eea;
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
  background: rgba(102, 126, 234, 0.08);
  color: #667eea;
  border-radius: 12px;
  border: 1px solid rgba(102, 126, 234, 0.1);
}

.plan-details {
  padding: 0 16px 16px;
  border-top: 1px solid rgba(102, 126, 234, 0.08);
}

.feedback-hint {
  padding: 8px 12px;
  margin: 12px 0;
  background: rgba(102, 126, 234, 0.08);
  color: #667eea;
  border-radius: 8px;
  font-size: 0.8rem;
  text-align: center;
  border: 1px solid rgba(102, 126, 234, 0.1);
}

.rationale {
  margin-top: 16px;
  padding: 12px;
  background: rgba(102, 126, 234, 0.04);
  border-radius: 10px;
  border: 1px solid rgba(102, 126, 234, 0.06);
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

.feedback-section {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid rgba(102, 126, 234, 0.08);
}

.feedback-toggle {
  width: 100%;
  padding: 10px;
  background: rgba(102, 126, 234, 0.06);
  border: 1px solid rgba(102, 126, 234, 0.1);
  border-radius: 10px;
  color: #667eea;
  font-size: 0.9rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.feedback-toggle:hover {
  background: rgba(102, 126, 234, 0.12);
}

.feedback-form textarea {
  width: 100%;
  padding: 10px;
  border: 1px solid rgba(102, 126, 234, 0.15);
  border-radius: 10px;
  font-size: 0.9rem;
  resize: vertical;
  font-family: inherit;
  background: rgba(255, 255, 255, 0.9);
}

.feedback-form textarea:focus {
  outline: none;
  border-color: rgba(102, 126, 234, 0.5);
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
}

.feedback-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 10px;
}

.cancel-btn {
  padding: 8px 16px;
  background: rgba(0, 0, 0, 0.04);
  border: 1px solid rgba(0, 0, 0, 0.06);
  border-radius: 8px;
  color: #4a5568;
  font-size: 0.85rem;
  cursor: pointer;
  transition: background 0.2s;
}

.cancel-btn:hover {
  background: rgba(0, 0, 0, 0.08);
}

.submit-btn {
  padding: 8px 16px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
  border-radius: 8px;
  color: white;
  font-size: 0.85rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.submit-btn:hover:not(:disabled) {
  box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
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
  border-radius: 10px;
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
  background: rgba(102, 126, 234, 0.06);
  border: 1px solid rgba(102, 126, 234, 0.1);
  border-radius: 8px;
  color: #667eea;
  font-size: 0.85rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.map-expand-btn:hover {
  background: rgba(102, 126, 234, 0.12);
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
