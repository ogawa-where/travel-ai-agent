<script setup lang="ts">
import type { Itinerary, POIFeedbackType, POICategory, MatchTag } from '../lib/api'

const props = defineProps<{
  itinerary: Itinerary
  feedbackEnabled?: boolean
  poiFeedback?: Record<string, POIFeedbackType>  // key: poi_name, value: 'good' | 'bad'
}>()

const emit = defineEmits<{
  'poi-feedback': [poiName: string, category: POICategory, feedbackType: POIFeedbackType, tags: string[]]
  'poi-click': [poiName: string, category: POICategory]
}>()

const handlePOIClick = (poiName: string, category: string) => {
  emit('poi-click', poiName, category as POICategory)
}

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

// マッチタグのアイコンを取得
const getMatchTagIcon = (type: string): string => {
  return type === 'preference' ? '💜' : '💛'
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
      <div v-for="day in itinerary.days" :key="day.day_number" class="day-section">
        <div class="day-header">
          <div class="day-badge">
            <span class="day-number">{{ day.day_number }}</span>
            <span class="day-label">日目</span>
          </div>
          <div class="day-info">
            <span v-if="day.date" class="day-date">{{ day.date }}</span>
            <span v-if="day.theme" class="day-theme">{{ day.theme }}</span>
          </div>
        </div>

        <div class="timeline">
          <div v-for="(item, index) in day.items" :key="index" class="timeline-item">
            <!-- タイムライン線 -->
            <div class="timeline-marker">
              <div class="timeline-dot" :class="item.poi.category"></div>
              <div v-if="index < day.items.length - 1 || day.accommodation" class="timeline-line"></div>
            </div>

            <!-- POIカード -->
            <div class="poi-card">
              <!-- 移動情報 -->
              <div v-if="item.travel_from_previous" class="travel-badge">
                {{ item.travel_from_previous }}
              </div>

              <!-- マッチタグ -->
              <div v-if="item.poi.match_tags && item.poi.match_tags.length > 0" class="match-tags">
                <span
                  v-for="tag in item.poi.match_tags"
                  :key="tag.text"
                  :class="['match-tag', tag.type]"
                >
                  {{ getMatchTagIcon(tag.type) }} {{ tag.text }}
                </span>
              </div>

              <!-- ヘッダー -->
              <div class="poi-header">
                <span class="poi-icon">{{ getCategoryIcon(item.poi.category) }}</span>
                <div class="poi-title-area">
                  <span class="poi-name clickable" @click="handlePOIClick(item.poi.name, item.poi.category)">
                    {{ item.poi.name }}
                  </span>
                  <span class="poi-category">{{ getCategoryLabel(item.poi.category) }}</span>
                </div>
                <div class="poi-time" v-if="item.time_start || item.time_end">
                  {{ formatTime(item.time_start, item.time_end) }}
                </div>
              </div>

              <!-- 説明 -->
              <p v-if="item.poi.description" class="poi-description">
                {{ item.poi.description }}
              </p>

              <!-- 詳細情報 -->
              <div class="poi-meta">
                <span v-if="item.poi.location" class="meta-item location">
                  {{ item.poi.location }}
                </span>
                <span v-if="item.poi.price_range" class="meta-item price">
                  {{ item.poi.price_range }}
                </span>
                <span v-if="item.poi.duration_minutes" class="meta-item duration">
                  約{{ item.poi.duration_minutes }}分
                </span>
              </div>

              <!-- タグ -->
              <div v-if="item.poi.tags && item.poi.tags.length > 0" class="poi-tags">
                <span v-for="tag in item.poi.tags" :key="tag" class="tag">{{ tag }}</span>
              </div>

              <!-- ノート -->
              <p v-if="item.notes" class="poi-notes">{{ item.notes }}</p>

              <!-- フィードバックボタン -->
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
          </div>

          <!-- 宿泊先 -->
          <div v-if="day.accommodation" class="timeline-item accommodation-item">
            <div class="timeline-marker">
              <div class="timeline-dot hotel"></div>
            </div>

            <div class="poi-card accommodation-card">
              <!-- マッチタグ -->
              <div v-if="day.accommodation.match_tags && day.accommodation.match_tags.length > 0" class="match-tags">
                <span
                  v-for="tag in day.accommodation.match_tags"
                  :key="tag.text"
                  :class="['match-tag', tag.type]"
                >
                  {{ getMatchTagIcon(tag.type) }} {{ tag.text }}
                </span>
              </div>

              <div class="poi-header">
                <span class="poi-icon">🏨</span>
                <div class="poi-title-area">
                  <span class="poi-name clickable" @click="handlePOIClick(day.accommodation.name, 'hotel')">
                    {{ day.accommodation.name }}
                  </span>
                  <span class="poi-category hotel">宿泊</span>
                </div>
              </div>

              <p v-if="day.accommodation.description" class="poi-description">
                {{ day.accommodation.description }}
              </p>

              <div class="poi-meta">
                <span v-if="day.accommodation.price_range" class="meta-item price">
                  {{ day.accommodation.price_range }}
                </span>
              </div>

              <!-- フィードバックボタン -->
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
          </div>
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
  border-radius: 8px;
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
  border-radius: 8px;
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
  gap: 1.5rem;
}

.day-section {
  background: #f8fafc;
  border-radius: 12px;
  padding: 1rem;
}

.day-header {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1rem;
}

.day-badge {
  display: flex;
  align-items: baseline;
  gap: 2px;
  background: linear-gradient(135deg, #3498db, #2980b9);
  color: white;
  padding: 0.5rem 0.75rem;
  border-radius: 8px;
}

.day-number {
  font-size: 1.25rem;
  font-weight: 700;
}

.day-label {
  font-size: 0.75rem;
}

.day-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.day-date {
  font-size: 0.8rem;
  color: #64748b;
}

.day-theme {
  font-size: 0.85rem;
  color: #334155;
  font-weight: 500;
}

/* タイムライン */
.timeline {
  position: relative;
  padding-left: 1.5rem;
}

.timeline-item {
  display: flex;
  gap: 1rem;
  margin-bottom: 1rem;
  position: relative;
}

.timeline-item:last-child {
  margin-bottom: 0;
}

.timeline-marker {
  position: absolute;
  left: -1.5rem;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.timeline-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: #3498db;
  border: 2px solid white;
  box-shadow: 0 0 0 2px #3498db;
  z-index: 1;
}

.timeline-dot.activity {
  background: #3498db;
  box-shadow: 0 0 0 2px #3498db;
}

.timeline-dot.food {
  background: #e67e22;
  box-shadow: 0 0 0 2px #e67e22;
}

.timeline-dot.hotel {
  background: #9b59b6;
  box-shadow: 0 0 0 2px #9b59b6;
}

.timeline-line {
  width: 2px;
  flex: 1;
  min-height: 40px;
  background: #e2e8f0;
  margin-top: 4px;
}

/* POIカード */
.poi-card {
  flex: 1;
  background: white;
  border-radius: 12px;
  padding: 1rem;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  transition: transform 0.2s, box-shadow 0.2s;
}

.poi-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.accommodation-card {
  background: linear-gradient(135deg, #fef9e7, #fdf6e3);
  border: 1px solid #f5e6c4;
}

/* 移動バッジ */
.travel-badge {
  display: inline-block;
  font-size: 0.7rem;
  color: #64748b;
  background: #f1f5f9;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  margin-bottom: 0.5rem;
}

/* マッチタグ */
.match-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.375rem;
  margin-bottom: 0.75rem;
}

.match-tag {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  font-size: 0.7rem;
  padding: 0.25rem 0.5rem;
  border-radius: 12px;
  font-weight: 500;
}

.match-tag.preference {
  background: #ede9fe;
  color: #7c3aed;
  border: 1px solid #ddd6fe;
}

.match-tag.wish {
  background: #fef3c7;
  color: #d97706;
  border: 1px solid #fde68a;
}

/* POIヘッダー */
.poi-header {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.poi-icon {
  font-size: 1.25rem;
  line-height: 1;
}

.poi-title-area {
  flex: 1;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
}

.poi-name {
  font-weight: 600;
  font-size: 0.95rem;
  color: #1e293b;
}

.poi-name.clickable {
  cursor: pointer;
  color: #2563eb;
  text-decoration: underline;
  text-decoration-style: dotted;
  text-underline-offset: 2px;
}

.poi-name.clickable:hover {
  color: #1d4ed8;
  text-decoration-style: solid;
}

.poi-category {
  font-size: 0.65rem;
  color: #64748b;
  background: #f1f5f9;
  padding: 0.15rem 0.4rem;
  border-radius: 4px;
}

.poi-category.hotel {
  background: #f5f3ff;
  color: #7c3aed;
}

.poi-time {
  font-size: 0.8rem;
  font-weight: 600;
  color: #3498db;
  white-space: nowrap;
}

/* POI説明 */
.poi-description {
  margin: 0 0 0.5rem;
  font-size: 0.8rem;
  color: #64748b;
  line-height: 1.5;
}

/* メタ情報 */
.poi-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-bottom: 0.5rem;
}

.meta-item {
  font-size: 0.75rem;
  color: #94a3b8;
}

.meta-item.location::before {
  content: '📍 ';
}

.meta-item.price::before {
  content: '💰 ';
}

.meta-item.duration::before {
  content: '⏱️ ';
}

/* タグ */
.poi-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem;
  margin-bottom: 0.5rem;
}

.tag {
  font-size: 0.65rem;
  background: #e0f2fe;
  color: #0284c7;
  padding: 0.15rem 0.4rem;
  border-radius: 4px;
}

/* ノート */
.poi-notes {
  margin: 0.5rem 0 0;
  font-size: 0.75rem;
  color: #ea580c;
  font-style: italic;
  padding: 0.5rem;
  background: #fff7ed;
  border-radius: 6px;
}

/* フィードバックボタン */
.feedback-buttons {
  display: flex;
  gap: 0.5rem;
  margin-top: 0.75rem;
  padding-top: 0.75rem;
  border-top: 1px solid #f1f5f9;
}

.feedback-btn {
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 8px;
  background: #f1f5f9;
  cursor: pointer;
  font-size: 0.9rem;
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
  background: #dcfce7;
}

.feedback-btn.bad:hover:not(:disabled) {
  background: #fee2e2;
}

.feedback-btn.active {
  opacity: 1;
}

.feedback-btn.good.active {
  background: #22c55e;
  color: white;
}

.feedback-btn.bad.active {
  background: #ef4444;
  color: white;
}

.feedback-btn:disabled:not(.active) {
  opacity: 0.3;
  cursor: not-allowed;
}
</style>
