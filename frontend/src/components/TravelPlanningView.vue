<script setup lang="ts">
import { ref, nextTick, computed, onUnmounted, reactive, watch } from 'vue'
import { api } from '../lib/api'
import { getErrorMessage } from '../lib/errors'
import type { User, TravelPlan, CollectedTravelInfo, BasicTravelInfo, RequiredInfoStatus, GeoEnrichedItinerary, POIFeedbackType, POICategory, POIDetail, TravelPlanRequestResponse } from '../lib/api'
import TravelPlanForm from './TravelPlanForm.vue'
import ItineraryDisplay from './ItineraryDisplay.vue'
import ItineraryMap from './ItineraryMap.vue'
import POIDetailModal from './POIDetailModal.vue'

interface Props {
  user: User | null
}

interface Emits {
  (e: 'plan-created', plan: TravelPlan): void
  (e: 'back-to-select'): void
}

interface Message {
  role: 'user' | 'assistant'
  content: string
  plan?: TravelPlan
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

type Phase = 'form' | 'confirm' | 'gathering' | 'ready' | 'planning' | 'result'
const phase = ref<Phase>('form')

const sessionId = ref<string | null>(null)
const messages = ref<Message[]>([])
const isLoading = ref(false)
const isStreaming = ref(false)
const streamingMessageIndex = ref(-1)
const inputMessage = ref('')
const messagesContainer = ref<HTMLElement | null>(null)
const currentPlan = ref<TravelPlan | null>(null)
const isComposing = ref(false)
const resultError = ref<string | null>(null)

const targetProgress = ref(0)
const displayProgress = ref(0)
const currentPhase = ref('')
let progressInterval: number | null = null

const phaseLabels: Record<string, string> = {
  translate: '準備中',
  search: '検索中',
  normalize: '整理中',
  rerank: '分析中',
  plan: 'プラン作成中',
  explain: '仕上げ中',
  complete: '完了',
}

const phaseMaxProgress: Record<string, number> = {
  translate: 15,
  search: 32,
  normalize: 49,
  rerank: 65,
  plan: 82,
  explain: 99,
  complete: 100,
}

const getPhaseLabel = (phase: string): string => {
  return phaseLabels[phase] || phase
}

const startProgressAnimation = () => {
  targetProgress.value = 0
  displayProgress.value = 0
  currentPhase.value = ''
  progressInterval = window.setInterval(() => {
    const target = targetProgress.value
    const current = displayProgress.value
    const phase = currentPhase.value
    const maxForPhase = phaseMaxProgress[phase] ?? 99
    if (current < target) {
      const diff = target - current
      const speed = diff > 20 ? 3 : diff > 10 ? 1.5 : 0.5
      displayProgress.value = Math.min(current + speed, target)
    } else if (current < maxForPhase) {
      displayProgress.value = current + 0.3
    }
  }, 100)
}

const updateProgress = (phase: string, percent: number) => {
  currentPhase.value = phase
  targetProgress.value = percent
}

const stopProgressAnimation = () => {
  if (progressInterval) {
    clearInterval(progressInterval)
    progressInterval = null
  }
}

onUnmounted(() => {
  stopProgressAnimation()
})

const basicInfo = ref<BasicTravelInfo | null>(null)
const collectedInfo = ref<CollectedTravelInfo>({
  area: '',
  start_date: '',
  end_date: '',
  num_people: 1,
})
const missingInfo = ref<string[]>([])

const requiredInfoStatus = ref<RequiredInfoStatus>({
  has_activities: false,
  has_food: false,
  has_accommodation: false,
  has_transportation: false,
  category_count: 0,
  is_complete: false,
})
const allRequiredSatisfied = ref(false)
const missingRequiredInfo = ref<string[]>(['やりたいこと', '食の好み', '宿泊の希望', '移動手段'])

// Geo data (moved from TravelPlanCard)
const geoData = ref<GeoEnrichedItinerary | null>(null)
const geoLoading = ref(false)
const geoError = ref(false)
const selectedDay = ref(0) // 0 = all days

// POI feedback
const poiFeedback = reactive<Record<string, POIFeedbackType>>({})

// POI Detail modal
const showPOIDetail = ref(false)
const poiDetail = ref<POIDetail | null>(null)
const poiDetailLoading = ref(false)
const poiDetailError = ref<string | null>(null)

// History panel
const showHistory = ref(false)
const planHistory = ref<TravelPlanRequestResponse[]>([])
const historyLoading = ref(false)

const handleCompositionStart = () => { isComposing.value = true }
const handleCompositionEnd = () => { setTimeout(() => { isComposing.value = false }, 200) }

const autoResizeTextarea = (event: Event) => {
  const textarea = event.target as HTMLTextAreaElement
  textarea.style.height = 'auto'
  textarea.style.height = Math.min(textarea.scrollHeight, 150) + 'px'
}

const handleKeydown = (event: KeyboardEvent) => {
  if (event.key !== 'Enter') return
  if (event.shiftKey) return
  event.preventDefault()
  if ((event.ctrlKey || event.metaKey) && !isComposing.value && !event.isComposing && event.keyCode !== 229) {
    sendGatheringMessage()
  }
}

const scrollToBottom = async () => {
  await nextTick()
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

const tripDays = computed(() => {
  if (!collectedInfo.value.start_date || !collectedInfo.value.end_date) return null
  const start = new Date(collectedInfo.value.start_date)
  const end = new Date(collectedInfo.value.end_date)
  return Math.ceil((end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24)) + 1
})

// Day tabs for the map
const dayCount = computed(() => currentPlan.value?.itinerary?.days?.length || 0)

const handleFormSubmit = async (data: BasicTravelInfo) => {
  if (!props.user) return
  basicInfo.value = data
  collectedInfo.value = {
    area: data.area,
    start_date: data.start_date,
    end_date: data.end_date,
    num_people: data.num_people,
    budget: data.budget,
    activity_preferences: data.activity_preferences ? [data.activity_preferences] : [],
    food_preferences: data.food_preferences ? [data.food_preferences] : [],
    accommodation_type: data.accommodation_type || undefined,
    transportation: data.transportation || undefined,
  }
  phase.value = 'confirm'
}

const confirmAndStartPlanning = () => {
  startPlanGenerationFromForm()
}

const backToForm = () => {
  phase.value = 'form'
}

const sendGatheringMessage = async () => {
  if (!props.user || isLoading.value || !inputMessage.value.trim()) return
  const userMessage = inputMessage.value.trim()
  inputMessage.value = ''
  messages.value.push({ role: 'user', content: userMessage })
  await scrollToBottom()
  try {
    isLoading.value = true
    isStreaming.value = true
    messages.value.push({ role: 'assistant', content: '' })
    streamingMessageIndex.value = messages.value.length - 1
    await scrollToBottom()
    await api.sendGatheringMessageStream(
      props.user.id, userMessage, sessionId.value || '',
      (content: string) => { if (streamingMessageIndex.value >= 0) { messages.value[streamingMessageIndex.value].content += content; scrollToBottom() } },
      (info: CollectedTravelInfo) => { collectedInfo.value = info },
      (response) => { sessionId.value = response.session_id; collectedInfo.value = response.collected_info; missingInfo.value = response.missing_info; requiredInfoStatus.value = response.required_info_status; allRequiredSatisfied.value = response.all_required_satisfied; missingRequiredInfo.value = response.missing_required_info; isStreaming.value = false; streamingMessageIndex.value = -1 },
      (error: string) => { console.error('Streaming error:', error); if (streamingMessageIndex.value >= 0) { messages.value[streamingMessageIndex.value].content = `エラー: ${error}` } isStreaming.value = false; streamingMessageIndex.value = -1 }
    )
  } catch (error) {
    console.error('Failed to send gathering message:', error)
    if (streamingMessageIndex.value >= 0) { messages.value[streamingMessageIndex.value].content = `エラー: ${getErrorMessage(error)}` }
    isStreaming.value = false; streamingMessageIndex.value = -1
  } finally { isLoading.value = false }
}

const finishGathering = () => { phase.value = 'ready' }
const backToGathering = () => { phase.value = 'gathering' }

// Fetch geo data for the current plan
const fetchGeoData = async () => {
  if (!currentPlan.value || geoData.value || geoLoading.value) return
  geoLoading.value = true
  geoError.value = false
  try {
    const destination = currentPlan.value.itinerary.days?.[0]?.items?.[0]?.poi?.location || ''
    geoData.value = await api.enrichItineraryGeo(currentPlan.value.itinerary, destination)
  } catch {
    geoError.value = true
  } finally {
    geoLoading.value = false
  }
}

// Fetch plan history
const fetchPlanHistory = async () => {
  if (!props.user) return
  historyLoading.value = true
  try {
    planHistory.value = await api.getUserTravelHistory(props.user.id)
  } catch (error) {
    console.error('Failed to fetch plan history:', error)
  } finally {
    historyLoading.value = false
  }
}

const toggleHistory = () => {
  showHistory.value = !showHistory.value
  if (showHistory.value && planHistory.value.length === 0) {
    fetchPlanHistory()
  }
}

// Load a past plan from history
const historyLoadingId = ref<string | null>(null)
const loadHistoryPlan = async (item: TravelPlanRequestResponse) => {
  if (item.status === 'failed' || historyLoadingId.value) return
  historyLoadingId.value = item.id
  try {
    const plans = await api.getPlansByRequestId(item.id)
    if (plans.length > 0) {
      // Use the selected plan, or the first one
      const plan = plans.find(p => p.is_selected) || plans[0]
      currentPlan.value = plan
      resultError.value = null
      geoData.value = null
      geoError.value = false
      selectedDay.value = 0
      Object.keys(poiFeedback).forEach(k => delete poiFeedback[k])
      phase.value = 'result'
      showHistory.value = false
      fetchGeoData()
    }
  } catch (error) {
    console.error('Failed to load history plan:', error)
  } finally {
    historyLoadingId.value = null
  }
}

// POI feedback handler
const handlePOIFeedback = async (
  poiName: string,
  category: POICategory,
  feedbackType: POIFeedbackType,
  tags: string[]
) => {
  if (!props.user || !currentPlan.value) return
  poiFeedback[poiName] = feedbackType
  try {
    await api.sendPOIFeedback(
      props.user.id,
      currentPlan.value.id,
      poiName,
      category,
      feedbackType,
      tags
    )
  } catch (error) {
    console.error('Failed to send POI feedback:', error)
    delete poiFeedback[poiName]
  }
}

// POI detail click handler
const handlePOIClick = async (poiName: string, category: POICategory) => {
  showPOIDetail.value = true
  poiDetailLoading.value = true
  poiDetailError.value = null
  poiDetail.value = null
  try {
    const destination = currentPlan.value?.itinerary.days?.[0]?.items?.[0]?.poi?.location || ''
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

const startPlanGenerationFromForm = async () => {
  if (!props.user || !basicInfo.value) return
  phase.value = 'planning'
  isLoading.value = true
  messages.value = []
  resultError.value = null
  geoData.value = null
  geoError.value = false
  selectedDay.value = 0
  Object.keys(poiFeedback).forEach(k => delete poiFeedback[k])
  startProgressAnimation()
  try {
    const formData = {
      user_id: props.user.id,
      destination: basicInfo.value.area,
      start_date: basicInfo.value.start_date,
      end_date: basicInfo.value.end_date,
      num_people: basicInfo.value.num_people,
      budget_total: basicInfo.value.budget,
      transportation: basicInfo.value.transportation || undefined,
      accommodation_type: basicInfo.value.accommodation_type || undefined,
      free_text: [
        basicInfo.value.activity_preferences ? `やりたいこと: ${basicInfo.value.activity_preferences}` : '',
        basicInfo.value.food_preferences ? `食の好み: ${basicInfo.value.food_preferences}` : '',
      ].filter(Boolean).join('。'),
    }
    await api.submitTravelFormStream(
      formData,
      (progressPhase: string, percent: number) => { updateProgress(progressPhase, percent) },
      (response) => {
        sessionId.value = response.session_id
        stopProgressAnimation()
        if (response.plan) {
          currentPlan.value = response.plan
          emit('plan-created', response.plan)
          fetchGeoData()
        } else {
          resultError.value = response.assistant_message
        }
        phase.value = 'result'
        isLoading.value = false
      },
      (error: string) => {
        console.error('Plan generation failed:', error)
        stopProgressAnimation()
        resultError.value = `プランの生成に失敗しました。\n${error}`
        phase.value = 'result'
        isLoading.value = false
      }
    )
  } catch (error) {
    console.error('Failed to generate plan:', error)
    stopProgressAnimation()
    resultError.value = `プランの生成に失敗しました。\n${getErrorMessage(error)}`
    phase.value = 'result'
    isLoading.value = false
  }
}

const startPlanGeneration = async () => {
  if (!props.user || !sessionId.value) return
  phase.value = 'planning'; isLoading.value = true; startProgressAnimation()
  resultError.value = null
  geoData.value = null
  geoError.value = false
  selectedDay.value = 0
  Object.keys(poiFeedback).forEach(k => delete poiFeedback[k])
  try {
    const response = await api.startPlanGeneration(props.user.id, sessionId.value, collectedInfo.value)
    if (response.plan) {
      currentPlan.value = response.plan
      emit('plan-created', response.plan)
      fetchGeoData()
    } else {
      resultError.value = response.assistant_message
    }
    stopProgressAnimation(); phase.value = 'result'
  } catch (error) {
    console.error('Failed to generate plan:', error); stopProgressAnimation()
    resultError.value = `プランの生成に失敗しました。\n${getErrorMessage(error)}`
    phase.value = 'result'
  } finally { isLoading.value = false }
}

const startNewPlan = () => {
  phase.value = 'form'; sessionId.value = null; messages.value = []; currentPlan.value = null; basicInfo.value = null
  collectedInfo.value = { area: '', start_date: '', end_date: '', num_people: 1 }; missingInfo.value = []
  requiredInfoStatus.value = { has_activities: false, has_food: false, has_accommodation: false, has_transportation: false, category_count: 0, is_complete: false }
  allRequiredSatisfied.value = false; missingRequiredInfo.value = ['やりたいこと', '食の好み', '宿泊の希望', '移動手段']
  resultError.value = null; geoData.value = null; geoError.value = false; selectedDay.value = 0
  Object.keys(poiFeedback).forEach(k => delete poiFeedback[k])
}

// Format history date
const formatHistoryDate = (dateStr: string): string => {
  const d = new Date(dateStr)
  return `${d.getFullYear()}/${(d.getMonth() + 1).toString().padStart(2, '0')}/${d.getDate().toString().padStart(2, '0')}`
}

// Get destination from constraints or raw_request
const getHistoryDestination = (constraints: Record<string, unknown>, rawRequest?: string): string => {
  if (constraints?.destination) return constraints.destination as string
  // Fallback: parse raw_request for "XXXへの旅行"
  if (rawRequest) {
    const match = rawRequest.match(/(.+?)への旅行/)
    if (match) return match[1]
  }
  return '不明'
}

// Get date range from constraints or raw_request
const getHistoryDateRange = (constraints: Record<string, unknown>, rawRequest?: string): string => {
  const start = constraints?.start_date as string
  const end = constraints?.end_date as string
  if (start && end) return `${start} ~ ${end}`
  // Fallback: parse raw_request for "期間: YYYY-MM-DD 〜 YYYY-MM-DD"
  if (rawRequest) {
    const match = rawRequest.match(/期間:\s*(\d{4}-\d{2}-\d{2})\s*[〜~]\s*(\d{4}-\d{2}-\d{2})/)
    if (match) return `${match[1]} ~ ${match[2]}`
  }
  return ''
}

// Route distance/time for selected day
const selectedDayRoute = computed(() => {
  if (!geoData.value) return null
  if (selectedDay.value === 0) {
    // Sum all days
    let totalDist = 0
    let totalDur = 0
    for (const day of geoData.value.days) {
      if (day.total_distance_km) totalDist += day.total_distance_km
      if (day.total_duration_minutes) totalDur += day.total_duration_minutes
    }
    if (totalDist === 0 && totalDur === 0) return null
    return { distance: totalDist, duration: totalDur }
  }
  const day = geoData.value.days.find(d => d.day_number === selectedDay.value)
  if (!day || (!day.total_distance_km && !day.total_duration_minutes)) return null
  return { distance: day.total_distance_km || 0, duration: day.total_duration_minutes || 0 }
})

const formatCollectedInfo = computed(() => {
  const info = collectedInfo.value; const items: { label: string; value: string }[] = []
  if (info.area) items.push({ label: '観光エリア', value: info.area })
  if (info.start_date && info.end_date) items.push({ label: '日程', value: `${info.start_date} 〜 ${info.end_date}（${tripDays.value}日間）` })
  if (info.num_people) items.push({ label: '人数', value: `${info.num_people}人` })
  if (info.budget) items.push({ label: '予算', value: `${info.budget.toLocaleString()}円` })
  if (info.transportation) items.push({ label: '移動手段', value: info.transportation })
  if (info.accommodation_type) items.push({ label: '宿泊タイプ', value: info.accommodation_type })
  if (info.food_preferences?.length) items.push({ label: '食事の好み', value: info.food_preferences.join('、') })
  if (info.activity_preferences?.length) items.push({ label: 'やりたいこと', value: info.activity_preferences.join('、') })
  return items
})
</script>

<template>
  <div class="travel-planning-view">
    <!-- ヘッダーバー -->
    <div class="chat-header">
      <div class="header-left">
        <button class="header-back-btn" @click="$emit('back-to-select')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="15 18 9 12 15 6"/>
          </svg>
          <span>戻る</span>
        </button>
        <div class="header-divider"></div>
        <div class="header-title">
          <h3>旅行企画</h3>
          <span class="header-subtitle">Travel Planning</span>
        </div>
      </div>

      <!-- フェーズインジケーター（中央） -->
      <div class="phase-indicator">
        <div class="phase-item" :class="{ active: phase === 'form', completed: ['confirm', 'gathering', 'ready', 'planning', 'result'].includes(phase) }">
          <div class="phase-dot">1</div>
          <span>入力</span>
        </div>
        <div class="phase-line" :class="{ active: ['confirm', 'gathering', 'ready', 'planning', 'result'].includes(phase) }"></div>
        <div class="phase-item" :class="{ active: phase === 'confirm', completed: ['gathering', 'ready', 'planning', 'result'].includes(phase) }">
          <div class="phase-dot">2</div>
          <span>確認</span>
        </div>
        <div class="phase-line" :class="{ active: ['gathering', 'ready', 'planning', 'result'].includes(phase) }"></div>
        <div class="phase-item" :class="{ active: phase === 'planning', completed: phase === 'result' }">
          <div class="phase-dot">3</div>
          <span>生成</span>
        </div>
        <div class="phase-line" :class="{ active: phase === 'result' }"></div>
        <div class="phase-item" :class="{ active: phase === 'result' }">
          <div class="phase-dot">4</div>
          <span>結果</span>
        </div>
      </div>

      <div class="header-right">
        <button class="header-history-btn" @click="toggleHistory">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"/>
            <polyline points="12 6 12 12 16 14"/>
          </svg>
          <span>履歴</span>
        </button>
        <button v-if="phase === 'result'" class="header-new-plan-btn" @click="startNewPlan">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="12" y1="5" x2="12" y2="19"/>
            <line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
          <span>新しいプラン</span>
        </button>
      </div>
    </div>

    <!-- メインエリア -->
    <main class="main-content">
      <!-- Phase 1: フォーム -->
      <div v-if="phase === 'form'" class="form-phase">
        <div class="form-container">
          <TravelPlanForm
            v-if="user"
            :user-id="user.id"
            :is-loading="isLoading"
            @submit="handleFormSubmit"
          />
          <div v-else class="no-user-message">ログインしてください</div>
        </div>
      </div>

      <!-- Phase 2: 確認画面 -->
      <div v-else-if="phase === 'confirm'" class="confirm-phase">
        <div class="confirm-layout">
          <!-- 左カラム: 入力内容サマリー -->
          <div class="confirm-card">
            <h3 class="confirm-card-title">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
                <line x1="16" y1="13" x2="8" y2="13"/>
                <line x1="16" y1="17" x2="8" y2="17"/>
                <polyline points="10 9 9 9 8 9"/>
              </svg>
              入力内容
            </h3>
            <div class="confirm-summary">
              <div v-for="item in formatCollectedInfo" :key="item.label" class="confirm-summary-item">
                <span class="confirm-summary-label">{{ item.label }}</span>
                <span class="confirm-summary-value">{{ item.value }}</span>
              </div>
            </div>
          </div>

          <!-- 右カラム: 実行ステップ一覧 -->
          <div class="confirm-card">
            <h3 class="confirm-card-title">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
              </svg>
              実行ステップ
            </h3>
            <div class="step-list">
              <div class="step-list-item">
                <div class="step-number">1</div>
                <div class="step-detail">
                  <span class="step-title">準備</span>
                  <span class="step-desc">入力情報の構造化</span>
                </div>
              </div>
              <div class="step-list-item">
                <div class="step-number">2</div>
                <div class="step-detail">
                  <span class="step-title">検索</span>
                  <span class="step-desc">4カテゴリ並列検索（体験・食・宿・交通）</span>
                </div>
              </div>
              <div class="step-list-item">
                <div class="step-number">3</div>
                <div class="step-detail">
                  <span class="step-title">整理</span>
                  <span class="step-desc">検索結果の正規化・重複排除</span>
                </div>
              </div>
              <div class="step-list-item">
                <div class="step-number">4</div>
                <div class="step-detail">
                  <span class="step-title">分析</span>
                  <span class="step-desc">嗜好に基づくスコアリング</span>
                </div>
              </div>
              <div class="step-list-item">
                <div class="step-number">5</div>
                <div class="step-detail">
                  <span class="step-title">プラン作成</span>
                  <span class="step-desc">旅程の自動生成</span>
                </div>
              </div>
              <div class="step-list-item">
                <div class="step-number">6</div>
                <div class="step-detail">
                  <span class="step-title">仕上げ</span>
                  <span class="step-desc">プランの説明文生成</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- フッター: アクションボタン -->
        <div class="confirm-actions">
          <button class="confirm-back-btn" @click="backToForm">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="15 18 9 12 15 6"/>
            </svg>
            戻る
          </button>
          <button class="confirm-start-btn" @click="confirmAndStartPlanning">
            企画を開始する
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="9 18 15 12 9 6"/>
            </svg>
          </button>
        </div>
      </div>

      <!-- Phase 4: プラン生成中 -->
      <div v-else-if="phase === 'planning'" class="planning-phase">
        <div class="planning-content">
          <div class="planning-animation">
            <div class="planning-avatar-area">
              <div class="avatar-ring ring-1"></div>
              <div class="avatar-ring ring-2"></div>
              <div class="avatar-ring ring-3"></div>
              <div class="planning-avatar">
                <img src="/ylab-logo.png" alt="Ylab" class="avatar-logo" @error="($event.target as HTMLImageElement).style.display='none'" />
                <svg class="avatar-logo-fallback" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                  <path d="M21 16v-2l-8-5V3.5A1.5 1.5 0 0011.5 2h-1A1.5 1.5 0 009 3.5V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L12 19v-5.5l9 2.5z"/>
                </svg>
              </div>
            </div>
          </div>
          <h2>プランを作成中</h2>
          <p class="planning-destination">{{ collectedInfo.area }}への旅行プランを生成しています</p>

          <div class="progress-section">
            <div class="progress-bar">
              <div class="progress-fill" :style="{ width: `${displayProgress}%` }"></div>
            </div>
            <div class="progress-info">
              <span class="progress-phase">{{ getPhaseLabel(currentPhase) }}</span>
              <span class="progress-percent">{{ Math.round(displayProgress) }}%</span>
            </div>
          </div>

          <div class="progress-steps">
            <div v-for="(label, key) in phaseLabels" :key="key" class="step" :class="{ active: currentPhase === key, completed: phaseMaxProgress[key] < displayProgress }">
              <span class="step-dot"></span>
              <span class="step-label">{{ label }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Phase 5: 結果表示（左右分割） -->
      <div v-else-if="phase === 'result'" class="result-phase">
        <!-- エラー時：フルワイド -->
        <div v-if="resultError && !currentPlan" class="result-error">
          <div class="error-card">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="error-icon">
              <circle cx="12" cy="12" r="10"/>
              <line x1="12" y1="8" x2="12" y2="12"/>
              <line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
            <p>{{ resultError }}</p>
            <button class="retry-btn" @click="startNewPlan">もう一度試す</button>
          </div>
        </div>

        <!-- 成功時：左右分割レイアウト -->
        <div v-else-if="currentPlan" class="result-layout">
          <!-- 左パネル：旅程 -->
          <div class="result-left">
            <div class="plan-header-section">
              <h2 class="plan-title">{{ currentPlan.itinerary.title || '旅行プラン' }}</h2>
              <p v-if="currentPlan.itinerary.summary" class="plan-summary">{{ currentPlan.itinerary.summary }}</p>
              <div v-if="currentPlan.itinerary.highlights && currentPlan.itinerary.highlights.length > 0" class="plan-highlights">
                <span v-for="(h, i) in currentPlan.itinerary.highlights" :key="i" class="highlight-chip">{{ h }}</span>
              </div>
              <div v-if="currentPlan.itinerary.total_budget_estimate" class="plan-budget">
                <span class="budget-label">予算目安</span>
                <span class="budget-value">{{ currentPlan.itinerary.total_budget_estimate.toLocaleString() }}円</span>
              </div>
            </div>

            <ItineraryDisplay
              :itinerary="currentPlan.itinerary"
              :feedback-enabled="!!user?.id"
              :poi-feedback="poiFeedback"
              @poi-feedback="handlePOIFeedback"
              @poi-click="handlePOIClick"
            />

            <div v-if="currentPlan.rationale" class="rationale-section">
              <h4>このプランについて</h4>
              <p>{{ currentPlan.rationale }}</p>
            </div>
          </div>

          <!-- 右パネル：地図 -->
          <div class="result-right">
            <div class="map-container">
              <div v-if="geoLoading" class="map-loading">
                <div class="map-skeleton"></div>
                <span class="map-loading-text">地図を読み込み中...</span>
              </div>
              <div v-else-if="geoData && !geoError" class="map-content">
                <ItineraryMap
                  :geo-data="geoData"
                  :selected-day="selectedDay"
                  height="100%"
                />
              </div>
              <div v-else-if="geoError" class="map-error">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/>
                  <circle cx="12" cy="10" r="3"/>
                </svg>
                <span>地図の読み込みに失敗しました</span>
              </div>
            </div>

            <!-- 日程切り替えタブ -->
            <div v-if="dayCount > 0" class="day-tab-bar">
              <button
                :class="['day-tab', { active: selectedDay === 0 }]"
                @click="selectedDay = 0"
              >全日程</button>
              <button
                v-for="n in dayCount"
                :key="n"
                :class="['day-tab', { active: selectedDay === n }]"
                @click="selectedDay = n"
              >{{ n }}日目</button>
            </div>

            <!-- ルート情報 -->
            <div v-if="selectedDayRoute" class="route-info">
              <div class="route-stat">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M18 6L6 18M6 6l12 12"/>
                </svg>
                <span>{{ selectedDayRoute.distance.toFixed(1) }} km</span>
              </div>
              <div class="route-stat">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <circle cx="12" cy="12" r="10"/>
                  <polyline points="12 6 12 12 16 14"/>
                </svg>
                <span>約{{ Math.round(selectedDayRoute.duration) }}分</span>
              </div>
            </div>
          </div>
        </div>

      </div>
    </main>

    <!-- 履歴パネル -->
    <Transition name="history">
      <div v-if="showHistory" class="history-overlay" @click.self="showHistory = false">
        <div class="history-panel">
          <div class="history-header">
            <h3>旅行履歴</h3>
            <button class="history-close-btn" @click="showHistory = false">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"/>
                <line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            </button>
          </div>
          <div class="history-list">
            <div v-if="historyLoading" class="history-loading">
              <div class="history-skeleton" v-for="i in 3" :key="i"></div>
            </div>
            <div v-else-if="planHistory.length === 0" class="history-empty">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/>
                <circle cx="12" cy="10" r="3"/>
              </svg>
              <p>まだ旅行プランがありません</p>
            </div>
            <div
              v-else
              v-for="item in planHistory"
              :key="item.id"
              :class="['history-item', { clickable: item.status !== 'failed', loading: historyLoadingId === item.id }]"
              @click="loadHistoryPlan(item)"
            >
              <div class="history-item-destination">{{ getHistoryDestination(item.constraints, item.raw_request) }}</div>
              <div class="history-item-meta">
                <span v-if="getHistoryDateRange(item.constraints, item.raw_request)" class="history-date-range">{{ getHistoryDateRange(item.constraints, item.raw_request) }}</span>
                <span class="history-created">作成: {{ formatHistoryDate(item.created_at) }}</span>
              </div>
              <div class="history-item-footer">
                <span :class="['history-status', item.status]">{{ item.status === 'completed' ? '完了' : item.status === 'failed' ? '失敗' : '完了' }}</span>
                <span v-if="historyLoadingId === item.id" class="history-item-loading">読み込み中...</span>
                <span v-else-if="item.status !== 'failed'" class="history-item-action">表示</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Transition>

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
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;600&family=Montserrat:wght@300;400;500;600&display=swap');

.travel-planning-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

/* ======== ヘッダーバー ======== */
.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 2rem;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  background: rgba(255, 255, 255, 0.5);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.header-back-btn {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.5rem 0.75rem 0.5rem 0.5rem;
  background: transparent;
  border: none;
  border-radius: 10px;
  font-family: 'Montserrat', sans-serif;
  font-size: 0.82rem;
  font-weight: 500;
  color: #718096;
  cursor: pointer;
  transition: all 0.2s ease;
  flex-shrink: 0;
}

.header-back-btn:hover {
  color: #4a5568;
  background: rgba(0, 0, 0, 0.04);
}

.header-back-btn svg {
  width: 18px;
  height: 18px;
  transition: transform 0.2s ease;
}

.header-back-btn:hover svg {
  transform: translateX(-2px);
}

.header-divider {
  width: 1px;
  height: 28px;
  background: rgba(0, 0, 0, 0.08);
  flex-shrink: 0;
}

.header-title h3 {
  font-family: 'Montserrat', sans-serif;
  font-size: 1.05rem;
  font-weight: 700;
  color: #1a202c;
  margin: 0;
  line-height: 1.2;
}

.header-subtitle {
  font-family: 'Montserrat', sans-serif;
  font-size: 0.72rem;
  font-weight: 400;
  color: #a0aec0;
  letter-spacing: 0.02em;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  min-width: 120px;
  justify-content: flex-end;
}

.header-history-btn {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.5rem 0.85rem;
  background: transparent;
  border: 1.5px solid rgba(0, 0, 0, 0.1);
  border-radius: 10px;
  font-family: 'Montserrat', sans-serif;
  font-size: 0.82rem;
  font-weight: 500;
  color: #718096;
  cursor: pointer;
  transition: all 0.25s ease;
  flex-shrink: 0;
  white-space: nowrap;
}

.header-history-btn:hover {
  color: #667eea;
  border-color: rgba(102, 126, 234, 0.3);
  background: rgba(102, 126, 234, 0.04);
}

.header-history-btn svg {
  width: 16px;
  height: 16px;
}

.header-new-plan-btn {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.55rem 1rem;
  background: transparent;
  border: 1.5px solid rgba(102, 126, 234, 0.3);
  border-radius: 10px;
  font-family: 'Montserrat', sans-serif;
  font-size: 0.82rem;
  font-weight: 600;
  color: #667eea;
  cursor: pointer;
  transition: all 0.25s ease;
  flex-shrink: 0;
  white-space: nowrap;
}

.header-new-plan-btn:hover {
  background: rgba(102, 126, 234, 0.06);
  border-color: rgba(102, 126, 234, 0.5);
  box-shadow: 0 2px 10px rgba(102, 126, 234, 0.12);
}

.header-new-plan-btn svg {
  width: 16px;
  height: 16px;
  stroke: #667eea;
}

/* ======== フェーズインジケーター（ヘッダー中央） ======== */
.phase-indicator {
  display: flex;
  align-items: center;
  gap: 0;
}

.phase-item {
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

.phase-dot {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.06);
  border-radius: 50%;
  font-family: 'Montserrat', sans-serif;
  font-size: 0.7rem;
  font-weight: 600;
  color: #a0aec0;
  transition: all 0.3s ease;
}

.phase-item.active .phase-dot {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.phase-item.completed .phase-dot {
  background: rgba(102, 126, 234, 0.2);
  color: #667eea;
}

.phase-item span:not(.phase-dot) {
  font-family: 'Montserrat', sans-serif;
  font-size: 0.7rem;
  font-weight: 500;
  color: #718096;
}

.phase-line {
  width: 20px;
  height: 2px;
  background: rgba(0, 0, 0, 0.08);
  margin: 0 6px;
  transition: all 0.3s ease;
}

.phase-line.active {
  background: rgba(102, 126, 234, 0.4);
}

/* ======== メインコンテンツ ======== */
.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
}

/* ======== フォームフェーズ ======== */
.form-phase {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 2rem 3rem 3rem;
  overflow-y: auto;
  min-height: 0;
}

.form-container {
  width: 100%;
}

/* ======== プラン生成中フェーズ ======== */
.planning-phase {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2rem;
}

.planning-content {
  text-align: center;
  max-width: 500px;
}

.planning-animation {
  margin-bottom: 2rem;
}

.planning-avatar-area {
  position: relative;
  width: 80px;
  height: 80px;
  margin: 0 auto;
}

.planning-avatar {
  position: relative;
  width: 80px;
  height: 80px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.12) 0%, rgba(118, 75, 162, 0.12) 100%);
  border: 1px solid rgba(102, 126, 234, 0.15);
  border-radius: 50%;
  overflow: hidden;
  z-index: 2;
  box-shadow: 0 0 16px rgba(102, 126, 234, 0.25);
}

.planning-avatar .avatar-logo {
  width: 48px;
  height: 48px;
  object-fit: contain;
}

.planning-avatar .avatar-logo-fallback {
  width: 36px;
  height: 36px;
  color: #667eea;
}

.planning-avatar .avatar-logo:not([style*="display: none"]) + .avatar-logo-fallback {
  display: none;
}

.planning-avatar-area .avatar-ring {
  position: absolute;
  inset: -4px;
  border-radius: 50%;
  border: 1.5px solid rgba(102, 126, 234, 0.3);
  z-index: 1;
}

.planning-avatar-area .ring-1 {
  animation: ring-pulse 2.4s ease-out infinite;
}

.planning-avatar-area .ring-2 {
  animation: ring-pulse 2.4s ease-out 0.8s infinite;
}

.planning-avatar-area .ring-3 {
  animation: ring-pulse 2.4s ease-out 1.6s infinite;
}

@keyframes ring-pulse {
  0% {
    transform: scale(1);
    opacity: 0.6;
  }
  100% {
    transform: scale(2);
    opacity: 0;
  }
}

.planning-content h2 {
  font-family: 'Montserrat', sans-serif;
  font-size: 1.5rem;
  font-weight: 600;
  color: #1a202c;
  margin: 0 0 0.5rem;
}

.planning-destination {
  font-family: 'Montserrat', sans-serif;
  font-size: 0.95rem;
  color: #718096;
  margin: 0 0 2rem;
}

.progress-section {
  margin-bottom: 2rem;
}

.progress-bar {
  height: 8px;
  background: rgba(0, 0, 0, 0.06);
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 0.75rem;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #667eea, #764ba2);
  border-radius: 4px;
  transition: width 0.3s ease-out;
}

.progress-info {
  display: flex;
  justify-content: space-between;
}

.progress-phase {
  font-family: 'Montserrat', sans-serif;
  font-size: 0.85rem;
  color: #718096;
}

.progress-percent {
  font-family: 'Montserrat', sans-serif;
  font-size: 1rem;
  font-weight: 600;
  color: #667eea;
}

.progress-steps {
  display: flex;
  justify-content: center;
  flex-wrap: wrap;
  gap: 1rem;
}

.step {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-family: 'Montserrat', sans-serif;
  font-size: 0.75rem;
  color: #a0aec0;
}

.step.active {
  color: #667eea;
}

.step.completed {
  color: #764ba2;
}

.step-dot {
  width: 6px;
  height: 6px;
  background: currentColor;
  border-radius: 50%;
  opacity: 0.5;
}

.step.active .step-dot {
  opacity: 1;
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.3); }
}

/* ======== 結果フェーズ（左右分割） ======== */
.result-phase {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.result-layout {
  flex: 1;
  display: flex;
  gap: 1.5rem;
  padding: 1.5rem 2rem;
  min-height: 0;
  overflow: hidden;
}

.result-left {
  flex: 1;
  min-width: 0;
  overflow-y: auto;
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(102, 126, 234, 0.1);
  border-radius: 16px;
  padding: 1.25rem;
}

.result-right {
  width: 45%;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  min-height: 0;
}

/* プランヘッダーセクション */
.plan-header-section {
  margin-bottom: 1.25rem;
  padding-bottom: 1.25rem;
  border-bottom: 1px solid rgba(102, 126, 234, 0.08);
}

.plan-title {
  font-family: 'Montserrat', sans-serif;
  font-size: 1.35rem;
  font-weight: 700;
  color: #1a202c;
  margin: 0 0 0.5rem;
}

.plan-summary {
  font-family: 'Montserrat', sans-serif;
  font-size: 0.9rem;
  color: #4a5568;
  line-height: 1.6;
  margin: 0 0 0.75rem;
}

.plan-highlights {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  margin-bottom: 0.75rem;
}

.highlight-chip {
  font-family: 'Montserrat', sans-serif;
  font-size: 0.75rem;
  padding: 0.3rem 0.75rem;
  background: rgba(102, 126, 234, 0.08);
  color: #667eea;
  border-radius: 12px;
  border: 1px solid rgba(102, 126, 234, 0.1);
}

.plan-budget {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.4rem 0.75rem;
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.06), rgba(118, 75, 162, 0.06));
  border: 1px solid rgba(102, 126, 234, 0.1);
  border-radius: 8px;
}

.budget-label {
  font-family: 'Montserrat', sans-serif;
  font-size: 0.8rem;
  color: #667eea;
}

.budget-value {
  font-family: 'Montserrat', sans-serif;
  font-size: 0.9rem;
  font-weight: 600;
  color: #4a5568;
}

.rationale-section {
  margin-top: 1.25rem;
  padding: 1rem;
  background: rgba(102, 126, 234, 0.04);
  border-radius: 10px;
  border: 1px solid rgba(102, 126, 234, 0.06);
}

.rationale-section h4 {
  margin: 0 0 0.5rem;
  font-family: 'Montserrat', sans-serif;
  font-size: 0.85rem;
  color: #2d3748;
}

.rationale-section p {
  margin: 0;
  font-size: 0.85rem;
  color: #4a5568;
  line-height: 1.5;
}

/* 右パネル：地図 */
.map-container {
  flex: 1;
  min-height: 0;
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(102, 126, 234, 0.1);
  border-radius: 16px;
  overflow: hidden;
  position: relative;
}

.map-content {
  width: 100%;
  height: 100%;
}

.map-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  min-height: 200px;
}

.map-skeleton {
  width: 80%;
  height: 60%;
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

.map-loading-text {
  font-family: 'Montserrat', sans-serif;
  font-size: 0.8rem;
  color: #a0aec0;
  margin-top: 0.75rem;
}

.map-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  min-height: 200px;
  color: #a0aec0;
  gap: 0.5rem;
}

.map-error svg {
  width: 32px;
  height: 32px;
}

.map-error span {
  font-family: 'Montserrat', sans-serif;
  font-size: 0.8rem;
}

/* 日程タブ */
.day-tab-bar {
  display: flex;
  gap: 0.4rem;
  flex-shrink: 0;
  overflow-x: auto;
  padding: 0.25rem;
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(102, 126, 234, 0.1);
  border-radius: 12px;
}

.day-tab {
  flex-shrink: 0;
  padding: 0.45rem 0.85rem;
  background: transparent;
  border: none;
  border-radius: 8px;
  font-family: 'Montserrat', sans-serif;
  font-size: 0.78rem;
  font-weight: 500;
  color: #718096;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
}

.day-tab:hover {
  background: rgba(102, 126, 234, 0.06);
  color: #667eea;
}

.day-tab.active {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  box-shadow: 0 2px 8px rgba(102, 126, 234, 0.25);
}

/* ルート情報 */
.route-info {
  display: flex;
  gap: 1rem;
  padding: 0.6rem 1rem;
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(102, 126, 234, 0.1);
  border-radius: 10px;
  flex-shrink: 0;
}

.route-stat {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  font-family: 'Montserrat', sans-serif;
  font-size: 0.8rem;
  color: #667eea;
  font-weight: 500;
}

.route-stat svg {
  width: 14px;
  height: 14px;
  stroke: #667eea;
}

/* エラー表示 */
.result-error {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2rem;
}

.error-card {
  text-align: center;
  max-width: 420px;
  padding: 2rem;
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(239, 68, 68, 0.15);
  border-radius: 16px;
}

.error-icon {
  width: 40px;
  height: 40px;
  color: #ef4444;
  margin-bottom: 1rem;
}

.error-card p {
  font-family: 'Montserrat', sans-serif;
  font-size: 0.9rem;
  color: #4a5568;
  line-height: 1.6;
  margin: 0 0 1.5rem;
  white-space: pre-line;
}

.retry-btn {
  padding: 0.6rem 1.5rem;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
  border-radius: 10px;
  color: white;
  font-family: 'Montserrat', sans-serif;
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.25s ease;
}

.retry-btn:hover {
  box-shadow: 0 4px 14px rgba(102, 126, 234, 0.35);
  transform: translateY(-1px);
}

/* ======== 履歴パネル ======== */
.history-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.3);
  z-index: 100;
  display: flex;
  justify-content: flex-end;
}

.history-panel {
  width: 380px;
  max-width: 90vw;
  height: 100%;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-left: 1px solid rgba(102, 126, 234, 0.1);
  display: flex;
  flex-direction: column;
  box-shadow: -8px 0 32px rgba(0, 0, 0, 0.1);
}

.history-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  flex-shrink: 0;
}

.history-header h3 {
  font-family: 'Montserrat', sans-serif;
  font-size: 1rem;
  font-weight: 700;
  color: #1a202c;
  margin: 0;
}

.history-close-btn {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  border-radius: 8px;
  color: #718096;
  cursor: pointer;
  transition: all 0.2s ease;
}

.history-close-btn:hover {
  background: rgba(0, 0, 0, 0.05);
  color: #4a5568;
}

.history-close-btn svg {
  width: 18px;
  height: 18px;
}

.history-list {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
}

.history-loading {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.history-skeleton {
  height: 72px;
  background: linear-gradient(110deg, #e2e8f0 8%, #edf2f7 18%, #e2e8f0 33%);
  background-size: 200% 100%;
  border-radius: 10px;
  animation: skeleton-shine 1.5s linear infinite;
}

.history-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem 1rem;
  color: #a0aec0;
  text-align: center;
}

.history-empty svg {
  width: 40px;
  height: 40px;
  margin-bottom: 0.75rem;
}

.history-empty p {
  font-family: 'Montserrat', sans-serif;
  font-size: 0.85rem;
  margin: 0;
}

.history-item {
  padding: 0.85rem 1rem;
  background: rgba(255, 255, 255, 0.8);
  border: 1px solid rgba(102, 126, 234, 0.08);
  border-radius: 10px;
  margin-bottom: 0.5rem;
  transition: all 0.2s ease;
}

.history-item.clickable {
  cursor: pointer;
}

.history-item.clickable:hover {
  border-color: rgba(102, 126, 234, 0.3);
  box-shadow: 0 2px 12px rgba(102, 126, 234, 0.1);
  background: rgba(255, 255, 255, 0.95);
}

.history-item.loading {
  opacity: 0.7;
  pointer-events: none;
}

.history-item:hover {
  border-color: rgba(102, 126, 234, 0.2);
  box-shadow: 0 2px 8px rgba(102, 126, 234, 0.06);
}

.history-item-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.history-item-action {
  font-family: 'Montserrat', sans-serif;
  font-size: 0.72rem;
  font-weight: 600;
  color: #667eea;
}

.history-item-loading {
  font-family: 'Montserrat', sans-serif;
  font-size: 0.72rem;
  color: #a0aec0;
  animation: pulse-text 1.5s ease-in-out infinite;
}

@keyframes pulse-text {
  0%, 100% { opacity: 0.5; }
  50% { opacity: 1; }
}

.history-item-destination {
  font-family: 'Montserrat', sans-serif;
  font-size: 0.9rem;
  font-weight: 600;
  color: #2d3748;
  margin-bottom: 0.25rem;
}

.history-item-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  font-family: 'Montserrat', sans-serif;
  font-size: 0.75rem;
  color: #718096;
  margin-bottom: 0.35rem;
}

.history-status {
  font-family: 'Montserrat', sans-serif;
  font-size: 0.7rem;
  font-weight: 500;
  padding: 0.15rem 0.5rem;
  border-radius: 4px;
}

.history-status.completed {
  background: rgba(72, 187, 120, 0.1);
  color: #38a169;
}

.history-status.pending {
  background: rgba(237, 137, 54, 0.1);
  color: #dd6b20;
}

/* 履歴パネルアニメーション */
.history-enter-active,
.history-leave-active {
  transition: all 0.3s ease;
}

.history-enter-active .history-panel,
.history-leave-active .history-panel {
  transition: transform 0.3s ease;
}

.history-enter-from {
  opacity: 0;
}

.history-enter-from .history-panel {
  transform: translateX(100%);
}

.history-leave-to {
  opacity: 0;
}

.history-leave-to .history-panel {
  transform: translateX(100%);
}

/* ======== 確認フェーズ ======== */
.confirm-phase {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 2rem 3rem;
  overflow-y: auto;
  min-height: 0;
}

.confirm-layout {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;
  flex: 1;
}

.confirm-card {
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(102, 126, 234, 0.1);
  border-radius: 16px;
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
}

.confirm-card-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-family: 'Montserrat', sans-serif;
  font-size: 1rem;
  font-weight: 700;
  color: #1a202c;
  margin: 0 0 1.25rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid rgba(102, 126, 234, 0.08);
}

.confirm-card-title svg {
  width: 20px;
  height: 20px;
  color: #667eea;
  flex-shrink: 0;
}

.confirm-summary {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.confirm-summary-item {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding: 0.6rem 0.75rem;
  background: rgba(102, 126, 234, 0.03);
  border-radius: 8px;
}

.confirm-summary-label {
  font-family: 'Montserrat', sans-serif;
  font-size: 0.8rem;
  font-weight: 500;
  color: #718096;
  flex-shrink: 0;
  margin-right: 1rem;
}

.confirm-summary-value {
  font-family: 'Montserrat', sans-serif;
  font-size: 0.88rem;
  font-weight: 600;
  color: #2d3748;
  text-align: right;
}

.step-list {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.step-list-item {
  display: flex;
  align-items: center;
  gap: 0.85rem;
  padding: 0.65rem 0.75rem;
  background: rgba(102, 126, 234, 0.03);
  border-radius: 10px;
  transition: all 0.2s ease;
}

.step-list-item:hover {
  background: rgba(102, 126, 234, 0.07);
}

.step-number {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.12) 0%, rgba(118, 75, 162, 0.12) 100%);
  border-radius: 50%;
  font-family: 'Montserrat', sans-serif;
  font-size: 0.75rem;
  font-weight: 700;
  color: #667eea;
  flex-shrink: 0;
}

.step-detail {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.step-title {
  font-family: 'Montserrat', sans-serif;
  font-size: 0.85rem;
  font-weight: 600;
  color: #2d3748;
}

.step-desc {
  font-family: 'Montserrat', sans-serif;
  font-size: 0.75rem;
  color: #718096;
}

.confirm-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 1.5rem;
  margin-top: 1rem;
  border-top: 1px solid rgba(0, 0, 0, 0.06);
  flex-shrink: 0;
}

.confirm-back-btn {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.65rem 1.25rem;
  background: transparent;
  border: 1.5px solid rgba(0, 0, 0, 0.1);
  border-radius: 10px;
  font-family: 'Montserrat', sans-serif;
  font-size: 0.85rem;
  font-weight: 500;
  color: #718096;
  cursor: pointer;
  transition: all 0.25s ease;
}

.confirm-back-btn:hover {
  color: #4a5568;
  border-color: rgba(0, 0, 0, 0.2);
  background: rgba(0, 0, 0, 0.02);
}

.confirm-back-btn svg {
  width: 16px;
  height: 16px;
  transition: transform 0.2s ease;
}

.confirm-back-btn:hover svg {
  transform: translateX(-2px);
}

.confirm-start-btn {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.7rem 1.75rem;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
  border-radius: 10px;
  font-family: 'Montserrat', sans-serif;
  font-size: 0.9rem;
  font-weight: 600;
  color: white;
  cursor: pointer;
  transition: all 0.25s ease;
  box-shadow: 0 2px 10px rgba(102, 126, 234, 0.25);
}

.confirm-start-btn:hover {
  box-shadow: 0 4px 18px rgba(102, 126, 234, 0.4);
  transform: translateY(-1px);
}

.confirm-start-btn svg {
  width: 16px;
  height: 16px;
  transition: transform 0.2s ease;
}

.confirm-start-btn:hover svg {
  transform: translateX(2px);
}

/* ======== レスポンシブ ======== */
@media (max-width: 600px) {
  .chat-header {
    padding: 0.75rem 1rem;
  }

  .header-title h3 {
    font-size: 0.9rem;
  }

  .header-subtitle {
    display: none;
  }

  .header-divider {
    display: none;
  }

  .header-back-btn span {
    display: none;
  }

  .header-back-btn {
    padding: 0.4rem;
  }

  .phase-indicator span:not(.phase-dot) {
    display: none;
  }

  .header-new-plan-btn span,
  .header-history-btn span {
    display: none;
  }

  .header-new-plan-btn,
  .header-history-btn {
    padding: 0.45rem;
  }

  .confirm-phase {
    padding: 1rem;
  }

  .confirm-layout {
    grid-template-columns: 1fr;
  }

  .result-layout {
    flex-direction: column;
    padding: 1rem;
    overflow-y: auto;
  }

  .result-left {
    overflow-y: visible;
  }

  .result-right {
    width: 100%;
    min-height: 350px;
  }
}
</style>
