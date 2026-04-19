<script setup lang="ts">
import { ref, watch } from 'vue'
import type { LearnedPreference } from '../lib/api'

const props = defineProps<{
  preferences: LearnedPreference[]
}>()

const emit = defineEmits<{
  clear: []
}>()

interface ToastItem {
  id: number
  preference: LearnedPreference
  visible: boolean
}

const toasts = ref<ToastItem[]>([])
let nextId = 0
const TOAST_DURATION = 4000

const categoryLabels: Record<string, string> = {
  likes: 'Like',
  dislikes: 'Dislike',
  experience_axis: 'Experience',
  constraints: 'Constraint',
}

const categoryIcons: Record<string, string> = {
  likes: '♥',
  dislikes: '✗',
  experience_axis: '◈',
  constraints: '⚙',
}

watch(
  () => props.preferences,
  (newPrefs) => {
    if (newPrefs && newPrefs.length > 0) {
      addToasts(newPrefs)
    }
  },
  { deep: true }
)

function addToasts(prefs: LearnedPreference[]) {
  prefs.forEach((pref, index) => {
    setTimeout(() => {
      const id = nextId++
      toasts.value.push({
        id,
        preference: pref,
        visible: true,
      })

      // Auto remove after duration
      setTimeout(() => {
        removeToast(id)
      }, TOAST_DURATION)
    }, index * 250)
  })

  // Emit clear after all toasts are processed
  setTimeout(() => {
    emit('clear')
  }, prefs.length * 250 + 100)
}

function removeToast(id: number) {
  const index = toasts.value.findIndex((t) => t.id === id)
  if (index !== -1) {
    toasts.value[index].visible = false
    setTimeout(() => {
      toasts.value = toasts.value.filter((t) => t.id !== id)
    }, 400)
  }
}
</script>

<template>
  <div class="toast-container">
    <TransitionGroup name="toast">
      <div
        v-for="toast in toasts"
        :key="toast.id"
        :class="['toast', toast.preference.category, { 'fade-out': !toast.visible }]"
      >
        <div class="toast-glow"></div>
        <span class="toast-icon">{{ categoryIcons[toast.preference.category] || '✦' }}</span>
        <span class="toast-content">
          <span class="toast-label">{{ categoryLabels[toast.preference.category] || 'Learned' }}</span>
          <span class="toast-tag">{{ toast.preference.tag }}</span>
          <span v-if="!toast.preference.is_new" class="toast-update">updated</span>
        </span>
        <div class="toast-progress"></div>
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.toast-container {
  position: fixed;
  bottom: 24px;
  right: 24px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  z-index: 1000;
  pointer-events: none;
}

.toast {
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 18px 12px 14px;
  background: rgba(255, 255, 255, 0.82);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  color: #2d3748;
  border-radius: 14px;
  font-family: 'Montserrat', sans-serif;
  font-size: 0.88rem;
  box-shadow:
    0 2px 8px rgba(102, 126, 234, 0.1),
    0 8px 32px rgba(102, 126, 234, 0.08);
  border: 1px solid rgba(102, 126, 234, 0.12);
  pointer-events: auto;
  transition: all 0.4s cubic-bezier(0.22, 1, 0.36, 1);
  overflow: hidden;
}

/* Subtle inner glow */
.toast-glow {
  position: absolute;
  inset: 0;
  border-radius: 14px;
  opacity: 0.08;
  pointer-events: none;
}

.toast.likes .toast-glow {
  background: linear-gradient(135deg, #667eea 0%, #f093fb 100%);
}

.toast.dislikes .toast-glow {
  background: linear-gradient(135deg, #fda4af 0%, #e879a0 100%);
}

.toast.experience_axis .toast-glow {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.toast.constraints .toast-glow {
  background: linear-gradient(135deg, #f6d365 0%, #fda085 100%);
}

/* Icon */
.toast-icon {
  width: 30px;
  height: 30px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 9px;
  font-size: 0.85rem;
  flex-shrink: 0;
  position: relative;
  z-index: 1;
}

.toast.likes .toast-icon {
  background: linear-gradient(135deg, #667eea 0%, #a78bfa 100%);
  color: white;
}

.toast.dislikes .toast-icon {
  background: linear-gradient(135deg, #fda4af 0%, #f472b6 100%);
  color: white;
}

.toast.experience_axis .toast-icon {
  background: linear-gradient(135deg, #818cf8 0%, #764ba2 100%);
  color: white;
}

.toast.constraints .toast-icon {
  background: linear-gradient(135deg, #fbbf24 0%, #f59e0b 100%);
  color: white;
}

/* Content */
.toast-content {
  display: flex;
  align-items: center;
  gap: 8px;
  position: relative;
  z-index: 1;
}

.toast-label {
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  opacity: 0.5;
}

.toast-tag {
  font-weight: 600;
  color: #1a202c;
}

.toast-update {
  font-size: 0.65rem;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  padding: 2px 6px;
  border-radius: 6px;
  background: rgba(102, 126, 234, 0.1);
  color: #667eea;
}

/* Progress bar at bottom */
.toast-progress {
  position: absolute;
  bottom: 0;
  left: 0;
  height: 2px;
  border-radius: 0 0 14px 14px;
  animation: progress-shrink 4s linear forwards;
}

.toast.likes .toast-progress {
  background: linear-gradient(90deg, #667eea, #a78bfa);
}

.toast.dislikes .toast-progress {
  background: linear-gradient(90deg, #fda4af, #f472b6);
}

.toast.experience_axis .toast-progress {
  background: linear-gradient(90deg, #818cf8, #764ba2);
}

.toast.constraints .toast-progress {
  background: linear-gradient(90deg, #fbbf24, #f59e0b);
}

@keyframes progress-shrink {
  from {
    width: 100%;
  }
  to {
    width: 0%;
  }
}

/* Fade out */
.toast.fade-out {
  opacity: 0;
  transform: translateX(24px) scale(0.95);
}

/* Transition animations */
.toast-enter-active {
  animation: toast-in 0.4s cubic-bezier(0.22, 1, 0.36, 1);
}

.toast-leave-active {
  animation: toast-out 0.35s cubic-bezier(0.22, 1, 0.36, 1);
}

@keyframes toast-in {
  0% {
    opacity: 0;
    transform: translateX(60px) scale(0.9);
  }
  100% {
    opacity: 1;
    transform: translateX(0) scale(1);
  }
}

@keyframes toast-out {
  0% {
    opacity: 1;
    transform: translateX(0) scale(1);
  }
  100% {
    opacity: 0;
    transform: translateX(60px) scale(0.9);
  }
}
</style>
