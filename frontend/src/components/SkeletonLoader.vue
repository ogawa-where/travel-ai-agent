<script setup lang="ts">
defineProps<{
  variant?: 'text' | 'circle' | 'rectangle'
  width?: string
  height?: string
  lines?: number
}>()
</script>

<template>
  <div class="skeleton-container">
    <template v-if="lines && lines > 1">
      <div
        v-for="i in lines"
        :key="i"
        class="skeleton skeleton-text"
        :style="{
          width: i === lines ? '60%' : '100%',
          height: height || '1rem',
        }"
      />
    </template>
    <div
      v-else
      :class="['skeleton', `skeleton-${variant || 'text'}`]"
      :style="{
        width: width || '100%',
        height: height || (variant === 'circle' ? width || '40px' : '1rem'),
      }"
    />
  </div>
</template>

<style scoped>
.skeleton-container {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.skeleton {
  background: linear-gradient(
    90deg,
    #e0e0e0 25%,
    #f0f0f0 50%,
    #e0e0e0 75%
  );
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: 4px;
}

.skeleton-circle {
  border-radius: 50%;
}

.skeleton-rectangle {
  border-radius: 6px;
}

@keyframes shimmer {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}
</style>
