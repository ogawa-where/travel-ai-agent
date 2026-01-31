<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted, nextTick } from 'vue'
import ItineraryMap from './ItineraryMap.vue'
import type { GeoEnrichedItinerary } from '../lib/api'

const props = defineProps<{
  geoData: GeoEnrichedItinerary
  visible: boolean
}>()

const emit = defineEmits<{
  close: []
}>()

const selectedDay = ref(0)
const mapRef = ref<InstanceType<typeof ItineraryMap> | null>(null)

const dayTabs = ref<{ label: string; value: number }[]>([])

watch(() => props.geoData, (data) => {
  const tabs = [{ label: '全日程', value: 0 }]
  data.days.forEach(d => {
    tabs.push({ label: `Day ${d.day_number}`, value: d.day_number })
  })
  dayTabs.value = tabs
}, { immediate: true })

watch(() => props.visible, async (visible) => {
  if (visible) {
    await nextTick()
    mapRef.value?.invalidateSize()
  }
})

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') emit('close')
}

onMounted(() => {
  document.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown)
})

function currentDayInfo() {
  if (selectedDay.value === 0) {
    const totalDist = props.geoData.days.reduce((s, d) => s + (d.total_distance_km || 0), 0)
    const totalDur = props.geoData.days.reduce((s, d) => s + (d.total_duration_minutes || 0), 0)
    return { distance: totalDist, duration: totalDur }
  }
  const day = props.geoData.days.find(d => d.day_number === selectedDay.value)
  return {
    distance: day?.total_distance_km || 0,
    duration: day?.total_duration_minutes || 0,
  }
}
</script>

<template>
  <Teleport to="body">
    <Transition name="modal-fade">
      <div v-if="visible" class="modal-overlay" @click.self="emit('close')">
        <div class="modal-panel">
          <div class="modal-header">
            <h3>旅程マップ</h3>
            <div class="route-info" v-if="currentDayInfo().distance > 0">
              <span>{{ currentDayInfo().distance.toFixed(1) }} km</span>
              <span class="separator">|</span>
              <span>{{ Math.round(currentDayInfo().duration) }} 分</span>
            </div>
            <button class="close-btn" @click="emit('close')" aria-label="閉じる">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </div>

          <div class="day-tabs">
            <button
              v-for="tab in dayTabs"
              :key="tab.value"
              :class="['tab-btn', { active: selectedDay === tab.value }]"
              @click="selectedDay = tab.value"
            >
              {{ tab.label }}
            </button>
          </div>

          <div class="modal-map">
            <ItineraryMap
              ref="mapRef"
              :geo-data="geoData"
              :selected-day="selectedDay"
              height="100%"
            />
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-panel {
  width: 90vw;
  height: 90vh;
  background: white;
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.modal-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 20px;
  border-bottom: 1px solid #e2e8f0;
}

.modal-header h3 {
  margin: 0;
  font-size: 1.1rem;
  color: #2d3748;
}

.route-info {
  flex: 1;
  font-size: 0.85rem;
  color: #718096;
}

.route-info .separator {
  margin: 0 6px;
  color: #cbd5e0;
}

.close-btn {
  background: none;
  border: none;
  padding: 4px;
  color: #a0aec0;
  cursor: pointer;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.close-btn:hover {
  color: #4a5568;
  background: #f7fafc;
}

.day-tabs {
  display: flex;
  gap: 4px;
  padding: 8px 20px;
  border-bottom: 1px solid #e2e8f0;
  overflow-x: auto;
}

.tab-btn {
  padding: 6px 14px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  background: white;
  color: #4a5568;
  font-size: 0.85rem;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.2s;
}

.tab-btn:hover {
  background: #f7fafc;
}

.tab-btn.active {
  background: #4299e1;
  color: white;
  border-color: #4299e1;
}

.modal-map {
  flex: 1;
  min-height: 0;
}

.modal-map :deep(.itinerary-map) {
  border-radius: 0;
  height: 100% !important;
}

/* Transition */
.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 0.2s ease;
}

.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}
</style>
