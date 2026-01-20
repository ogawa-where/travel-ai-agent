<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { api } from './lib/api'
import type { User, PreferenceSignal, TravelPlan, UserProfile } from './lib/api'
import AppHeader from './components/AppHeader.vue'
import ChatContainer from './components/ChatContainer.vue'
import PreferenceSidebar from './components/PreferenceSidebar.vue'
import TravelSidebar from './components/TravelSidebar.vue'

type AppMode = 'preference' | 'travel'

interface Message {
  role: 'user' | 'assistant'
  content: string
}

const currentMode = ref<AppMode>('preference')
const user = ref<User | null>(null)
const sessionId = ref<string | null>(null)
const messages = ref<Message[]>([])
const isLoading = ref(false)
const signals = ref<PreferenceSignal[]>([])
const userProfile = ref<UserProfile | null>(null)
const currentPlan = ref<TravelPlan | null>(null)
const isCompletingLearning = ref(false)
const isSendingFeedback = ref(false)

const modeTitle = computed(() => {
  return currentMode.value === 'preference' ? '嗜好学習モード' : '旅行企画モード'
})

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
    userProfile.value = user.value.profile
    signals.value = user.value.preference_signals || []
    await initializePreferenceChat()
  } catch (error) {
    console.error('Failed to initialize app:', error)
  } finally {
    isLoading.value = false
  }
}

const sendMessage = async (userMessage: string) => {
  if (!user.value || isLoading.value) return

  messages.value.push({
    role: 'user',
    content: userMessage,
  })

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

const completeLearning = async () => {
  if (!user.value || !sessionId.value || isCompletingLearning.value) return

  try {
    isCompletingLearning.value = true
    const response = await api.completeLearning(user.value.id, sessionId.value)

    messages.value.push({
      role: 'assistant',
      content: `学習が完了しました！\n\n📝 プロフィール要約:\n${response.profile_summary}\n\n✅ 学習した嗜好: ${response.total_signals}件`,
    })

    // Refresh signals and profile
    signals.value = await api.getUserSignals(user.value.id)
    const updatedUser = await api.getUser(user.value.id)
    userProfile.value = updatedUser.profile
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

const sendFeedback = async (feedback: string) => {
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
      content: `フィードバックを受け付けました！${response.profile_updated ? '\nプロフィールを更新しました。' : ''}${response.updated_signals_count > 0 ? `\n${response.updated_signals_count}件の嗜好を学習しました。` : ''}`,
    })
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
    <AppHeader
      :current-mode="currentMode"
      :mode-title="modeTitle"
      @switch-mode="switchMode"
    />

    <main class="main">
      <ChatContainer
        :messages="messages"
        :is-loading="isLoading"
        :current-mode="currentMode"
        @send-message="sendMessage"
      />

      <aside class="sidebar">
        <PreferenceSidebar
          v-if="currentMode === 'preference'"
          :signals="signals"
          :is-completing-learning="isCompletingLearning"
          :profile="userProfile"
          @complete-learning="completeLearning"
        />

        <TravelSidebar
          v-else
          :plan="currentPlan"
          :is-sending-feedback="isSendingFeedback"
          @send-feedback="sendFeedback"
        />
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

.main {
  flex: 1;
  display: flex;
  max-width: 1200px;
  margin: 0 auto;
  width: 100%;
  padding: 1rem;
  gap: 1rem;
}

.sidebar {
  width: 280px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  padding: 1rem;
}
</style>
