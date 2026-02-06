<script setup lang="ts">
import { ref, nextTick, computed, onUnmounted } from 'vue'
import { api } from '../lib/api'
import { getErrorMessage } from '../lib/errors'
import type { User, TravelPlan, CollectedTravelInfo, BasicTravelInfo, RequiredInfoStatus } from '../lib/api'
import TravelPlanCard from './TravelPlanCard.vue'
import TravelPlanForm from './TravelPlanForm.vue'

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

type Phase = 'form' | 'gathering' | 'ready' | 'planning' | 'result'
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

const formatMessage = (content: string): string => {
  return content.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>').replace(/\n/g, '<br>')
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
  await startPlanGenerationFromForm()
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

const startPlanGenerationFromForm = async () => {
  if (!props.user || !basicInfo.value) return
  phase.value = 'planning'
  isLoading.value = true
  messages.value = []
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
      (response) => { sessionId.value = response.session_id; stopProgressAnimation(); if (response.plan) { currentPlan.value = response.plan; messages.value = [{ role: 'assistant', content: response.assistant_message, plan: response.plan }]; emit('plan-created', response.plan) } else { messages.value = [{ role: 'assistant', content: response.assistant_message }] } phase.value = 'result'; scrollToBottom(); isLoading.value = false },
      (error: string) => { console.error('Plan generation failed:', error); stopProgressAnimation(); messages.value = [{ role: 'assistant', content: `プランの生成に失敗しました。\n${error}` }]; phase.value = 'result'; scrollToBottom(); isLoading.value = false }
    )
  } catch (error) {
    console.error('Failed to generate plan:', error); stopProgressAnimation()
    messages.value = [{ role: 'assistant', content: `プランの生成に失敗しました。\n${getErrorMessage(error)}` }]
    phase.value = 'result'; await scrollToBottom(); isLoading.value = false
  }
}

const startPlanGeneration = async () => {
  if (!props.user || !sessionId.value) return
  phase.value = 'planning'; isLoading.value = true; startProgressAnimation()
  try {
    const response = await api.startPlanGeneration(props.user.id, sessionId.value, collectedInfo.value)
    if (response.plan) { currentPlan.value = response.plan; messages.value = [{ role: 'assistant', content: response.assistant_message, plan: response.plan }]; emit('plan-created', response.plan) } else { messages.value = [{ role: 'assistant', content: response.assistant_message }] }
    stopProgressAnimation(); phase.value = 'result'; await scrollToBottom()
  } catch (error) {
    console.error('Failed to generate plan:', error); stopProgressAnimation()
    messages.value = [{ role: 'assistant', content: `プランの生成に失敗しました。\n${getErrorMessage(error)}` }]
    phase.value = 'result'; await scrollToBottom()
  } finally { isLoading.value = false }
}

const sendResultMessage = async () => {
  if (!props.user || isLoading.value || !inputMessage.value.trim()) return
  const userMessage = inputMessage.value.trim(); inputMessage.value = ''
  messages.value.push({ role: 'user', content: userMessage }); await scrollToBottom()
  try {
    isLoading.value = true
    const response = await api.sendTravelMessage(props.user.id, userMessage, sessionId.value || undefined)
    sessionId.value = response.session_id
    const newMessage: Message = { role: 'assistant', content: response.assistant_message }
    if (response.plan) { newMessage.plan = response.plan; currentPlan.value = response.plan; emit('plan-created', response.plan) }
    messages.value.push(newMessage); await scrollToBottom()
  } catch (error) {
    console.error('Failed to send message:', error)
    messages.value.push({ role: 'assistant', content: `エラー: ${getErrorMessage(error)}` }); await scrollToBottom()
  } finally { isLoading.value = false }
}

const handleResultKeydown = (event: KeyboardEvent) => {
  if (event.key !== 'Enter') return; if (event.shiftKey) return; event.preventDefault()
  if ((event.ctrlKey || event.metaKey) && !isComposing.value && !event.isComposing && event.keyCode !== 229) { sendResultMessage() }
}

const startNewPlan = () => {
  phase.value = 'form'; sessionId.value = null; messages.value = []; currentPlan.value = null; basicInfo.value = null
  collectedInfo.value = { area: '', start_date: '', end_date: '', num_people: 1 }; missingInfo.value = []
  requiredInfoStatus.value = { has_activities: false, has_food: false, has_accommodation: false, has_transportation: false, category_count: 0, is_complete: false }
  allRequiredSatisfied.value = false; missingRequiredInfo.value = ['やりたいこと', '食の好み', '宿泊の希望', '移動手段']
}

const handleFeedback = async (feedback: string) => {
  if (!props.user || !currentPlan.value) return
  try { await api.sendFeedback(props.user.id, currentPlan.value.id, feedback); messages.value.push({ role: 'assistant', content: 'フィードバックありがとうございます！あなたの好みを学習しました。' }); await scrollToBottom() } catch (error) { console.error('Failed to send feedback:', error) }
}

const handlePOIFeedback = async (_poiName: string, _feedbackType: 'good' | 'bad', _learned: { category: string; tag: string; is_new: boolean } | null) => {}

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
    <!-- サイドバー -->
    <aside class="sidebar">
      <div class="sidebar-header">
        <button class="back-btn" @click="$emit('back-to-select')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="15 18 9 12 15 6"/>
          </svg>
          戻る
        </button>
      </div>

      <div class="sidebar-content">
        <div class="mode-info">
          <div class="mode-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <circle cx="12" cy="12" r="10"/>
              <polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"/>
            </svg>
          </div>
          <h2>旅行企画</h2>
          <p class="mode-subtitle">Travel Planning</p>
        </div>

        <!-- フェーズインジケーター -->
        <div class="phase-indicator">
          <div class="phase-item" :class="{ active: phase === 'form', completed: ['gathering', 'ready', 'planning', 'result'].includes(phase) }">
            <div class="phase-dot">1</div>
            <span>入力</span>
          </div>
          <div class="phase-line" :class="{ active: ['gathering', 'ready', 'planning', 'result'].includes(phase) }"></div>
          <div class="phase-item" :class="{ active: phase === 'planning', completed: phase === 'result' }">
            <div class="phase-dot">2</div>
            <span>生成</span>
          </div>
          <div class="phase-line" :class="{ active: phase === 'result' }"></div>
          <div class="phase-item" :class="{ active: phase === 'result' }">
            <div class="phase-dot">3</div>
            <span>結果</span>
          </div>
        </div>

        <!-- 収集した情報 -->
        <div v-if="formatCollectedInfo.length > 0" class="collected-summary">
          <h3>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
              <line x1="16" y1="13" x2="8" y2="13"/>
              <line x1="16" y1="17" x2="8" y2="17"/>
            </svg>
            旅行情報
          </h3>
          <div class="info-list">
            <div v-for="item in formatCollectedInfo" :key="item.label" class="info-row">
              <span class="info-label">{{ item.label }}</span>
              <span class="info-value">{{ item.value }}</span>
            </div>
          </div>
        </div>
      </div>

      <div class="sidebar-footer" v-if="phase === 'result'">
        <button class="action-btn secondary" @click="startNewPlan">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="12" y1="5" x2="12" y2="19"/>
            <line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
          新しいプランを作成
        </button>
      </div>
    </aside>

    <!-- メインエリア -->
    <main class="main-content">
      <!-- Phase 1: フォーム -->
      <div v-if="phase === 'form'" class="form-phase">
        <div class="phase-header">
          <h3>旅行情報を入力</h3>
          <p>行き先と日程を教えてください</p>
        </div>
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

      <!-- Phase 4: プラン生成中 -->
      <div v-else-if="phase === 'planning'" class="planning-phase">
        <div class="planning-content">
          <div class="planning-animation">
            <div class="plane-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                <path d="M21 16v-2l-8-5V3.5A1.5 1.5 0 0011.5 2h-1A1.5 1.5 0 009 3.5V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L12 19v-5.5l9 2.5z"/>
              </svg>
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

      <!-- Phase 5: 結果表示 -->
      <div v-else-if="phase === 'result'" class="result-phase">
        <div class="result-header">
          <div class="result-title">
            <h3>{{ collectedInfo.area }}の旅行プラン</h3>
            <p>チャットでプランを調整できます</p>
          </div>
        </div>

        <div class="messages-container" ref="messagesContainer">
          <div class="messages-wrapper">
            <div v-for="(message, index) in messages" :key="index" :class="['message', message.role]">
              <div class="message-avatar">
                <svg v-if="message.role === 'assistant'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                  <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
                </svg>
                <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                  <circle cx="12" cy="7" r="4"/>
                </svg>
              </div>
              <div class="message-content">
                <div class="message-meta">
                  <span class="message-sender">{{ message.role === 'assistant' ? 'Travel AI' : 'あなた' }}</span>
                </div>
                <div class="message-text" v-html="formatMessage(message.content)"></div>
                <TravelPlanCard
                  v-if="message.plan"
                  :plan="message.plan"
                  :user-id="user?.id"
                  @feedback="handleFeedback"
                  @poi-feedback="handlePOIFeedback"
                />
              </div>
            </div>

            <div v-if="isLoading" class="message assistant">
              <div class="message-avatar">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                  <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
                </svg>
              </div>
              <div class="message-content">
                <div class="typing-indicator">
                  <span></span><span></span><span></span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="input-area">
          <div class="input-container">
            <textarea
              v-model="inputMessage"
              @keydown="handleResultKeydown"
              @input="autoResizeTextarea"
              @compositionstart="handleCompositionStart"
              @compositionend="handleCompositionEnd"
              placeholder="プランへのフィードバックを入力..."
              :disabled="isLoading || !user"
              rows="1"
            ></textarea>
            <div class="input-actions">
              <span class="input-hint">⌘ + Enter</span>
              <button type="button" @click="sendResultMessage" :disabled="!inputMessage.trim() || isLoading || !user" class="send-btn">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <line x1="22" y1="2" x2="11" y2="13"/>
                  <polygon points="22 2 15 22 11 13 2 9 22 2"/>
                </svg>
              </button>
            </div>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;600&family=Montserrat:wght@300;400;500;600&display=swap');

.travel-planning-view {
  display: flex;
  height: 100%;
  min-height: 600px;
}

/* サイドバー */
.sidebar {
  width: 300px;
  display: flex;
  flex-direction: column;
  background: rgba(56, 178, 172, 0.03);
  border-right: 1px solid rgba(56, 178, 172, 0.1);
  flex-shrink: 0;
}

.sidebar-header {
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid rgba(56, 178, 172, 0.08);
}

.back-btn {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  background: transparent;
  border: 1px solid rgba(0, 0, 0, 0.1);
  border-radius: 8px;
  font-family: 'Montserrat', sans-serif;
  font-size: 0.85rem;
  font-weight: 500;
  color: #4a5568;
  cursor: pointer;
  transition: all 0.2s ease;
}

.back-btn:hover {
  background: rgba(0, 0, 0, 0.03);
}

.back-btn svg {
  width: 18px;
  height: 18px;
}

.sidebar-content {
  flex: 1;
  padding: 1.5rem;
  overflow-y: auto;
}

.mode-info {
  text-align: center;
  padding-bottom: 1.5rem;
  border-bottom: 1px solid rgba(56, 178, 172, 0.1);
  margin-bottom: 1.5rem;
}

.mode-icon {
  width: 60px;
  height: 60px;
  margin: 0 auto 1rem;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, rgba(56, 178, 172, 0.15) 0%, rgba(49, 151, 149, 0.15) 100%);
  border-radius: 16px;
  color: #38b2ac;
}

.mode-icon svg {
  width: 30px;
  height: 30px;
}

.mode-info h2 {
  font-family: 'Montserrat', sans-serif;
  font-size: 1.3rem;
  font-weight: 700;
  color: #1a202c;
  margin: 0 0 0.25rem;
}

.mode-subtitle {
  font-family: 'Montserrat', sans-serif;
  font-size: 0.7rem;
  font-weight: 500;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: #a0aec0;
  margin: 0;
}

/* フェーズインジケーター */
.phase-indicator {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0;
  margin-bottom: 1.5rem;
  padding: 1rem;
  background: rgba(255, 255, 255, 0.5);
  border-radius: 12px;
}

.phase-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.35rem;
}

.phase-dot {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.06);
  border-radius: 50%;
  font-family: 'Montserrat', sans-serif;
  font-size: 0.75rem;
  font-weight: 600;
  color: #a0aec0;
  transition: all 0.3s ease;
}

.phase-item.active .phase-dot {
  background: #38b2ac;
  color: white;
}

.phase-item.completed .phase-dot {
  background: rgba(56, 178, 172, 0.2);
  color: #38b2ac;
}

.phase-item span:not(.phase-dot) {
  font-family: 'Montserrat', sans-serif;
  font-size: 0.7rem;
  font-weight: 500;
  color: #718096;
}

.phase-line {
  width: 24px;
  height: 2px;
  background: rgba(0, 0, 0, 0.08);
  margin: 0 4px;
  margin-bottom: 1.25rem;
  transition: all 0.3s ease;
}

.phase-line.active {
  background: rgba(56, 178, 172, 0.4);
}

/* 収集情報サマリー */
.collected-summary h3 {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-family: 'Montserrat', sans-serif;
  font-size: 0.8rem;
  font-weight: 600;
  color: #4a5568;
  margin: 0 0 0.75rem;
}

.collected-summary h3 svg {
  width: 16px;
  height: 16px;
  color: #38b2ac;
}

.info-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.info-row {
  display: flex;
  justify-content: space-between;
  padding: 0.5rem 0;
  border-bottom: 1px solid rgba(0, 0, 0, 0.04);
}

.info-label {
  font-family: 'Montserrat', sans-serif;
  font-size: 0.75rem;
  color: #718096;
}

.info-value {
  font-family: 'Montserrat', sans-serif;
  font-size: 0.75rem;
  font-weight: 500;
  color: #2d3748;
}

.sidebar-footer {
  padding: 1.25rem 1.5rem;
  border-top: 1px solid rgba(56, 178, 172, 0.08);
}

.action-btn {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  border-radius: 10px;
  font-family: 'Montserrat', sans-serif;
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
}

.action-btn.secondary {
  background: rgba(56, 178, 172, 0.1);
  border: 1px solid rgba(56, 178, 172, 0.2);
  color: #319795;
}

.action-btn.secondary:hover {
  background: rgba(56, 178, 172, 0.2);
}

.action-btn svg {
  width: 18px;
  height: 18px;
}

/* メインコンテンツ */
.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

/* フォームフェーズ */
.form-phase {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 2rem;
  overflow-y: auto;
}

.phase-header {
  margin-bottom: 1.5rem;
}

.phase-header h3 {
  font-family: 'Montserrat', sans-serif;
  font-size: 1.25rem;
  font-weight: 600;
  color: #1a202c;
  margin: 0 0 0.25rem;
}

.phase-header p {
  font-family: 'Montserrat', sans-serif;
  font-size: 0.9rem;
  color: #718096;
  margin: 0;
}

.form-container {
  flex: 1;
}

/* プラン生成中フェーズ */
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

.plane-icon {
  width: 80px;
  height: 80px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, rgba(56, 178, 172, 0.15) 0%, rgba(49, 151, 149, 0.15) 100%);
  border-radius: 20px;
  color: #38b2ac;
  animation: float 3s ease-in-out infinite;
}

.plane-icon svg {
  width: 40px;
  height: 40px;
}

@keyframes float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-10px); }
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
  background: linear-gradient(90deg, #38b2ac, #319795);
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
  color: #38b2ac;
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
  color: #38b2ac;
}

.step.completed {
  color: #319795;
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

/* 結果フェーズ */
.result-phase {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.result-header {
  padding: 1.25rem 2rem;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  background: rgba(255, 255, 255, 0.5);
}

.result-title h3 {
  font-family: 'Montserrat', sans-serif;
  font-size: 1.1rem;
  font-weight: 600;
  color: #1a202c;
  margin: 0 0 0.2rem;
}

.result-title p {
  font-family: 'Montserrat', sans-serif;
  font-size: 0.8rem;
  color: #718096;
  margin: 0;
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem 2rem;
}

.messages-wrapper {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.message {
  display: flex;
  gap: 1rem;
  max-width: 90%;
}

.message.user {
  align-self: flex-end;
  flex-direction: row-reverse;
}

.message-avatar {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  flex-shrink: 0;
}

.message.assistant .message-avatar {
  background: linear-gradient(135deg, rgba(56, 178, 172, 0.15) 0%, rgba(49, 151, 149, 0.15) 100%);
  color: #38b2ac;
}

.message.user .message-avatar {
  background: rgba(0, 0, 0, 0.06);
  color: #4a5568;
}

.message-avatar svg {
  width: 20px;
  height: 20px;
}

.message-content {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  min-width: 0;
}

.message-meta {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.message-sender {
  font-family: 'Montserrat', sans-serif;
  font-size: 0.75rem;
  font-weight: 600;
  color: #4a5568;
}

.message-text {
  padding: 1rem 1.25rem;
  border-radius: 16px;
  font-family: 'Montserrat', sans-serif;
  font-size: 0.9rem;
  line-height: 1.6;
}

.message.assistant .message-text {
  background: rgba(255, 255, 255, 0.8);
  color: #2d3748;
  border: 1px solid rgba(0, 0, 0, 0.06);
  border-top-left-radius: 4px;
}

.message.user .message-text {
  background: linear-gradient(135deg, #38b2ac 0%, #319795 100%);
  color: white;
  border-top-right-radius: 4px;
}

.typing-indicator {
  display: flex;
  gap: 6px;
  padding: 0.5rem 0;
}

.typing-indicator span {
  width: 8px;
  height: 8px;
  background: #a0aec0;
  border-radius: 50%;
  animation: bounce 1.4s infinite ease-in-out both;
}

.typing-indicator span:nth-child(1) { animation-delay: -0.32s; }
.typing-indicator span:nth-child(2) { animation-delay: -0.16s; }

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}

/* 入力エリア */
.input-area {
  padding: 1.25rem 2rem;
}

.input-container {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.75rem 1rem;
  background: rgba(255, 255, 255, 0.8);
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 16px;
  transition: all 0.3s ease;
}

.input-container:focus-within {
  border-color: rgba(56, 178, 172, 0.4);
  box-shadow: 0 0 0 4px rgba(56, 178, 172, 0.1);
}

.input-container textarea {
  flex: 1;
  padding: 0.5rem;
  background: transparent;
  border: none;
  font-family: 'Montserrat', sans-serif;
  font-size: 0.95rem;
  line-height: 1.5;
  color: #2d3748;
  resize: none;
  min-height: 24px;
  max-height: 150px;
  outline: none;
  overflow-y: auto;
}

.input-container textarea::placeholder {
  color: #a0aec0;
}

.input-actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.input-hint {
  font-family: 'Montserrat', sans-serif;
  font-size: 0.7rem;
  color: #a0aec0;
  white-space: nowrap;
}

.send-btn {
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #38b2ac 0%, #319795 100%);
  border: none;
  border-radius: 12px;
  color: white;
  cursor: pointer;
  transition: all 0.3s ease;
}

.send-btn:hover:not(:disabled) {
  transform: scale(1.05);
  box-shadow: 0 4px 12px rgba(56, 178, 172, 0.3);
}

.send-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.send-btn svg {
  width: 20px;
  height: 20px;
}

/* レスポンシブ */
@media (max-width: 900px) {
  .sidebar {
    display: none;
  }
}
</style>
