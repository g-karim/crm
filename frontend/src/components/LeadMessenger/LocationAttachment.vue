<template>
  <div
    class="overflow-hidden rounded-md border border-outline-gray-2 bg-surface-white"
  >
    <div
      ref="mapElement"
      class="h-40 w-full bg-surface-gray-2"
      role="img"
      :aria-label="__('Геолокация: {0}', [coordinateText])"
    />
    <div class="flex items-center justify-between gap-3 px-3 py-2 text-sm">
      <div class="min-w-0">
        <div v-if="location.title" class="truncate font-medium">
          {{ location.title }}
        </div>
        <div v-if="location.address" class="truncate text-ink-gray-6">
          {{ location.address }}
        </div>
        <div class="tabular-nums text-ink-gray-5">{{ coordinateText }}</div>
      </div>
      <a
        :href="openUrl"
        target="_blank"
        rel="noopener noreferrer"
        class="shrink-0 text-ink-blue-3 hover:underline"
      >
        {{ __('Открыть карту') }}
      </a>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

const props = defineProps({
  attachment: { type: Object, required: true },
})

const mapElement = ref(null)
const location = computed(() => props.attachment.location || {})
const latitude = computed(() => Number(location.value.latitude || 0))
const longitude = computed(() => Number(location.value.longitude || 0))
const coordinateText = computed(
  () => `${latitude.value.toFixed(6)}, ${longitude.value.toFixed(6)}`,
)
const openUrl = computed(
  () =>
    `https://www.openstreetmap.org/?mlat=${latitude.value}&mlon=${longitude.value}#map=16/${latitude.value}/${longitude.value}`,
)
let map
let observer

async function initMap() {
  if (map || !mapElement.value) return
  await import('leaflet/dist/leaflet.css')
  let module = await import('leaflet')
  if (map || !mapElement.value) return
  let L = module.default ?? module
  map = L.map(mapElement.value, {
    attributionControl: true,
    zoomControl: false,
    dragging: false,
    touchZoom: false,
    doubleClickZoom: false,
    scrollWheelZoom: false,
    boxZoom: false,
    keyboard: false,
  }).setView([latitude.value, longitude.value], 15)
  map.attributionControl.setPrefix(false)
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>',
  }).addTo(map)
  L.marker([latitude.value, longitude.value], {
    interactive: false,
    icon: L.divIcon({
      className: 'crm-location-message-marker',
      html: '<span class="block size-5 rounded-full border-2 border-white bg-blue-500 shadow"></span>',
      iconSize: [20, 20],
      iconAnchor: [10, 10],
    }),
  }).addTo(map)
}

onMounted(() => {
  if (!('IntersectionObserver' in window)) return initMap()
  observer = new IntersectionObserver(
    (entries) => {
      if (!entries.some((entry) => entry.isIntersecting)) return
      observer?.disconnect()
      observer = null
      initMap()
    },
    { rootMargin: '200px' },
  )
  observer.observe(mapElement.value)
})

onBeforeUnmount(() => {
  observer?.disconnect()
  map?.remove()
  map = null
})
</script>
