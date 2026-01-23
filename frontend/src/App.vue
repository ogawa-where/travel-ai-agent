<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { api } from './lib/api'
import { storage } from './lib/storage'
import { getErrorMessage } from './lib/errors'
import type { User, TravelPlan, UserProfile, LearnedPreference, PreferenceSignal, LoginResponse } from './lib/api'
import AppHeader from './components/AppHeader.vue'
import LoginScreen from './components/LoginScreen.vue'
import PreferenceToast from './components/PreferenceToast.vue'
import TravelPlanCard from './components/TravelPlanCard.vue'

// Note: ChatContainer is no longer used - chat is now built directly in App.vue

interface Message {
  role: 'user' | 'assistant'
  content: string
  plan?: TravelPlan
}

const user = ref<User | null>(null)
const sessionId = ref<string | null>(null)
const messages = ref<Message[]>([])
const isLoading = ref(false)
const isInitializing = ref(true)
const isLoggedIn = ref(false)
const userProfile = ref<UserProfile | null>(null)
const preferenceSignals = ref<PreferenceSignal[]>([])
const currentPlan = ref<TravelPlan | null>(null)
const isSendingFeedback = ref(false)
const showProfileModal = ref(false)
const inputMessage = ref('')
const messagesContainer = ref<HTMLElement | null>(null)

// Toast notifications for learned preferences
const pendingToasts = ref<LearnedPreference[]>([])

// Group preferences by category
const groupedPreferences = computed(() => {
  const groups: Record<string, PreferenceSignal[]> = {}
  for (const signal of preferenceSignals.value) {
    if (!groups[signal.category]) {
      groups[signal.category] = []
    }
    groups[signal.category].push(signal)
  }
  // Sort by weight within each group
  for (const category in groups) {
    groups[category].sort((a, b) => b.weight - a.weight)
  }
  return groups
})

const categoryLabels: Record<string, string> = {
  food: '食事',
  activity: '観光・体験',
  accommodation: '宿泊',
  travel_style: '旅行スタイル',
  budget: '予算',
  general: 'その他',
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

const initializeChat = async () => {
  if (!user.value) return

  try {
    isLoading.value = true
    const response = await api.startUnifiedChat(user.value.id)
    sessionId.value = response.session_id
    messages.value.push({
      role: 'assistant',
      content: response.assistant_message,
    })
    await scrollToBottom()
  } catch (error) {
    console.error('Failed to initialize chat:', error)
    messages.value.push({
      role: 'assistant',
      content: `チャットの初期化に失敗しました。\n${getErrorMessage(error)}`,
    })
  } finally {
    isLoading.value = false
  }
}

const initializeApp = async () => {
  try {
    isLoading.value = true
    isInitializing.value = true

    // Check for existing username in localStorage
    const storedUsername = storage.getUsername()
    if (storedUsername) {
      try {
        // Re-login with stored username
        const response = await api.login(storedUsername)
        user.value = response.user
        storage.setUserId(response.user.id)
        userProfile.value = response.user.profile
        preferenceSignals.value = response.user.preference_signals || []
        isLoggedIn.value = true
        await initializeChat()
        return
      } catch {
        // Login failed, clear storage and show login screen
        storage.clearAll()
      }
    }

    // No stored username, show login screen
    isLoggedIn.value = false
  } catch (error) {
    console.error('Failed to initialize app:', error)
  } finally {
    isLoading.value = false
    isInitializing.value = false
  }
}

const handleLogin = async (response: LoginResponse) => {
  user.value = response.user
  storage.setUserId(response.user.id)
  storage.setUsername(response.user.username || '')
  userProfile.value = response.user.profile
  preferenceSignals.value = response.user.preference_signals || []
  isLoggedIn.value = true
  await initializeChat()
}

const resetApp = () => {
  storage.clearAll()
  user.value = null
  sessionId.value = null
  messages.value = []
  userProfile.value = null
  preferenceSignals.value = []
  currentPlan.value = null
  isLoggedIn.value = false
}

const logout = () => {
  resetApp()
}

const sendMessage = async (userMessage: string) => {
  if (!user.value || isLoading.value || !userMessage.trim()) return

  messages.value.push({
    role: 'user',
    content: userMessage,
  })
  await scrollToBottom()

  try {
    isLoading.value = true
    const response = await api.sendUnifiedMessage(
      user.value.id,
      userMessage,
      sessionId.value || undefined
    )

    sessionId.value = response.session_id

    // Handle learned preferences for toast notifications
    if (response.learned_preferences && response.learned_preferences.length > 0) {
      pendingToasts.value = [...response.learned_preferences]
    }

    // Create message with optional plan
    const newMessage: Message = {
      role: 'assistant',
      content: response.assistant_message,
    }

    if (response.plan) {
      newMessage.plan = response.plan
      currentPlan.value = response.plan
    }

    messages.value.push(newMessage)
    await scrollToBottom()

    // Refresh user profile if preferences were learned
    if (response.learned_preferences && response.learned_preferences.length > 0) {
      const updatedUser = await api.getUser(user.value.id)
      userProfile.value = updatedUser.profile
      preferenceSignals.value = updatedUser.preference_signals || []
    }
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

const handleSend = () => {
  if (inputMessage.value.trim() && !isLoading.value && !isInitializing.value) {
    const message = inputMessage.value
    inputMessage.value = ''
    sendMessage(message)
  }
}

const clearToasts = () => {
  pendingToasts.value = []
}

const sendPlanFeedback = async (feedback: string) => {
  if (!user.value || !currentPlan.value || isSendingFeedback.value) return

  try {
    isSendingFeedback.value = true
    const response = await api.sendFeedback(
      user.value.id,
      currentPlan.value.id,
      feedback
    )

    messages.value.push({
      role: 'assistant',
      content: `フィードバックありがとうございます！${response.profile_updated ? '\nあなたの好みを学習しました。' : ''}`,
    })
    await scrollToBottom()

    // Refresh profile
    const updatedUser = await api.getUser(user.value.id)
    userProfile.value = updatedUser.profile
    preferenceSignals.value = updatedUser.preference_signals || []
  } catch (error) {
    console.error('Failed to send feedback:', error)
    messages.value.push({
      role: 'assistant',
      content: `フィードバックの送信中にエラーが発生しました。\n${getErrorMessage(error)}`,
    })
  } finally {
    isSendingFeedback.value = false
  }
}

const handlePOIFeedback = async (
  _poiName: string,
  feedbackType: 'good' | 'bad',
  learned: { category: string; tag: string; is_new: boolean } | null
) => {
  // Show toast notification if a preference was learned
  if (learned) {
    pendingToasts.value.push({
      category: learned.category,
      tag: learned.tag,
      weight: feedbackType === 'good' ? 1 : -1,
      is_new: learned.is_new,
    })
  }

  // Refresh user profile to get updated preferences
  if (user.value) {
    try {
      const updatedUser = await api.getUser(user.value.id)
      userProfile.value = updatedUser.profile
      preferenceSignals.value = updatedUser.preference_signals || []
    } catch (error) {
      console.error('Failed to refresh user profile:', error)
    }
  }
}

const showProfile = () => {
  showProfileModal.value = true
}

const closeProfile = () => {
  showProfileModal.value = false
}

onMounted(() => {
  initializeApp()
})
</script>

<template>
  <div class="app">
    <!-- Login Screen -->
    <LoginScreen v-if="!isLoggedIn && !isInitializing" @login="handleLogin" />

    <!-- Main App -->
    <template v-else-if="isLoggedIn">
      <AppHeader
        :profile-summary="userProfile?.summary || ''"
        :username="user?.username || ''"
        @show-profile="showProfile"
        @logout="logout"
      />

      <main class="main">
      <div class="chat-wrapper">
        <div class="messages-container" ref="messagesContainer">
          <div v-if="isInitializing" class="loading-state">
            <div class="spinner"></div>
            <p>読み込み中...</p>
          </div>

          <template v-else>
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
                  @feedback="sendPlanFeedback"
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
          </template>
        </div>

        <div class="input-container">
          <textarea
            v-model="inputMessage"
            @keydown.enter.exact.prevent="handleSend"
            placeholder="メッセージを入力..."
            :disabled="isLoading || isInitializing"
            rows="1"
          ></textarea>
          <button
            @click="handleSend"
            :disabled="!inputMessage.trim() || isLoading || isInitializing"
            class="send-btn"
          >
            送信
          </button>
        </div>
      </div>
      </main>

      <!-- Toast notifications for learned preferences -->
      <PreferenceToast :preferences="pendingToasts" @clear="clearToasts" />

      <!-- Profile Modal -->
      <Teleport to="body">
        <div v-if="showProfileModal" class="modal-overlay" @click="closeProfile">
          <div class="modal-content" @click.stop>
            <div class="modal-header">
              <h2>あなたのプロフィール</h2>
              <button class="close-btn" @click="closeProfile">&times;</button>
            </div>
            <div class="modal-body">
              <div v-if="userProfile?.summary" class="profile-summary">
                <h3>サマリー</h3>
                <p>{{ userProfile.summary }}</p>
              </div>

              <div v-if="Object.keys(groupedPreferences).length > 0" class="preferences-detail">
                <h3>学習した嗜好</h3>
                <div
                  v-for="(signals, category) in groupedPreferences"
                  :key="category"
                  class="preference-category"
                >
                  <h4>{{ categoryLabels[category] || category }}</h4>
                  <div class="preference-tags">
                    <div
                      v-for="signal in signals"
                      :key="signal.id"
                      class="preference-tag"
                      :class="{ 'positive': signal.weight > 0, 'negative': signal.weight < 0 }"
                      :title="signal.evidence"
                    >
                      <span class="tag-icon">{{ signal.weight > 0 ? '👍' : '👎' }}</span>
                      <span class="tag-name">{{ signal.tag }}</span>
                      <span class="tag-weight">{{ Math.abs(signal.weight).toFixed(1) }}</span>
                    </div>
                  </div>
                </div>
              </div>

              <div v-if="!userProfile?.summary && Object.keys(groupedPreferences).length === 0" class="no-profile">
                <p>まだプロフィールがありません。</p>
                <p>チャットを通じてあなたの好みを教えてください！</p>
              </div>
            </div>
          </div>
        </div>
      </Teleport>
    </template>

    <!-- Initial Loading State -->
    <div v-if="isInitializing" class="initializing-screen">
      <div class="spinner"></div>
      <p>読み込み中...</p>
    </div>
  </div>
</template>

<style scoped>
.app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: #f5f7fa;
}

.main {
  flex: 1;
  display: flex;
  justify-content: center;
  padding: 1rem;
}

.chat-wrapper {
  width: 100%;
  max-width: 800px;
  display: flex;
  flex-direction: column;
  background: white;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  overflow: hidden;
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  min-height: 400px;
  max-height: calc(100vh - 200px);
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  padding: 3rem;
  color: #718096;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid #e2e8f0;
  border-top-color: #4299e1;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
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
  padding: 12px 16px;
  border-radius: 12px;
  line-height: 1.5;
}

.message.user .message-content {
  background: #4299e1;
  color: white;
  border-bottom-right-radius: 4px;
}

.message.assistant .message-content {
  background: #f7fafc;
  color: #2d3748;
  border-bottom-left-radius: 4px;
  border: 1px solid #e2e8f0;
}

.message-text {
  font-size: 0.95rem;
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
  0%,
  80%,
  100% {
    transform: scale(0);
  }
  40% {
    transform: scale(1);
  }
}

.input-container {
  display: flex;
  gap: 0.75rem;
  padding: 1rem 1.5rem;
  border-top: 1px solid #e2e8f0;
  background: #f7fafc;
}

.input-container textarea {
  flex: 1;
  padding: 12px 16px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 0.95rem;
  font-family: inherit;
  resize: none;
  min-height: 44px;
  max-height: 120px;
  outline: none;
  transition: border-color 0.2s;
}

.input-container textarea:focus {
  border-color: #4299e1;
}

.send-btn {
  padding: 0 24px;
  background: #4299e1;
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 0.95rem;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s;
}

.send-btn:hover:not(:disabled) {
  background: #3182ce;
}

.send-btn:disabled {
  background: #a0aec0;
  cursor: not-allowed;
}

/* Modal styles */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: white;
  border-radius: 12px;
  width: 90%;
  max-width: 500px;
  max-height: 80vh;
  overflow: hidden;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.2);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.5rem;
  border-bottom: 1px solid #e2e8f0;
}

.modal-header h2 {
  margin: 0;
  font-size: 1.25rem;
  color: #2d3748;
}

.close-btn {
  background: none;
  border: none;
  font-size: 1.5rem;
  color: #a0aec0;
  cursor: pointer;
  padding: 0;
  line-height: 1;
}

.close-btn:hover {
  color: #718096;
}

.modal-body {
  padding: 1.5rem;
  overflow-y: auto;
  max-height: 60vh;
}

.profile-summary h3,
.preferences-detail h3 {
  margin: 0 0 0.75rem;
  font-size: 0.9rem;
  font-weight: 600;
  color: #2d3748;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.profile-summary p {
  margin: 0;
  line-height: 1.6;
  color: #4a5568;
  white-space: pre-wrap;
}

.profile-summary {
  margin-bottom: 1.5rem;
  padding-bottom: 1.5rem;
  border-bottom: 1px solid #e2e8f0;
}

.preferences-detail {
  margin-bottom: 1rem;
}

.preference-category {
  margin-bottom: 1rem;
}

.preference-category h4 {
  margin: 0 0 0.5rem;
  font-size: 0.85rem;
  font-weight: 500;
  color: #718096;
}

.preference-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.preference-tag {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.35rem 0.6rem;
  border-radius: 20px;
  font-size: 0.8rem;
  cursor: default;
  transition: transform 0.1s;
}

.preference-tag:hover {
  transform: scale(1.02);
}

.preference-tag.positive {
  background: rgba(72, 187, 120, 0.15);
  color: #276749;
  border: 1px solid rgba(72, 187, 120, 0.3);
}

.preference-tag.negative {
  background: rgba(245, 101, 101, 0.15);
  color: #c53030;
  border: 1px solid rgba(245, 101, 101, 0.3);
}

.tag-icon {
  font-size: 0.75rem;
}

.tag-name {
  font-weight: 500;
}

.tag-weight {
  font-size: 0.7rem;
  opacity: 0.7;
  font-weight: 400;
}

.no-profile {
  text-align: center;
  color: #718096;
}

.no-profile p {
  margin: 0.5rem 0;
}

.initializing-screen {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.initializing-screen .spinner {
  width: 50px;
  height: 50px;
  border: 3px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

.initializing-screen p {
  font-size: 1rem;
  opacity: 0.9;
}
</style>
