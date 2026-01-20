<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from './lib/api'

const healthStatus = ref<string>('checking...')

onMounted(async () => {
  try {
    const response = await api.healthCheck()
    healthStatus.value = response.status
  } catch {
    healthStatus.value = 'error'
  }
})
</script>

<template>
  <div class="container">
    <h1>Travel AI Agent</h1>
    <p>体験型旅行企画マルチエージェントシステム</p>
    <p>Backend Status: {{ healthStatus }}</p>
  </div>
</template>

<style scoped>
.container {
  max-width: 800px;
  margin: 0 auto;
  padding: 2rem;
  font-family: sans-serif;
}

h1 {
  color: #333;
}
</style>
