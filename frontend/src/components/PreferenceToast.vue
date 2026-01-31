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
const TOAST_DURATION = 3000

const categoryLabels: Record<string, string> = {
  likes: '好み',
  dislikes: '苦手',
  experience_axis: '体験',
  constraints: '条件',
}

const categoryIcons: Record<string, string> = {
  likes: '+',
  dislikes: '-',
  experience_axis: '*',
  constraints: '!',
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
    }, index * 200) // Stagger the toasts
  })

  // Emit clear after all toasts are processed
  setTimeout(() => {
    emit('clear')
  }, prefs.length * 200 + 100)
}

function removeToast(id: number) {
  const index = toasts.value.findIndex((t) => t.id === id)
  if (index !== -1) {
    toasts.value[index].visible = false
    setTimeout(() => {
      toasts.value = toasts.value.filter((t) => t.id !== id)
    }, 300) // Wait for fade out animation
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
        <span class="toast-icon">{{ categoryIcons[toast.preference.category] || '+' }}</span>
        <span class="toast-content">
          <span class="toast-label">{{ categoryLabels[toast.preference.category] || '学習' }}</span>
          <span class="toast-tag">{{ toast.preference.tag }}</span>
          <span v-if="!toast.preference.is_new" class="toast-update">(更新)</span>
        </span>
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.toast-container {
  position: fixed;
  bottom: 20px;
  right: 20px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  z-index: 1000;
  pointer-events: none;
}

.toast {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  background: rgba(45, 55, 72, 0.95);
  color: white;
  border-radius: 8px;
  font-size: 0.9rem;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  backdrop-filter: blur(8px);
  pointer-events: auto;
  transition: all 0.3s ease;
}

.toast.likes {
  background: rgba(72, 187, 120, 0.95);
}

.toast.dislikes {
  background: rgba(245, 101, 101, 0.95);
}

.toast.experience_axis {
  background: rgba(66, 153, 225, 0.95);
}

.toast.constraints {
  background: rgba(237, 137, 54, 0.95);
}

.toast-icon {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 50%;
  font-weight: bold;
}

.toast-content {
  display: flex;
  align-items: center;
  gap: 6px;
}

.toast-label {
  font-size: 0.75rem;
  opacity: 0.8;
}

.toast-tag {
  font-weight: 600;
}

.toast-update {
  font-size: 0.75rem;
  opacity: 0.7;
}

.toast.fade-out {
  opacity: 0;
  transform: translateX(20px);
}

/* Transition animations */
.toast-enter-active {
  animation: slideIn 0.3s ease;
}

.toast-leave-active {
  animation: slideOut 0.3s ease;
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateX(100px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

@keyframes slideOut {
  from {
    opacity: 1;
    transform: translateX(0);
  }
  to {
    opacity: 0;
    transform: translateX(100px);
  }
}
</style>
