<script setup lang="ts">
import { computed } from 'vue'
import type { POIDetail } from '../lib/api'

const props = defineProps<{
  visible: boolean
  poi: POIDetail | null
  loading?: boolean
  error?: string | null
}>()

const emit = defineEmits<{
  close: []
}>()

const close = () => {
  emit('close')
}

const getCategoryIcon = (category: string): string => {
  switch (category) {
    case 'activity':
      return '🎯'
    case 'food':
      return '🍽️'
    case 'hotel':
      return '🏨'
    case 'transportation':
      return '🚃'
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
    case 'transportation':
      return '交通'
    default:
      return 'その他'
  }
}

const formatRating = (rating: number | null): string => {
  if (rating === null) return '-'
  return rating.toFixed(1)
}

const formatReviewCount = (count: number | null): string => {
  if (count === null) return ''
  if (count >= 1000) {
    return `${(count / 1000).toFixed(1)}k件`
  }
  return `${count}件`
}

const hasOpeningHours = computed(() => {
  return props.poi?.hours && Object.keys(props.poi.hours).length > 0
})
</script>

<template>
  <Teleport to="body">
    <div v-if="visible" class="modal-overlay" @click.self="close">
      <div class="modal-content">
        <!-- Header -->
        <div class="modal-header">
          <div class="header-left">
            <span class="category-icon">{{ poi ? getCategoryIcon(poi.category) : '' }}</span>
            <h3 class="modal-title">{{ poi?.name || '' }}</h3>
            <span v-if="poi" class="category-badge">{{ getCategoryLabel(poi.category) }}</span>
          </div>
          <button class="close-btn" @click="close" aria-label="閉じる">×</button>
        </div>

        <!-- Loading -->
        <div v-if="loading" class="modal-body loading">
          <div class="spinner"></div>
          <p>読み込み中...</p>
        </div>

        <!-- Error -->
        <div v-else-if="error" class="modal-body error">
          <p>{{ error }}</p>
        </div>

        <!-- Content -->
        <div v-else-if="poi" class="modal-body">
          <!-- 説明 -->
          <p v-if="poi.description" class="description">{{ poi.description }}</p>

          <!-- 評価・レビュー -->
          <div class="info-row rating-row">
            <span v-if="poi.rating !== null" class="rating">
              <span class="star">⭐</span>
              <span class="rating-value">{{ formatRating(poi.rating) }}</span>
            </span>
            <span v-if="poi.review_count !== null" class="review-count">
              ({{ formatReviewCount(poi.review_count) }})
            </span>
          </div>

          <!-- 場所・住所 -->
          <div v-if="poi.location || poi.address" class="info-section">
            <h4>📍 場所</h4>
            <p v-if="poi.location" class="location">{{ poi.location }}</p>
            <p v-if="poi.address" class="address">{{ poi.address }}</p>
          </div>

          <!-- 価格情報 -->
          <div v-if="poi.price_range || poi.budget_per_person" class="info-section">
            <h4>💰 価格</h4>
            <p v-if="poi.price_range" class="price-range">{{ poi.price_range }}</p>
            <p v-if="poi.budget_per_person" class="budget">
              目安: 約{{ poi.budget_per_person.toLocaleString() }}円/人
            </p>
          </div>

          <!-- 所要時間 -->
          <div v-if="poi.duration_minutes" class="info-section">
            <h4>⏱️ 所要時間</h4>
            <p>約{{ poi.duration_minutes }}分</p>
          </div>

          <!-- 営業時間 -->
          <div v-if="hasOpeningHours" class="info-section">
            <h4>🕐 営業時間</h4>
            <div class="hours">
              <div v-for="(time, day) in poi.hours" :key="day" class="hour-row">
                <span class="day">{{ day }}</span>
                <span class="time">{{ time }}</span>
              </div>
            </div>
          </div>

          <!-- 特徴 -->
          <div v-if="poi.features && poi.features.length > 0" class="info-section">
            <h4>✨ 特徴</h4>
            <div class="tags-container">
              <span v-for="feature in poi.features" :key="feature" class="tag feature">
                {{ feature }}
              </span>
            </div>
          </div>

          <!-- タグ -->
          <div v-if="poi.tags && poi.tags.length > 0" class="info-section">
            <h4>🏷️ タグ</h4>
            <div class="tags-container">
              <span v-for="tag in poi.tags" :key="tag" class="tag">
                {{ tag }}
              </span>
            </div>
          </div>

          <!-- 体験情報 -->
          <div v-if="poi.experiences && poi.experiences.length > 0" class="info-section">
            <h4>🎭 体験</h4>
            <div class="tags-container">
              <span v-for="exp in poi.experiences" :key="exp" class="tag experience">
                {{ exp }}
              </span>
            </div>
          </div>

          <!-- ソースURL -->
          <div v-if="poi.source_url" class="source-section">
            <a :href="poi.source_url" target="_blank" rel="noopener noreferrer" class="source-link">
              詳細を見る →
            </a>
            <span v-if="poi.source_name" class="source-name">
              ({{ poi.source_name }})
            </span>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 1rem;
}

.modal-content {
  background: white;
  border-radius: 12px;
  width: 100%;
  max-width: 500px;
  max-height: 80vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid #e0e0e0;
  background: #f8f9fa;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex: 1;
  min-width: 0;
}

.category-icon {
  font-size: 1.25rem;
  flex-shrink: 0;
}

.modal-title {
  margin: 0;
  font-size: 1.1rem;
  color: #2c3e50;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.category-badge {
  font-size: 0.7rem;
  color: #7f8c8d;
  background: #ecf0f1;
  padding: 0.15rem 0.5rem;
  border-radius: 4px;
  flex-shrink: 0;
}

.close-btn {
  background: none;
  border: none;
  font-size: 1.5rem;
  color: #7f8c8d;
  cursor: pointer;
  padding: 0;
  line-height: 1;
  flex-shrink: 0;
}

.close-btn:hover {
  color: #2c3e50;
}

.modal-body {
  padding: 1.25rem;
  overflow-y: auto;
  flex: 1;
}

.modal-body.loading,
.modal-body.error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 150px;
  color: #7f8c8d;
}

.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid #e0e0e0;
  border-top-color: #3498db;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.description {
  margin: 0 0 1rem;
  font-size: 0.9rem;
  color: #34495e;
  line-height: 1.5;
}

.info-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.rating-row .rating {
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.rating-row .star {
  font-size: 1rem;
}

.rating-row .rating-value {
  font-size: 1rem;
  font-weight: 600;
  color: #f39c12;
}

.rating-row .review-count {
  font-size: 0.85rem;
  color: #7f8c8d;
}

.info-section {
  margin-bottom: 1rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid #f0f0f0;
}

.info-section:last-child {
  border-bottom: none;
  margin-bottom: 0;
  padding-bottom: 0;
}

.info-section h4 {
  margin: 0 0 0.5rem;
  font-size: 0.85rem;
  color: #2c3e50;
}

.info-section p {
  margin: 0;
  font-size: 0.9rem;
  color: #34495e;
}

.location {
  font-weight: 500;
}

.address {
  font-size: 0.85rem !important;
  color: #7f8c8d !important;
  margin-top: 0.25rem !important;
}

.hours {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.hour-row {
  display: flex;
  font-size: 0.85rem;
}

.hour-row .day {
  width: 40px;
  color: #7f8c8d;
  text-transform: capitalize;
}

.hour-row .time {
  color: #34495e;
}

.tags-container {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.tag {
  font-size: 0.75rem;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  background: #e8f4fc;
  color: #2980b9;
}

.tag.feature {
  background: #e8f5e9;
  color: #388e3c;
}

.tag.experience {
  background: #fff3e0;
  color: #e65100;
}

.source-section {
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid #f0f0f0;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.source-link {
  color: #3498db;
  text-decoration: none;
  font-size: 0.9rem;
}

.source-link:hover {
  text-decoration: underline;
}

.source-name {
  font-size: 0.75rem;
  color: #95a5a6;
}
</style>
