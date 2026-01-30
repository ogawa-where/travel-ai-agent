<script setup lang="ts">
import { ref, nextTick } from 'vue'
import { api } from '../lib/api'
import { getErrorMessage } from '../lib/errors'
import type { User, TravelPlan, TravelChatResponse, TravelPlanFormData } from '../lib/api'
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

// 2フェーズ状態: form → chat
const phase = ref<'form' | 'chat'>('form')

const sessionId = ref<string | null>(null)
const messages = ref<Message[]>([])
const isLoading = ref(false)
const inputMessage = ref('')
const messagesContainer = ref<HTMLElement | null>(null)
const currentPlan = ref<TravelPlan | null>(null)

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

// フォーム送信ハンドラ
const handleFormSubmit = async (data: TravelPlanFormData) => {
  if (!props.user) return

  isLoading.value = true

  try {
    const response: TravelChatResponse = await api.submitTravelForm(data)

    sessionId.value = response.session_id

    // チャットフェーズに遷移し、生成結果を表示
    messages.value = []

    if (response.plan) {
      currentPlan.value = response.plan
      messages.value.push({
        role: 'assistant',
        content: response.assistant_message,
        plan: response.plan,
      })
      emit('plan-created', response.plan)
    } else {
      messages.value.push({
        role: 'assistant',
        content: response.assistant_message,
      })
    }

    phase.value = 'chat'
    await scrollToBottom()
  } catch (error) {
    console.error('Failed to generate plan from form:', error)
    // エラー時もチャットフェーズに遷移してエラーを表示
    messages.value = [{
      role: 'assistant',
      content: `プランの生成に失敗しました。\n${getErrorMessage(error)}`,
    }]
    phase.value = 'chat'
    await scrollToBottom()
  } finally {
    isLoading.value = false
  }
}

const handleFormCancel = () => {
  // フォームキャンセル時: 既にチャット履歴があればチャットに戻る
  if (messages.value.length > 0) {
    phase.value = 'chat'
  }
}

// 「新しいプランを作成」でフォームに戻る
const startNewPlan = () => {
  phase.value = 'form'
  currentPlan.value = null
}

// チャットメッセージ送信（フィードバック・調整用）
const sendMessage = async () => {
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
    const response: TravelChatResponse = await api.sendTravelMessage(
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
  // POI単位のフィードバック処理（必要に応じて実装）
}
</script>

<template>
  <div class="travel-planning-view">
    <!-- フェーズ1: フォーム入力 -->
    <div v-if="phase === 'form'" class="form-phase">
      <TravelPlanForm
        v-if="user"
        :user-id="user.id"
        :is-loading="isLoading"
        @submit="handleFormSubmit"
        @cancel="handleFormCancel"
      />
      <div v-else class="no-user-message">
        ログインしてください
      </div>
    </div>

    <!-- フェーズ2: チャット（プラン表示 + フィードバック・調整） -->
    <div v-else class="chat-phase">
      <div class="view-header">
        <div class="header-content">
          <div>
            <h2>旅行プラン</h2>
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
            @keydown.enter.exact.prevent="sendMessage"
            placeholder="プランへのフィードバックや調整を入力..."
            :disabled="isLoading || !user"
            rows="1"
          ></textarea>
          <button
            @click="sendMessage"
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
  justify-content: center;
  padding: 1rem;
  overflow-y: auto;
}

.no-user-message {
  text-align: center;
  color: #718096;
  font-size: 0.9rem;
}

/* チャットフェーズ */
.chat-phase {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

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

.new-plan-btn {
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

.new-plan-btn:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.3);
}

.new-plan-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

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
</style>
