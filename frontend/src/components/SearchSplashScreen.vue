<script setup lang="ts">
import { ref, onMounted } from 'vue'

const emit = defineEmits<{
  done: []
}>()

// 検索バーIMEアニメーション
const cursorEl = ref<HTMLElement | null>(null)
const typedEl = ref<HTMLElement | null>(null)
const caretEl = ref<HTMLElement | null>(null)
const searchBtnEl = ref<HTMLElement | null>(null)
const searchBarEl = ref<HTMLElement | null>(null)

const showContent = ref(false)
const searchFocused = ref(false)
const showCandidate = ref(false)
const candidateItems = ref<string[]>([])
const selectedIndex = ref(0)
const searchReady = ref(false)

const IME_INPUT = 'とらべるAIえーじぇんと'
const CANDIDATES = ['トラベルAIエージェント', 'Travel AI Agent', 'とらべるAIえーじぇんと']

function sleep(ms: number) {
  return new Promise<void>(r => setTimeout(r, ms))
}

/** 要素の中心座標を返す */
function getCenter(el: HTMLElement) {
  const r = el.getBoundingClientRect()
  return { x: r.left + r.width / 2, y: r.top + r.height / 2 }
}

/** カーソルを指定要素の中心へ移動（カーソル先端=左上なので少しオフセット） */
function moveCursorTo(cur: HTMLElement, target: HTMLElement) {
  const c = getCenter(target)
  // カーソルSVGの先端は左上(0,0)なので、ターゲット中心に先端が来るように
  cur.style.left = `${c.x}px`
  cur.style.top = `${c.y}px`
  cur.style.transform = 'translate(0, 0)'
}

async function runSplashAnimation() {
  const cur = cursorEl.value
  const typed = typedEl.value
  const caret = caretEl.value
  const bar = searchBarEl.value
  const btn = searchBtnEl.value
  if (!cur || !typed || !caret || !bar || !btn) return

  const ring = cur.querySelector('.cursor-click-ring') as HTMLElement | null

  // 初期位置: 検索バーの左上あたり
  const barRect = bar.getBoundingClientRect()
  cur.style.left = `${barRect.left - 80}px`
  cur.style.top = `${barRect.top - 60}px`
  cur.style.transform = 'translate(0, 0)'

  // Phase 1: カーソル登場 → 検索バーの入力エリアへ
  await sleep(400)
  cur.style.opacity = '1'
  await sleep(50)
  // 検索バー入力エリアの中央付近へ
  const inputTarget = bar.querySelector('.search-input-area') as HTMLElement
  if (inputTarget) {
    const inputCenter = getCenter(inputTarget)
    cur.style.left = `${inputCenter.x - 40}px`
    cur.style.top = `${inputCenter.y}px`
  }
  await sleep(700)

  // Phase 2: 検索バーをクリック → フォーカス
  if (ring) ring.classList.add('clicking')
  await sleep(200)
  searchFocused.value = true
  cur.style.transition = 'opacity 0.15s ease'
  cur.style.opacity = '0'
  await sleep(200)

  // Phase 3: タイピング（IME未確定入力）
  caret.classList.add('blinking')
  await sleep(300)
  for (let i = 0; i < IME_INPUT.length; i++) {
    typed.textContent = IME_INPUT.slice(0, i + 1)
    if (i === 0) typed.classList.add('ime-active')
    await sleep(100 + Math.random() * 60)
  }
  await sleep(500)

  // Phase 4: 第1変換 → カタカナ候補
  typed.textContent = CANDIDATES[0]
  candidateItems.value = [...CANDIDATES]
  selectedIndex.value = 0
  showCandidate.value = true
  await sleep(700)

  // Phase 5: 第2変換 → 英語候補
  typed.textContent = CANDIDATES[1]
  selectedIndex.value = 1
  await sleep(600)

  // Phase 6: 確定（候補ウィンドウ閉じ、下線消滅）
  showCandidate.value = false
  typed.classList.remove('ime-active')
  caret.classList.remove('blinking')
  caret.style.transition = 'opacity 0.2s ease'
  caret.style.opacity = '0'
  searchReady.value = true
  await sleep(400)

  // Phase 7: カーソル再登場 → 検索ボタンの実座標へ
  if (ring) ring.classList.remove('clicking')

  // カーソルをボタンの右上あたりからスタートさせる
  const btnCenter = getCenter(btn)
  cur.style.transition = 'none'
  cur.style.left = `${btnCenter.x + 60}px`
  cur.style.top = `${btnCenter.y - 50}px`
  await sleep(50)

  cur.style.transition = 'left 0.6s cubic-bezier(0.16, 1, 0.3, 1), top 0.6s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.2s ease'
  cur.style.opacity = '1'
  await sleep(50)

  // 検索ボタンの中心へ正確に移動
  moveCursorTo(cur, btn)
  await sleep(600)

  // Phase 8: 検索ボタンクリック → 完了
  if (ring) {
    void ring.offsetWidth
    ring.classList.add('clicking')
  }
  btn.classList.add('clicked')
  await sleep(500)
  emit('done')
}

onMounted(() => {
  setTimeout(() => { showContent.value = true }, 100)
  document.fonts.load('400 1rem "Noto Sans JP"').then(() => runSplashAnimation())
})
</script>

<template>
  <div class="search-splash">
    <!-- スプラッシュコンテンツ -->
    <div class="splash-section">
      <div class="splash-content" :class="{ 'show': showContent }">
        <p class="search-prompt">あなたの旅を、どんな体験で彩りたい？</p>

        <div ref="searchBarEl" class="search-bar" :class="{ focused: searchFocused, 'has-candidates': showCandidate }">
          <div class="search-icon-left">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="11" cy="11" r="8"/>
              <line x1="21" y1="21" x2="16.65" y2="16.65"/>
            </svg>
          </div>
          <div class="search-input-area">
            <span ref="typedEl" class="search-typed"></span>
            <span ref="caretEl" class="search-caret"></span>
          </div>
          <button ref="searchBtnEl" class="search-btn" :class="{ ready: searchReady }">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <line x1="5" y1="12" x2="19" y2="12"/>
              <polyline points="12 5 19 12 12 19"/>
            </svg>
          </button>

          <!-- Google風サジェストウィンドウ -->
          <div class="ime-candidate" v-if="showCandidate">
            <div class="candidate-divider"></div>
            <div
              v-for="(item, i) in candidateItems"
              :key="i"
              class="candidate-item"
              :class="{ selected: i === selectedIndex }"
            >
              <svg class="candidate-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="11" cy="11" r="8"/>
                <line x1="21" y1="21" x2="16.65" y2="16.65"/>
              </svg>
              <span class="candidate-text">{{ item }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- マウスカーソル -->
      <div ref="cursorEl" class="pc-cursor">
        <svg viewBox="0 0 28 28" width="28" height="28" xmlns="http://www.w3.org/2000/svg">
          <path d="M2 2 L2 22 L7.5 16.5 L12 26 L16 24.5 L11.5 15 L19 15 Z"
                fill="white" stroke="rgba(0,0,0,0.7)" stroke-width="1.5" stroke-linejoin="round"/>
        </svg>
        <span class="cursor-click-ring"></span>
      </div>
    </div>
  </div>
</template>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500&family=Montserrat:wght@300;400;500;600&display=swap');

.search-splash {
  position: relative;
  width: 100%;
  height: 100vh;
  overflow: hidden;
  background: radial-gradient(ellipse at 50% 40%, #1a1a2e 0%, #0f0f1a 100%);
}

.splash-section {
  position: relative;
  z-index: 10;
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
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

/* 検索プロンプト */
.search-prompt {
  font-family: 'Noto Sans JP', 'Montserrat', sans-serif;
  font-size: 2.4rem;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.9);
  margin: 0 0 2.5rem;
  letter-spacing: 3px;
}

/* 検索バー */
.search-bar {
  display: flex;
  align-items: center;
  width: 100%;
  max-width: 720px;
  height: 72px;
  margin: 0 auto;
  background: rgba(255, 255, 255, 0.08);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 36px;
  padding: 0 10px 0 28px;
  position: relative;
  transition: border-color 0.3s ease, box-shadow 0.3s ease, background 0.3s ease;
}

.search-bar.focused {
  border-color: rgba(255, 255, 255, 0.4);
  background: rgba(255, 255, 255, 0.12);
  box-shadow: 0 0 0 4px rgba(102, 126, 234, 0.2), 0 8px 32px rgba(0, 0, 0, 0.15);
}

.search-bar.has-candidates {
  border-radius: 36px 36px 0 0;
  border-bottom-color: transparent;
}

.search-icon-left {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  color: rgba(255, 255, 255, 0.4);
  margin-right: 16px;
}

.search-icon-left svg {
  width: 100%;
  height: 100%;
}

.search-input-area {
  flex: 1;
  min-width: 0;
  font-family: 'Noto Sans JP', sans-serif;
  font-size: 1.2rem;
  color: white;
  white-space: nowrap;
  overflow: hidden;
  position: relative;
}

.search-typed {
  position: relative;
}

.search-typed.ime-active {
  border-bottom: 2px solid rgba(255, 255, 255, 0.5);
  padding-bottom: 1px;
}

.search-caret {
  display: inline-block;
  width: 1.5px;
  height: 1.2em;
  background: white;
  vertical-align: text-bottom;
  margin-left: 1px;
  opacity: 0;
}

.search-caret.blinking {
  animation: caret-blink 1s step-end infinite;
}

@keyframes caret-blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

/* 検索ボタン */
.search-btn {
  flex-shrink: 0;
  width: 54px;
  height: 54px;
  border-radius: 50%;
  border: none;
  background: rgba(255, 255, 255, 0.08);
  color: rgba(255, 255, 255, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: default;
  transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
}

.search-btn svg {
  width: 22px;
  height: 22px;
}

.search-btn.ready {
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.6), rgba(118, 75, 162, 0.6));
  color: white;
  cursor: pointer;
}

.search-btn.clicked {
  transform: scale(0.88);
  box-shadow: 0 0 20px rgba(102, 126, 234, 0.5);
}

/* Google風サジェストウィンドウ */
.ime-candidate {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  background: rgba(255, 255, 255, 0.12);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-top: none;
  border-radius: 0 0 36px 36px;
  padding: 0 0 12px;
  z-index: 30;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
}

.candidate-divider {
  height: 1px;
  margin: 0 28px;
  background: rgba(255, 255, 255, 0.15);
}

.candidate-item {
  display: flex;
  align-items: center;
  padding: 12px 28px;
  font-family: 'Noto Sans JP', sans-serif;
  font-size: 1.1rem;
  color: rgba(255, 255, 255, 0.7);
  transition: background 0.12s ease;
  cursor: default;
}

.candidate-item.selected {
  background: rgba(255, 255, 255, 0.1);
  color: white;
}

.candidate-icon {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
  margin-right: 16px;
  color: rgba(255, 255, 255, 0.35);
}

.candidate-item.selected .candidate-icon {
  color: rgba(255, 255, 255, 0.6);
}

.candidate-text {
  flex: 1;
  min-width: 0;
}

/* マウスカーソル（position: fixed で画面座標を直接指定） */
.pc-cursor {
  position: fixed;
  top: 0;
  left: 0;
  opacity: 0;
  pointer-events: none;
  z-index: 50;
  transition: left 0.7s cubic-bezier(0.16, 1, 0.3, 1), top 0.7s cubic-bezier(0.16, 1, 0.3, 1);
  filter: drop-shadow(0 2px 8px rgba(0, 0, 0, 0.5));
}

.pc-cursor svg {
  display: block;
}

/* クリック波紋 */
.cursor-click-ring {
  position: absolute;
  top: 0;
  left: 0;
  width: 20px;
  height: 20px;
  border: 2px solid rgba(255, 255, 255, 0.6);
  border-radius: 50%;
  transform: translate(-30%, -30%) scale(0);
  opacity: 0;
  pointer-events: none;
}

.cursor-click-ring.clicking {
  animation: click-once 0.4s ease-out forwards;
}

@keyframes click-once {
  0% { opacity: 0.8; transform: translate(-30%, -30%) scale(0.3); }
  100% { opacity: 0; transform: translate(-30%, -30%) scale(2.5); }
}

/* レスポンシブ */
@media (max-width: 600px) {
  .search-prompt {
    font-size: 1.4rem;
  }

  .search-bar {
    max-width: 100%;
    height: 56px;
    border-radius: 28px;
    padding: 0 8px 0 20px;
  }

  .search-bar.has-candidates {
    border-radius: 28px 28px 0 0;
  }

  .search-icon-left {
    width: 20px;
    height: 20px;
  }

  .search-input-area {
    font-size: 1rem;
  }

  .search-btn {
    width: 42px;
    height: 42px;
  }

  .search-btn svg {
    width: 18px;
    height: 18px;
  }

  .ime-candidate {
    border-radius: 0 0 28px 28px;
    padding: 0 0 8px;
  }

  .candidate-item {
    padding: 10px 20px;
    font-size: 0.95rem;
  }

  .candidate-divider {
    margin: 0 20px;
  }

  .candidate-icon {
    width: 16px;
    height: 16px;
    margin-right: 12px;
  }

  .pc-cursor {
    display: none;
  }
}
</style>
