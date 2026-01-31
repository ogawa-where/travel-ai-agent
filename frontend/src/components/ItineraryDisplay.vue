<script setup lang="ts">
import type { Itinerary, POIFeedbackType, POICategory } from '../lib/api'

const props = defineProps<{
  itinerary: Itinerary
  feedbackEnabled?: boolean
  poiFeedback?: Record<string, POIFeedbackType>  // key: poi_name, value: 'good' | 'bad'
}>()

const emit = defineEmits<{
  'poi-feedback': [poiName: string, category: POICategory, feedbackType: POIFeedbackType, tags: string[]]
}>()

const formatTime = (start: string, end: string): string => {
  if (!start && !end) return ''
  if (!end) return start
  return `${start} - ${end}`
}

const getCategoryIcon = (category: string): string => {
  switch (category) {
    case 'activity':
      return '🎯'
    case 'food':
      return '🍽️'
    case 'hotel':
      return '🏨'
    default:
      return '📍'
  }
}

const getCategoryLabel = (category: string): string => {
  switch (category) {
    case 'activity':
      return '観光・体験'
    case 'food':
      return '食事'
    case 'hotel':
      return '宿泊'
    default:
      return 'その他'
  }
}

const getFeedbackState = (poiName: string): POIFeedbackType | null => {
  return props.poiFeedback?.[poiName] || null
}

const handleFeedback = (poiName: string, category: string, feedbackType: POIFeedbackType, tags: string[] = []) => {
  emit('poi-feedback', poiName, category as POICategory, feedbackType, tags)
}
</script>

<template>
  <div class="itinerary-display">
    <div class="itinerary-header">
      <h3 class="itinerary-title">{{ itinerary.title || '旅程' }}</h3>
      <p v-if="itinerary.summary" class="itinerary-summary">{{ itinerary.summary }}</p>
    </div>

    <div v-if="itinerary.highlights && itinerary.highlights.length > 0" class="highlights">
      <h4>ハイライト</h4>
      <ul class="highlight-list">
        <li v-for="(highlight, index) in itinerary.highlights" :key="index">
          {{ highlight }}
        </li>
      </ul>
    </div>

    <div v-if="itinerary.total_budget_estimate" class="budget-estimate">
      <span class="budget-label">予算目安:</span>
      <span class="budget-value">{{ itinerary.total_budget_estimate.toLocaleString() }}円</span>
    </div>

    <div class="days-container">
      <div v-for="day in itinerary.days" :key="day.day_number" class="day-card">
        <div class="day-header">
          <span class="day-number">{{ day.day_number }}日目</span>
          <span v-if="day.date" class="day-date">{{ day.date }}</span>
          <span v-if="day.theme" class="day-theme">{{ day.theme }}</span>
        </div>

        <div class="day-items">
          <div v-for="(item, index) in day.items" :key="index" class="item-card">
            <div v-if="item.travel_from_previous" class="travel-info">
              {{ item.travel_from_previous }}
            </div>
            <div class="item-content">
              <div class="item-time" v-if="item.time_start || item.time_end">
                {{ formatTime(item.time_start, item.time_end) }}
              </div>
              <div class="item-main">
                <div class="item-header">
                  <span class="item-icon">{{ getCategoryIcon(item.poi.category) }}</span>
                  <span class="item-name">{{ item.poi.name }}</span>
                  <span class="item-category">{{ getCategoryLabel(item.poi.category) }}</span>

                  <!-- Feedback buttons -->
                  <div v-if="feedbackEnabled" class="feedback-buttons">
                    <button
                      :class="['feedback-btn', 'good', { active: getFeedbackState(item.poi.name) === 'good' }]"
                      @click.stop="handleFeedback(item.poi.name, item.poi.category, 'good', item.poi.tags || [])"
                      :disabled="getFeedbackState(item.poi.name) !== null"
                      title="良かった"
                    >
                      👍
                    </button>
                    <button
                      :class="['feedback-btn', 'bad', { active: getFeedbackState(item.poi.name) === 'bad' }]"
                      @click.stop="handleFeedback(item.poi.name, item.poi.category, 'bad', item.poi.tags || [])"
                      :disabled="getFeedbackState(item.poi.name) !== null"
                      title="改善希望"
                    >
                      👎
                    </button>
                  </div>
                </div>
                <p v-if="item.poi.description" class="item-description">
                  {{ item.poi.description }}
                </p>
                <div class="item-details">
                  <span v-if="item.poi.location" class="item-location">
                    {{ item.poi.location }}
                  </span>
                  <span v-if="item.poi.price_range" class="item-price">
                    {{ item.poi.price_range }}
                  </span>
                  <span v-if="item.poi.duration_minutes" class="item-duration">
                    約{{ item.poi.duration_minutes }}分
                  </span>
                </div>
                <div v-if="item.poi.tags && item.poi.tags.length > 0" class="item-tags">
                  <span v-for="tag in item.poi.tags" :key="tag" class="tag">{{ tag }}</span>
                </div>
                <p v-if="item.notes" class="item-notes">{{ item.notes }}</p>
              </div>
            </div>
          </div>
        </div>

        <div v-if="day.accommodation" class="accommodation">
          <div class="accommodation-header">
            <span class="accommodation-icon">🏨</span>
            <span class="accommodation-label">宿泊</span>

            <!-- Feedback buttons for accommodation -->
            <div v-if="feedbackEnabled" class="feedback-buttons">
              <button
                :class="['feedback-btn', 'good', { active: getFeedbackState(day.accommodation.name) === 'good' }]"
                @click.stop="handleFeedback(day.accommodation.name, 'hotel', 'good', day.accommodation.tags || [])"
                :disabled="getFeedbackState(day.accommodation.name) !== null"
                title="良かった"
              >
                👍
              </button>
              <button
                :class="['feedback-btn', 'bad', { active: getFeedbackState(day.accommodation.name) === 'bad' }]"
                @click.stop="handleFeedback(day.accommodation.name, 'hotel', 'bad', day.accommodation.tags || [])"
                :disabled="getFeedbackState(day.accommodation.name) !== null"
                title="改善希望"
              >
                👎
              </button>
            </div>
          </div>
          <div class="accommodation-content">
            <span class="accommodation-name">{{ day.accommodation.name }}</span>
            <span v-if="day.accommodation.price_range" class="accommodation-price">
              {{ day.accommodation.price_range }}
            </span>
          </div>
          <p v-if="day.accommodation.description" class="accommodation-description">
            {{ day.accommodation.description }}
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.itinerary-display {
  padding: 0.5rem;
}

.itinerary-header {
  margin-bottom: 1rem;
}

.itinerary-title {
  margin: 0 0 0.5rem;
  font-size: 1.1rem;
  color: #2c3e50;
}

.itinerary-summary {
  margin: 0;
  font-size: 0.85rem;
  color: #7f8c8d;
  line-height: 1.4;
}

.highlights {
  margin-bottom: 1rem;
  padding: 0.75rem;
  background: #f8f9fa;
  border-radius: 6px;
}

.highlights h4 {
  margin: 0 0 0.5rem;
  font-size: 0.85rem;
  color: #2c3e50;
}

.highlight-list {
  margin: 0;
  padding-left: 1.2rem;
  font-size: 0.8rem;
  color: #34495e;
}

.highlight-list li {
  margin-bottom: 0.25rem;
}

.budget-estimate {
  margin-bottom: 1rem;
  padding: 0.5rem 0.75rem;
  background: #e8f5e9;
  border-radius: 6px;
  font-size: 0.85rem;
}

.budget-label {
  color: #2e7d32;
}

.budget-value {
  font-weight: 600;
  color: #1b5e20;
  margin-left: 0.5rem;
}

.days-container {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.day-card {
  background: white;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  overflow: hidden;
}

.day-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem;
  background: #3498db;
  color: white;
}

.day-number {
  font-weight: 600;
  font-size: 0.9rem;
}

.day-date {
  font-size: 0.8rem;
  opacity: 0.9;
}

.day-theme {
  margin-left: auto;
  font-size: 0.8rem;
  background: rgba(255, 255, 255, 0.2);
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
}

.day-items {
  padding: 0.75rem;
}

.item-card {
  margin-bottom: 0.75rem;
}

.item-card:last-child {
  margin-bottom: 0;
}

.travel-info {
  font-size: 0.75rem;
  color: #7f8c8d;
  padding: 0.25rem 0.5rem;
  margin-bottom: 0.25rem;
  border-left: 2px solid #bdc3c7;
  margin-left: 0.5rem;
}

.item-content {
  display: flex;
  gap: 0.75rem;
  padding: 0.5rem;
  background: #f8f9fa;
  border-radius: 6px;
}

.item-time {
  min-width: 80px;
  font-size: 0.75rem;
  font-weight: 500;
  color: #3498db;
  padding-top: 0.25rem;
}

.item-main {
  flex: 1;
}

.item-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.25rem;
  flex-wrap: wrap;
}

.item-icon {
  font-size: 1rem;
}

.item-name {
  font-weight: 500;
  font-size: 0.9rem;
  color: #2c3e50;
}

.item-category {
  font-size: 0.7rem;
  color: #7f8c8d;
  background: #ecf0f1;
  padding: 0.1rem 0.4rem;
  border-radius: 3px;
}

/* Feedback buttons */
.feedback-buttons {
  display: flex;
  gap: 4px;
  margin-left: auto;
}

.feedback-btn {
  width: 28px;
  height: 28px;
  border: none;
  border-radius: 6px;
  background: #e2e8f0;
  cursor: pointer;
  font-size: 0.85rem;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  opacity: 0.7;
}

.feedback-btn:hover:not(:disabled) {
  opacity: 1;
  transform: scale(1.1);
}

.feedback-btn.good:hover:not(:disabled) {
  background: #c6f6d5;
}

.feedback-btn.bad:hover:not(:disabled) {
  background: #fed7d7;
}

.feedback-btn.active {
  opacity: 1;
}

.feedback-btn.good.active {
  background: #48bb78;
  color: white;
}

.feedback-btn.bad.active {
  background: #f56565;
  color: white;
}

.feedback-btn:disabled:not(.active) {
  opacity: 0.3;
  cursor: not-allowed;
}

.item-description {
  margin: 0.25rem 0;
  font-size: 0.8rem;
  color: #7f8c8d;
  line-height: 1.4;
}

.item-details {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 0.25rem;
  font-size: 0.75rem;
  color: #95a5a6;
}

.item-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem;
  margin-top: 0.25rem;
}

.tag {
  font-size: 0.7rem;
  background: #e8f4fc;
  color: #2980b9;
  padding: 0.1rem 0.4rem;
  border-radius: 3px;
}

.item-notes {
  margin: 0.25rem 0 0;
  font-size: 0.75rem;
  color: #e67e22;
  font-style: italic;
}

.accommodation {
  padding: 0.75rem;
  background: #fff8e1;
  border-top: 1px solid #e0e0e0;
}

.accommodation-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.25rem;
}

.accommodation-icon {
  font-size: 1rem;
}

.accommodation-label {
  font-size: 0.75rem;
  font-weight: 500;
  color: #f57c00;
}

.accommodation-content {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.accommodation-name {
  font-weight: 500;
  font-size: 0.9rem;
  color: #2c3e50;
}

.accommodation-price {
  font-size: 0.75rem;
  color: #7f8c8d;
}

.accommodation-description {
  margin: 0.25rem 0 0;
  font-size: 0.8rem;
  color: #7f8c8d;
}
</style>
