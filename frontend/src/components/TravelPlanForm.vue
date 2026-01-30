<script setup lang="ts">
import { ref, computed } from 'vue'
import type { TravelPlanFormData } from '../lib/api'

interface Props {
  userId: string
  isLoading?: boolean
}

interface Emits {
  (e: 'submit', data: TravelPlanFormData): void
  (e: 'cancel'): void
}

const props = withDefaults(defineProps<Props>(), {
  isLoading: false,
})
const emit = defineEmits<Emits>()

const destination = ref('')
const startDate = ref('')
const endDate = ref('')
const departurePlace = ref('')
const budgetTotal = ref<number | undefined>(undefined)
const numPeople = ref(1)
const transportation = ref('')
const accommodationType = ref('')
const freeText = ref('')

const transportationOptions = [
  { value: '', label: '指定なし' },
  { value: '新幹線', label: '新幹線' },
  { value: '飛行機', label: '飛行機' },
  { value: 'レンタカー', label: 'レンタカー' },
  { value: 'バス', label: 'バス' },
]

const accommodationOptions = [
  { value: '', label: '指定なし' },
  { value: 'ホテル', label: 'ホテル' },
  { value: '旅館', label: '旅館' },
  { value: '民泊', label: '民泊' },
]

const isValid = computed(() => {
  if (!destination.value.trim()) return false
  if (!startDate.value) return false
  if (!endDate.value) return false
  if (startDate.value > endDate.value) return false
  if (numPeople.value < 1) return false
  return true
})

const dateError = computed(() => {
  if (startDate.value && endDate.value && startDate.value > endDate.value) {
    return '帰着日は出発日以降を選択してください'
  }
  return ''
})

const handleSubmit = () => {
  if (!isValid.value || props.isLoading) return

  const data: TravelPlanFormData = {
    user_id: props.userId,
    destination: destination.value.trim(),
    start_date: startDate.value,
    end_date: endDate.value,
    num_people: numPeople.value,
    free_text: freeText.value.trim(),
  }

  if (departurePlace.value.trim()) {
    data.departure_place = departurePlace.value.trim()
  }
  if (budgetTotal.value && budgetTotal.value > 0) {
    data.budget_total = budgetTotal.value
  }
  if (transportation.value) {
    data.transportation = transportation.value
  }
  if (accommodationType.value) {
    data.accommodation_type = accommodationType.value
  }

  emit('submit', data)
}
</script>

<template>
  <div class="travel-plan-form">
    <div class="form-header">
      <h3>旅行プランを作成</h3>
      <p>行き先や日程を入力してください</p>
    </div>

    <form @submit.prevent="handleSubmit" class="form-body">
      <!-- 必須フィールド -->
      <div class="form-section">
        <div class="form-group">
          <label for="destination" class="required">行き先</label>
          <input
            id="destination"
            v-model="destination"
            type="text"
            placeholder="例: 京都府"
            required
            :disabled="isLoading"
          />
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
      </div>

      <!-- 任意フィールド -->
      <div class="form-section">
        <div class="form-row">
          <div class="form-group">
            <label for="departurePlace">出発地</label>
            <input
              id="departurePlace"
              v-model="departurePlace"
              type="text"
              placeholder="例: 秋田県"
              :disabled="isLoading"
            />
          </div>
          <div class="form-group">
            <label for="numPeople">人数</label>
            <input
              id="numPeople"
              v-model.number="numPeople"
              type="number"
              min="1"
              :disabled="isLoading"
            />
          </div>
        </div>

        <div class="form-group">
          <label for="budgetTotal">総予算（円）</label>
          <input
            id="budgetTotal"
            v-model.number="budgetTotal"
            type="number"
            min="0"
            step="1000"
            placeholder="例: 100000"
            :disabled="isLoading"
          />
        </div>

        <div class="form-row">
          <div class="form-group">
            <label for="transportation">移動手段</label>
            <select
              id="transportation"
              v-model="transportation"
              :disabled="isLoading"
            >
              <option
                v-for="opt in transportationOptions"
                :key="opt.value"
                :value="opt.value"
              >
                {{ opt.label }}
              </option>
            </select>
          </div>
          <div class="form-group">
            <label for="accommodationType">宿泊タイプ</label>
            <select
              id="accommodationType"
              v-model="accommodationType"
              :disabled="isLoading"
            >
              <option
                v-for="opt in accommodationOptions"
                :key="opt.value"
                :value="opt.value"
              >
                {{ opt.label }}
              </option>
            </select>
          </div>
        </div>
      </div>

      <!-- 自由記述 -->
      <div class="form-section">
        <div class="form-group">
          <label for="freeText">その他の要望</label>
          <textarea
            id="freeText"
            v-model="freeText"
            placeholder="例: 神社仏閣を巡りたい、美味しい和食を楽しみたい..."
            rows="3"
            :disabled="isLoading"
          ></textarea>
        </div>
      </div>

      <!-- ボタン -->
      <div class="form-actions">
        <button
          type="button"
          class="btn-cancel"
          @click="emit('cancel')"
          :disabled="isLoading"
        >
          キャンセル
        </button>
        <button
          type="submit"
          class="btn-submit"
          :disabled="!isValid || isLoading"
        >
          <span v-if="isLoading" class="spinner"></span>
          {{ isLoading ? 'プラン生成中...' : 'プランを作成' }}
        </button>
      </div>
    </form>
  </div>
</template>

<style scoped>
.travel-plan-form {
  background: white;
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid #e2e8f0;
}

.form-header {
  padding: 1rem 1.5rem;
  background: linear-gradient(135deg, #38b2ac 0%, #319795 100%);
  color: white;
}

.form-header h3 {
  margin: 0 0 0.25rem;
  font-size: 1.1rem;
}

.form-header p {
  margin: 0;
  font-size: 0.8rem;
  opacity: 0.9;
}

.form-body {
  padding: 1.25rem 1.5rem;
}

.form-section {
  margin-bottom: 1rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid #edf2f7;
}

.form-section:last-of-type {
  border-bottom: none;
  margin-bottom: 0;
}

.form-group {
  margin-bottom: 0.75rem;
}

.form-group label {
  display: block;
  margin-bottom: 0.3rem;
  font-size: 0.85rem;
  font-weight: 500;
  color: #4a5568;
}

.form-group label.required::after {
  content: ' *';
  color: #e53e3e;
}

.form-group input,
.form-group select,
.form-group textarea {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  font-size: 0.9rem;
  font-family: inherit;
  background: white;
  transition: border-color 0.2s;
  box-sizing: border-box;
}

.form-group input:focus,
.form-group select:focus,
.form-group textarea:focus {
  outline: none;
  border-color: #38b2ac;
  box-shadow: 0 0 0 3px rgba(56, 178, 172, 0.1);
}

.form-group input:disabled,
.form-group select:disabled,
.form-group textarea:disabled {
  background: #f7fafc;
  cursor: not-allowed;
}

.form-group textarea {
  resize: vertical;
  min-height: 60px;
}

.form-row {
  display: flex;
  gap: 1rem;
}

.form-row .form-group {
  flex: 1;
}

.field-error {
  color: #e53e3e;
  font-size: 0.8rem;
  margin: 0.25rem 0 0;
}

.form-actions {
  display: flex;
  gap: 0.75rem;
  justify-content: flex-end;
  padding-top: 0.5rem;
}

.btn-cancel,
.btn-submit {
  padding: 10px 24px;
  border: none;
  border-radius: 8px;
  font-size: 0.9rem;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s;
}

.btn-cancel {
  background: #edf2f7;
  color: #4a5568;
}

.btn-cancel:hover:not(:disabled) {
  background: #e2e8f0;
}

.btn-submit {
  background: #38b2ac;
  color: white;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.btn-submit:hover:not(:disabled) {
  background: #319795;
}

.btn-submit:disabled {
  background: #a0aec0;
  cursor: not-allowed;
}

.btn-cancel:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.spinner {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
