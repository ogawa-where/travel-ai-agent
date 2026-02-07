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
const planeEl = ref<HTMLElement | null>(null)
const exhaustCanvasEl = ref<HTMLCanvasElement | null>(null)

const animateContrail = async () => {
  const title = titleEl.value
  const plane = planeEl.value
  const canvas = exhaustCanvasEl.value
  if (!title || !plane || !canvas) return

  await document.fonts.load('700 128px "Dancing Script"')
  await nextTick()

  const dpr = window.devicePixelRatio || 1
  const w = title.offsetWidth
  const h = title.offsetHeight

  // 飛行機サイズ: テキスト高さに合わせる
  const PH = h * 0.85
  const PW = PH * 3.2

  // キャンバス: テキスト幅 + 飛行機の余白
  const cW = w + PW
  const cH = h * 2.2
  const cOffX = -PW * 0.3
  const cOffY = -(cH - h) / 2

  canvas.width = cW * dpr
  canvas.height = cH * dpr
  canvas.style.width = `${cW}px`
  canvas.style.height = `${cH}px`
  canvas.style.left = `${cOffX}px`
  canvas.style.top = `${cOffY}px`
  const ctx = canvas.getContext('2d')!
  ctx.scale(dpr, dpr)

  title.style.opacity = '0'

  // 飛行経路
  const flightPos = (t: number) => ({
    x: -PW * 0.5 + t * (w + PW),
    y: h / 2 + h * 0.05 * Math.sin(t * Math.PI * 1.5),
  })

  // 排気パーティクル
  type Smoke = { x: number; y: number; r: number; a: number; vx: number; vy: number; mr: number }
  const smokes: Smoke[] = []

  const ENT_MS = 700
  const FLY_MS = 5500
  const t0 = performance.now()
  let flyDone = false
  let exitDone = false
  let textShowing = false

  plane.style.opacity = '0'
  plane.style.transition = 'none'
  plane.style.width = `${PW}px`
  plane.style.height = `${PH}px`

  const frame = (now: number) => {
    const el = now - t0

    // === フェーズ1: 飛行機が左から登場 ===
    if (el < ENT_MS) {
      const t = el / ENT_MS
      const e = t * t * (3 - 2 * t)
      const p0 = flightPos(0)
      const sx = -PW - 60
      const px = sx + (p0.x - sx) * e
      plane.style.transform = `translate(${px - PW / 2}px,${p0.y - PH / 2}px)`
      plane.style.opacity = `${Math.min(1, t * 2.5)}`
      requestAnimationFrame(frame)
      return
    }

    // === フェーズ2: 飛行（排気ガスを出しながら）===
    const ft = Math.min((el - ENT_MS) / FLY_MS, 1)
    const et = ft < 0.1 ? (ft / 0.1) ** 2 * 0.1
      : ft > 0.9 ? 0.9 + (1 - (1 - (ft - 0.9) / 0.1) ** 2) * 0.1 : ft

    const pos = flightPos(et)
    const px = pos.x, py = pos.y

    // 排気口位置（機体後方 → キャンバス座標系）
    const exX = px - PW * 0.35 - cOffX
    const exY = py - cOffY

    // 排気パーティクル生成
    if (ft > 0.01 && ft < 0.98) {
      for (let i = 0; i < 6; i++) {
        smokes.push({
          x: exX + (Math.random() - 0.5) * 14,
          y: exY + (Math.random() - 0.5) * PH * 0.3,
          r: 3 + Math.random() * 5, a: 0.55 + Math.random() * 0.35,
          vx: -1.0 - Math.random() * 1.5, vy: (Math.random() - 0.5) * 0.7,
          mr: 20 + Math.random() * 35,
        })
      }
      for (let i = 0; i < 4; i++) {
        smokes.push({
          x: exX + (Math.random() - 0.5) * 8,
          y: exY + (Math.random() - 0.5) * PH * 0.5,
          r: 1.5 + Math.random() * 2.5, a: 0.3 + Math.random() * 0.2,
          vx: -0.4 - Math.random() * 0.8, vy: (Math.random() - 0.5) * 1.0,
          mr: 10 + Math.random() * 18,
        })
      }
    }

    // パーティクル更新＆描画
    ctx.clearRect(0, 0, cW, cH)
    for (let i = smokes.length - 1; i >= 0; i--) {
      const s = smokes[i]
      s.x += s.vx; s.y += s.vy; s.vy *= 0.995
      if (s.r < s.mr) s.r += (s.mr - s.r) * 0.025
      s.a -= flyDone ? 0.007 : 0.0015
      if (s.a <= 0) { smokes.splice(i, 1); continue }
      ctx.globalAlpha = s.a
      const g = ctx.createRadialGradient(s.x, s.y, 0, s.x, s.y, s.r)
      g.addColorStop(0, 'rgba(255,255,255,0.9)')
      g.addColorStop(0.45, 'rgba(255,255,255,0.5)')
      g.addColorStop(1, 'rgba(255,255,255,0)')
      ctx.fillStyle = g
      ctx.beginPath()
      ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2)
      ctx.fill()
    }
    ctx.globalAlpha = 1

    // 飛行機の位置と角度
    if (!exitDone) {
      const np = flightPos(Math.min(et + 0.005, 1))
      const ang = Math.atan2(np.y - pos.y, np.x - pos.x) * 180 / Math.PI
      plane.style.transform = `translate(${px - PW / 2}px,${py - PH / 2}px) rotate(${ang}deg)`
      plane.style.opacity = '1'
    }

    if (ft < 1) {
      requestAnimationFrame(frame)
    } else if (!flyDone) {
      // === フェーズ3: 飛行機が右へ飛び去る ===
      flyDone = true
      plane.style.transition = 'transform 1.2s ease-in, opacity 0.8s ease 0.3s'
      plane.style.transform = `translate(${w + PW}px,${py - PH / 2 - 50}px) rotate(-5deg)`
      plane.style.opacity = '0'
      setTimeout(() => { exitDone = true }, 1200)
      requestAnimationFrame(frame)
    } else {
      // === フェーズ4: 左から右へ排気が消えて一文字ずつテキスト出現 ===
      const sinceDone = el - ENT_MS - FLY_MS
      const REVEAL_DELAY = 300
      const REVEAL_MS = 3500

      if (sinceDone > REVEAL_DELAY) {
        const rt = Math.min((sinceDone - REVEAL_DELAY) / REVEAL_MS, 1)
        const re = rt < 0.05 ? (rt / 0.05) ** 2 * 0.05 : rt
        const revealPct = re * 100

        if (!textShowing) {
          textShowing = true
          title.style.opacity = '1'
          title.style.clipPath = 'inset(0 100% 0 0)'
        }
        title.style.clipPath = `inset(0 ${Math.max(0, 100 - revealPct)}% 0 0)`

        // 表示済み領域の煙を加速消去
        const revealWorldX = re * (w + PW * 0.3) - cOffX
        for (const s of smokes) {
          if (s.x < revealWorldX) s.a -= 0.025
        }
      }

      if (sinceDone < REVEAL_DELAY + REVEAL_MS + 500 || smokes.length > 0) {
        requestAnimationFrame(frame)
      } else {
        canvas.style.display = 'none'
        title.style.clipPath = 'none'
        setTimeout(() => { showSubtitle.value = true }, 600)
      }
    }
  }

  requestAnimationFrame(frame)
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
            <canvas ref="exhaustCanvasEl" class="exhaust-canvas"></canvas>
            <div ref="planeEl" class="plane-container">
              <svg class="plane-svg" viewBox="0 0 320 100" fill="none" xmlns="http://www.w3.org/2000/svg">
                <!-- 胴体（JAL風クリーンホワイト） -->
                <path d="M45,50 C45,37 62,28 90,27 L278,27 C302,27 314,37 318,50 C314,63 302,73 278,73 L90,73 C62,72 45,63 45,50Z" fill="white" fill-opacity="0.96"/>
                <!-- 胴体下部シェード -->
                <path d="M90,54 L278,54 C300,55 312,61 315,67 C310,72 298,73 278,73 L90,73 C64,72 48,63 46,53Z" fill="rgba(180,190,210,0.12)"/>
                <!-- JAL風ベリーストライプ（Ylab赤） -->
                <path d="M315,56 C310,62 295,68 275,70 L85,70 C65,69 50,63 47,56 C50,59 65,65 85,66 L275,66 C295,65 310,59 315,53Z" fill="#C03030" fill-opacity="0.65"/>
                <!-- ベリーストライプ上の細いオレンジライン -->
                <path d="M312,53 C308,57 294,62 275,63 L85,63 C66,62 52,58 48,53" stroke="#D98830" stroke-width="0.8" stroke-opacity="0.5" fill="none"/>
                <!-- 窓帯ライン -->
                <rect x="95" y="40.5" width="185" height="1" rx="0.5" fill="rgba(80,80,100,0.1)"/>
                <!-- コックピット窓 -->
                <path d="M300,42 C304,37 310,34 315,35 L317,47 L307,48Z" fill="rgba(30,50,90,0.7)"/>
                <path d="M303,43 C306,39 310,38 314,38 L315,46 L308,47Z" fill="rgba(70,110,170,0.25)"/>
                <!-- 客室窓 -->
                <g fill="rgba(30,50,90,0.25)">
                  <circle cx="104" cy="40" r="1.2"/><circle cx="112" cy="40" r="1.2"/><circle cx="120" cy="40" r="1.2"/><circle cx="128" cy="40" r="1.2"/><circle cx="136" cy="40" r="1.2"/><circle cx="144" cy="40" r="1.2"/><circle cx="152" cy="40" r="1.2"/><circle cx="160" cy="40" r="1.2"/><circle cx="168" cy="40" r="1.2"/>
                  <circle cx="212" cy="40" r="1.2"/><circle cx="220" cy="40" r="1.2"/><circle cx="228" cy="40" r="1.2"/><circle cx="236" cy="40" r="1.2"/><circle cx="244" cy="40" r="1.2"/><circle cx="252" cy="40" r="1.2"/><circle cx="260" cy="40" r="1.2"/><circle cx="268" cy="40" r="1.2"/><circle cx="276" cy="40" r="1.2"/>
                </g>
                <!-- 主翼（後退翼） -->
                <path d="M178,33 L132,5 C129,2 133,-1 136,2 L205,28Z" fill="white" fill-opacity="0.93"/>
                <path d="M178,67 L132,95 C129,98 133,101 136,98 L205,72Z" fill="white" fill-opacity="0.87"/>
                <!-- 翼上面ハイライト -->
                <path d="M180,34 L148,12 L153,10 L205,29Z" fill="rgba(255,255,255,0.15)"/>
                <!-- エンジンポッド（グレー系） -->
                <rect x="143" y="77" width="30" height="12" rx="6" fill="rgba(160,165,175,0.85)"/>
                <ellipse cx="144" cy="83" rx="4" ry="5.5" fill="rgba(80,90,110,0.3)"/>
                <!-- エンジン排気口 -->
                <ellipse cx="173" cy="83" rx="2" ry="4" fill="rgba(100,110,130,0.2)"/>
                <!-- 垂直尾翼（大きめ・JAL風） -->
                <path d="M65,27 L38,2 C36,-1 40,-3 43,0 L78,25Z" fill="white" fill-opacity="0.96"/>
                <!-- 尾翼のYlab赤アクセント（JAL鶴丸エリア） -->
                <path d="M63,27 L44,7 C43,5 46,4 48,6 L70,25Z" fill="#C03030" fill-opacity="0.55"/>
                <!-- 水平尾翼 -->
                <path d="M57,34 L40,18 C38,15 42,13 44,16 L68,32Z" fill="white" fill-opacity="0.9"/>
                <path d="M57,66 L40,82 C38,85 42,87 44,84 L68,68Z" fill="white" fill-opacity="0.84"/>
                <!-- 機首先端 -->
                <ellipse cx="318" cy="50" rx="2" ry="8" fill="rgba(255,255,255,0.2)"/>
              </svg>
              <img src="/ylab-logo.png" class="plane-logo" alt="" />
            </div>
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

.exhaust-canvas {
  position: absolute;
  top: 0;
  left: 0;
  pointer-events: none;
  z-index: 5;
}

.plane-container {
  position: absolute;
  top: 0;
  left: 0;
  opacity: 0;
  filter: drop-shadow(0 4px 20px rgba(0,0,0,0.35));
  pointer-events: none;
  z-index: 10;
}

.plane-svg {
  width: 100%;
  height: 100%;
  display: block;
}

.plane-logo {
  position: absolute;
  left: 11%;
  top: 2%;
  height: 30%;
  width: auto;
  object-fit: contain;
  pointer-events: none;
  opacity: 0.85;
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
