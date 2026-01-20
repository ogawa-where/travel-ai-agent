<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { api } from './lib/api'
import type { User, PreferenceSignal } from './lib/api'

interface Message {
  role: 'user' | 'assistant'
  content: string
}

const user = ref<User | null>(null)
const messages = ref<Message[]>([])
const inputMessage = ref('')
const isLoading = ref(false)
const signals = ref<PreferenceSignal[]>([])
const messagesContainer = ref<HTMLElement | null>(null)

const scrollToBottom = async () => {
  await nextTick()
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

const initializeChat = async () => {
  try {
    isLoading.value = true
    // Create new user
    user.value = await api.createUser()
    // Start chat
    const response = await api.startChat(user.value.id)
    messages.value.push({
      role: 'assistant',
      content: response.assistant_message,
    })
    await scrollToBottom()
  } catch (error) {
    console.error('Failed to initialize chat:', error)
  } finally {
    isLoading.value = false
  }
}

const sendMessage = async () => {
  if (!inputMessage.value.trim() || !user.value || isLoading.value) return

  const userMessage = inputMessage.value.trim()
  inputMessage.value = ''

  // Add user message to UI
  messages.value.push({
    role: 'user',
    content: userMessage,
  })
  await scrollToBottom()

  try {
    isLoading.value = true
    const response = await api.sendMessage(user.value.id, userMessage)

    // Add assistant response
    messages.value.push({
      role: 'assistant',
      content: response.assistant_message,
    })

    // Update signals if any
    if (response.updated_signals.length > 0) {
      signals.value = [...signals.value, ...response.updated_signals]
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

onMounted(() => {
  initializeChat()
})
</script>

<template>
  <div class="app">
    <header class="header">
      <h1>Travel AI Agent</h1>
      <p>嗜好学習モード</p>
    </header>

    <main class="main">
      <div class="chat-container">
        <div class="messages" ref="messagesContainer">
          <div
            v-for="(message, index) in messages"
            :key="index"
            :class="['message', message.role]"
          >
            <div class="message-content">
              {{ message.content }}
            </div>
          </div>
          <div v-if="isLoading" class="message assistant">
            <div class="message-content loading">
              考え中...
            </div>
          </div>
        </div>

        <div class="input-area">
          <textarea
            v-model="inputMessage"
            @keydown="handleKeydown"
            placeholder="メッセージを入力..."
            :disabled="isLoading"
            rows="2"
          />
          <button @click="sendMessage" :disabled="isLoading || !inputMessage.trim()">
            送信
          </button>
        </div>
      </div>

      <aside class="sidebar">
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

.header h1 {
  margin: 0;
  font-size: 1.5rem;
}

.header p {
  margin: 0.25rem 0 0;
  opacity: 0.8;
  font-size: 0.9rem;
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

.no-signals {
  color: #7f8c8d;
  font-size: 0.9rem;
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
</style>
