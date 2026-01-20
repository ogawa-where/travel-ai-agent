<script setup lang="ts">
type AppMode = 'preference' | 'travel'

const props = defineProps<{
  currentMode: AppMode
  modeTitle: string
}>()

const emit = defineEmits<{
  switchMode: [mode: AppMode]
}>()
</script>

<template>
  <header class="header">
    <div class="header-content">
      <div>
        <h1>Travel AI Agent</h1>
        <p>{{ modeTitle }}</p>
      </div>
      <div class="mode-switcher">
        <button
          :class="['mode-btn', { active: currentMode === 'preference' }]"
          @click="emit('switchMode', 'preference')"
        >
          嗜好学習
        </button>
        <button
          :class="['mode-btn', { active: currentMode === 'travel' }]"
          @click="emit('switchMode', 'travel')"
        >
          旅行企画
        </button>
      </div>
    </div>
  </header>
</template>

<style scoped>
.header {
  background: #2c3e50;
  color: white;
  padding: 1rem 2rem;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  max-width: 1200px;
  margin: 0 auto;
}

.header h1 {
  margin: 0;
  font-size: 1.5rem;
}

.header p {
  margin: 0.25rem 0 0;
  opacity: 0.8;
  font-size: 0.9rem;
}

.mode-switcher {
  display: flex;
  gap: 0.5rem;
}

.mode-btn {
  padding: 0.5rem 1rem;
  border: 1px solid rgba(255, 255, 255, 0.3);
  background: transparent;
  color: white;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.9rem;
  transition: all 0.2s;
}

.mode-btn:hover {
  background: rgba(255, 255, 255, 0.1);
}

.mode-btn.active {
  background: white;
  color: #2c3e50;
}
</style>
