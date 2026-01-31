<script setup lang="ts">
import SkeletonLoader from './SkeletonLoader.vue'
</script>

<template>
  <div class="chat-skeleton">
    <div class="message-skeleton assistant">
      <SkeletonLoader variant="circle" width="32px" height="32px" />
      <div class="message-content">
        <SkeletonLoader :lines="3" />
      </div>
    </div>
    <div class="message-skeleton user">
      <div class="message-content">
        <SkeletonLoader width="70%" />
      </div>
    </div>
    <div class="message-skeleton assistant">
      <SkeletonLoader variant="circle" width="32px" height="32px" />
      <div class="message-content">
        <SkeletonLoader :lines="2" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat-skeleton {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding: 1rem;
}

.message-skeleton {
  display: flex;
  gap: 0.75rem;
  max-width: 80%;
}

.message-skeleton.user {
  align-self: flex-end;
  flex-direction: row-reverse;
}

.message-content {
  flex: 1;
  padding: 0.75rem 1rem;
  background: #f8f9fa;
  border-radius: 12px;
  min-width: 200px;
}

.message-skeleton.user .message-content {
  background: #e8f4fd;
}
</style>
