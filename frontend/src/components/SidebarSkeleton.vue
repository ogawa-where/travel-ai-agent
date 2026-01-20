<script setup lang="ts">
import SkeletonLoader from './SkeletonLoader.vue'

defineProps<{
  variant?: 'preference' | 'travel'
}>()
</script>

<template>
  <div class="sidebar-skeleton">
    <SkeletonLoader width="40%" height="1.25rem" />

    <div class="section">
      <SkeletonLoader :lines="2" />
    </div>

    <template v-if="variant === 'preference'">
      <div class="signals-skeleton">
        <div v-for="i in 4" :key="i" class="signal-item">
          <SkeletonLoader width="50px" height="1.25rem" />
          <SkeletonLoader width="80px" />
          <SkeletonLoader width="30px" />
        </div>
      </div>
    </template>

    <template v-else>
      <div class="score-skeleton">
        <div class="score-header">
          <SkeletonLoader width="60px" />
          <SkeletonLoader width="40px" />
        </div>
        <div v-for="i in 4" :key="i" class="score-item">
          <SkeletonLoader width="50px" />
          <SkeletonLoader height="6px" />
          <SkeletonLoader width="30px" />
        </div>
      </div>
    </template>

    <SkeletonLoader variant="rectangle" height="40px" />
  </div>
</template>

<style scoped>
.sidebar-skeleton {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.section {
  padding: 0.75rem;
  background: #f8f9fa;
  border-radius: 6px;
}

.signals-skeleton {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.signal-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0;
  border-bottom: 1px solid #ecf0f1;
}

.signal-item:last-child {
  border-bottom: none;
}

.score-skeleton {
  padding: 0.75rem;
  background: #f8f9fa;
  border-radius: 6px;
}

.score-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 0.75rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid #e0e0e0;
}

.score-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.score-item > :nth-child(2) {
  flex: 1;
}
</style>
