<script setup lang="ts">
import { ref } from 'vue'
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

// POI展開/折りたたみ
const expandedPOIs = ref<Set<string>>(new Set())

const togglePOI = (dayNumber: number, index: number) => {
  const key = `${dayNumber}-${index}`
  const newSet = new Set(expandedPOIs.value)
  if (newSet.has(key)) newSet.delete(key)
  else newSet.add(key)
  expandedPOIs.value = newSet
}

const isPOIExpanded = (dayNumber: number, index: number): boolean =>
  expandedPOIs.value.has(`${dayNumber}-${index}`)

// POIの左ボーダー色を決定
const getSourceType = (matchTags?: MatchTag[]): 'preference' | 'wish' | 'none' => {
  if (!matchTags?.length) return 'none'
  if (matchTags.some(t => t.type === 'preference')) return 'preference'
  if (matchTags.some(t => t.type === 'wish')) return 'wish'
  return 'none'
}

// マッチタグのアイコンを取得
const getMatchTagIcon = (type: string): string => {
  return type === 'preference' ? '💜' : '💛'
}
</script>

<template>
  <div class="itinerary-display">
    <!-- 凡例 -->
    <div class="source-legend">
      <span class="legend-label">スポットの由来:</span>
      <span class="legend-item"><span class="legend-bar preference"></span>あなたの嗜好</span>
      <span class="legend-item"><span class="legend-bar wish"></span>今回の要望</span>
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

            <!-- POI行（コンパクト） -->
            <div :class="['poi-row', getSourceType(item.poi.match_tags)]">
              <!-- 移動情報 -->
              <div v-if="item.travel_from_previous" class="travel-badge">
                {{ item.travel_from_previous }}
              </div>

              <!-- コンパクト行 -->
              <div class="poi-compact" @click="togglePOI(day.day_number, index)">
                <span class="poi-time-inline" v-if="item.time_start">{{ item.time_start }}</span>
                <span class="poi-icon-badge" :class="item.poi.category">
                  <!-- Activity: sparkle -->
                  <svg v-if="item.poi.category === 'activity'" viewBox="0 0 24 24">
                    <path d="M12 2l2.5 7.5L22 12l-7.5 2.5L12 22l-2.5-7.5L2 12l7.5-2.5Z" fill="currentColor"/>
                  </svg>
                  <!-- Food: utensils -->
                  <svg v-else-if="item.poi.category === 'food'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M3 2v7c0 1.1.9 2 2 2h4a2 2 0 0 0 2-2V2"/><path d="M7 2v20"/><path d="M21 15V2a5 5 0 0 0-5 5v6c0 1.1.9 2 2 2h3zm0 0v7"/>
                  </svg>
                  <!-- Default: map pin -->
                  <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/>
                  </svg>
                </span>
                <span class="poi-name clickable" @click.stop="handlePOIClick(item.poi.name, item.poi.category)">
                  {{ item.poi.name }}
                </span>
                <span class="poi-category-inline">{{ getCategoryLabel(item.poi.category) }}</span>
                <!-- ソースピル -->
                <template v-if="item.poi.match_tags && item.poi.match_tags.length > 0">
                  <span v-if="item.poi.match_tags.some(t => t.type === 'preference')" class="source-dot preference">嗜好</span>
                  <span v-if="item.poi.match_tags.some(t => t.type === 'wish')" class="source-dot wish">要望</span>
                </template>
                <span class="poi-compact-spacer"></span>
                <span v-if="item.poi.price_range" class="poi-price-inline">{{ item.poi.price_range }}</span>
                <!-- フィードバックボタン（コンパクト） -->
                <div v-if="feedbackEnabled" class="feedback-compact">
                  <button
                    :class="['fb-btn', 'good', { active: getFeedbackState(item.poi.name) === 'good' }]"
                    @click.stop="handleFeedback(item.poi.name, item.poi.category, 'good', item.poi.tags || [])"
                    :disabled="getFeedbackState(item.poi.name) !== null"
                    title="良かった"
                  >👍</button>
                  <button
                    :class="['fb-btn', 'bad', { active: getFeedbackState(item.poi.name) === 'bad' }]"
                    @click.stop="handleFeedback(item.poi.name, item.poi.category, 'bad', item.poi.tags || [])"
                    :disabled="getFeedbackState(item.poi.name) !== null"
                    title="改善希望"
                  >👎</button>
                </div>
                <span :class="['expand-chevron', { expanded: isPOIExpanded(day.day_number, index) }]">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
                </span>
              </div>

              <!-- 展開詳細 -->
              <Transition name="detail-slide">
                <div v-if="isPOIExpanded(day.day_number, index)" class="poi-detail">
                  <!-- マッチタグ詳細 -->
                  <div v-if="item.poi.match_tags && item.poi.match_tags.length > 0" class="match-tags">
                    <span
                      v-for="tag in item.poi.match_tags"
                      :key="tag.text"
                      :class="['match-tag', tag.type]"
                    >
                      {{ getMatchTagIcon(tag.type) }} {{ tag.text }}
                    </span>
                  </div>

                  <!-- 説明 -->
                  <p v-if="item.poi.description" class="poi-description">
                    {{ item.poi.description }}
                  </p>

                  <!-- 詳細情報 -->
                  <div class="poi-meta">
                    <span v-if="item.poi.location" class="meta-item location">{{ item.poi.location }}</span>
                    <span v-if="item.poi.price_range" class="meta-item price">{{ item.poi.price_range }}</span>
                    <span v-if="item.poi.duration_minutes" class="meta-item duration">約{{ item.poi.duration_minutes }}分</span>
                    <span v-if="item.time_start || item.time_end" class="meta-item time">{{ formatTime(item.time_start, item.time_end) }}</span>
                  </div>

                  <!-- タグ -->
                  <div v-if="item.poi.tags && item.poi.tags.length > 0" class="poi-tags">
                    <span v-for="tag in item.poi.tags" :key="tag" class="tag">{{ tag }}</span>
                  </div>

                  <!-- ノート -->
                  <p v-if="item.notes" class="poi-notes">{{ item.notes }}</p>
                </div>
              </Transition>
            </div>
          </div>

          <!-- 宿泊先 -->
          <div v-if="day.accommodation" class="timeline-item accommodation-item">
            <div class="timeline-marker">
              <div class="timeline-dot hotel"></div>
            </div>

            <div :class="['poi-row', 'accommodation', getSourceType(day.accommodation.match_tags)]">
              <!-- コンパクト行 -->
              <div class="poi-compact" @click="togglePOI(day.day_number, -1)">
                <span class="poi-icon-badge hotel">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/>
                  </svg>
                </span>
                <span class="poi-name clickable" @click.stop="handlePOIClick(day.accommodation.name, 'hotel')">
                  {{ day.accommodation.name }}
                </span>
                <span class="poi-category-inline hotel">宿泊</span>
                <!-- ソースピル -->
                <template v-if="day.accommodation.match_tags && day.accommodation.match_tags.length > 0">
                  <span v-if="day.accommodation.match_tags.some(t => t.type === 'preference')" class="source-dot preference">嗜好</span>
                  <span v-if="day.accommodation.match_tags.some(t => t.type === 'wish')" class="source-dot wish">要望</span>
                </template>
                <span class="poi-compact-spacer"></span>
                <span v-if="day.accommodation.price_range" class="poi-price-inline">{{ day.accommodation.price_range }}</span>
                <!-- フィードバックボタン（コンパクト） -->
                <div v-if="feedbackEnabled" class="feedback-compact">
                  <button
                    :class="['fb-btn', 'good', { active: getFeedbackState(day.accommodation.name) === 'good' }]"
                    @click.stop="handleFeedback(day.accommodation.name, 'hotel', 'good', day.accommodation.tags || [])"
                    :disabled="getFeedbackState(day.accommodation.name) !== null"
                    title="良かった"
                  >👍</button>
                  <button
                    :class="['fb-btn', 'bad', { active: getFeedbackState(day.accommodation.name) === 'bad' }]"
                    @click.stop="handleFeedback(day.accommodation.name, 'hotel', 'bad', day.accommodation.tags || [])"
                    :disabled="getFeedbackState(day.accommodation.name) !== null"
                    title="改善希望"
                  >👎</button>
                </div>
                <span :class="['expand-chevron', { expanded: isPOIExpanded(day.day_number, -1) }]">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
                </span>
              </div>

              <!-- 展開詳細 -->
              <Transition name="detail-slide">
                <div v-if="isPOIExpanded(day.day_number, -1)" class="poi-detail">
                  <!-- マッチタグ詳細 -->
                  <div v-if="day.accommodation.match_tags && day.accommodation.match_tags.length > 0" class="match-tags">
                    <span
                      v-for="tag in day.accommodation.match_tags"
                      :key="tag.text"
                      :class="['match-tag', tag.type]"
                    >
                      {{ getMatchTagIcon(tag.type) }} {{ tag.text }}
                    </span>
                  </div>

                  <p v-if="day.accommodation.description" class="poi-description">
                    {{ day.accommodation.description }}
                  </p>

                  <div class="poi-meta">
                    <span v-if="day.accommodation.price_range" class="meta-item price">{{ day.accommodation.price_range }}</span>
                  </div>
                </div>
              </Transition>
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

/* 凡例 */
.source-legend {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.5rem 0.75rem;
  margin-bottom: 0.75rem;
  background: rgba(255, 255, 255, 0.6);
  border: 1px solid rgba(0, 0, 0, 0.06);
  border-radius: 8px;
  font-size: 0.75rem;
}

.legend-label {
  color: #64748b;
  font-weight: 500;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  color: #475569;
}

.legend-bar {
  display: inline-block;
  width: 14px;
  height: 14px;
  border-radius: 3px;
}

.legend-bar.preference {
  background: #7c3aed;
}

.legend-bar.wish {
  background: #d97706;
}

.days-container {
  display: flex;
  flex-direction: column;
  gap: 1rem;
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
  margin-bottom: 0.75rem;
}

.day-badge {
  display: flex;
  align-items: baseline;
  gap: 2px;
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: white;
  padding: 0.4rem 0.65rem;
  border-radius: 8px;
}

.day-number {
  font-size: 1.1rem;
  font-weight: 700;
}

.day-label {
  font-size: 0.7rem;
}

.day-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.day-date {
  font-size: 0.75rem;
  color: #64748b;
}

.day-theme {
  font-size: 0.8rem;
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
  gap: 0.75rem;
  margin-bottom: 0.5rem;
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
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #667eea;
  border: 2px solid white;
  box-shadow: 0 0 0 2px #667eea;
  z-index: 1;
}

.timeline-dot.activity {
  background: #667eea;
  box-shadow: 0 0 0 2px #667eea;
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
  min-height: 20px;
  background: #e2e8f0;
  margin-top: 4px;
}

/* POI行（コンパクト） */
.poi-row {
  flex: 1;
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  border: 1px solid rgba(102, 126, 234, 0.08);
  border-radius: 8px;
  border-left: 4px solid #cbd5e1;
  overflow: hidden;
  transition: box-shadow 0.2s;
}

.poi-row:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.poi-row.preference {
  border-left-color: #7c3aed;
}

.poi-row.wish {
  border-left-color: #d97706;
}

.poi-row.none {
  border-left-color: #cbd5e1;
}

.poi-row.accommodation {
  background: linear-gradient(135deg, rgba(254, 249, 231, 0.7), rgba(253, 246, 227, 0.7));
  border-color: rgba(245, 230, 196, 0.5);
}

.poi-row.accommodation.preference {
  border-left-color: #7c3aed;
}

.poi-row.accommodation.wish {
  border-left-color: #d97706;
}

/* 移動バッジ */
.travel-badge {
  display: inline-block;
  font-size: 0.65rem;
  color: #64748b;
  background: #f1f5f9;
  padding: 0.15rem 0.4rem;
  border-radius: 0 0 4px 0;
  margin: 0;
}

/* コンパクト行 */
.poi-compact {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  min-height: 40px;
  cursor: pointer;
  user-select: none;
  transition: background 0.15s;
}

.poi-compact:hover {
  background: rgba(102, 126, 234, 0.03);
}

.poi-time-inline {
  font-size: 0.75rem;
  font-weight: 600;
  color: #667eea;
  white-space: nowrap;
  min-width: 36px;
}

/* カテゴリアイコンバッジ */
.poi-icon-badge {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  flex-shrink: 0;
  color: white;
  background: linear-gradient(135deg, #94a3b8, #64748b);
}

.poi-icon-badge svg {
  width: 15px;
  height: 15px;
}

.poi-icon-badge.activity {
  background: linear-gradient(135deg, #667eea, #764ba2);
}

.poi-icon-badge.food {
  background: linear-gradient(135deg, #f59e0b, #e67e22);
}

.poi-icon-badge.hotel {
  background: linear-gradient(135deg, #8b5cf6, #6d28d9);
}

.poi-name {
  font-weight: 600;
  font-size: 0.85rem;
  color: #1e293b;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.poi-name.clickable {
  cursor: pointer;
  color: #667eea;
  text-decoration: underline;
  text-decoration-style: dotted;
  text-underline-offset: 2px;
}

.poi-name.clickable:hover {
  color: #764ba2;
  text-decoration-style: solid;
}

.poi-category-inline {
  font-size: 0.6rem;
  color: #64748b;
  background: #f1f5f9;
  padding: 0.1rem 0.35rem;
  border-radius: 3px;
  white-space: nowrap;
  flex-shrink: 0;
}

.poi-category-inline.hotel {
  background: #f5f3ff;
  color: #7c3aed;
}

/* ソースピル */
.source-dot {
  font-size: 0.6rem;
  font-weight: 600;
  padding: 0.1rem 0.4rem;
  border-radius: 8px;
  white-space: nowrap;
  flex-shrink: 0;
}

.source-dot.preference {
  background: #ede9fe;
  color: #7c3aed;
}

.source-dot.wish {
  background: #fef3c7;
  color: #d97706;
}

.poi-compact-spacer {
  flex: 1;
}

.poi-price-inline {
  font-size: 0.7rem;
  color: #94a3b8;
  white-space: nowrap;
  flex-shrink: 0;
}

/* フィードバックボタン（コンパクト） */
.feedback-compact {
  display: flex;
  gap: 0.25rem;
  flex-shrink: 0;
}

.feedback-compact .fb-btn {
  width: 26px;
  height: 26px;
  border: none;
  border-radius: 6px;
  background: #f1f5f9;
  cursor: pointer;
  font-size: 0.75rem;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  opacity: 0.6;
}

.feedback-compact .fb-btn:hover:not(:disabled) {
  opacity: 1;
  transform: scale(1.1);
}

.feedback-compact .fb-btn.good:hover:not(:disabled) {
  background: #dcfce7;
}

.feedback-compact .fb-btn.bad:hover:not(:disabled) {
  background: #fee2e2;
}

.feedback-compact .fb-btn.active {
  opacity: 1;
}

.feedback-compact .fb-btn.good.active {
  background: #22c55e;
  color: white;
}

.feedback-compact .fb-btn.bad.active {
  background: #ef4444;
  color: white;
}

.feedback-compact .fb-btn:disabled:not(.active) {
  opacity: 0.25;
  cursor: not-allowed;
}

/* 展開シェブロン */
.expand-chevron {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: transform 0.25s ease;
}

.expand-chevron svg {
  width: 16px;
  height: 16px;
  color: #94a3b8;
}

.expand-chevron.expanded {
  transform: rotate(180deg);
}

/* 展開詳細 */
.poi-detail {
  padding: 0.5rem 0.75rem 0.75rem;
  border-top: 1px solid rgba(0, 0, 0, 0.04);
}

/* Transition */
.detail-slide-enter-active,
.detail-slide-leave-active {
  transition: all 0.25s ease;
  overflow: hidden;
}

.detail-slide-enter-from,
.detail-slide-leave-to {
  max-height: 0;
  opacity: 0;
  padding-top: 0;
  padding-bottom: 0;
}

.detail-slide-enter-to,
.detail-slide-leave-from {
  max-height: 500px;
  opacity: 1;
}

/* マッチタグ */
.match-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.375rem;
  margin-bottom: 0.5rem;
}

.match-tag {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  font-size: 0.7rem;
  padding: 0.2rem 0.45rem;
  border-radius: 10px;
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

/* POI説明 */
.poi-description {
  margin: 0 0 0.5rem;
  font-size: 0.78rem;
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
  font-size: 0.72rem;
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

.meta-item.time::before {
  content: '🕐 ';
}

/* タグ */
.poi-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem;
  margin-bottom: 0.5rem;
}

.tag {
  font-size: 0.62rem;
  background: rgba(102, 126, 234, 0.1);
  color: #667eea;
  padding: 0.12rem 0.35rem;
  border-radius: 4px;
}

/* ノート */
.poi-notes {
  margin: 0.5rem 0 0;
  font-size: 0.72rem;
  color: #ea580c;
  font-style: italic;
  padding: 0.4rem;
  background: #fff7ed;
  border-radius: 6px;
}
</style>
