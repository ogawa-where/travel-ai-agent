<script setup lang="ts">
import { ref, onMounted, nextTick, computed } from 'vue'
import { api } from './lib/api'
import type { User, PreferenceSignal, TravelPlan } from './lib/api'

type AppMode = 'preference' | 'travel'

interface Message {
  role: 'user' | 'assistant'
  content: string
}

const currentMode = ref<AppMode>('preference')
const user = ref<User | null>(null)
const sessionId = ref<string | null>(null)
const messages = ref<Message[]>([])
const inputMessage = ref('')
const isLoading = ref(false)
const signals = ref<PreferenceSignal[]>([])
const currentPlan = ref<TravelPlan | null>(null)
const messagesContainer = ref<HTMLElement | null>(null)
const isCompletingLearning = ref(false)
const feedbackText = ref('')
const isSendingFeedback = ref(false)

const modeTitle = computed(() => {
  return currentMode.value === 'preference' ? '嗜好学習モード' : '旅行企画モード'
})

const scrollToBottom = async () => {
  await nextTick()
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

const switchMode = async (mode: AppMode) => {
  if (mode === currentMode.value) return

  currentMode.value = mode
  messages.value = []
  sessionId.value = null
  currentPlan.value = null

  if (user.value) {
    if (mode === 'preference') {
      await initializePreferenceChat()
    } else {
      await initializeTravelChat()
    }
  }
}

const initializePreferenceChat = async () => {
  if (!user.value) return

  try {
    isLoading.value = true
    const response = await api.startChat(user.value.id)
    sessionId.value = response.session_id
    messages.value.push({
      role: 'assistant',
      content: response.assistant_message,
    })
    await scrollToBottom()
  } catch (error) {
    console.error('Failed to initialize preference chat:', error)
  } finally {
    isLoading.value = false
  }
}

const initializeTravelChat = async () => {
  if (!user.value) return

  try {
    isLoading.value = true
    const response = await api.startTravelChat(user.value.id)
    sessionId.value = response.session_id
    messages.value.push({
      role: 'assistant',
      content: response.assistant_message,
    })
    await scrollToBottom()
  } catch (error) {
    console.error('Failed to initialize travel chat:', error)
  } finally {
    isLoading.value = false
  }
}

const initializeApp = async () => {
  try {
    isLoading.value = true
    user.value = await api.createUser()
    await initializePreferenceChat()
  } catch (error) {
    console.error('Failed to initialize app:', error)
  } finally {
    isLoading.value = false
  }
}

const sendMessage = async () => {
  if (!inputMessage.value.trim() || !user.value || isLoading.value) return

  const userMessage = inputMessage.value.trim()
  inputMessage.value = ''

  messages.value.push({
    role: 'user',
    content: userMessage,
  })
  await scrollToBottom()

  try {
    isLoading.value = true

    if (currentMode.value === 'preference') {
      const response = await api.sendMessage(user.value.id, userMessage, sessionId.value || undefined)
      sessionId.value = response.session_id
      messages.value.push({
        role: 'assistant',
        content: response.assistant_message,
      })
      if (response.updated_signals.length > 0) {
        signals.value = [...signals.value, ...response.updated_signals]
      }
    } else {
      const response = await api.sendTravelMessage(user.value.id, userMessage, sessionId.value || undefined)
      sessionId.value = response.session_id
      messages.value.push({
        role: 'assistant',
        content: response.assistant_message,
      })
      if (response.plan) {
        currentPlan.value = response.plan
      }
    }

    await scrollToBottom()
  } catch (error) {
    console.error('Failed to send message:', error)
    messages.value.push({
      role: 'assistant',
      content: 'エラーが発生しました。もう一度お試しください。',
    })
  } finally {
    isLoading.value = false
  }
}

const handleKeydown = (event: KeyboardEvent) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    sendMessage()
  }
}

const completeLearning = async () => {
  if (!user.value || !sessionId.value || isCompletingLearning.value) return

  try {
    isCompletingLearning.value = true
    const response = await api.completeLearning(user.value.id, sessionId.value)

    messages.value.push({
      role: 'assistant',
      content: `学習が完了しました！\n\n📝 プロフィール要約:\n${response.profile_summary}\n\n✅ 学習した嗜好: ${response.total_signals}件`,
    })
    await scrollToBottom()

    // Refresh signals
    signals.value = await api.getUserSignals(user.value.id)
  } catch (error) {
    console.error('Failed to complete learning:', error)
    messages.value.push({
      role: 'assistant',
      content: '学習の完了処理中にエラーが発生しました。',
    })
  } finally {
    isCompletingLearning.value = false
  }
}

const sendFeedback = async () => {
  if (!user.value || !currentPlan.value || !feedbackText.value.trim() || isSendingFeedback.value) return

  try {
    isSendingFeedback.value = true
    const response = await api.sendFeedback(
      user.value.id,
      currentPlan.value.id,
      feedbackText.value.trim()
    )

    messages.value.push({
      role: 'assistant',
      content: `フィードバックを受け付けました！${response.profile_updated ? '\nプロフィールを更新しました。' : ''}${response.updated_signals_count > 0 ? `\n${response.updated_signals_count}件の嗜好を学習しました。` : ''}`,
    })
    feedbackText.value = ''
    await scrollToBottom()
  } catch (error) {
    console.error('Failed to send feedback:', error)
    messages.value.push({
      role: 'assistant',
      content: 'フィードバックの送信中にエラーが発生しました。',
    })
  } finally {
    isSendingFeedback.value = false
  }
}

onMounted(() => {
  initializeApp()
})
</script>

<template>
  <div class="app">
    <header class="header">
      <div class="header-content">
        <div>
          <h1>Travel AI Agent</h1>
          <p>{{ modeTitle }}</p>
        </div>
        <div class="mode-switcher">
          <button
            :class="['mode-btn', { active: currentMode === 'preference' }]"
            @click="switchMode('preference')"
          >
            嗜好学習
          </button>
          <button
            :class="['mode-btn', { active: currentMode === 'travel' }]"
            @click="switchMode('travel')"
          >
            旅行企画
          </button>
        </div>
      </div>
    </header>

    <main class="main">
      <div class="chat-container">
        <div class="messages" ref="messagesContainer">
          <div
            v-for="(message, index) in messages"
            :key="index"
            :class="['message', message.role]"
          >
            <div class="message-content" v-html="message.content.replace(/\n/g, '<br>')">
            </div>
          </div>
          <div v-if="isLoading" class="message assistant">
            <div class="message-content loading">
              {{ currentMode === 'travel' ? 'プラン作成中...' : '考え中...' }}
            </div>
          </div>
        </div>

        <div class="input-area">
          <textarea
            v-model="inputMessage"
            @keydown="handleKeydown"
            :placeholder="currentMode === 'travel' ? '旅行の希望を入力... (例: 来月、京都に2泊3日で一人旅したい)' : 'メッセージを入力...'"
            :disabled="isLoading"
            rows="2"
          />
          <button @click="sendMessage" :disabled="isLoading || !inputMessage.trim()">
            送信
          </button>
        </div>
      </div>

      <aside class="sidebar">
        <!-- 嗜好学習モードのサイドバー -->
        <template v-if="currentMode === 'preference'">
          <h2>学習した嗜好</h2>
          <div v-if="signals.length === 0" class="no-signals">
            まだ嗜好が学習されていません
          </div>
          <ul v-else class="signals-list">
            <li v-for="signal in signals" :key="signal.id" class="signal-item">
              <span class="signal-category">{{ signal.category }}</span>
              <span class="signal-tag">{{ signal.tag }}</span>
              <span class="signal-weight">({{ (signal.weight * 100).toFixed(0) }}%)</span>
            </li>
          </ul>
          <div class="learning-actions" v-if="signals.length > 0">
            <button
              class="complete-learning-btn"
              @click="completeLearning"
              :disabled="isCompletingLearning"
            >
              {{ isCompletingLearning ? '処理中...' : '学習を完了する' }}
            </button>
            <p class="action-hint">学習を完了すると、嗜好が整理・統合されます</p>
          </div>
        </template>

        <!-- 旅行企画モードのサイドバー -->
        <template v-else>
          <h2>旅行プラン</h2>
          <div v-if="!currentPlan" class="no-plan">
            まだプランが作成されていません。<br>
            希望を入力して「プランを作って」と言ってみてください。
          </div>
          <div v-else class="plan-summary">
            <h3>{{ currentPlan.itinerary.title || '旅程' }}</h3>
            <p class="plan-score">スコア: {{ (currentPlan.score * 100).toFixed(0) }}%</p>
            <div class="score-breakdown">
              <div v-for="(score, key) in currentPlan.score_breakdown" :key="key" class="score-item">
                <span class="score-label">{{ key }}</span>
                <span class="score-value">{{ (score * 100).toFixed(0) }}%</span>
              </div>
            </div>
            <div class="feedback-section">
              <h4>フィードバック</h4>
              <p class="feedback-hint">このプランへのご意見を教えてください</p>
              <textarea
                v-model="feedbackText"
                placeholder="良かった点、改善点など..."
                rows="3"
                class="feedback-input"
              />
              <button
                class="feedback-btn"
                @click="sendFeedback"
                :disabled="isSendingFeedback || !feedbackText.trim()"
              >
                {{ isSendingFeedback ? '送信中...' : 'フィードバックを送信' }}
              </button>
            </div>
          </div>
        </template>
      </aside>
    </main>
  </div>
</template>

<style scoped>
.app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

.header {
  background: #2c3e50;
  color: white;
  padding: 1rem 2rem;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  max-width: 1200px;
  margin: 0 auto;
}

.header h1 {
  margin: 0;
  font-size: 1.5rem;
}

.header p {
  margin: 0.25rem 0 0;
  opacity: 0.8;
  font-size: 0.9rem;
}

.mode-switcher {
  display: flex;
  gap: 0.5rem;
}

.mode-btn {
  padding: 0.5rem 1rem;
  border: 1px solid rgba(255, 255, 255, 0.3);
  background: transparent;
  color: white;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.9rem;
  transition: all 0.2s;
}

.mode-btn:hover {
  background: rgba(255, 255, 255, 0.1);
}

.mode-btn.active {
  background: white;
  color: #2c3e50;
}

.main {
  flex: 1;
  display: flex;
  max-width: 1200px;
  margin: 0 auto;
  width: 100%;
  padding: 1rem;
  gap: 1rem;
}

.chat-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  overflow: hidden;
}

.messages {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  min-height: 400px;
  max-height: 600px;
}

.message {
  max-width: 80%;
  padding: 0.75rem 1rem;
  border-radius: 12px;
  line-height: 1.5;
}

.message.user {
  align-self: flex-end;
  background: #3498db;
  color: white;
}

.message.assistant {
  align-self: flex-start;
  background: #ecf0f1;
  color: #2c3e50;
  white-space: pre-wrap;
}

.message-content.loading {
  opacity: 0.7;
  font-style: italic;
}

.input-area {
  display: flex;
  gap: 0.5rem;
  padding: 1rem;
  border-top: 1px solid #ecf0f1;
}

.input-area textarea {
  flex: 1;
  padding: 0.75rem;
  border: 1px solid #ddd;
  border-radius: 8px;
  resize: none;
  font-family: inherit;
  font-size: 1rem;
}

.input-area textarea:focus {
  outline: none;
  border-color: #3498db;
}

.input-area button {
  padding: 0.75rem 1.5rem;
  background: #3498db;
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 1rem;
}

.input-area button:hover:not(:disabled) {
  background: #2980b9;
}

.input-area button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.sidebar {
  width: 280px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  padding: 1rem;
}

.sidebar h2 {
  margin: 0 0 1rem;
  font-size: 1rem;
  color: #2c3e50;
}

.no-signals,
.no-plan {
  color: #7f8c8d;
  font-size: 0.9rem;
  line-height: 1.5;
}

.signals-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.signal-item {
  padding: 0.5rem 0;
  border-bottom: 1px solid #ecf0f1;
  font-size: 0.9rem;
}

.signal-item:last-child {
  border-bottom: none;
}

.signal-category {
  display: inline-block;
  background: #e74c3c;
  color: white;
  padding: 0.125rem 0.5rem;
  border-radius: 4px;
  font-size: 0.75rem;
  margin-right: 0.5rem;
}

.signal-tag {
  color: #2c3e50;
}

.signal-weight {
  color: #7f8c8d;
  font-size: 0.8rem;
}

/* 旅行企画モード用スタイル */
.plan-summary h3 {
  margin: 0 0 0.5rem;
  font-size: 1rem;
  color: #2c3e50;
}

.plan-score {
  font-size: 0.9rem;
  color: #27ae60;
  margin: 0 0 1rem;
}

.score-breakdown {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.score-item {
  display: flex;
  justify-content: space-between;
  font-size: 0.85rem;
}

.score-label {
  color: #7f8c8d;
}

.score-value {
  color: #2c3e50;
  font-weight: 500;
}

/* 学習完了ボタン */
.learning-actions {
  margin-top: 1.5rem;
  padding-top: 1rem;
  border-top: 1px solid #ecf0f1;
}

.complete-learning-btn {
  width: 100%;
  padding: 0.75rem 1rem;
  background: #27ae60;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.9rem;
  font-weight: 500;
  transition: background 0.2s;
}

.complete-learning-btn:hover:not(:disabled) {
  background: #219a52;
}

.complete-learning-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.action-hint {
  margin-top: 0.5rem;
  font-size: 0.75rem;
  color: #7f8c8d;
  text-align: center;
}

/* フィードバックセクション */
.feedback-section {
  margin-top: 1.5rem;
  padding-top: 1rem;
  border-top: 1px solid #ecf0f1;
}

.feedback-section h4 {
  margin: 0 0 0.5rem;
  font-size: 0.9rem;
  color: #2c3e50;
}

.feedback-hint {
  margin: 0 0 0.5rem;
  font-size: 0.75rem;
  color: #7f8c8d;
}

.feedback-input {
  width: 100%;
  padding: 0.5rem;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-family: inherit;
  font-size: 0.85rem;
  resize: none;
  box-sizing: border-box;
}

.feedback-input:focus {
  outline: none;
  border-color: #3498db;
}

.feedback-btn {
  width: 100%;
  margin-top: 0.5rem;
  padding: 0.5rem 1rem;
  background: #3498db;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.85rem;
  transition: background 0.2s;
}

.feedback-btn:hover:not(:disabled) {
  background: #2980b9;
}

.feedback-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
