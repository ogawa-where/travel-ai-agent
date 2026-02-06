<script setup lang="ts">
import { ref, nextTick, onMounted, watch } from 'vue'
import { api } from '../lib/api'
import { getErrorMessage } from '../lib/errors'
import type { User, PreferenceSignal } from '../lib/api'

interface Props {
  user: User | null
}

interface Emits {
  (e: 'preferences-updated', signals: PreferenceSignal[]): void
  (e: 'back-to-select'): void
  (e: 'go-to-planning'): void
}

interface Message {
  role: 'user' | 'assistant'
  content: string
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const sessionId = ref<string | null>(null)
const messages = ref<Message[]>([])
const isLoading = ref(false)
const inputMessage = ref('')
const messagesContainer = ref<HTMLElement | null>(null)
const isInitialized = ref(false)
const isComposing = ref(false)

const handleCompositionStart = () => {
  isComposing.value = true
}

const handleCompositionEnd = () => {
  setTimeout(() => {
    isComposing.value = false
  }, 200)
}

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
    sendMessage()
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

const initializeChat = async () => {
  if (!props.user || isInitialized.value) return

  try {
    isLoading.value = true
    const response = await api.startChat(props.user.id)
    sessionId.value = response.session_id
    messages.value = [{
      role: 'assistant',
      content: response.assistant_message,
    }]
    isInitialized.value = true
    await scrollToBottom()
  } catch (error) {
    console.error('Failed to initialize preference learning chat:', error)
    messages.value = [{
      role: 'assistant',
      content: `チャットの初期化に失敗しました。\n${getErrorMessage(error)}`,
    }]
  } finally {
    isLoading.value = false
  }
}

const isStreaming = ref(false)
const streamingMessageIndex = ref(-1)

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
    isStreaming.value = true

    messages.value.push({
      role: 'assistant',
      content: '',
    })
    streamingMessageIndex.value = messages.value.length - 1
    await scrollToBottom()

    await api.sendMessageStream(
      props.user.id,
      userMessage,
      sessionId.value || undefined,
      (content: string) => {
        if (streamingMessageIndex.value >= 0) {
          messages.value[streamingMessageIndex.value].content += content
          scrollToBottom()
        }
      },
      (signals) => {
        if (signals && signals.length > 0) {
          emit('preferences-updated', signals)
        }
      },
      (newSessionId: string) => {
        sessionId.value = newSessionId
        isStreaming.value = false
        streamingMessageIndex.value = -1
      },
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
    console.error('Failed to send message:', error)
    if (streamingMessageIndex.value >= 0) {
      messages.value[streamingMessageIndex.value].content = `エラー: ${getErrorMessage(error)}`
    } else {
      messages.value.push({
        role: 'assistant',
        content: `エラー: ${getErrorMessage(error)}`,
      })
    }
    await scrollToBottom()
    isStreaming.value = false
    streamingMessageIndex.value = -1
  } finally {
    isLoading.value = false
  }
}

watch(() => props.user, (newUser) => {
  if (newUser && !isInitialized.value) {
    initializeChat()
  }
}, { immediate: true })

onMounted(() => {
  if (props.user && !isInitialized.value) {
    initializeChat()
  }
})
</script>

<template>
  <div class="preference-learning-view">
    <!-- 左サイドバー -->
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
              <path d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z"/>
            </svg>
          </div>
          <h2>嗜好学習</h2>
          <p class="mode-subtitle">Preference Learning</p>
        </div>

        <div class="info-section">
          <h3>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"/>
              <line x1="12" y1="16" x2="12" y2="12"/>
              <line x1="12" y1="8" x2="12.01" y2="8"/>
            </svg>
            このモードについて
          </h3>
          <p>
            AIとの自然な対話を通じて、あなたの旅行の好みを学習します。
            食事、アクティビティ、宿泊施設など、様々な観点から好みを把握します。
          </p>
        </div>

        <div class="tips-section">
          <h3>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
            </svg>
            話題の例
          </h3>
          <ul>
            <li>好きな料理・苦手な食べ物</li>
            <li>旅行のペース（ゆっくり or アクティブ）</li>
            <li>興味のあるアクティビティ</li>
            <li>宿泊施設の好み</li>
            <li>予算感・旅行スタイル</li>
          </ul>
        </div>
      </div>

      <div class="sidebar-footer">
        <button class="action-btn" @click="$emit('go-to-planning')">
          <span>旅行企画へ進む</span>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="5" y1="12" x2="19" y2="12"/>
            <polyline points="12 5 19 12 12 19"/>
          </svg>
        </button>
      </div>
    </aside>

    <!-- メインチャットエリア -->
    <main class="chat-main">
      <div class="chat-header">
        <div class="chat-title">
          <h3>AIとの対話</h3>
          <p>旅行の好みについて教えてください</p>
        </div>
        <div class="chat-status" :class="{ active: isLoading }">
          <span class="status-dot"></span>
          <span>{{ isLoading ? '応答中...' : 'オンライン' }}</span>
        </div>
      </div>

      <div class="messages-container" ref="messagesContainer">
        <div class="messages-wrapper">
          <div
            v-for="(message, index) in messages"
            :key="index"
            :class="['message', message.role]"
          >
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
            </div>
          </div>

          <div v-if="isLoading && !isStreaming" class="message assistant">
            <div class="message-avatar">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
              </svg>
            </div>
            <div class="message-content">
              <div class="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="input-area">
        <div class="input-container">
          <textarea
            v-model="inputMessage"
            @keydown="handleKeydown"
            @input="autoResizeTextarea"
            @compositionstart="handleCompositionStart"
            @compositionend="handleCompositionEnd"
            placeholder="旅行の好みを教えてください..."
            :disabled="isLoading || !user"
            rows="1"
          ></textarea>
          <div class="input-actions">
            <span class="input-hint">⌘ + Enter で送信</span>
            <button
              type="button"
              @click="sendMessage"
              :disabled="!inputMessage.trim() || isLoading || !user"
              class="send-btn"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="22" y1="2" x2="11" y2="13"/>
                <polygon points="22 2 15 22 11 13 2 9 22 2"/>
              </svg>
            </button>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;600&family=Montserrat:wght@300;400;500;600&display=swap');

.preference-learning-view {
  display: flex;
  height: 100%;
  min-height: 600px;
}

/* サイドバー */
.sidebar {
  width: 320px;
  display: flex;
  flex-direction: column;
  background: rgba(102, 126, 234, 0.03);
  border-right: 1px solid rgba(102, 126, 234, 0.1);
  flex-shrink: 0;
}

.sidebar-header {
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid rgba(102, 126, 234, 0.08);
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
  border-bottom: 1px solid rgba(102, 126, 234, 0.1);
  margin-bottom: 1.5rem;
}

.mode-icon {
  width: 60px;
  height: 60px;
  margin: 0 auto 1rem;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.15) 0%, rgba(118, 75, 162, 0.15) 100%);
  border-radius: 16px;
  color: #667eea;
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

.info-section,
.tips-section {
  margin-bottom: 1.5rem;
}

.info-section h3,
.tips-section h3 {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-family: 'Montserrat', sans-serif;
  font-size: 0.8rem;
  font-weight: 600;
  color: #4a5568;
  margin: 0 0 0.75rem;
}

.info-section h3 svg,
.tips-section h3 svg {
  width: 16px;
  height: 16px;
  color: #667eea;
}

.info-section p {
  font-family: 'Montserrat', sans-serif;
  font-size: 0.85rem;
  line-height: 1.6;
  color: #718096;
  margin: 0;
}

.tips-section ul {
  margin: 0;
  padding: 0;
  list-style: none;
}

.tips-section li {
  font-family: 'Montserrat', sans-serif;
  font-size: 0.8rem;
  color: #718096;
  padding: 0.5rem 0;
  padding-left: 1.25rem;
  position: relative;
  border-bottom: 1px solid rgba(0, 0, 0, 0.04);
}

.tips-section li:last-child {
  border-bottom: none;
}

.tips-section li::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 6px;
  height: 6px;
  background: #667eea;
  border-radius: 50%;
  opacity: 0.5;
}

.sidebar-footer {
  padding: 1.25rem 1.5rem;
  border-top: 1px solid rgba(102, 126, 234, 0.08);
}

.action-btn {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  padding: 0.875rem 1.25rem;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
  border-radius: 12px;
  font-family: 'Montserrat', sans-serif;
  font-size: 0.9rem;
  font-weight: 600;
  color: white;
  cursor: pointer;
  transition: all 0.3s ease;
}

.action-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgba(102, 126, 234, 0.3);
}

.action-btn svg {
  width: 18px;
  height: 18px;
  transition: transform 0.3s ease;
}

.action-btn:hover svg {
  transform: translateX(4px);
}

/* メインチャットエリア */
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.25rem 2rem;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  background: rgba(255, 255, 255, 0.5);
}

.chat-title h3 {
  font-family: 'Montserrat', sans-serif;
  font-size: 1.1rem;
  font-weight: 600;
  color: #1a202c;
  margin: 0 0 0.2rem;
}

.chat-title p {
  font-family: 'Montserrat', sans-serif;
  font-size: 0.8rem;
  color: #718096;
  margin: 0;
}

.chat-status {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.4rem 0.75rem;
  background: rgba(72, 187, 120, 0.1);
  border-radius: 20px;
  font-family: 'Montserrat', sans-serif;
  font-size: 0.75rem;
  font-weight: 500;
  color: #276749;
}

.chat-status.active {
  background: rgba(102, 126, 234, 0.1);
  color: #5a67d8;
}

.status-dot {
  width: 8px;
  height: 8px;
  background: #48bb78;
  border-radius: 50%;
  animation: pulse-dot 2s infinite;
}

.chat-status.active .status-dot {
  background: #667eea;
}

@keyframes pulse-dot {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
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
  max-width: 85%;
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
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.15) 0%, rgba(118, 75, 162, 0.15) 100%);
  color: #667eea;
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
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
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
  border-color: rgba(102, 126, 234, 0.4);
  box-shadow: 0 0 0 4px rgba(102, 126, 234, 0.1);
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
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
  border-radius: 12px;
  color: white;
  cursor: pointer;
  transition: all 0.3s ease;
}

.send-btn:hover:not(:disabled) {
  transform: scale(1.05);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
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
