<script setup lang="ts">
defineProps<{
  profileSummary: string
}>()

const emit = defineEmits<{
  showProfile: []
  reset: []
}>()
</script>

<template>
  <header class="header">
    <div class="header-content">
      <div class="header-brand">
        <h1>Travel AI</h1>
        <p>あなたの旅をサポート</p>
      </div>
      <div class="header-actions">
        <button
          class="profile-btn"
          @click="emit('showProfile')"
          title="プロフィールを見る"
          :class="{ 'has-profile': profileSummary }"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
            <circle cx="12" cy="7" r="4" />
          </svg>
          <span>プロフィール</span>
        </button>
        <button class="reset-btn" @click="emit('reset')" title="新しいユーザーとして開始">
          リセット
        </button>
      </div>
    </div>
  </header>
</template>

<style scoped>
.header {
  background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%);
  color: white;
  padding: 1rem 2rem;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  max-width: 1200px;
  margin: 0 auto;
}

.header-brand h1 {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 700;
  letter-spacing: -0.5px;
}

.header-brand p {
  margin: 0.25rem 0 0;
  opacity: 0.8;
  font-size: 0.85rem;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.profile-btn {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  border: 1px solid rgba(255, 255, 255, 0.3);
  background: transparent;
  color: white;
  border-radius: 8px;
  cursor: pointer;
  font-size: 0.85rem;
  transition: all 0.2s;
}

.profile-btn:hover {
  background: rgba(255, 255, 255, 0.1);
  border-color: rgba(255, 255, 255, 0.5);
}

.profile-btn.has-profile {
  background: rgba(72, 187, 120, 0.2);
  border-color: rgba(72, 187, 120, 0.5);
}

.profile-btn.has-profile:hover {
  background: rgba(72, 187, 120, 0.3);
}

.reset-btn {
  padding: 0.5rem 0.75rem;
  border: 1px solid rgba(255, 255, 255, 0.2);
  background: transparent;
  color: rgba(255, 255, 255, 0.7);
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.8rem;
  transition: all 0.2s;
}

.reset-btn:hover {
  background: rgba(231, 76, 60, 0.8);
  border-color: rgba(231, 76, 60, 0.8);
  color: white;
}
</style>
