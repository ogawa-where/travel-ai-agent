<script setup lang="ts">
export type SelectableMode = 'preference' | 'planning'

interface Emits {
  (e: 'select', mode: SelectableMode): void
}

defineEmits<Emits>()
</script>

<template>
  <div class="mode-select-screen">
    <!-- 左側: 嗜好学習モード -->
    <div class="mode-panel preference" @click="$emit('select', 'preference')">
      <div class="panel-background"></div>
      <div class="panel-content">
        <div class="panel-header">
          <div class="mode-number">01</div>
          <div class="mode-badge">Learning Mode</div>
        </div>

        <div class="mode-main">
          <div class="mode-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z"/>
            </svg>
          </div>
          <h2>嗜好学習</h2>
          <p class="mode-subtitle">Preference Learning</p>
          <p class="mode-description">
            AIとの対話を通じて、あなたの旅行スタイルや好みを学習します。
            学習した内容は次回以降のプラン作成に活用されます。
          </p>
        </div>

        <div class="mode-features">
          <div class="feature-item">
            <div class="feature-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
              </svg>
            </div>
            <div class="feature-text">
              <span class="feature-title">対話形式</span>
              <span class="feature-desc">自然な会話で好みを登録</span>
            </div>
          </div>
          <div class="feature-item">
            <div class="feature-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
              </svg>
            </div>
            <div class="feature-text">
              <span class="feature-title">スタイル分析</span>
              <span class="feature-desc">旅行傾向を可視化</span>
            </div>
          </div>
          <div class="feature-item">
            <div class="feature-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
              </svg>
            </div>
            <div class="feature-text">
              <span class="feature-title">継続学習</span>
              <span class="feature-desc">使うほど精度向上</span>
            </div>
          </div>
        </div>

        <div class="mode-action">
          <span>始める</span>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="5" y1="12" x2="19" y2="12"/>
            <polyline points="12 5 19 12 12 19"/>
          </svg>
        </div>
      </div>
    </div>

    <!-- 中央: ディバイダー -->
    <div class="center-divider">
      <div class="divider-line"></div>
      <div class="divider-text">
        <span>SELECT</span>
        <span>MODE</span>
      </div>
      <div class="divider-line"></div>
    </div>

    <!-- 右側: 旅行企画モード -->
    <div class="mode-panel planning" @click="$emit('select', 'planning')">
      <div class="panel-background"></div>
      <div class="panel-content">
        <div class="panel-header">
          <div class="mode-number">02</div>
          <div class="mode-badge">Planning Mode</div>
        </div>

        <div class="mode-main">
          <div class="mode-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <circle cx="12" cy="12" r="10"/>
              <polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"/>
            </svg>
          </div>
          <h2>旅行企画</h2>
          <p class="mode-subtitle">Travel Planning</p>
          <p class="mode-description">
            行き先と日程を入力するだけで、あなたの好みに合わせた
            オーダーメイドの旅行プランを自動生成します。
          </p>
        </div>

        <div class="mode-features">
          <div class="feature-item">
            <div class="feature-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/>
                <line x1="16" y1="2" x2="16" y2="6"/>
                <line x1="8" y1="2" x2="8" y2="6"/>
                <line x1="3" y1="10" x2="21" y2="10"/>
              </svg>
            </div>
            <div class="feature-text">
              <span class="feature-title">簡単入力</span>
              <span class="feature-desc">日程と行き先だけでOK</span>
            </div>
          </div>
          <div class="feature-item">
            <div class="feature-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>
              </svg>
            </div>
            <div class="feature-text">
              <span class="feature-title">好み反映</span>
              <span class="feature-desc">学習した嗜好を活用</span>
            </div>
          </div>
          <div class="feature-item">
            <div class="feature-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/>
                <circle cx="12" cy="10" r="3"/>
              </svg>
            </div>
            <div class="feature-text">
              <span class="feature-title">完全カスタム</span>
              <span class="feature-desc">オーダーメイドプラン</span>
            </div>
          </div>
        </div>

        <div class="mode-action">
          <span>始める</span>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="5" y1="12" x2="19" y2="12"/>
            <polyline points="12 5 19 12 12 19"/>
          </svg>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;600;700&family=Montserrat:wght@300;400;500;600;700&display=swap');

.mode-select-screen {
  flex: 1;
  display: flex;
  min-height: 600px;
  position: relative;
}

/* パネル共通 */
.mode-panel {
  flex: 1;
  position: relative;
  cursor: pointer;
  overflow: hidden;
  transition: all 0.5s cubic-bezier(0.16, 1, 0.3, 1);
}

.mode-panel:hover {
  flex: 1.15;
}

.mode-panel .panel-background {
  position: absolute;
  inset: 0;
  opacity: 0;
  transition: opacity 0.5s ease;
}

.mode-panel.preference .panel-background {
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.08) 0%, rgba(118, 75, 162, 0.08) 100%);
}

.mode-panel.planning .panel-background {
  background: linear-gradient(135deg, rgba(56, 178, 172, 0.08) 0%, rgba(49, 151, 149, 0.08) 100%);
}

.mode-panel:hover .panel-background {
  opacity: 1;
}

.panel-content {
  position: relative;
  z-index: 1;
  height: 100%;
  padding: 2.5rem;
  display: flex;
  flex-direction: column;
}

/* ヘッダー */
.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 2rem;
}

.mode-number {
  font-family: 'Playfair Display', serif;
  font-size: 3.5rem;
  font-weight: 700;
  line-height: 1;
  opacity: 0.12;
}

.mode-panel.preference .mode-number {
  color: #667eea;
}

.mode-panel.planning .mode-number {
  color: #38b2ac;
}

.mode-badge {
  font-family: 'Montserrat', sans-serif;
  font-size: 0.65rem;
  font-weight: 600;
  letter-spacing: 2px;
  text-transform: uppercase;
  padding: 0.4rem 0.8rem;
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.04);
  color: #718096;
}

/* メインコンテンツ */
.mode-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
}

.mode-icon {
  width: 70px;
  height: 70px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 20px;
  margin-bottom: 1.5rem;
  transition: all 0.4s ease;
}

.mode-panel.preference .mode-icon {
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.15) 0%, rgba(118, 75, 162, 0.15) 100%);
  color: #667eea;
}

.mode-panel.planning .mode-icon {
  background: linear-gradient(135deg, rgba(56, 178, 172, 0.15) 0%, rgba(49, 151, 149, 0.15) 100%);
  color: #38b2ac;
}

.mode-panel:hover .mode-icon {
  transform: scale(1.1);
}

.mode-icon svg {
  width: 36px;
  height: 36px;
}

.mode-main h2 {
  font-family: 'Montserrat', sans-serif;
  font-size: 1.8rem;
  font-weight: 700;
  color: #1a202c;
  margin: 0 0 0.25rem;
  letter-spacing: -0.5px;
}

.mode-subtitle {
  font-family: 'Montserrat', sans-serif;
  font-size: 0.75rem;
  font-weight: 500;
  letter-spacing: 3px;
  text-transform: uppercase;
  color: #a0aec0;
  margin: 0 0 1.25rem;
}

.mode-description {
  font-family: 'Montserrat', sans-serif;
  font-size: 0.95rem;
  font-weight: 400;
  line-height: 1.7;
  color: #4a5568;
  margin: 0;
  max-width: 320px;
}

/* フィーチャーリスト */
.mode-features {
  margin-top: auto;
  padding-top: 2rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.feature-item {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.75rem 1rem;
  background: rgba(255, 255, 255, 0.6);
  border-radius: 12px;
  transition: all 0.3s ease;
}

.mode-panel:hover .feature-item {
  background: rgba(255, 255, 255, 0.8);
}

.feature-icon {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  flex-shrink: 0;
}

.mode-panel.preference .feature-icon {
  background: rgba(102, 126, 234, 0.1);
  color: #667eea;
}

.mode-panel.planning .feature-icon {
  background: rgba(56, 178, 172, 0.1);
  color: #38b2ac;
}

.feature-icon svg {
  width: 20px;
  height: 20px;
}

.feature-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.feature-title {
  font-family: 'Montserrat', sans-serif;
  font-size: 0.85rem;
  font-weight: 600;
  color: #2d3748;
}

.feature-desc {
  font-family: 'Montserrat', sans-serif;
  font-size: 0.75rem;
  font-weight: 400;
  color: #718096;
}

/* アクションボタン */
.mode-action {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-top: 1.5rem;
  padding: 1rem 1.5rem;
  border-radius: 12px;
  font-family: 'Montserrat', sans-serif;
  font-size: 0.95rem;
  font-weight: 600;
  transition: all 0.4s ease;
}

.mode-panel.preference .mode-action {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.mode-panel.planning .mode-action {
  background: linear-gradient(135deg, #38b2ac 0%, #319795 100%);
  color: white;
}

.mode-action svg {
  width: 20px;
  height: 20px;
  transition: transform 0.3s ease;
}

.mode-panel:hover .mode-action svg {
  transform: translateX(5px);
}

/* 中央ディバイダー */
.center-divider {
  width: 80px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 2rem 0;
  flex-shrink: 0;
}

.divider-line {
  flex: 1;
  width: 1px;
  background: linear-gradient(180deg, transparent, rgba(0, 0, 0, 0.1), transparent);
}

.divider-text {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 1.5rem 0;
}

.divider-text span {
  font-family: 'Montserrat', sans-serif;
  font-size: 0.65rem;
  font-weight: 600;
  letter-spacing: 3px;
  color: #a0aec0;
}

/* レスポンシブ */
@media (max-width: 900px) {
  .mode-select-screen {
    flex-direction: column;
  }

  .center-divider {
    width: 100%;
    height: 60px;
    flex-direction: row;
    padding: 0 2rem;
  }

  .divider-line {
    flex: 1;
    height: 1px;
    width: auto;
    background: linear-gradient(90deg, transparent, rgba(0, 0, 0, 0.1), transparent);
  }

  .divider-text {
    flex-direction: row;
    gap: 8px;
    padding: 0 1.5rem;
  }

  .mode-panel:hover {
    flex: 1;
  }

  .panel-content {
    padding: 1.5rem;
  }

  .mode-number {
    font-size: 2.5rem;
  }

  .mode-main h2 {
    font-size: 1.4rem;
  }
}
</style>
