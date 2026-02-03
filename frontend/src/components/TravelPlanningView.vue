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
}

interface Message {
  role: 'user' | 'assistant'
  content: string
  plan?: TravelPlan
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

// フェーズ: form → gathering → ready → planning → result
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

// 進捗メーター用
const targetProgress = ref(0)  // サーバーから受け取った目標進捗
const displayProgress = ref(0)  // 画面表示用（アニメーション）
const currentPhase = ref('')  // 現在のフェーズ名
let progressInterval: number | null = null

// フェーズ名の日本語マッピング
const phaseLabels: Record<string, string> = {
  translate: '準備中',
  search: '検索中',
  normalize: '整理中',
  rerank: '分析中',
  plan: 'プラン作成中',
  explain: '仕上げ中',
  complete: '完了',
}

// 各フェーズの上限値（次のフェーズの手前まで）
const phaseMaxProgress: Record<string, number> = {
  translate: 15,   // 0 → 15
  search: 32,      // 16 → 32
  normalize: 49,   // 33 → 49
  rerank: 65,      // 50 → 65
  plan: 82,        // 66 → 82
  explain: 99,     // 83 → 99
  complete: 100,   // 100
}

const getPhaseLabel = (phase: string): string => {
  return phaseLabels[phase] || phase
}

const startProgressAnimation = () => {
  targetProgress.value = 0
  displayProgress.value = 0
  currentPhase.value = ''

  // ゆっくり目標に近づくアニメーション
  progressInterval = window.setInterval(() => {
    const target = targetProgress.value
    const current = displayProgress.value
    const phase = currentPhase.value
    const maxForPhase = phaseMaxProgress[phase] ?? 99

    if (current < target) {
      // 目標より低い場合：追いつく（速度は差分に応じて調整）
      const diff = target - current
      const speed = diff > 20 ? 3 : diff > 10 ? 1.5 : 0.5
      displayProgress.value = Math.min(current + speed, target)
    } else if (current < maxForPhase) {
      // フェーズ内をゆっくり進む（フェーズの上限まで）
      displayProgress.value = current + 0.3
    }
    // maxForPhaseに達したら停滞（次のフェーズを待つ）
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

// 収集した情報
const basicInfo = ref<BasicTravelInfo | null>(null)
const collectedInfo = ref<CollectedTravelInfo>({
  area: '',
  start_date: '',
  end_date: '',
  num_people: 1,
})
const missingInfo = ref<string[]>([])

// 4カテゴリの収集状況
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

// IME変換状態を追跡
const handleCompositionStart = () => {
  isComposing.value = true
}

const handleCompositionEnd = () => {
  setTimeout(() => {
    isComposing.value = false
  }, 200)
}

// キーボードイベント処理
const handleKeydown = (event: KeyboardEvent) => {
  if (event.key !== 'Enter') return
  if (event.shiftKey) return
  event.preventDefault()
  if ((event.ctrlKey || event.metaKey) && !isComposing.value && !event.isComposing && event.keyCode !== 229) {
    sendGatheringMessage()
  }
}

const formatMessage = (content: string): string => {
  return content
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>')
}

const scrollToBottom = async () => {
  await nextTick()
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

// 旅行日数を計算
const tripDays = computed(() => {
  if (!collectedInfo.value.start_date || !collectedInfo.value.end_date) return null
  const start = new Date(collectedInfo.value.start_date)
  const end = new Date(collectedInfo.value.end_date)
  return Math.ceil((end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24)) + 1
})

// Phase 1: フォーム送信 → 直接プラン生成へ
const handleFormSubmit = async (data: BasicTravelInfo) => {
  if (!props.user) return

  basicInfo.value = data

  // フォームの情報をcollectedInfoに変換
  collectedInfo.value = {
    area: data.area,
    start_date: data.start_date,
    end_date: data.end_date,
    num_people: data.num_people,
    budget: data.budget,
    // 4カテゴリ（文字列をリストに変換）
    activity_preferences: data.activity_preferences ? [data.activity_preferences] : [],
    food_preferences: data.food_preferences ? [data.food_preferences] : [],
    accommodation_type: data.accommodation_type || undefined,
    transportation: data.transportation || undefined,
  }

  // 直接プラン生成へ
  await startPlanGenerationFromForm()
}

// Phase 2: 情報収集の対話
const sendGatheringMessage = async () => {
  if (!props.user || isLoading.value || !inputMessage.value.trim()) return

  const userMessage = inputMessage.value.trim()
  inputMessage.value = ''

  messages.value.push({
    role: 'user',
    content: userMessage,
  })
  await scrollToBottom()

  try {
    isLoading.value = true
    isStreaming.value = true

    // ストリーミング用の空メッセージを追加
    messages.value.push({
      role: 'assistant',
      content: '',
    })
    streamingMessageIndex.value = messages.value.length - 1
    await scrollToBottom()

    await api.sendGatheringMessageStream(
      props.user.id,
      userMessage,
      sessionId.value || '',
      // onChunk
      (content: string) => {
        if (streamingMessageIndex.value >= 0) {
          messages.value[streamingMessageIndex.value].content += content
          scrollToBottom()
        }
      },
      // onInfo
      (info: CollectedTravelInfo) => {
        collectedInfo.value = info
      },
      // onDone
      (response) => {
        sessionId.value = response.session_id
        collectedInfo.value = response.collected_info
        missingInfo.value = response.missing_info
        // 新しいフィールド
        requiredInfoStatus.value = response.required_info_status
        allRequiredSatisfied.value = response.all_required_satisfied
        missingRequiredInfo.value = response.missing_required_info
        isStreaming.value = false
        streamingMessageIndex.value = -1
      },
      // onError
      (error: string) => {
        console.error('Streaming error:', error)
        if (streamingMessageIndex.value >= 0) {
          messages.value[streamingMessageIndex.value].content = `エラー: ${error}`
        }
        isStreaming.value = false
        streamingMessageIndex.value = -1
      }
    )
  } catch (error) {
    console.error('Failed to send gathering message:', error)
    if (streamingMessageIndex.value >= 0) {
      messages.value[streamingMessageIndex.value].content = `エラー: ${getErrorMessage(error)}`
    }
    isStreaming.value = false
    streamingMessageIndex.value = -1
  } finally {
    isLoading.value = false
  }
}

// Phase 2 → Phase 3: 情報収集完了
const finishGathering = () => {
  phase.value = 'ready'
}

// Phase 3 → Phase 2: 追加情報入力に戻る
const backToGathering = () => {
  phase.value = 'gathering'
}

// フォームから直接プラン生成を開始
const startPlanGenerationFromForm = async () => {
  if (!props.user || !basicInfo.value) return

  phase.value = 'planning'
  isLoading.value = true
  messages.value = []
  startProgressAnimation()

  try {
    // フォームデータをTravelPlanFormDataに変換
    const formData = {
      user_id: props.user.id,
      destination: basicInfo.value.area,
      start_date: basicInfo.value.start_date,
      end_date: basicInfo.value.end_date,
      num_people: basicInfo.value.num_people,
      budget_total: basicInfo.value.budget,
      transportation: basicInfo.value.transportation || undefined,
      accommodation_type: basicInfo.value.accommodation_type || undefined,
      // free_textに4カテゴリの希望を含める
      free_text: [
        basicInfo.value.activity_preferences ? `やりたいこと: ${basicInfo.value.activity_preferences}` : '',
        basicInfo.value.food_preferences ? `食の好み: ${basicInfo.value.food_preferences}` : '',
      ].filter(Boolean).join('。'),
    }

    await api.submitTravelFormStream(
      formData,
      // onProgress
      (progressPhase: string, percent: number) => {
        updateProgress(progressPhase, percent)
      },
      // onDone
      (response) => {
        sessionId.value = response.session_id
        stopProgressAnimation()

        if (response.plan) {
          currentPlan.value = response.plan
          messages.value = [{
            role: 'assistant',
            content: response.assistant_message,
            plan: response.plan,
          }]
          emit('plan-created', response.plan)
        } else {
          messages.value = [{
            role: 'assistant',
            content: response.assistant_message,
          }]
        }

        phase.value = 'result'
        scrollToBottom()
        isLoading.value = false
      },
      // onError
      (error: string) => {
        console.error('Plan generation failed:', error)
        stopProgressAnimation()
        messages.value = [{
          role: 'assistant',
          content: `プランの生成に失敗しました。\n${error}`,
        }]
        phase.value = 'result'
        scrollToBottom()
        isLoading.value = false
      }
    )
  } catch (error) {
    console.error('Failed to generate plan:', error)
    stopProgressAnimation()
    messages.value = [{
      role: 'assistant',
      content: `プランの生成に失敗しました。\n${getErrorMessage(error)}`,
    }]
    phase.value = 'result'
    await scrollToBottom()
    isLoading.value = false
  }
}

// Phase 3 → Phase 4: プラン生成開始（gatheringフェーズから）
const startPlanGeneration = async () => {
  if (!props.user || !sessionId.value) return

  phase.value = 'planning'
  isLoading.value = true
  startProgressAnimation()

  try {
    const response = await api.startPlanGeneration(
      props.user.id,
      sessionId.value,
      collectedInfo.value
    )

    if (response.plan) {
      currentPlan.value = response.plan
      messages.value = [{
        role: 'assistant',
        content: response.assistant_message,
        plan: response.plan,
      }]
      emit('plan-created', response.plan)
    } else {
      messages.value = [{
        role: 'assistant',
        content: response.assistant_message,
      }]
    }

    stopProgressAnimation(true)
    phase.value = 'result'
    await scrollToBottom()
  } catch (error) {
    console.error('Failed to generate plan:', error)
    stopProgressAnimation(false)
    messages.value = [{
      role: 'assistant',
      content: `プランの生成に失敗しました。\n${getErrorMessage(error)}`,
    }]
    phase.value = 'result'
    await scrollToBottom()
  } finally {
    isLoading.value = false
  }
}

// Phase 5: 結果表示後のフィードバック送信
const sendResultMessage = async () => {
  if (!props.user || isLoading.value || !inputMessage.value.trim()) return

  const userMessage = inputMessage.value.trim()
  inputMessage.value = ''

  messages.value.push({
    role: 'user',
    content: userMessage,
  })
  await scrollToBottom()

  try {
    isLoading.value = true
    const response = await api.sendTravelMessage(
      props.user.id,
      userMessage,
      sessionId.value || undefined
    )

    sessionId.value = response.session_id

    const newMessage: Message = {
      role: 'assistant',
      content: response.assistant_message,
    }

    if (response.plan) {
      newMessage.plan = response.plan
      currentPlan.value = response.plan
      emit('plan-created', response.plan)
    }

    messages.value.push(newMessage)
    await scrollToBottom()
  } catch (error) {
    console.error('Failed to send message:', error)
    messages.value.push({
      role: 'assistant',
      content: `エラー: ${getErrorMessage(error)}`,
    })
    await scrollToBottom()
  } finally {
    isLoading.value = false
  }
}

// result フェーズでのキーボードイベント処理
const handleResultKeydown = (event: KeyboardEvent) => {
  if (event.key !== 'Enter') return
  if (event.shiftKey) return
  event.preventDefault()
  if ((event.ctrlKey || event.metaKey) && !isComposing.value && !event.isComposing && event.keyCode !== 229) {
    sendResultMessage()
  }
}

// 新しいプラン作成
const startNewPlan = () => {
  phase.value = 'form'
  sessionId.value = null
  messages.value = []
  currentPlan.value = null
  basicInfo.value = null
  collectedInfo.value = {
    area: '',
    start_date: '',
    end_date: '',
    num_people: 1,
  }
  missingInfo.value = []
  // 4カテゴリ状態のリセット
  requiredInfoStatus.value = {
    has_activities: false,
    has_food: false,
    has_accommodation: false,
    has_transportation: false,
    category_count: 0,
    is_complete: false,
  }
  allRequiredSatisfied.value = false
  missingRequiredInfo.value = ['やりたいこと', '食の好み', '宿泊の希望', '移動手段']
}

const handleFeedback = async (feedback: string) => {
  if (!props.user || !currentPlan.value) return

  try {
    await api.sendFeedback(props.user.id, currentPlan.value.id, feedback)
    messages.value.push({
      role: 'assistant',
      content: 'フィードバックありがとうございます！あなたの好みを学習しました。',
    })
    await scrollToBottom()
  } catch (error) {
    console.error('Failed to send feedback:', error)
  }
}

const handlePOIFeedback = async (
  _poiName: string,
  _feedbackType: 'good' | 'bad',
  _learned: { category: string; tag: string; is_new: boolean } | null
) => {
  // POI単位のフィードバック処理
}

// 収集情報の表示用フォーマット
const formatCollectedInfo = computed(() => {
  const info = collectedInfo.value
  const items: { label: string; value: string }[] = []

  if (info.area) items.push({ label: '観光エリア', value: info.area })
  if (info.start_date && info.end_date) {
    items.push({ label: '日程', value: `${info.start_date} 〜 ${info.end_date}（${tripDays.value}日間）` })
  }
  if (info.num_people) items.push({ label: '人数', value: `${info.num_people}人` })
  if (info.budget) items.push({ label: '予算', value: `${info.budget.toLocaleString()}円` })
  if (info.budget_per_person) items.push({ label: '1人あたり予算', value: `${info.budget_per_person.toLocaleString()}円` })
  if (info.transportation) items.push({ label: '移動手段', value: info.transportation })
  if (info.accommodation_type) items.push({ label: '宿泊タイプ', value: info.accommodation_type })
  if (info.food_preferences?.length) items.push({ label: '食事の好み', value: info.food_preferences.join('、') })
  if (info.activity_preferences?.length) items.push({ label: 'やりたいこと', value: info.activity_preferences.join('、') })
  if (info.must_visit?.length) items.push({ label: '行きたい場所', value: info.must_visit.join('、') })
  if (info.avoid?.length) items.push({ label: '避けたいこと', value: info.avoid.join('、') })
  if (info.pace) items.push({ label: 'ペース', value: info.pace })
  if (info.special_requests) items.push({ label: 'その他要望', value: info.special_requests })

  return items
})
</script>

<template>
  <div class="travel-planning-view">
    <!-- Phase 1: フォーム入力 -->
    <div v-if="phase === 'form'" class="form-phase">
      <TravelPlanForm
        v-if="user"
        :user-id="user.id"
        :is-loading="isLoading"
        @submit="handleFormSubmit"
      />
      <div v-else class="no-user-message">
        ログインしてください
      </div>
    </div>

    <!-- Phase 2: 情報収集の対話 -->
    <div v-else-if="phase === 'gathering'" class="gathering-phase">
      <div class="view-header">
        <div class="header-content">
          <div>
            <h2>{{ collectedInfo.area }}への旅行</h2>
            <p v-if="!allRequiredSatisfied">詳細をお聞かせください</p>
            <p v-else>準備完了！プランを作成できます</p>
          </div>
          <!-- 必須情報が揃ったらプラン作成ボタンを表示 -->
          <button
            v-if="allRequiredSatisfied"
            class="generate-header-btn"
            @click="startPlanGeneration"
            :disabled="isLoading"
          >
            プランを作成
          </button>
        </div>
        <!-- 4カテゴリ収集状況インジケーター -->
        <div class="collected-progress">
          <div class="progress-item" :class="{ completed: requiredInfoStatus.has_activities }">
            <span class="check-icon">{{ requiredInfoStatus.has_activities ? '✓' : '○' }}</span>
            <span>体験</span>
          </div>
          <div class="progress-item" :class="{ completed: requiredInfoStatus.has_food }">
            <span class="check-icon">{{ requiredInfoStatus.has_food ? '✓' : '○' }}</span>
            <span>食</span>
          </div>
          <div class="progress-item" :class="{ completed: requiredInfoStatus.has_accommodation }">
            <span class="check-icon">{{ requiredInfoStatus.has_accommodation ? '✓' : '○' }}</span>
            <span>宿</span>
          </div>
          <div class="progress-item" :class="{ completed: requiredInfoStatus.has_transportation }">
            <span class="check-icon">{{ requiredInfoStatus.has_transportation ? '✓' : '○' }}</span>
            <span>交通</span>
          </div>
          <div class="progress-count">
            {{ requiredInfoStatus.category_count }}/4
          </div>
        </div>
      </div>

      <div class="chat-container">
        <div class="messages-container" ref="messagesContainer">
          <div
            v-for="(message, index) in messages"
            :key="index"
            :class="['message', message.role]"
          >
            <div class="message-content">
              <div class="message-text" v-html="formatMessage(message.content)"></div>
            </div>
          </div>

          <div v-if="isLoading && !isStreaming" class="message assistant">
            <div class="message-content">
              <div class="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          </div>
        </div>

        <div class="input-container">
          <textarea
            v-model="inputMessage"
            @keydown="handleKeydown"
            @compositionstart="handleCompositionStart"
            @compositionend="handleCompositionEnd"
            placeholder="詳細を入力... (⌘/Ctrl+Enterで送信)"
            :disabled="isLoading || !user"
            rows="1"
          ></textarea>
          <button
            type="button"
            @click="sendGatheringMessage"
            :disabled="!inputMessage.trim() || isLoading || !user"
            class="send-btn"
          >
            送信
          </button>
        </div>
      </div>
    </div>

    <!-- Phase 3: 確認画面 -->
    <div v-else-if="phase === 'ready'" class="ready-phase">
      <div class="ready-container">
        <div class="ready-header">
          <h2>収集した情報</h2>
          <p>以下の内容で旅行プランを作成します</p>
        </div>

        <div class="collected-info">
          <div
            v-for="item in formatCollectedInfo"
            :key="item.label"
            class="info-item"
          >
            <span class="info-label">{{ item.label }}</span>
            <span class="info-value">{{ item.value }}</span>
          </div>

          <div v-if="formatCollectedInfo.length === 0" class="no-info">
            基本情報のみ収集されています
          </div>
        </div>

        <div class="ready-actions">
          <button class="back-btn" @click="backToGathering">
            追加情報を入力
          </button>
          <button class="generate-btn" @click="startPlanGeneration" :disabled="isLoading">
            旅行プランを作成
          </button>
        </div>
      </div>
    </div>

    <!-- Phase 4: プラン生成中 -->
    <div v-else-if="phase === 'planning'" class="planning-phase">
      <div class="planning-container">
        <div class="planning-icon">✈️</div>
        <h2>プランを作成中...</h2>
        <p>{{ collectedInfo.area }}への旅行プランを生成しています</p>
        <div class="progress-meter">
          <div class="progress-bar">
            <div class="progress-fill" :style="{ width: `${displayProgress}%` }"></div>
          </div>
          <div class="progress-info">
            <span class="progress-phase">{{ getPhaseLabel(currentPhase) }}</span>
            <span class="progress-text">{{ Math.round(displayProgress) }}%</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Phase 5: 結果表示 -->
    <div v-else-if="phase === 'result'" class="result-phase">
      <div class="view-header">
        <div class="header-content">
          <div>
            <h2>{{ collectedInfo.area }}の旅行プラン</h2>
            <p>チャットでプランを調整できます</p>
          </div>
          <button class="new-plan-btn" @click="startNewPlan" :disabled="isLoading">
            新しいプランを作成
          </button>
        </div>
      </div>

      <div class="chat-container">
        <div class="messages-container" ref="messagesContainer">
          <div
            v-for="(message, index) in messages"
            :key="index"
            :class="['message', message.role]"
          >
            <div class="message-content">
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
            <div class="message-content">
              <div class="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          </div>
        </div>

        <div class="input-container">
          <textarea
            v-model="inputMessage"
            @keydown="handleResultKeydown"
            @compositionstart="handleCompositionStart"
            @compositionend="handleCompositionEnd"
            placeholder="プランへのフィードバックや調整を入力... (⌘/Ctrl+Enterで送信)"
            :disabled="isLoading || !user"
            rows="1"
          ></textarea>
          <button
            type="button"
            @click="sendResultMessage"
            :disabled="!inputMessage.trim() || isLoading || !user"
            class="send-btn"
          >
            送信
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.travel-planning-view {
  display: flex;
  flex-direction: column;
  height: 100%;
}

/* フォームフェーズ */
.form-phase {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  padding: 1rem;
  overflow: hidden;
  min-height: 0;
}

.no-user-message {
  text-align: center;
  color: #718096;
  font-size: 0.9rem;
}

/* 共通ヘッダー */
.view-header {
  padding: 0.75rem 1.5rem;
  background: linear-gradient(135deg, #38b2ac 0%, #319795 100%);
  color: white;
  border-radius: 12px 12px 0 0;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.view-header h2 {
  margin: 0 0 0.15rem;
  font-size: 1.1rem;
}

.view-header p {
  margin: 0;
  font-size: 0.8rem;
  opacity: 0.9;
}

/* gatheringフェーズ */
.gathering-phase,
.result-phase {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.new-plan-btn,
.generate-header-btn {
  padding: 6px 14px;
  background: rgba(255, 255, 255, 0.2);
  color: white;
  border: 1px solid rgba(255, 255, 255, 0.4);
  border-radius: 6px;
  font-size: 0.8rem;
  cursor: pointer;
  transition: background 0.2s;
  white-space: nowrap;
}

.generate-header-btn {
  background: #48bb78;
  border-color: #48bb78;
  font-weight: 600;
}

.new-plan-btn:hover:not(:disabled),
.generate-header-btn:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.3);
}

.generate-header-btn:hover:not(:disabled) {
  background: #38a169;
}

.new-plan-btn:disabled,
.generate-header-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* 収集状況の進捗インジケーター */
.collected-progress {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-top: 0.75rem;
  padding-top: 0.75rem;
  border-top: 1px solid rgba(255, 255, 255, 0.2);
}

.collected-progress .progress-item {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.6);
  transition: color 0.2s;
}

.collected-progress .progress-item.completed {
  color: #9ae6b4;
}

.collected-progress .check-icon {
  font-size: 0.8rem;
}

.collected-progress .progress-count {
  margin-left: auto;
  font-size: 0.8rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.9);
  background: rgba(255, 255, 255, 0.2);
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
}

/* チャットコンテナ */
.chat-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: white;
  border-radius: 0 0 12px 12px;
  overflow: hidden;
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.message {
  display: flex;
  max-width: 85%;
}

.message.user {
  align-self: flex-end;
}

.message.assistant {
  align-self: flex-start;
}

.message-content {
  padding: 10px 14px;
  border-radius: 12px;
  line-height: 1.5;
  font-size: 0.9rem;
}

.message.user .message-content {
  background: #38b2ac;
  color: white;
  border-bottom-right-radius: 4px;
}

.message.assistant .message-content {
  background: #f7fafc;
  color: #2d3748;
  border-bottom-left-radius: 4px;
  border: 1px solid #e2e8f0;
}

.typing-indicator {
  display: flex;
  gap: 4px;
  padding: 4px 0;
}

.typing-indicator span {
  width: 8px;
  height: 8px;
  background: #a0aec0;
  border-radius: 50%;
  animation: bounce 1.4s infinite ease-in-out both;
}

.typing-indicator span:nth-child(1) {
  animation-delay: -0.32s;
}

.typing-indicator span:nth-child(2) {
  animation-delay: -0.16s;
}

@keyframes bounce {
  0%, 80%, 100% {
    transform: scale(0);
  }
  40% {
    transform: scale(1);
  }
}

.input-container {
  display: flex;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  border-top: 1px solid #e2e8f0;
  background: #f7fafc;
}

.input-container textarea {
  flex: 1;
  padding: 10px 14px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 0.9rem;
  font-family: inherit;
  resize: none;
  min-height: 40px;
  max-height: 100px;
  outline: none;
  transition: border-color 0.2s;
}

.input-container textarea:focus {
  border-color: #38b2ac;
}

.send-btn {
  padding: 0 20px;
  background: #38b2ac;
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 0.9rem;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s;
}

.send-btn:hover:not(:disabled) {
  background: #319795;
}

.send-btn:disabled {
  background: #a0aec0;
  cursor: not-allowed;
}

/* readyフェーズ */
.ready-phase {
  flex: 1;
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 1rem;
}

.ready-container {
  background: white;
  border-radius: 12px;
  max-width: 600px;
  width: 100%;
  overflow: hidden;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
}

.ready-header {
  padding: 1.25rem 1.5rem;
  background: linear-gradient(135deg, #38b2ac 0%, #319795 100%);
  color: white;
}

.ready-header h2 {
  margin: 0 0 0.25rem;
  font-size: 1.2rem;
}

.ready-header p {
  margin: 0;
  font-size: 0.85rem;
  opacity: 0.9;
}

.collected-info {
  padding: 1.5rem;
}

.info-item {
  display: flex;
  padding: 0.75rem 0;
  border-bottom: 1px solid #edf2f7;
}

.info-item:last-child {
  border-bottom: none;
}

.info-label {
  flex: 0 0 140px;
  color: #718096;
  font-size: 0.9rem;
}

.info-value {
  flex: 1;
  color: #2d3748;
  font-size: 0.9rem;
  font-weight: 500;
}

.no-info {
  color: #a0aec0;
  text-align: center;
  padding: 1rem;
}

.ready-actions {
  display: flex;
  gap: 1rem;
  padding: 1rem 1.5rem 1.5rem;
  background: #f7fafc;
}

.back-btn {
  flex: 1;
  padding: 12px 20px;
  background: #edf2f7;
  color: #4a5568;
  border: none;
  border-radius: 8px;
  font-size: 0.95rem;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s;
}

.back-btn:hover {
  background: #e2e8f0;
}

.generate-btn {
  flex: 2;
  padding: 12px 20px;
  background: #38b2ac;
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 0.95rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s;
}

.generate-btn:hover:not(:disabled) {
  background: #319795;
}

.generate-btn:disabled {
  background: #a0aec0;
  cursor: not-allowed;
}

/* planningフェーズ */
.planning-phase {
  flex: 1;
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 1rem;
}

.planning-container {
  text-align: center;
  padding: 2rem;
}

.planning-icon {
  font-size: 3rem;
  margin-bottom: 1rem;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% {
    transform: scale(1);
  }
  50% {
    transform: scale(1.1);
  }
}

.planning-container h2 {
  margin: 0 0 0.5rem;
  color: #2d3748;
}

.planning-container p {
  margin: 0 0 2rem;
  color: #718096;
}

/* 進捗メーター */
.progress-meter {
  max-width: 400px;
  margin: 0 auto;
}

.progress-bar {
  height: 12px;
  background: #e2e8f0;
  border-radius: 6px;
  overflow: hidden;
  margin-bottom: 0.75rem;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #38b2ac, #319795);
  border-radius: 6px;
  transition: width 0.3s ease-out;
}

.progress-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.progress-phase {
  font-size: 0.9rem;
  color: #718096;
}

.progress-text {
  font-size: 1.25rem;
  font-weight: 600;
  color: #38b2ac;
}
</style>
