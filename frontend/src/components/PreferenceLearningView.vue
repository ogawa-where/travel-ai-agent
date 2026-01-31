<script setup lang="ts">
import { ref, nextTick, onMounted, watch } from 'vue'
import { api } from '../lib/api'
import { getErrorMessage } from '../lib/errors'
import type { User, PreferenceSignal, ChatResponse } from '../lib/api'

interface Props {
  user: User | null
}

interface Emits {
  (e: 'preferences-updated', signals: PreferenceSignal[]): void
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

// IME変換状態を追跡
const handleCompositionStart = () => {
  isComposing.value = true
}

const handleCompositionEnd = () => {
  // 変換確定直後のEnterキーを誤検知しないよう遅延
  setTimeout(() => {
    isComposing.value = false
  }, 200)
}

// キーボードイベント処理
const handleKeydown = (event: KeyboardEvent) => {
  if (event.key !== 'Enter') return

  // Shift+Enter: 改行（デフォルト動作を許可）
  if (event.shiftKey) return

  // それ以外のEnter: すべてブロック
  event.preventDefault()

  // Ctrl+Enter または Cmd+Enter かつ IME変換中でない場合のみ送信
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
    const response: ChatResponse = await api.sendMessage(
      props.user.id,
      userMessage,
      sessionId.value || undefined
    )

    sessionId.value = response.session_id
    messages.value.push({
      role: 'assistant',
      content: response.assistant_message,
    })
    await scrollToBottom()

    // 嗜好シグナルが更新されたらイベントを発火
    if (response.updated_signals && response.updated_signals.length > 0) {
      emit('preferences-updated', response.updated_signals)
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

// ユーザーが変わったらチャットを初期化
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
    <div class="view-header">
      <h2>嗜好学習モード</h2>
      <p>旅行の好みを教えてください。学習した内容は旅行プランに反映されます。</p>
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
          @keydown="handleKeydown"
          @compositionstart="handleCompositionStart"
          @compositionend="handleCompositionEnd"
          placeholder="旅行の好みを教えてください... (⌘/Ctrl+Enterで送信)"
          :disabled="isLoading || !user"
          rows="1"
        ></textarea>
        <button
          type="button"
          @click="sendMessage"
          :disabled="!inputMessage.trim() || isLoading || !user"
          class="send-btn"
        >
          送信
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.preference-learning-view {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.view-header {
  padding: 1rem 1.5rem;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border-radius: 12px 12px 0 0;
}

.view-header h2 {
  margin: 0 0 0.25rem;
  font-size: 1.1rem;
}

.view-header p {
  margin: 0;
  font-size: 0.8rem;
  opacity: 0.9;
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
  background: #667eea;
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
  border-color: #667eea;
}

.send-btn {
  padding: 0 20px;
  background: #667eea;
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 0.9rem;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s;
}

.send-btn:hover:not(:disabled) {
  background: #5a67d8;
}

.send-btn:disabled {
  background: #a0aec0;
  cursor: not-allowed;
}
</style>
