<script setup lang="ts">
import { ref, nextTick, watch } from 'vue'

type AppMode = 'preference' | 'travel'

interface Message {
  role: 'user' | 'assistant'
  content: string
}

const props = defineProps<{
  messages: Message[]
  isLoading: boolean
  currentMode: AppMode
}>()

const emit = defineEmits<{
  sendMessage: [message: string]
}>()

const inputMessage = ref('')
const messagesContainer = ref<HTMLElement | null>(null)

const scrollToBottom = async () => {
  await nextTick()
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

const handleSend = () => {
  if (!inputMessage.value.trim() || props.isLoading) return
  emit('sendMessage', inputMessage.value.trim())
  inputMessage.value = ''
}

const handleKeydown = (event: KeyboardEvent) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    handleSend()
  }
}

const placeholderText = () => {
  return props.currentMode === 'travel'
    ? '旅行の希望を入力... (例: 来月、京都に2泊3日で一人旅したい)'
    : 'メッセージを入力...'
}

const loadingText = () => {
  return props.currentMode === 'travel' ? 'プラン作成中...' : '考え中...'
}

// メッセージが追加されたらスクロール
watch(() => props.messages.length, scrollToBottom)
</script>

<template>
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
          {{ loadingText() }}
        </div>
      </div>
    </div>

    <div class="input-area">
      <textarea
        v-model="inputMessage"
        @keydown="handleKeydown"
        :placeholder="placeholderText()"
        :disabled="isLoading"
        rows="2"
      />
      <button @click="handleSend" :disabled="isLoading || !inputMessage.trim()">
        送信
      </button>
    </div>
  </div>
</template>

<style scoped>
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
</style>
