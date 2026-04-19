<script setup lang="ts">
import { ref, computed } from 'vue'

interface BasicTravelInfo {
  user_id: string
  area: string
  start_date: string
  end_date: string
  num_people: number
  budget: number  // 予算（円）- 必須
  // 4カテゴリ（任意）
  activity_preferences?: string  // 体験・観光の希望
  food_preferences?: string  // 食の希望
  accommodation_type?: string  // 宿泊の希望
  transportation?: string  // 交通の希望
}

interface Props {
  userId: string
  isLoading?: boolean
}

interface Emits {
  (e: 'submit', data: BasicTravelInfo): void
}

const props = withDefaults(defineProps<Props>(), {
  isLoading: false,
})
const emit = defineEmits<Emits>()

const area = ref('')
const startDate = ref('')
const endDate = ref('')
const numPeople = ref(1)
const budget = ref<number | null>(null)

// 4カテゴリ（任意）
const activityPreferences = ref('')
const foodPreferences = ref('')
const accommodationType = ref('')
const transportation = ref('')

const isValid = computed(() => {
  if (!area.value.trim()) return false
  if (!startDate.value) return false
  if (!endDate.value) return false
  if (startDate.value > endDate.value) return false
  if (numPeople.value < 1) return false
  if (!budget.value || budget.value <= 0) return false  // 予算必須
  return true
})

const dateError = computed(() => {
  if (startDate.value && endDate.value && startDate.value > endDate.value) {
    return '帰着日は出発日以降を選択してください'
  }
  return ''
})

// バリデーションエラーメッセージ
const validationErrors = computed(() => {
  const errors: string[] = []
  if (!area.value.trim()) errors.push('観光エリア')
  if (!startDate.value) errors.push('出発日')
  if (!endDate.value) errors.push('帰着日')
  if (!budget.value || budget.value <= 0) errors.push('予算')
  return errors
})

const tripDays = computed(() => {
  if (!startDate.value || !endDate.value) return null
  const start = new Date(startDate.value)
  const end = new Date(endDate.value)
  const diff = Math.ceil((end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24))
  return diff + 1
})

const handleSubmit = () => {
  if (!isValid.value || props.isLoading) return

  const data: BasicTravelInfo = {
    user_id: props.userId,
    area: area.value.trim(),
    start_date: startDate.value,
    end_date: endDate.value,
    num_people: numPeople.value,
    budget: budget.value!,
    // 4カテゴリ（任意）
    activity_preferences: activityPreferences.value.trim() || undefined,
    food_preferences: foodPreferences.value.trim() || undefined,
    accommodation_type: accommodationType.value.trim() || undefined,
    transportation: transportation.value.trim() || undefined,
  }

  emit('submit', data)
}
</script>

<template>
  <div class="travel-plan-form">
    <form @submit.prevent="handleSubmit">
      <!-- 2カラムグリッド -->
      <div class="form-grid">
        <!-- 左カラム: 必須情報 -->
        <div class="form-column">
          <div class="column-header">
            <div class="column-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                <circle cx="12" cy="12" r="10"/>
                <polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"/>
              </svg>
            </div>
            <div>
              <h3>旅行の基本情報</h3>
              <p>行き先と日程を教えてください</p>
            </div>
          </div>

          <div class="form-group">
            <label for="area" class="required">観光エリア</label>
            <input
              id="area"
              v-model="area"
              type="text"
              placeholder="例: 京都、箱根、沖縄本島"
              required
              :disabled="isLoading"
            />
            <p class="field-hint">このエリア内でスポット・食事・宿泊を探します</p>
          </div>

          <div class="form-row">
            <div class="form-group">
              <label for="startDate" class="required">出発日</label>
              <input
                id="startDate"
                v-model="startDate"
                type="date"
                required
                :disabled="isLoading"
              />
            </div>
            <div class="form-group">
              <label for="endDate" class="required">帰着日</label>
              <input
                id="endDate"
                v-model="endDate"
                type="date"
                required
                :min="startDate"
                :disabled="isLoading"
              />
            </div>
          </div>
          <p v-if="dateError" class="field-error">{{ dateError }}</p>
          <p v-else-if="tripDays" class="field-info">{{ tripDays }}日間の旅行</p>

          <div class="form-row">
            <div class="form-group">
              <label for="numPeople">人数</label>
              <input
                id="numPeople"
                v-model.number="numPeople"
                type="number"
                min="1"
                max="20"
                :disabled="isLoading"
              />
            </div>
            <div class="form-group">
              <label for="budget" class="required">予算（円）</label>
              <input
                id="budget"
                v-model.number="budget"
                type="number"
                min="1000"
                step="1"
                placeholder="例: 50000"
                required
                :disabled="isLoading"
              />
            </div>
          </div>
        </div>

        <!-- 右カラム: 任意の希望 -->
        <div class="form-column">
          <div class="column-header">
            <div class="column-icon secondary">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>
              </svg>
            </div>
            <div>
              <h3>旅の希望</h3>
              <p>あれば入力してください（任意）</p>
            </div>
          </div>

          <div class="form-group">
            <label for="activityPreferences">
              <span class="label-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14.5 10c-.83 0-1.5-.67-1.5-1.5v-5c0-.83.67-1.5 1.5-1.5s1.5.67 1.5 1.5v5c0 .83-.67 1.5-1.5 1.5z"/><path d="M20.5 10H19V8.5c0-.83.67-1.5 1.5-1.5s1.5.67 1.5 1.5-.67 1.5-1.5 1.5z"/><path d="M9.5 14c.83 0 1.5.67 1.5 1.5v5c0 .83-.67 1.5-1.5 1.5S8 21.33 8 20.5v-5c0-.83.67-1.5 1.5-1.5z"/><path d="M3.5 14H5v1.5C5 16.33 4.33 17 3.5 17S2 16.33 2 15.5 2.67 14 3.5 14z"/><path d="M14 14.5c0-.83.67-1.5 1.5-1.5h5c.83 0 1.5.67 1.5 1.5s-.67 1.5-1.5 1.5h-5c-.83 0-1.5-.67-1.5-1.5z"/><path d="M15.5 19H14v1.5c0 .83.67 1.5 1.5 1.5s1.5-.67 1.5-1.5-.67-1.5-1.5-1.5z"/><path d="M10 9.5C10 10.33 9.33 11 8.5 11h-5C2.67 11 2 10.33 2 9.5S2.67 8 3.5 8h5c.83 0 1.5.67 1.5 1.5z"/><path d="M8.5 5H10V3.5C10 2.67 9.33 2 8.5 2S7 2.67 7 3.5 7.67 5 8.5 5z"/></svg>
              </span>
              体験・観光
            </label>
            <input
              id="activityPreferences"
              v-model="activityPreferences"
              type="text"
              placeholder="例: 温泉、景色を楽しむ、美術館"
              :disabled="isLoading"
            />
          </div>

          <div class="form-group">
            <label for="foodPreferences">
              <span class="label-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 8h1a4 4 0 0 1 0 8h-1"/><path d="M2 8h16v9a4 4 0 0 1-4 4H6a4 4 0 0 1-4-4V8z"/><line x1="6" y1="1" x2="6" y2="4"/><line x1="10" y1="1" x2="10" y2="4"/><line x1="14" y1="1" x2="14" y2="4"/></svg>
              </span>
              食事
            </label>
            <input
              id="foodPreferences"
              v-model="foodPreferences"
              type="text"
              placeholder="例: 和食、地元の名物、海鮮"
              :disabled="isLoading"
            />
          </div>

          <div class="form-group">
            <label for="accommodationType">
              <span class="label-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>
              </span>
              宿泊
            </label>
            <input
              id="accommodationType"
              v-model="accommodationType"
              type="text"
              placeholder="例: 旅館、ホテル、民宿"
              :disabled="isLoading"
            />
          </div>

          <div class="form-group">
            <label for="transportation">
              <span class="label-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="1" y="3" width="15" height="13" rx="2" ry="2"/><polygon points="16 8 20 8 23 11 23 16 16 16 16 8"/><circle cx="5.5" cy="18.5" r="2.5"/><circle cx="18.5" cy="18.5" r="2.5"/></svg>
              </span>
              移動手段
            </label>
            <input
              id="transportation"
              v-model="transportation"
              type="text"
              placeholder="例: レンタカー、公共交通機関、徒歩"
              :disabled="isLoading"
            />
          </div>
        </div>
      </div>

      <!-- 送信 -->
      <div class="form-footer">
        <p v-if="validationErrors.length > 0" class="validation-hint">
          未入力: {{ validationErrors.join('、') }}
        </p>
        <button
          type="submit"
          class="btn-submit"
          :disabled="!isValid || isLoading"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 16v-2l-8-5V3.5A1.5 1.5 0 0011.5 2h-1A1.5 1.5 0 009 3.5V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L12 19v-5.5l9 2.5z"/>
          </svg>
          {{ isLoading ? 'プラン作成中...' : 'プランを作成' }}
        </button>
      </div>
    </form>
  </div>
</template>

<style scoped>
.travel-plan-form {
  width: 100%;
}

form {
  display: flex;
  flex-direction: column;
  gap: 2rem;
}

/* ======== 2カラムグリッド ======== */
.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0;
  position: relative;
}

/* 中央のグラデーション区切り線 */
.form-grid::before {
  content: '';
  position: absolute;
  left: 50%;
  top: 10%;
  bottom: 10%;
  width: 1px;
  background: linear-gradient(
    180deg,
    transparent 0%,
    rgba(102, 126, 234, 0.2) 30%,
    rgba(118, 75, 162, 0.25) 50%,
    rgba(102, 126, 234, 0.2) 70%,
    transparent 100%
  );
  transform: translateX(-50%);
}

.form-column {
  padding: 0.5rem 2.5rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

/* ======== セクションヘッダー ======== */
.column-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.25rem;
}

.column-icon {
  width: 38px;
  height: 38px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.15) 0%, rgba(118, 75, 162, 0.15) 100%);
  border-radius: 12px;
  color: #667eea;
  flex-shrink: 0;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  border: 1px solid rgba(102, 126, 234, 0.1);
}

.column-icon.secondary {
  background: linear-gradient(135deg, rgba(118, 75, 162, 0.15) 0%, rgba(102, 126, 234, 0.1) 100%);
  color: #764ba2;
  border-color: rgba(118, 75, 162, 0.1);
}

.column-icon svg {
  width: 18px;
  height: 18px;
}

.column-header h3 {
  font-family: 'Montserrat', sans-serif;
  font-size: 0.95rem;
  font-weight: 700;
  margin: 0;
  line-height: 1.2;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.column-header p {
  font-family: 'Montserrat', sans-serif;
  font-size: 0.72rem;
  color: #a0aec0;
  margin: 0;
  letter-spacing: 0.01em;
}

/* ======== フォーム要素 ======== */
.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.form-group label {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.8rem;
  font-weight: 600;
  color: #4a5568;
  letter-spacing: 0.02em;
  padding-left: 2px;
}

.form-group label.required::after {
  content: '*';
  color: #667eea;
  font-size: 0.7rem;
  margin-left: 1px;
}

.label-icon {
  display: flex;
  align-items: center;
  color: #667eea;
  opacity: 0.5;
}

.label-icon svg {
  width: 14px;
  height: 14px;
}

.form-group input {
  width: 100%;
  padding: 10px 14px;
  border: 1px solid rgba(102, 126, 234, 0.1);
  border-radius: 12px;
  font-size: 0.9rem;
  font-family: inherit;
  background: rgba(255, 255, 255, 0.45);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  transition: all 0.25s ease;
  box-sizing: border-box;
  color: #2d3748;
}

.form-group input::placeholder {
  color: #a0aec0;
}

.form-group input:hover {
  border-color: rgba(102, 126, 234, 0.2);
  background: rgba(255, 255, 255, 0.55);
}

.form-group input:focus {
  outline: none;
  border-color: rgba(102, 126, 234, 0.45);
  background: rgba(255, 255, 255, 0.65);
  box-shadow:
    0 0 0 3px rgba(102, 126, 234, 0.08),
    0 2px 12px rgba(102, 126, 234, 0.1);
}

.form-group input:disabled {
  background: rgba(247, 250, 252, 0.5);
  cursor: not-allowed;
  opacity: 0.6;
}

.form-row {
  display: flex;
  gap: 0.75rem;
}

.form-row .form-group {
  flex: 1;
}

.field-error {
  color: #e53e3e;
  font-size: 0.78rem;
  margin: 0;
  padding-left: 2px;
}

.field-hint {
  color: #a0aec0;
  font-size: 0.7rem;
  margin: 0;
  padding-left: 2px;
}

.field-info {
  font-size: 0.8rem;
  margin: 0;
  font-weight: 600;
  padding-left: 2px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

/* ======== フッター（送信） ======== */
.form-footer {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
}

.validation-hint {
  color: #e53e3e;
  font-size: 0.78rem;
  margin: 0;
}

.btn-submit {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  width: 100%;
  max-width: 340px;
  padding: 13px 28px;
  border: none;
  border-radius: 16px;
  font-size: 0.95rem;
  font-weight: 600;
  font-family: 'Montserrat', sans-serif;
  letter-spacing: 0.02em;
  cursor: pointer;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  transition: all 0.3s ease;
  overflow: hidden;
}

/* ボタンのシマー */
.btn-submit::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(
    90deg,
    transparent 0%,
    rgba(255, 255, 255, 0.15) 50%,
    transparent 100%
  );
  background-size: 200% 100%;
  animation: btn-shimmer 3s ease-in-out infinite;
}

@keyframes btn-shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.btn-submit svg {
  width: 18px;
  height: 18px;
  position: relative;
  z-index: 1;
}

.btn-submit span,
.btn-submit {
  position: relative;
  z-index: 1;
}

.btn-submit:hover:not(:disabled) {
  box-shadow:
    0 4px 20px rgba(102, 126, 234, 0.35),
    0 8px 40px rgba(118, 75, 162, 0.15);
  transform: translateY(-2px);
}

.btn-submit:active:not(:disabled) {
  transform: translateY(0);
}

.btn-submit:disabled {
  background: rgba(160, 174, 192, 0.5);
  cursor: not-allowed;
}

.btn-submit:disabled::before {
  display: none;
}

/* ======== レスポンシブ ======== */
@media (max-width: 700px) {
  .form-grid {
    grid-template-columns: 1fr;
  }

  .form-grid::before {
    display: none;
  }

  .form-column {
    padding: 0.5rem 0;
  }
}
</style>
