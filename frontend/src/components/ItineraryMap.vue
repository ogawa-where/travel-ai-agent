<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted, nextTick } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import type { GeoEnrichedItinerary } from '../lib/api'

const props = withDefaults(defineProps<{
  geoData: GeoEnrichedItinerary
  selectedDay: number // 0 = all days
  height: string
}>(), {
  selectedDay: 0,
  height: '300px',
})

const mapContainer = ref<HTMLDivElement | null>(null)
let map: L.Map | null = null
const layerGroup = L.layerGroup()

const CATEGORY_COLORS: Record<string, string> = {
  activity: '#3182ce',
  food: '#e53e3e',
  hotel: '#38a169',
  transportation: '#718096',
}

const DAY_ROUTE_COLORS = [
  '#3182ce', '#e53e3e', '#38a169', '#d69e2e',
  '#805ad5', '#dd6b20', '#319795', '#b83280',
]

function createMarkerIcon(color: string): L.DivIcon {
  return L.divIcon({
    className: 'custom-marker',
    html: `<div style="
      width: 24px; height: 24px;
      background: ${color};
      border: 2px solid white;
      border-radius: 50%;
      box-shadow: 0 2px 4px rgba(0,0,0,0.3);
    "></div>`,
    iconSize: [24, 24],
    iconAnchor: [12, 12],
    popupAnchor: [0, -14],
  })
}

function renderMap() {
  if (!map) return
  layerGroup.clearLayers()

  const bounds: L.LatLngExpression[] = []
  const days = props.geoData.days

  const daysToRender = props.selectedDay === 0
    ? days
    : days.filter(d => d.day_number === props.selectedDay)

  daysToRender.forEach((day, dayIdx) => {
    const routeColor = DAY_ROUTE_COLORS[dayIdx % DAY_ROUTE_COLORS.length]

    // POI markers
    day.pois.forEach(poi => {
      if (poi.latitude == null || poi.longitude == null) return
      const latLng: L.LatLngExpression = [poi.latitude, poi.longitude]
      bounds.push(latLng)

      const color = CATEGORY_COLORS[poi.category] || '#718096'
      const marker = L.marker(latLng, { icon: createMarkerIcon(color) })
      marker.bindPopup(`
        <div style="min-width:120px">
          <strong>${poi.name}</strong><br>
          <span style="color:${color};font-size:0.85em">${poi.category}</span>
          ${poi.description ? `<br><span style="font-size:0.8em;color:#666">${poi.description}</span>` : ''}
        </div>
      `)
      layerGroup.addLayer(marker)
    })

    // Route polyline
    if (day.route_geometry?.coordinates) {
      const coords = day.route_geometry.coordinates.map(
        (c: number[]) => [c[1], c[0]] as L.LatLngExpression
      )
      const polyline = L.polyline(coords, {
        color: routeColor,
        weight: 4,
        opacity: 0.7,
      })
      layerGroup.addLayer(polyline)
      coords.forEach(c => bounds.push(c))
    }
  })

  if (bounds.length > 0) {
    map.fitBounds(L.latLngBounds(bounds), { padding: [30, 30] })
  }
}

onMounted(async () => {
  await nextTick()
  if (!mapContainer.value) return

  map = L.map(mapContainer.value, {
    zoomControl: true,
    attributionControl: true,
  }).setView([36.2, 138.2], 6) // Japan center

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    maxZoom: 19,
  }).addTo(map)

  layerGroup.addTo(map)
  renderMap()
})

onUnmounted(() => {
  if (map) {
    map.remove()
    map = null
  }
})

watch(() => [props.geoData, props.selectedDay], () => {
  renderMap()
}, { deep: true })

defineExpose({
  invalidateSize: () => {
    if (map) {
      setTimeout(() => map?.invalidateSize(), 100)
    }
  },
})
</script>

<template>
  <div ref="mapContainer" class="itinerary-map" :style="{ height: height }"></div>
</template>

<style scoped>
.itinerary-map {
  width: 100%;
  border-radius: 8px;
  z-index: 0;
}
</style>
