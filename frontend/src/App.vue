<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { api } from './lib/api'
import { storage } from './lib/storage'
import type { User, UserProfile, PreferenceSignal, LoginResponse } from './lib/api'
import AppHeader from './components/AppHeader.vue'
import LoginScreen from './components/LoginScreen.vue'
import ModeTabs, { type TabMode } from './components/ModeTabs.vue'
import PreferenceLearningView from './components/PreferenceLearningView.vue'
import TravelPlanningView from './components/TravelPlanningView.vue'
import PreferenceToast from './components/PreferenceToast.vue'

const user = ref<User | null>(null)
const isLoading = ref(false)
const isInitializing = ref(true)
const isLoggedIn = ref(false)
const userProfile = ref<UserProfile | null>(null)
const preferenceSignals = ref<PreferenceSignal[]>([])
const showProfileModal = ref(false)
const activeMode = ref<TabMode>('preference')

// Toast notifications for learned preferences
const pendingToasts = ref<{category: string; tag: string; weight: number; is_new: boolean}[]>([])

// Group preferences by category
const groupedPreferences = computed(() => {
  const groups: Record<string, PreferenceSignal[]> = {}
  for (const signal of preferenceSignals.value) {
    if (!groups[signal.category]) {
      groups[signal.category] = []
    }
    groups[signal.category].push(signal)
  }
  // Sort by weight within each group
  for (const category in groups) {
    groups[category].sort((a, b) => b.weight - a.weight)
  }
  return groups
})

const categoryLabels: Record<string, string> = {
  likes: '好き',
  dislikes: '嫌い',
  experience_axis: '体験軸',
  tendency: '傾向',
  food: '食事',
  activity: '観光・体験',
  accommodation: '宿泊',
  travel_style: '旅行スタイル',
  budget: '予算',
  general: 'その他',
}

const initializeApp = async () => {
  try {
    isLoading.value = true
    isInitializing.value = true

    // Check for existing username in localStorage
    const storedUsername = storage.getUsername()
    if (storedUsername) {
      try {
        // Re-login with stored username
        const response = await api.login(storedUsername)
        user.value = response.user
        storage.setUserId(response.user.id)
        userProfile.value = response.user.profile
        preferenceSignals.value = response.user.preference_signals || []
        isLoggedIn.value = true
        return
      } catch {
        // Login failed, clear storage and show login screen
        storage.clearAll()
      }
    }

    // No stored username, show login screen
    isLoggedIn.value = false
  } catch (error) {
    console.error('Failed to initialize app:', error)
  } finally {
    isLoading.value = false
    isInitializing.value = false
  }
}

const handleLogin = async (response: LoginResponse) => {
  user.value = response.user
  storage.setUserId(response.user.id)
  storage.setUsername(response.user.username || '')
  userProfile.value = response.user.profile
  preferenceSignals.value = response.user.preference_signals || []
  isLoggedIn.value = true
}

const resetApp = () => {
  storage.clearAll()
  user.value = null
  userProfile.value = null
  preferenceSignals.value = []
  isLoggedIn.value = false
}

const logout = () => {
  resetApp()
}

const handleModeChange = (mode: TabMode) => {
  activeMode.value = mode
}

const handlePreferencesUpdated = async (newSignals: PreferenceSignal[]) => {
  // Show toast for new signals
  for (const signal of newSignals) {
    pendingToasts.value.push({
      category: signal.category,
      tag: signal.tag,
      weight: signal.weight,
      is_new: true,
    })
  }

  // Refresh user profile
  if (user.value) {
    try {
      const updatedUser = await api.getUser(user.value.id)
      userProfile.value = updatedUser.profile
      preferenceSignals.value = updatedUser.preference_signals || []
    } catch (error) {
      console.error('Failed to refresh user profile:', error)
    }
  }
}

const clearToasts = () => {
  pendingToasts.value = []
}

const showProfile = () => {
  showProfileModal.value = true
}

const closeProfile = () => {
  showProfileModal.value = false
}

onMounted(() => {
  initializeApp()
})
</script>

<template>
  <div class="app">
    <!-- Login Screen -->
    <LoginScreen v-if="!isLoggedIn && !isInitializing" @login="handleLogin" />

    <!-- Main App -->
    <template v-else-if="isLoggedIn">
      <AppHeader
        :profile-summary="userProfile?.summary || ''"
        :username="user?.username || ''"
        @show-profile="showProfile"
        @logout="logout"
      />

      <main class="main">
        <div class="content-wrapper">
          <!-- Mode Tabs -->
          <ModeTabs :active-mode="activeMode" @change="handleModeChange" />

          <!-- Mode Views -->
          <div class="view-container">
            <PreferenceLearningView
              v-if="activeMode === 'preference'"
              :user="user"
              @preferences-updated="handlePreferencesUpdated"
            />
            <TravelPlanningView
              v-else-if="activeMode === 'planning'"
              :user="user"
            />
          </div>
        </div>
      </main>

      <!-- Toast notifications for learned preferences -->
      <PreferenceToast :preferences="pendingToasts" @clear="clearToasts" />

      <!-- Profile Modal -->
      <Teleport to="body">
        <div v-if="showProfileModal" class="modal-overlay" @click="closeProfile">
          <div class="modal-content" @click.stop>
            <div class="modal-header">
              <h2>あなたのプロフィール</h2>
              <button class="close-btn" @click="closeProfile">&times;</button>
            </div>
            <div class="modal-body">
              <div v-if="userProfile?.summary" class="profile-summary">
                <h3>サマリー</h3>
                <p>{{ userProfile.summary }}</p>
              </div>

              <div v-if="Object.keys(groupedPreferences).length > 0" class="preferences-detail">
                <h3>学習した嗜好</h3>
                <div
                  v-for="(signals, category) in groupedPreferences"
                  :key="category"
                  class="preference-category"
                >
                  <h4>{{ categoryLabels[category] || category }}</h4>
                  <div class="preference-tags">
                    <div
                      v-for="signal in signals"
                      :key="signal.id"
                      class="preference-tag"
                      :class="{ 'positive': signal.weight > 0, 'negative': signal.weight < 0 }"
                      :title="signal.evidence"
                    >
                      <span class="tag-name">{{ signal.tag }}</span>
                      <span class="tag-weight">{{ Math.abs(signal.weight).toFixed(1) }}</span>
                    </div>
                  </div>
                </div>
              </div>

              <div v-if="!userProfile?.summary && Object.keys(groupedPreferences).length === 0" class="no-profile">
                <p>まだプロフィールがありません。</p>
                <p>嗜好学習モードであなたの好みを教えてください！</p>
              </div>
            </div>
          </div>
        </div>
      </Teleport>
    </template>

    <!-- Initial Loading State -->
    <div v-if="isInitializing" class="initializing-screen">
      <div class="spinner"></div>
      <p>読み込み中...</p>
    </div>
  </div>
</template>

<style scoped>
.app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: #f5f7fa;
}

.main {
  flex: 1;
  display: flex;
  justify-content: center;
  padding: 1rem;
}

.content-wrapper {
  width: 100%;
  max-width: 800px;
  display: flex;
  flex-direction: column;
  background: white;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  overflow: hidden;
}

.view-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 500px;
  max-height: calc(100vh - 200px);
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid #e2e8f0;
  border-top-color: #4299e1;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* Modal styles */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: white;
  border-radius: 12px;
  width: 90%;
  max-width: 500px;
  max-height: 80vh;
  overflow: hidden;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.2);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.5rem;
  border-bottom: 1px solid #e2e8f0;
}

.modal-header h2 {
  margin: 0;
  font-size: 1.25rem;
  color: #2d3748;
}

.close-btn {
  background: none;
  border: none;
  font-size: 1.5rem;
  color: #a0aec0;
  cursor: pointer;
  padding: 0;
  line-height: 1;
}

.close-btn:hover {
  color: #718096;
}

.modal-body {
  padding: 1.5rem;
  overflow-y: auto;
  max-height: 60vh;
}

.profile-summary h3,
.preferences-detail h3 {
  margin: 0 0 0.75rem;
  font-size: 0.9rem;
  font-weight: 600;
  color: #2d3748;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.profile-summary p {
  margin: 0;
  line-height: 1.6;
  color: #4a5568;
  white-space: pre-wrap;
}

.profile-summary {
  margin-bottom: 1.5rem;
  padding-bottom: 1.5rem;
  border-bottom: 1px solid #e2e8f0;
}

.preferences-detail {
  margin-bottom: 1rem;
}

.preference-category {
  margin-bottom: 1rem;
}

.preference-category h4 {
  margin: 0 0 0.5rem;
  font-size: 0.85rem;
  font-weight: 500;
  color: #718096;
}

.preference-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.preference-tag {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.35rem 0.6rem;
  border-radius: 20px;
  font-size: 0.8rem;
  cursor: default;
  transition: transform 0.1s;
}

.preference-tag:hover {
  transform: scale(1.02);
}

.preference-tag.positive {
  background: rgba(72, 187, 120, 0.15);
  color: #276749;
  border: 1px solid rgba(72, 187, 120, 0.3);
}

.preference-tag.negative {
  background: rgba(245, 101, 101, 0.15);
  color: #c53030;
  border: 1px solid rgba(245, 101, 101, 0.3);
}

.tag-name {
  font-weight: 500;
}

.tag-weight {
  font-size: 0.7rem;
  opacity: 0.7;
  font-weight: 400;
}

.no-profile {
  text-align: center;
  color: #718096;
}

.no-profile p {
  margin: 0.5rem 0;
}

.initializing-screen {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.initializing-screen .spinner {
  width: 50px;
  height: 50px;
  border: 3px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

.initializing-screen p {
  font-size: 1rem;
  opacity: 0.9;
}
</style>
