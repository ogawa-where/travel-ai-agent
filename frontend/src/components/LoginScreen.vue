<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
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
const showContent = ref(false)
const showLoginCard = ref(false)
const showSubtitle = ref(false)

// 飛行機雲アニメーション
const titleEl = ref<HTMLElement | null>(null)
const planeEl = ref<SVGSVGElement | null>(null)
const trailCanvasEl = ref<HTMLCanvasElement | null>(null)

const animateContrail = async () => {
  const title = titleEl.value
  const plane = planeEl.value
  const visCanvas = trailCanvasEl.value
  if (!title || !plane || !visCanvas) return

  const text = 'Travel AI Agent'
  await document.fonts.load('700 128px "Dancing Script"')
  await nextTick()

  const dpr = window.devicePixelRatio || 1
  const w = title.offsetWidth
  const h = title.offsetHeight

  const makeCtx = (c: HTMLCanvasElement) => {
    c.width = w * dpr; c.height = h * dpr
    const cx = c.getContext('2d')!
    cx.scale(dpr, dpr)
    return cx
  }

  visCanvas.style.width = `${w}px`
  visCanvas.style.height = `${h}px`
  const ctx = makeCtx(visCanvas)

  // テキスト描画（オフスクリーン）
  const textC = document.createElement('canvas')
  const tCtx = makeCtx(textC)
  const cs = getComputedStyle(title)
  tCtx.font = `${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`
  tCtx.fillStyle = 'white'
  tCtx.textAlign = 'center'
  tCtx.textBaseline = 'alphabetic'
  const met = tCtx.measureText(text)
  const tx = w / 2
  const ty = (h + met.actualBoundingBoxAscent - met.actualBoundingBoxDescent) / 2
  tCtx.shadowColor = 'rgba(0,0,0,0.3)'
  tCtx.shadowOffsetY = 4
  tCtx.shadowBlur = 25
  tCtx.fillText(text, tx, ty)

  // コントレイルマスク（オフスクリーン）
  const maskC = document.createElement('canvas')
  const mCtx = makeCtx(maskC)

  title.style.opacity = '0'

  // 飛行経路（ゆるやかな波形で左から右へ）
  const getFlightPos = (t: number) => ({
    x: -0.06 + t * 1.12,
    y: 0.48 + 0.07 * Math.sin(t * Math.PI * 2),
  })

  // 雲パーティクル
  type CloudPt = { x: number; y: number; r: number; alpha: number; vy: number }
  const clouds: CloudPt[] = []

  // 飛行機サイズ（CSS px）
  const PLANE_W = 52, PLANE_H = 22

  // アニメーション定数
  const ENTRANCE_MS = 600
  const FLIGHT_MS = 7000
  const startTime = performance.now()
  let prevX = -PLANE_W

  plane.style.opacity = '0'
  plane.style.transition = 'none'

  const step = (now: number) => {
    const elapsed = now - startTime

    // === フェーズ1: 飛行機が左から登場 ===
    if (elapsed < ENTRANCE_MS) {
      const t = elapsed / ENTRANCE_MS
      const eased = t * t * (3 - 2 * t)
      const pos = getFlightPos(0)
      const sx = -PLANE_W - 40
      const ex = pos.x * w
      const px = sx + (ex - sx) * eased
      const py = pos.y * h
      plane.style.transform = `translate(${px - PLANE_W / 2}px, ${py - PLANE_H / 2}px)`
      plane.style.opacity = `${Math.min(1, t * 3)}`
      prevX = px
      requestAnimationFrame(step)
      return
    }

    // === フェーズ2: 飛行（コントレイルでテキストを描く）===
    const fe = elapsed - ENTRANCE_MS
    const rawT = Math.min(fe / FLIGHT_MS, 1)
    // 加速→等速→減速
    const easedT = rawT < 0.12
      ? (rawT / 0.12) ** 2 * 0.12
      : rawT > 0.88
        ? 0.88 + (1 - (1 - (rawT - 0.88) / 0.12) ** 2) * 0.12
        : rawT

    const pos = getFlightPos(easedT)
    const px = pos.x * w
    const py = pos.y * h

    // コントレイルマスク描画（テキスト高さ全体をカバーする放射グラデーション）
    const trailR = h * 0.85
    const grad = mCtx.createRadialGradient(px, h / 2, 0, px, h / 2, trailR)
    grad.addColorStop(0, 'rgba(255,255,255,1)')
    grad.addColorStop(0.35, 'rgba(255,255,255,0.95)')
    grad.addColorStop(0.65, 'rgba(255,255,255,0.5)')
    grad.addColorStop(1, 'rgba(255,255,255,0)')
    mCtx.fillStyle = grad
    mCtx.beginPath()
    mCtx.arc(px, h / 2, trailR, 0, Math.PI * 2)
    mCtx.fill()

    // ツインコントレイル（2本の飛行機雲ライン）
    const gap = 4
    for (const oy of [-gap, gap]) {
      mCtx.strokeStyle = 'rgba(255,255,255,0.6)'
      mCtx.lineWidth = 2.5
      mCtx.lineCap = 'round'
      mCtx.beginPath()
      mCtx.moveTo(prevX, py + oy)
      mCtx.lineTo(px, py + oy)
      mCtx.stroke()
    }

    // 雲パーティクル生成（飛行機の後方に散布）
    if (rawT > 0.01 && rawT < 0.99) {
      for (let i = 0; i < 3; i++) {
        clouds.push({
          x: px - 14 - Math.random() * 10,
          y: py + (Math.random() - 0.5) * 14,
          r: 2 + Math.random() * 4,
          alpha: 0.25 + Math.random() * 0.25,
          vy: (Math.random() - 0.5) * 0.3,
        })
      }
    }

    // パーティクル更新＆描画
    for (let i = clouds.length - 1; i >= 0; i--) {
      const c = clouds[i]
      c.y += c.vy
      c.r += 0.04
      c.alpha -= 0.004
      if (c.alpha <= 0) { clouds.splice(i, 1); continue }
      mCtx.globalAlpha = c.alpha
      mCtx.fillStyle = 'white'
      mCtx.beginPath()
      mCtx.arc(c.x, c.y, c.r, 0, Math.PI * 2)
      mCtx.fill()
    }
    mCtx.globalAlpha = 1
    prevX = px

    // 合成: テキスト × コントレイルマスク
    ctx.clearRect(0, 0, w, h)
    ctx.drawImage(textC, 0, 0, w, h)
    ctx.globalCompositeOperation = 'destination-in'
    ctx.drawImage(maskC, 0, 0, w, h)
    ctx.globalCompositeOperation = 'source-over'

    // 飛行機の位置と飛行角度
    const np = getFlightPos(Math.min(easedT + 0.005, 1))
    const angle = Math.atan2((np.y - pos.y) * h, (np.x - pos.x) * w) * 180 / Math.PI
    plane.style.transform = `translate(${px - PLANE_W / 2}px, ${py - PLANE_H / 2}px) rotate(${angle}deg)`
    plane.style.opacity = '1'

    if (rawT < 1) {
      requestAnimationFrame(step)
    } else {
      // === フェーズ3: 飛行機が右へ飛び去る ===
      plane.style.transition = 'transform 1s ease-in, opacity 0.7s ease 0.3s'
      plane.style.transform = `translate(${w + 60}px, ${py - PLANE_H / 2 - 30}px) rotate(-3deg)`
      plane.style.opacity = '0'

      visCanvas.style.transition = 'opacity 0.6s ease 0.3s'
      title.style.transition = 'opacity 0.6s ease 0.3s'
      title.style.opacity = '1'
      visCanvas.style.opacity = '0'
      setTimeout(() => { showSubtitle.value = true }, 600)
    }
  }

  requestAnimationFrame(step)
}

onMounted(() => {
  setTimeout(() => {
    showContent.value = true
  }, 100)

  // フェードイン後に飛行機雲アニメーション開始
  setTimeout(() => {
    animateContrail()
  }, 800)

  // Intersection Observerでログインセクションを監視
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          showLoginCard.value = true
        }
      })
    },
    { threshold: 0.3 }
  )

  if (loginSection.value) {
    observer.observe(loginSection.value)
  }
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
      <!-- セクション1: スプラッシュ -->
      <section class="splash-section" @wheel="handleWheel">
        <div class="splash-content" :class="{ 'show': showContent }">
          <div class="title-decoration">
            <span class="line left"></span>
            <span class="diamond"></span>
            <span class="line right"></span>
          </div>
          <div class="contrail-wrapper">
            <h1 ref="titleEl" class="contrail-title">Travel AI Agent</h1>
            <canvas ref="trailCanvasEl" class="trail-canvas"></canvas>
            <svg ref="planeEl" class="plane-icon" viewBox="0 0 52 22" fill="none">
              <!-- 機体 -->
              <ellipse cx="22" cy="11" rx="22" ry="3.2" fill="rgba(255,255,255,0.95)"/>
              <!-- 上翼 -->
              <polygon points="16,8 10,0 34,9" fill="rgba(255,255,255,0.9)"/>
              <!-- 下翼 -->
              <polygon points="16,14 10,22 34,13" fill="rgba(255,255,255,0.85)"/>
              <!-- 垂直尾翼 -->
              <polygon points="40,9 46,3 46,9.5" fill="rgba(255,255,255,0.9)"/>
              <!-- 水平尾翼下 -->
              <polygon points="40,13 46,19 46,12.5" fill="rgba(255,255,255,0.85)"/>
              <!-- コックピット -->
              <ellipse cx="3" cy="11" rx="2.5" ry="2" fill="rgba(180,215,255,0.5)"/>
            </svg>
          </div>
          <p class="subtitle" :class="{ 'show': showSubtitle }">Your Journey, Personalized</p>
          <div class="title-decoration bottom" :class="{ 'show': showSubtitle }">
            <span class="line left"></span>
            <span class="diamond"></span>
            <span class="line right"></span>
          </div>
        </div>

        <!-- スクロールインジケーター -->
        <div class="scroll-indicator" :class="{ 'show': showSubtitle }" @click="scrollToLogin">
          <span class="scroll-text">Scroll</span>
          <div class="scroll-arrow">
            <span></span>
            <span></span>
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
@import url('https://fonts.googleapis.com/css2?family=Dancing+Script:wght@400;700&family=Playfair+Display:wght@400;700&family=Montserrat:wght@300;400;500;600&display=swap');

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
  opacity: 0;
  transform: translateY(40px);
  transition: all 1.2s cubic-bezier(0.16, 1, 0.3, 1);
}

.splash-content.show {
  opacity: 1;
  transform: translateY(0);
}

.title-decoration {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 15px;
  margin-bottom: 20px;
}

.title-decoration.bottom {
  margin-top: 20px;
  margin-bottom: 0;
  opacity: 0;
  transition: opacity 0.8s cubic-bezier(0.16, 1, 0.3, 1) 0.2s;
}

.title-decoration.bottom.show {
  opacity: 1;
}

.title-decoration .line {
  width: 60px;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(255,255,255,0.6), transparent);
}

.title-decoration .diamond {
  width: 8px;
  height: 8px;
  background: rgba(255,255,255,0.8);
  transform: rotate(45deg);
}

/* 飛行機雲アニメーション */
.contrail-wrapper {
  position: relative;
  display: inline-block;
  overflow: visible;
}

.contrail-title {
  font-family: 'Dancing Script', cursive;
  font-size: 8rem;
  font-weight: 700;
  color: white;
  white-space: nowrap;
  margin: 0;
  text-shadow: 0 4px 30px rgba(0, 0, 0, 0.3);
  opacity: 0;
}

.trail-canvas {
  position: absolute;
  top: 0;
  left: 0;
  pointer-events: none;
}

.plane-icon {
  position: absolute;
  top: 0;
  left: 0;
  width: 52px;
  height: 22px;
  opacity: 0;
  filter: drop-shadow(0 2px 8px rgba(255,255,255,0.4));
  pointer-events: none;
  z-index: 10;
}

.subtitle {
  font-family: 'Montserrat', sans-serif;
  font-size: 1.5rem;
  font-weight: 300;
  color: rgba(255, 255, 255, 0.9);
  margin: 1.5rem 0 0;
  letter-spacing: 6px;
  text-transform: uppercase;
  opacity: 0;
  transform: translateY(15px);
  transition: opacity 0.9s cubic-bezier(0.16, 1, 0.3, 1),
              transform 0.9s cubic-bezier(0.16, 1, 0.3, 1);
}

.subtitle.show {
  opacity: 1;
  transform: translateY(0);
}

/* スクロールインジケーター */
.scroll-indicator {
  position: absolute;
  bottom: 50px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  cursor: pointer;
  opacity: 0;
  transition: opacity 1s ease 0.6s;
}

.scroll-indicator.show {
  opacity: 1;
}

.scroll-text {
  font-family: 'Montserrat', sans-serif;
  font-size: 0.75rem;
  font-weight: 400;
  color: rgba(255, 255, 255, 0.8);
  letter-spacing: 3px;
  text-transform: uppercase;
  margin-bottom: 12px;
}

.scroll-arrow {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.scroll-arrow span {
  display: block;
  width: 18px;
  height: 18px;
  border-right: 2px solid rgba(255, 255, 255, 0.6);
  border-bottom: 2px solid rgba(255, 255, 255, 0.6);
  transform: rotate(45deg);
  animation: scroll-bounce 2s infinite;
}

.scroll-arrow span:nth-child(2) {
  animation-delay: 0.2s;
  margin-top: -10px;
}

@keyframes scroll-bounce {
  0% {
    opacity: 0;
    transform: rotate(45deg) translate(-5px, -5px);
  }
  50% {
    opacity: 1;
  }
  100% {
    opacity: 0;
    transform: rotate(45deg) translate(5px, 5px);
  }
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
  .contrail-title {
    font-size: 4.5rem;
  }

  .subtitle {
    font-size: 1rem;
    letter-spacing: 3px;
  }

  .welcome-text h2 {
    font-size: 2rem;
    letter-spacing: 4px;
  }

  .login-header h1 {
    font-size: 1.4rem;
  }

  .title-decoration .line {
    width: 40px;
  }
}
</style>
