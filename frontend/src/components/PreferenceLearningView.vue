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

interface InlineSignal {
  category: string
  tag: string
  weight: number
  visible: boolean
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

// メッセージごとの学習済み嗜好
const messageSignals = ref<Map<number, InlineSignal[]>>(new Map())

const signalCategoryIcon: Record<string, string> = {
  likes: '♥',
  dislikes: '✗',
  experience_axis: '◈',
  constraints: '⚙',
}

const signalCategoryLabel: Record<string, string> = {
  likes: 'Like',
  dislikes: 'Dislike',
  experience_axis: 'Experience',
  constraints: 'Constraint',
}

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

const showScrollArrow = ref(false)

const scrollToBottom = async () => {
  await nextTick()
  if (messagesContainer.value) {
    messagesContainer.value.scrollTo({
      top: messagesContainer.value.scrollHeight,
      behavior: 'smooth',
    })
  }
}

const scrollToMessage = async (messageIndex: number) => {
  await nextTick()
  if (!messagesContainer.value) return
  const els = messagesContainer.value.querySelectorAll('.messages-wrapper > .message')
  const target = els[messageIndex] as HTMLElement | undefined
  if (target) {
    const containerTop = messagesContainer.value.getBoundingClientRect().top
    const targetTop = target.getBoundingClientRect().top
    const offset = targetTop - containerTop + messagesContainer.value.scrollTop
    messagesContainer.value.scrollTo({ top: offset, behavior: 'smooth' })
  }
}

const checkScrollArrow = () => {
  if (!messagesContainer.value) {
    showScrollArrow.value = false
    return
  }
  const { scrollTop, scrollHeight, clientHeight } = messagesContainer.value
  showScrollArrow.value = scrollHeight - scrollTop - clientHeight > 80
}

const onContainerScroll = () => {
  checkScrollArrow()
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
    await nextTick()
    checkScrollArrow()
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

  const userMessageIndex = messages.value.length
  messages.value.push({
    role: 'user',
    content: userMessage,
  })

  try {
    isLoading.value = true
    isStreaming.value = true

    messages.value.push({
      role: 'assistant',
      content: '',
    })
    streamingMessageIndex.value = messages.value.length - 1

    // ユーザーメッセージを画面トップにスクロール
    await scrollToMessage(userMessageIndex)

    await api.sendMessageStream(
      props.user.id,
      userMessage,
      sessionId.value || undefined,
      (content: string) => {
        if (streamingMessageIndex.value >= 0) {
          messages.value[streamingMessageIndex.value].content += content
          // 自動追尾しない。矢印の表示判定のみ更新
          nextTick(() => checkScrollArrow())
        }
      },
      (signals) => {
        if (signals && signals.length > 0) {
          emit('preferences-updated', signals)
          // メッセージにインライン表示用のシグナルを紐付け
          const msgIdx = streamingMessageIndex.value
          if (msgIdx >= 0) {
            const existing = messageSignals.value.get(msgIdx) || []
            const newSignals = signals.map(s => ({
              category: s.category,
              tag: s.tag,
              weight: s.weight,
              visible: false,
            }))
            messageSignals.value.set(msgIdx, [...existing, ...newSignals])
            // 時差で表示アニメーション
            newSignals.forEach((sig, i) => {
              setTimeout(() => { sig.visible = true }, (existing.length + i) * 150)
            })
          }
        }
      },
      (newSessionId: string) => {
        sessionId.value = newSessionId
        isStreaming.value = false
        streamingMessageIndex.value = -1
        nextTick(() => checkScrollArrow())
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
    isStreaming.value = false
    streamingMessageIndex.value = -1
  } finally {
    isLoading.value = false
    nextTick(() => checkScrollArrow())
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
    <!-- メインチャットエリア -->
    <main class="chat-main">
      <div class="chat-header">
        <div class="header-left">
          <button class="header-back-btn" @click="$emit('back-to-select')">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="15 18 9 12 15 6"/>
            </svg>
            <span>戻る</span>
          </button>
          <div class="header-divider"></div>
          <div class="header-title">
            <h3>嗜好学習</h3>
            <span class="header-subtitle">AIとの対話で好みを学習</span>
          </div>
        </div>
        <button class="header-planning-btn" @click="$emit('go-to-planning')">
          <span>旅行企画へ進む</span>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="9 18 15 12 9 6"/>
          </svg>
        </button>
      </div>

      <div class="messages-area">
      <div class="messages-container" ref="messagesContainer" @scroll="onContainerScroll">
        <div class="messages-wrapper">
          <div
            v-for="(message, index) in messages"
            :key="index"
            :class="['message', message.role, 'message-enter']"
            :style="{ animationDelay: index * 0.05 + 's' }"
          >
            <!-- アバターエリア（思考中はリング付き） -->
            <div class="avatar-area" :class="{ 'is-thinking': isStreaming && index === streamingMessageIndex && !message.content }">
              <template v-if="isStreaming && index === streamingMessageIndex && !message.content">
                <div class="avatar-ring ring-1"></div>
                <div class="avatar-ring ring-2"></div>
                <div class="avatar-ring ring-3"></div>
              </template>
              <div class="message-avatar">
                <template v-if="message.role === 'assistant'">
                  <img :src="'/ylab-logo.png'" alt="Ylab" class="avatar-logo" @error="($event.target as HTMLImageElement).style.display='none'" />
                  <svg class="avatar-logo-fallback" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                    <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
                  </svg>
                </template>
                <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                  <circle cx="12" cy="7" r="4"/>
                </svg>
              </div>
            </div>

            <div class="message-content">
              <div class="message-meta">
                <span class="message-sender">{{ message.role === 'assistant' ? 'Travel AI' : 'あなた' }}</span>
              </div>
              <!-- 思考中UI -->
              <div v-if="isStreaming && index === streamingMessageIndex && !message.content" class="thinking-card">
                <div class="thinking-flow">
                  <div class="thinking-flow-layer flow-1"></div>
                  <div class="thinking-flow-layer flow-2"></div>
                  <div class="thinking-flow-layer flow-3"></div>
                </div>
                <div class="thinking-body">
                  <span class="thinking-label">Thinking<span class="thinking-dots"><span>.</span><span>.</span><span>.</span></span></span>
                  <div class="thinking-shimmer-track"><div class="thinking-shimmer-bar"></div></div>
                </div>
              </div>
              <!-- 通常メッセージ -->
              <div v-else class="message-bubble">
                <div class="message-text" v-html="formatMessage(message.content)"></div>
              </div>
              <!-- 学習した嗜好シグナル（インライン表示） -->
              <div v-if="message.role === 'assistant' && messageSignals.get(index)?.length" class="learned-signals">
                <TransitionGroup name="signal">
                  <span
                    v-for="(sig, si) in messageSignals.get(index)"
                    :key="si"
                    :class="['signal-chip', sig.category, { 'signal-visible': sig.visible }]"
                  >
                    <span class="signal-icon">{{ signalCategoryIcon[sig.category] || '✦' }}</span>
                    <span class="signal-category">{{ signalCategoryLabel[sig.category] || 'Learned' }}</span>
                    <span class="signal-tag">{{ sig.tag }}</span>
                  </span>
                </TransitionGroup>
              </div>
            </div>
          </div>

          <!-- 初回ロード時の思考中（ストリーミング前） -->
          <div v-if="isLoading && !isStreaming" class="message assistant message-enter">
            <div class="avatar-area is-thinking">
              <div class="avatar-ring ring-1"></div>
              <div class="avatar-ring ring-2"></div>
              <div class="avatar-ring ring-3"></div>
              <div class="message-avatar">
                <img :src="'/ylab-logo.png'" alt="Ylab" class="avatar-logo" @error="($event.target as HTMLImageElement).style.display='none'" />
                <svg class="avatar-logo-fallback" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                  <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
                </svg>
              </div>
            </div>
            <div class="message-content">
              <div class="message-meta">
                <span class="message-sender">Travel AI</span>
              </div>
              <div class="thinking-card">
                <div class="thinking-flow">
                  <div class="thinking-flow-layer flow-1"></div>
                  <div class="thinking-flow-layer flow-2"></div>
                  <div class="thinking-flow-layer flow-3"></div>
                </div>
                <div class="thinking-body">
                  <span class="thinking-label">Thinking<span class="thinking-dots"><span>.</span><span>.</span><span>.</span></span></span>
                  <div class="thinking-shimmer-track"><div class="thinking-shimmer-bar"></div></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 下にスクロールする矢印 -->
      <Transition name="arrow-fade">
        <button
          v-if="showScrollArrow"
          class="scroll-arrow-btn"
          @click="scrollToBottom"
          aria-label="最下部へスクロール"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="6 9 12 15 18 9"/>
          </svg>
        </button>
      </Transition>
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
  flex-direction: column;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

/* メインチャットエリア */
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  min-width: 0;
}

/* ======== ヘッダー ======== */
.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 2rem;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  background: rgba(255, 255, 255, 0.5);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.header-back-btn {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.5rem 0.75rem 0.5rem 0.5rem;
  background: transparent;
  border: none;
  border-radius: 10px;
  font-family: 'Montserrat', sans-serif;
  font-size: 0.82rem;
  font-weight: 500;
  color: #718096;
  cursor: pointer;
  transition: all 0.2s ease;
  flex-shrink: 0;
}

.header-back-btn:hover {
  color: #4a5568;
  background: rgba(0, 0, 0, 0.04);
}

.header-back-btn svg {
  width: 18px;
  height: 18px;
  transition: transform 0.2s ease;
}

.header-back-btn:hover svg {
  transform: translateX(-2px);
}

.header-divider {
  width: 1px;
  height: 28px;
  background: rgba(0, 0, 0, 0.08);
  flex-shrink: 0;
}

.header-title h3 {
  font-family: 'Montserrat', sans-serif;
  font-size: 1.05rem;
  font-weight: 700;
  color: #1a202c;
  margin: 0;
  line-height: 1.2;
}

.header-subtitle {
  font-family: 'Montserrat', sans-serif;
  font-size: 0.72rem;
  font-weight: 400;
  color: #a0aec0;
  letter-spacing: 0.02em;
}

.header-planning-btn {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.55rem 1rem;
  background: transparent;
  border: 1.5px solid rgba(102, 126, 234, 0.3);
  border-radius: 10px;
  font-family: 'Montserrat', sans-serif;
  font-size: 0.82rem;
  font-weight: 600;
  color: #667eea;
  cursor: pointer;
  transition: all 0.25s ease;
  flex-shrink: 0;
  white-space: nowrap;
}

.header-planning-btn:hover {
  background: rgba(102, 126, 234, 0.06);
  border-color: rgba(102, 126, 234, 0.5);
  box-shadow: 0 2px 10px rgba(102, 126, 234, 0.12);
}

.header-planning-btn svg {
  width: 15px;
  height: 15px;
  transition: transform 0.25s ease;
  stroke: #667eea;
}

.header-planning-btn:hover svg {
  transform: translateX(2px);
}

/* ======== メッセージエリア ======== */
.messages-area {
  flex: 1;
  min-height: 0;
  position: relative;
  display: flex;
  flex-direction: column;
}

.messages-container {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 2rem 2rem;
}

/* 下スクロール矢印 */
.scroll-arrow-btn {
  position: absolute;
  bottom: 20px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 10;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(102, 126, 234, 0.2);
  border-radius: 50%;
  color: #667eea;
  cursor: pointer;
  transition: all 0.2s ease;
  box-shadow:
    0 4px 16px rgba(0, 0, 0, 0.08),
    0 0 0 1px rgba(102, 126, 234, 0.05);
}

.scroll-arrow-btn:hover {
  background: rgba(255, 255, 255, 0.95);
  border-color: rgba(102, 126, 234, 0.4);
  box-shadow:
    0 6px 20px rgba(102, 126, 234, 0.15),
    0 0 0 1px rgba(102, 126, 234, 0.1);
  transform: translateX(-50%) translateY(-2px);
}

.scroll-arrow-btn svg {
  width: 20px;
  height: 20px;
  animation: arrow-bounce 2s ease-in-out infinite;
}

@keyframes arrow-bounce {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(3px); }
}

/* 矢印のフェードイン/アウト */
.arrow-fade-enter-active {
  transition: all 0.25s ease-out;
}

.arrow-fade-leave-active {
  transition: all 0.2s ease-in;
}

.arrow-fade-enter-from {
  opacity: 0;
  transform: translateX(-50%) translateY(10px);
}

.arrow-fade-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(10px);
}

.messages-wrapper {
  display: flex;
  flex-direction: column;
  gap: 1.75rem;
  max-width: 800px;
  margin: 0 auto;
}

/* メッセージ入場アニメーション */
.message-enter {
  animation: msg-slide-in 0.35s ease-out both;
}

@keyframes msg-slide-in {
  from {
    opacity: 0;
    transform: translateY(12px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
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

/* アバターエリア（リングのコンテナ） */
.avatar-area {
  position: relative;
  width: 44px;
  height: 44px;
  flex-shrink: 0;
  align-self: flex-start;
}

.message-avatar {
  position: relative;
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  flex-shrink: 0;
  overflow: hidden;
  z-index: 2;
}

.message.assistant .message-avatar {
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.12) 0%, rgba(118, 75, 162, 0.12) 100%);
  border: 1px solid rgba(102, 126, 234, 0.1);
}

.is-thinking .message-avatar {
  box-shadow: 0 0 12px rgba(102, 126, 234, 0.25);
}

.avatar-logo {
  width: 30px;
  height: 30px;
  object-fit: contain;
}

.avatar-logo-fallback {
  width: 22px;
  height: 22px;
  color: #667eea;
}

.avatar-logo:not([style*="display: none"]) + .avatar-logo-fallback {
  display: none;
}

.message.user .message-avatar {
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.08) 0%, rgba(118, 75, 162, 0.08) 100%);
  border: 1px solid rgba(102, 126, 234, 0.08);
  color: #667eea;
}

.message-avatar svg {
  width: 22px;
  height: 22px;
}

/* アバター周囲のパルスリング */
.avatar-ring {
  position: absolute;
  inset: -3px;
  border-radius: 50%;
  border: 1.5px solid rgba(102, 126, 234, 0.3);
  z-index: 1;
}

.ring-1 {
  animation: ring-pulse 2.4s ease-out infinite;
}

.ring-2 {
  animation: ring-pulse 2.4s ease-out 0.8s infinite;
}

.ring-3 {
  animation: ring-pulse 2.4s ease-out 1.6s infinite;
}

@keyframes ring-pulse {
  0% {
    transform: scale(1);
    opacity: 0.6;
  }
  100% {
    transform: scale(2);
    opacity: 0;
  }
}

.message-content {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
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
  color: #718096;
  letter-spacing: 0.02em;
}

/* メッセージバブル */
.message-bubble {
  position: relative;
}

.message-text {
  padding: 1.1rem 1.4rem;
  border-radius: 20px;
  font-family: 'Montserrat', sans-serif;
  font-size: 0.92rem;
  line-height: 1.75;
  word-break: break-word;
}

.message.assistant .message-text {
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  color: #2d3748;
  border: 1px solid rgba(102, 126, 234, 0.1);
  border-radius: 4px 20px 20px 20px;
  box-shadow:
    0 1px 3px rgba(102, 126, 234, 0.06),
    0 4px 16px rgba(102, 126, 234, 0.04);
  transition: box-shadow 0.3s ease;
}

.message.assistant .message-text:hover {
  box-shadow:
    0 2px 6px rgba(102, 126, 234, 0.1),
    0 8px 24px rgba(102, 126, 234, 0.06);
}

.message.user .message-text {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border-radius: 20px 4px 20px 20px;
  box-shadow:
    0 2px 8px rgba(102, 126, 234, 0.2),
    0 4px 20px rgba(118, 75, 162, 0.15);
  transition: box-shadow 0.3s ease;
}

.message.user .message-text:hover {
  box-shadow:
    0 4px 12px rgba(102, 126, 234, 0.3),
    0 8px 28px rgba(118, 75, 162, 0.2);
}

.message.user .message-sender {
  text-align: right;
}

/* ======== 学習シグナル（インライン） ======== */
.learned-signals {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
  padding-left: 2px;
}

.signal-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 12px 4px 8px;
  border-radius: 20px;
  font-family: 'Montserrat', sans-serif;
  font-size: 0.75rem;
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  border: 1px solid rgba(102, 126, 234, 0.12);
  box-shadow: 0 1px 4px rgba(102, 126, 234, 0.06);
  opacity: 0;
  transform: translateY(6px) scale(0.92);
  transition: opacity 0.35s cubic-bezier(0.22, 1, 0.36, 1),
              transform 0.35s cubic-bezier(0.22, 1, 0.36, 1),
              box-shadow 0.25s ease;
}

.signal-chip.signal-visible {
  opacity: 1;
  transform: translateY(0) scale(1);
}

.signal-chip:hover {
  box-shadow: 0 2px 8px rgba(102, 126, 234, 0.14);
}

.signal-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  font-size: 0.6rem;
  flex-shrink: 0;
}

.signal-chip.likes .signal-icon {
  background: linear-gradient(135deg, #667eea, #a78bfa);
  color: white;
}

.signal-chip.dislikes .signal-icon {
  background: linear-gradient(135deg, #fda4af, #f472b6);
  color: white;
}

.signal-chip.experience_axis .signal-icon {
  background: linear-gradient(135deg, #818cf8, #764ba2);
  color: white;
}

.signal-chip.constraints .signal-icon {
  background: linear-gradient(135deg, #fbbf24, #f59e0b);
  color: white;
}

.signal-category {
  font-weight: 500;
  opacity: 0.45;
  font-size: 0.65rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.signal-tag {
  font-weight: 600;
  color: #2d3748;
}

.signal-chip.likes { border-color: rgba(102, 126, 234, 0.18); }
.signal-chip.dislikes { border-color: rgba(244, 114, 182, 0.18); }
.signal-chip.experience_axis { border-color: rgba(129, 140, 248, 0.18); }
.signal-chip.constraints { border-color: rgba(251, 191, 36, 0.18); }

/* signal transition group */
.signal-enter-active {
  transition: all 0.35s cubic-bezier(0.22, 1, 0.36, 1);
}

.signal-leave-active {
  transition: all 0.25s ease;
}

.signal-enter-from {
  opacity: 0;
  transform: translateY(8px) scale(0.9);
}

.signal-leave-to {
  opacity: 0;
  transform: scale(0.9);
}

/* ======== 思考中インジケーター ======== */
.thinking-card {
  position: relative;
  padding: 1rem 1.4rem;
  background: rgba(255, 255, 255, 0.55);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid rgba(102, 126, 234, 0.12);
  border-radius: 18px;
  border-top-left-radius: 4px;
  box-shadow:
    0 4px 24px rgba(102, 126, 234, 0.08),
    0 1px 4px rgba(0, 0, 0, 0.03);
  overflow: hidden;
}

/* 流れるグラデーション背景 */
.thinking-flow {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.thinking-flow-layer {
  position: absolute;
  inset: 0;
  border-radius: inherit;
}

.flow-1 {
  background: linear-gradient(
    90deg,
    transparent 0%,
    rgba(102, 126, 234, 0.1) 20%,
    rgba(118, 75, 162, 0.14) 40%,
    rgba(102, 126, 234, 0.1) 60%,
    transparent 100%
  );
  background-size: 200% 100%;
  animation: flow-sweep 3s ease-in-out infinite;
}

.flow-2 {
  background: linear-gradient(
    90deg,
    transparent 0%,
    rgba(118, 75, 162, 0.08) 30%,
    rgba(102, 126, 234, 0.12) 50%,
    rgba(118, 75, 162, 0.08) 70%,
    transparent 100%
  );
  background-size: 200% 100%;
  animation: flow-sweep 3s ease-in-out 1s infinite;
}

.flow-3 {
  background: linear-gradient(
    90deg,
    transparent 0%,
    rgba(102, 126, 234, 0.06) 25%,
    rgba(167, 139, 250, 0.1) 50%,
    rgba(102, 126, 234, 0.06) 75%,
    transparent 100%
  );
  background-size: 200% 100%;
  animation: flow-sweep 3s ease-in-out 2s infinite;
}

@keyframes flow-sweep {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* カード内コンテンツ */
.thinking-body {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.thinking-label {
  font-family: 'Montserrat', sans-serif;
  font-size: 0.85rem;
  font-weight: 600;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  white-space: nowrap;
  letter-spacing: 0.04em;
}

.thinking-dots span {
  -webkit-text-fill-color: #667eea;
  animation: dot-fade 1.4s ease-in-out infinite;
}

.thinking-dots span:nth-child(1) { animation-delay: 0s; }
.thinking-dots span:nth-child(2) { animation-delay: 0.2s; }
.thinking-dots span:nth-child(3) { animation-delay: 0.4s; }

@keyframes dot-fade {
  0%, 60%, 100% { opacity: 0; }
  30% { opacity: 1; }
}

/* シマーバー */
.thinking-shimmer-track {
  width: 120px;
  height: 3px;
  background: rgba(102, 126, 234, 0.1);
  border-radius: 2px;
  overflow: hidden;
}

.thinking-shimmer-bar {
  width: 100%;
  height: 100%;
  background: linear-gradient(
    90deg,
    transparent 0%,
    rgba(102, 126, 234, 0.5) 25%,
    rgba(118, 75, 162, 0.7) 50%,
    rgba(102, 126, 234, 0.5) 75%,
    transparent 100%
  );
  background-size: 200% 100%;
  animation: shimmer 1.8s ease-in-out infinite;
  border-radius: 2px;
}

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* ======== 入力エリア ======== */
.input-area {
  padding: 1.25rem 2rem 1.5rem;
  flex-shrink: 0;
}

.input-container {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.85rem 1.1rem;
  background: rgba(255, 255, 255, 0.85);
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 18px;
  transition: all 0.3s ease;
  max-width: 800px;
  margin: 0 auto;
}

.input-container:focus-within {
  border-color: rgba(102, 126, 234, 0.4);
  box-shadow: 0 0 0 4px rgba(102, 126, 234, 0.08);
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
  width: 46px;
  height: 46px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
  border-radius: 14px;
  color: white;
  cursor: pointer;
  transition: all 0.3s ease;
}

.send-btn:hover:not(:disabled) {
  transform: scale(1.05);
  box-shadow: 0 4px 14px rgba(102, 126, 234, 0.35);
}

.send-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.send-btn svg {
  width: 20px;
  height: 20px;
}

/* ======== レスポンシブ ======== */
@media (max-width: 600px) {
  .chat-header {
    padding: 0.75rem 1rem;
  }

  .header-title h3 {
    font-size: 0.9rem;
  }

  .header-subtitle {
    display: none;
  }

  .header-divider {
    display: none;
  }

  .header-back-btn span {
    display: none;
  }

  .header-back-btn {
    padding: 0.4rem;
  }

  .header-planning-btn {
    font-size: 0.75rem;
    padding: 0.45rem 0.7rem;
  }

  .messages-container {
    padding: 1.25rem 1rem;
  }

  .input-area {
    padding: 1rem 1rem 1.25rem;
  }

  .input-hint {
    display: none;
  }
}
</style>
