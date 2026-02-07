<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '../lib/api'
import type { LoginResponse } from '../lib/api'

const emit = defineEmits<{
  login: [response: LoginResponse]
}>()

const username = ref('')
const isLoading = ref(false)
const error = ref<string | null>(null)

// スクロール・アニメーション関連
const loginSection = ref<HTMLElement | null>(null)
const titleChars = 'Travel AI Agent'.split('')
const animateTitle = ref(false)
const showSubtitle = ref(false)
const showScrollHint = ref(false)
const showLoginCard = ref(false)

// タイトル全文字の出現完了までの時間を計算
const titleDuration = 300 + titleChars.length * 80 + 1200 // start + stagger + animation

onMounted(() => {
  setTimeout(() => { animateTitle.value = true }, 300)
  setTimeout(() => { showSubtitle.value = true }, titleDuration)
  setTimeout(() => { showScrollHint.value = true }, titleDuration + 800)

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) showLoginCard.value = true
      })
    },
    { threshold: 0.3 }
  )
  if (loginSection.value) observer.observe(loginSection.value)
})

const scrollToLogin = () => {
  loginSection.value?.scrollIntoView({ behavior: 'smooth' })
}

const handleWheel = (e: WheelEvent) => {
  if (e.deltaY > 0) {
    scrollToLogin()
  }
}

const handleSubmit = async () => {
  const trimmedUsername = username.value.trim()

  if (!trimmedUsername) {
    error.value = 'ユーザー名を入力してください'
    return
  }

  if (trimmedUsername.length > 50) {
    error.value = 'ユーザー名は50文字以内にしてください'
    return
  }

  try {
    isLoading.value = true
    error.value = null
    const response = await api.login(trimmedUsername)
    emit('login', response)
  } catch (e) {
    console.error('Login failed:', e)
    error.value = 'ログインに失敗しました。もう一度お試しください。'
  } finally {
    isLoading.value = false
  }
}

const handleKeydown = (e: KeyboardEvent) => {
  if (e.isComposing) return
  if (e.key === 'Enter' && !isLoading.value) {
    handleSubmit()
  }
}
</script>

<template>
  <div class="login-screen">
    <!-- 動画背景 -->
    <video
      class="video-background"
      autoplay
      muted
      loop
      playsinline
    >
      <source src="/login-bg.mp4" type="video/mp4" />
    </video>
    <div class="video-overlay"></div>

    <!-- スクロールコンテナ -->
    <div class="scroll-container">
      <!-- セクション1: 筆記体タイトルスプラッシュ -->
      <section class="splash-section" @wheel="handleWheel">
        <div class="splash-content">
          <h1 class="cursive-title">
            <span
              v-for="(char, i) in titleChars"
              :key="i"
              class="title-char"
              :class="{ animate: animateTitle }"
              :style="{ animationDelay: `${i * 80}ms` }"
            >{{ char === ' ' ? '\u00A0' : char }}</span>
          </h1>
          <div class="subtitle-area" :class="{ 'show': showSubtitle }">
            <span class="subtitle-line"></span>
            <p class="subtitle">Your Journey, Personalized</p>
            <span class="subtitle-line"></span>
          </div>
        </div>

        <!-- スクロールインジケーター -->
        <div class="scroll-indicator" :class="{ 'show': showScrollHint }" @click="scrollToLogin">
          <span class="scroll-text">Scroll</span>
          <div class="scroll-arrow">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="6 9 12 15 18 9"/>
            </svg>
          </div>
        </div>
      </section>

      <!-- セクション2: ログイン -->
      <section class="login-section" ref="loginSection">
        <!-- 装飾パーティクル -->
        <div class="particles">
          <div class="particle"></div>
          <div class="particle"></div>
          <div class="particle"></div>
          <div class="particle"></div>
          <div class="particle"></div>
        </div>

        <div class="login-wrapper" :class="{ 'show': showLoginCard }">
          <!-- ウェルカムテキスト -->
          <div class="welcome-text">
            <h2>Welcome</h2>
            <p>あなただけの旅が始まります</p>
          </div>

          <!-- ログインカード -->
          <div class="login-container">
            <div class="card-glow"></div>

            <div class="login-header">
              <div class="header-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                  <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
                </svg>
              </div>
              <h1>Travel AI Agent</h1>
            </div>

            <div class="login-form">
              <div class="form-group">
                <div class="input-wrapper">
                  <div class="input-icon">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                      <circle cx="12" cy="7" r="4"/>
                    </svg>
                  </div>
                  <input
                    id="username"
                    v-model="username"
                    type="text"
                    placeholder="ユーザー名を入力"
                    :disabled="isLoading"
                    @keydown="handleKeydown"
                  />
                  <div class="input-highlight"></div>
                </div>
                <p class="hint">既存のユーザー名でログイン、または新規作成されます</p>
              </div>

              <div v-if="error" class="error-message">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <circle cx="12" cy="12" r="10"/>
                  <line x1="12" y1="8" x2="12" y2="12"/>
                  <line x1="12" y1="16" x2="12.01" y2="16"/>
                </svg>
                {{ error }}
              </div>

              <button
                class="login-btn"
                :disabled="isLoading || !username.trim()"
                @click="handleSubmit"
              >
                <span v-if="isLoading" class="spinner"></span>
                <template v-else>
                  <span>ログイン</span>
                  <svg class="arrow-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="5" y1="12" x2="19" y2="12"/>
                    <polyline points="12 5 19 12 12 19"/>
                  </svg>
                </template>
              </button>
            </div>

            <div class="login-footer">
              <div class="divider">
                <span class="divider-line"></span>
                <span class="divider-text">INFO</span>
                <span class="divider-line"></span>
              </div>
              <p>パスワードなしでログインできます</p>
            </div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Dancing+Script:wght@400;700&family=Noto+Sans+JP:wght@400;500&family=Playfair+Display:wght@400;700&family=Montserrat:wght@300;400;500;600&display=swap');

.login-screen {
  position: relative;
  width: 100%;
  height: 100vh;
  overflow: hidden;
}

.video-background {
  position: fixed;
  top: 50%;
  left: 50%;
  min-width: 115%;
  min-height: 115%;
  width: auto;
  height: auto;
  /* 拡大して右下にオフセット（ウォーターマークを画面外に） */
  transform: translate(-55%, -48%);
  object-fit: cover;
  z-index: 0;
}

.video-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: linear-gradient(
    135deg,
    rgba(102, 126, 234, 0.25) 0%,
    rgba(118, 75, 162, 0.25) 100%
  );
  z-index: 1;
}

/* スクロールコンテナ */
.scroll-container {
  position: relative;
  z-index: 10;
  height: 100vh;
  overflow-y: auto;
  scroll-snap-type: y mandatory;
  scroll-behavior: smooth;
}

.splash-section,
.login-section {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  scroll-snap-align: start;
  position: relative;
}

/* スプラッシュセクション */
.splash-section {
  flex-direction: column;
}

.splash-content {
  text-align: center;
}

/* 筆記体タイトル */
.cursive-title {
  font-family: 'Dancing Script', cursive;
  font-size: 8rem;
  font-weight: 700;
  color: white;
  margin: 0;
  line-height: 1.1;
}

.title-char {
  display: inline-block;
  opacity: 0;
  filter: blur(12px);
  transform: translateY(8px);
}

.title-char.animate {
  animation: char-appear 1.2s cubic-bezier(0.16, 1, 0.3, 1) forwards;
}

@keyframes char-appear {
  0% {
    opacity: 0;
    filter: blur(12px);
    transform: translateY(8px);
  }
  60% {
    opacity: 0.8;
    filter: blur(3px);
    transform: translateY(-2px);
  }
  100% {
    opacity: 1;
    filter: blur(0);
    transform: translateY(0);
    text-shadow: 0 4px 30px rgba(0, 0, 0, 0.3), 0 1px 3px rgba(0, 0, 0, 0.2);
  }
}

/* サブタイトル */
.subtitle-area {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 1.5rem;
  margin-top: 1.5rem;
  opacity: 0;
  transform: translateY(15px);
  transition: opacity 1.4s cubic-bezier(0.16, 1, 0.3, 1), transform 1.4s cubic-bezier(0.16, 1, 0.3, 1);
}

.subtitle-area.show {
  opacity: 1;
  transform: translateY(0);
}

.subtitle-line {
  width: 60px;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.6), transparent);
}

.subtitle {
  font-family: 'Montserrat', sans-serif;
  font-size: 1.2rem;
  font-weight: 300;
  color: rgba(255, 255, 255, 0.85);
  margin: 0;
  letter-spacing: 4px;
  text-transform: uppercase;
}

/* スクロールインジケーター */
.scroll-indicator {
  position: absolute;
  bottom: 3rem;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
  opacity: 0;
  transform: translateY(20px);
  transition: opacity 1.4s cubic-bezier(0.16, 1, 0.3, 1), transform 1.4s cubic-bezier(0.16, 1, 0.3, 1);
}

.scroll-indicator.show {
  opacity: 1;
  transform: translateY(0);
}

.scroll-text {
  font-family: 'Montserrat', sans-serif;
  font-size: 0.75rem;
  font-weight: 400;
  color: rgba(255, 255, 255, 0.6);
  letter-spacing: 3px;
  text-transform: uppercase;
}

.scroll-arrow {
  width: 24px;
  height: 24px;
  color: rgba(255, 255, 255, 0.6);
  animation: bounce-arrow 2s ease-in-out infinite;
}

.scroll-arrow svg {
  width: 100%;
  height: 100%;
}

@keyframes bounce-arrow {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(8px); }
}

/* ログインセクション */
.login-section {
  padding: 2rem;
  flex-direction: column;
}

/* パーティクル装飾 */
.particles {
  position: absolute;
  width: 100%;
  height: 100%;
  overflow: hidden;
  pointer-events: none;
}

.particle {
  position: absolute;
  width: 6px;
  height: 6px;
  background: rgba(255, 255, 255, 0.3);
  border-radius: 50%;
  animation: float 15s infinite;
}

.particle:nth-child(1) { left: 10%; top: 20%; animation-delay: 0s; animation-duration: 12s; }
.particle:nth-child(2) { left: 80%; top: 30%; animation-delay: 2s; animation-duration: 18s; }
.particle:nth-child(3) { left: 30%; top: 70%; animation-delay: 4s; animation-duration: 14s; }
.particle:nth-child(4) { left: 70%; top: 80%; animation-delay: 1s; animation-duration: 16s; }
.particle:nth-child(5) { left: 50%; top: 50%; animation-delay: 3s; animation-duration: 20s; }

@keyframes float {
  0%, 100% { transform: translateY(0) rotate(0deg); opacity: 0.3; }
  50% { transform: translateY(-30px) rotate(180deg); opacity: 0.8; }
}

/* ログインラッパー */
.login-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2rem;
  opacity: 0;
  transform: translateY(60px) scale(0.95);
  transition: all 1s cubic-bezier(0.16, 1, 0.3, 1);
}

.login-wrapper.show {
  opacity: 1;
  transform: translateY(0) scale(1);
}

/* ウェルカムテキスト */
.welcome-text {
  text-align: center;
}

.welcome-text h2 {
  font-family: 'Playfair Display', serif;
  font-size: 3rem;
  font-weight: 400;
  color: white;
  margin: 0;
  letter-spacing: 8px;
  text-transform: uppercase;
  text-shadow: 0 2px 20px rgba(0, 0, 0, 0.3);
}

.welcome-text p {
  font-family: 'Montserrat', sans-serif;
  font-size: 1rem;
  font-weight: 300;
  color: rgba(255, 255, 255, 0.8);
  margin: 0.75rem 0 0;
  letter-spacing: 3px;
}

/* ログインカード */
.login-container {
  position: relative;
  background: rgba(255, 255, 255, 0.08);
  backdrop-filter: blur(30px);
  -webkit-backdrop-filter: blur(30px);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 28px;
  width: 100%;
  max-width: 440px;
  overflow: hidden;
}

/* カードの光るエフェクト */
.card-glow {
  position: absolute;
  top: -50%;
  left: -50%;
  width: 200%;
  height: 200%;
  background: conic-gradient(
    from 0deg,
    transparent,
    rgba(102, 126, 234, 0.15),
    transparent,
    rgba(118, 75, 162, 0.15),
    transparent
  );
  animation: rotate-glow 8s linear infinite;
  pointer-events: none;
}

@keyframes rotate-glow {
  100% { transform: rotate(360deg); }
}

.login-container::before {
  content: '';
  position: absolute;
  inset: 0;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 28px;
  z-index: 1;
}

.login-header {
  position: relative;
  z-index: 2;
  padding: 2.5rem 2rem 2rem;
  text-align: center;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.header-icon {
  width: 50px;
  height: 50px;
  margin: 0 auto 1rem;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.3), rgba(118, 75, 162, 0.3));
  border-radius: 14px;
  border: 1px solid rgba(255, 255, 255, 0.2);
}

.header-icon svg {
  width: 26px;
  height: 26px;
  color: white;
}

.login-header h1 {
  margin: 0;
  font-family: 'Playfair Display', serif;
  font-size: 1.6rem;
  font-weight: 700;
  color: white;
  letter-spacing: 1px;
}

.login-form {
  position: relative;
  z-index: 2;
  padding: 2rem;
}

.form-group {
  margin-bottom: 1.5rem;
}

.input-wrapper {
  position: relative;
}

.input-icon {
  position: absolute;
  left: 16px;
  top: 50%;
  transform: translateY(-50%);
  width: 20px;
  height: 20px;
  color: rgba(255, 255, 255, 0.5);
  pointer-events: none;
  transition: color 0.3s ease;
  z-index: 1;
}

.input-icon svg {
  width: 100%;
  height: 100%;
}

.form-group input {
  width: 100%;
  padding: 1.1rem 1.25rem 1.1rem 52px;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 14px;
  font-family: 'Montserrat', sans-serif;
  font-size: 1rem;
  color: white;
  transition: all 0.3s ease;
  box-sizing: border-box;
}

.form-group input::placeholder {
  color: rgba(255, 255, 255, 0.4);
}

.form-group input:focus {
  outline: none;
  background: rgba(255, 255, 255, 0.12);
  border-color: rgba(255, 255, 255, 0.4);
}

.form-group input:focus + .input-highlight {
  opacity: 1;
}

.form-group input:focus ~ .input-icon,
.input-wrapper:focus-within .input-icon {
  color: rgba(255, 255, 255, 0.9);
}

.input-highlight {
  position: absolute;
  inset: -2px;
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.5), rgba(118, 75, 162, 0.5));
  border-radius: 16px;
  opacity: 0;
  transition: opacity 0.3s ease;
  z-index: -1;
  filter: blur(8px);
}

.form-group .hint {
  margin: 0.75rem 0 0;
  padding-left: 4px;
  font-family: 'Montserrat', sans-serif;
  font-size: 0.8rem;
  color: rgba(255, 255, 255, 0.5);
}

.error-message {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 1rem;
  padding: 1rem;
  background: rgba(245, 101, 101, 0.15);
  border: 1px solid rgba(245, 101, 101, 0.3);
  border-radius: 12px;
  color: #ffb4b4;
  font-family: 'Montserrat', sans-serif;
  font-size: 0.875rem;
}

.error-message svg {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
}

.login-btn {
  width: 100%;
  padding: 1.1rem 1.5rem;
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.6), rgba(118, 75, 162, 0.6));
  color: white;
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 14px;
  font-family: 'Montserrat', sans-serif;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  letter-spacing: 1px;
  position: relative;
  overflow: hidden;
}

.login-btn::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, rgba(255,255,255,0.1), transparent);
  opacity: 0;
  transition: opacity 0.3s ease;
}

.login-btn:hover:not(:disabled)::before {
  opacity: 1;
}

.login-btn:hover:not(:disabled) {
  transform: translateY(-3px);
  box-shadow:
    0 15px 35px rgba(102, 126, 234, 0.3),
    0 5px 15px rgba(0, 0, 0, 0.2);
  border-color: rgba(255, 255, 255, 0.3);
}

.login-btn:hover:not(:disabled) .arrow-icon {
  transform: translateX(5px);
}

.login-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
  transform: none;
}

.arrow-icon {
  width: 20px;
  height: 20px;
  transition: transform 0.3s ease;
}

.spinner {
  width: 22px;
  height: 22px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.login-footer {
  position: relative;
  z-index: 2;
  padding: 1.5rem 2rem 2rem;
  text-align: center;
}

.divider {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.divider-line {
  flex: 1;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(255,255,255,0.15), transparent);
}

.divider-text {
  font-family: 'Montserrat', sans-serif;
  font-size: 0.65rem;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.4);
  letter-spacing: 2px;
}

.login-footer p {
  margin: 0;
  font-family: 'Montserrat', sans-serif;
  font-size: 0.8rem;
  color: rgba(255, 255, 255, 0.5);
}

/* レスポンシブ */
@media (max-width: 600px) {
  .cursive-title {
    font-size: 4rem;
  }

  .subtitle {
    font-size: 0.9rem;
    letter-spacing: 2px;
  }

  .subtitle-line {
    width: 30px;
  }

  .welcome-text h2 {
    font-size: 2rem;
    letter-spacing: 4px;
  }

  .login-header h1 {
    font-size: 1.4rem;
  }
}
</style>
