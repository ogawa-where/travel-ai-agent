<script setup lang="ts">
import { ref, computed } from 'vue'

interface BasicTravelInfo {
  user_id: string
  area: string
  start_date: string
  end_date: string
  num_people: number
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

const isValid = computed(() => {
  if (!area.value.trim()) return false
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
  }

  emit('submit', data)
}
</script>

<template>
  <div class="travel-plan-form">
    <div class="form-header">
      <h3>旅行の基本情報</h3>
      <p>観光エリアと日程を入力してください</p>
    </div>

    <form @submit.prevent="handleSubmit" class="form-body">
      <!-- 観光エリア -->
      <div class="form-section">
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
          <p class="field-hint">このエリア内で観光スポット・食事・宿泊を探します</p>
        </div>
      </div>

      <!-- 日程 -->
      <div class="form-section">
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
      </div>

      <!-- 人数 -->
      <div class="form-section">
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
      </div>

      <!-- ボタン -->
      <div class="form-actions">
        <button
          type="submit"
          class="btn-submit"
          :disabled="!isValid || isLoading"
        >
          次へ：詳細を入力
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
  max-width: 500px;
  margin: 0 auto;
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

.form-group:last-child {
  margin-bottom: 0;
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

.form-group input {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  font-size: 0.95rem;
  font-family: inherit;
  background: white;
  transition: border-color 0.2s;
  box-sizing: border-box;
}

.form-group input:focus {
  outline: none;
  border-color: #38b2ac;
  box-shadow: 0 0 0 3px rgba(56, 178, 172, 0.1);
}

.form-group input:disabled {
  background: #f7fafc;
  cursor: not-allowed;
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
  margin: 0.5rem 0 0;
}

.field-hint {
  color: #718096;
  font-size: 0.75rem;
  margin: 0.3rem 0 0;
}

.field-info {
  color: #38b2ac;
  font-size: 0.85rem;
  margin: 0.5rem 0 0;
  font-weight: 500;
}

.form-actions {
  padding-top: 0.5rem;
}

.btn-submit {
  width: 100%;
  padding: 12px 24px;
  border: none;
  border-radius: 8px;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  background: #38b2ac;
  color: white;
  transition: background 0.2s;
}

.btn-submit:hover:not(:disabled) {
  background: #319795;
}

.btn-submit:disabled {
  background: #a0aec0;
  cursor: not-allowed;
}
</style>
