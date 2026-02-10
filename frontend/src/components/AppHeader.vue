<script setup lang="ts">
defineProps<{
  profileSummary: string
  username: string
}>()

const emit = defineEmits<{
  showProfile: []
  logout: []
}>()
</script>

<template>
  <header class="header">
    <div class="header-content">
      <div class="header-brand">
        <h1>Travel AI Agent</h1>
        <span class="brand-badge">
          <span class="brand-by">by</span>
          <img :src="'/ylab-logo.png'" alt="Ylab" class="brand-logo" @error="($event.target as HTMLImageElement).style.display='none'" />
        </span>
      </div>
      <div class="header-actions">
        <button
          class="profile-btn"
          @click="emit('showProfile')"
          title="プロフィールを見る"
          :class="{ 'has-profile': profileSummary }"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
            <circle cx="12" cy="7" r="4" />
          </svg>
          <span>プロフィール</span>
        </button>
        <span v-if="username" class="username">{{ username }}</span>
        <button class="logout-btn" @click="emit('logout')" title="ログアウト">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
            <polyline points="16 17 21 12 16 7"/>
            <line x1="21" y1="12" x2="9" y2="12"/>
          </svg>
          ログアウト
        </button>
      </div>
    </div>
  </header>
</template>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600&family=Montserrat:wght@300;400;500;600&display=swap');

.header {
  background: rgba(255, 255, 255, 0.15);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-bottom: 1px solid rgba(255, 255, 255, 0.2);
  padding: 1rem 2rem;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  max-width: 1200px;
  margin: 0 auto;
}

.header-brand {
  display: flex;
  align-items: center;
  gap: 12px;
}

.brand-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px 5px 10px;
  background: rgba(255, 255, 255, 0.55);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  border: 1px solid rgba(0, 0, 0, 0.05);
  border-radius: 20px;
  transition: box-shadow 0.2s ease;
}

.brand-badge:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.brand-by {
  font-family: 'Montserrat', sans-serif;
  font-size: 0.7rem;
  font-weight: 400;
  font-style: italic;
  color: #a0aec0;
}

.brand-logo {
  height: 26px;
  width: auto;
  object-fit: contain;
}


.header-brand h1 {
  margin: 0;
  font-family: 'Playfair Display', serif;
  font-size: 1.5rem;
  font-weight: 600;
  color: #1a202c;
  letter-spacing: 0.5px;
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
  padding: 0.6rem 1rem;
  background: rgba(255, 255, 255, 0.6);
  border: 1px solid rgba(255, 255, 255, 0.8);
  color: #4a5568;
  border-radius: 10px;
  cursor: pointer;
  font-family: 'Montserrat', sans-serif;
  font-size: 0.85rem;
  font-weight: 500;
  transition: all 0.3s ease;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

.profile-btn:hover {
  background: rgba(255, 255, 255, 0.8);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.profile-btn.has-profile {
  background: rgba(72, 187, 120, 0.15);
  border-color: rgba(72, 187, 120, 0.4);
  color: #276749;
}

.profile-btn.has-profile:hover {
  background: rgba(72, 187, 120, 0.25);
}

.username {
  padding: 0.5rem 0.85rem;
  background: rgba(102, 126, 234, 0.1);
  border: 1px solid rgba(102, 126, 234, 0.2);
  border-radius: 8px;
  font-family: 'Montserrat', sans-serif;
  font-size: 0.85rem;
  font-weight: 500;
  color: #4a5568;
}

.logout-btn {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.5rem 0.85rem;
  background: rgba(255, 255, 255, 0.4);
  border: 1px solid rgba(0, 0, 0, 0.08);
  color: #718096;
  border-radius: 8px;
  cursor: pointer;
  font-family: 'Montserrat', sans-serif;
  font-size: 0.8rem;
  font-weight: 500;
  transition: all 0.3s ease;
}

.logout-btn:hover {
  background: rgba(231, 76, 60, 0.1);
  border-color: rgba(231, 76, 60, 0.3);
  color: #c53030;
}

.logout-btn svg {
  opacity: 0.7;
}

.logout-btn:hover svg {
  opacity: 1;
}

@media (max-width: 600px) {
  .header {
    padding: 0.75rem 1rem;
  }

  .brand-logo {
    height: 20px;
  }

  .header-brand h1 {
    font-size: 1.2rem;
  }

  .profile-btn span {
    display: none;
  }

  .username {
    display: none;
  }
}
</style>
