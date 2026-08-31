<template>
  <Dialog v-model="show" :options="{ title: __('Send Location'), size: '3xl' }">
    <template #body-content>
      <div
        ref="mapElement"
        class="h-[clamp(10rem,55dvh,26.25rem)] w-full rounded-md"
      />
      <div v-if="selected" class="mt-2 text-sm tabular-nums text-ink-gray-6">
        {{ selected.latitude.toFixed(6) }}, {{ selected.longitude.toFixed(6) }}
      </div>
    </template>
    <template #actions>
      <div class="flex justify-end gap-2">
        <Button :label="__('Cancel')" variant="outline" @click="show = false" />
        <Button
          :label="__('Add Location')"
          variant="solid"
          :disabled="!selected"
          @click="confirm"
        />
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { Button, Dialog } from 'frappe-ui'
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  location: { type: Object, default: null },
})
const emit = defineEmits(['update:modelValue', 'select'])
const show = ref(props.modelValue)
const selected = ref(props.location ? { ...props.location } : null)
const mapElement = ref(null)
let L
let map
let marker

watch(
  () => props.modelValue,
  (value) => (show.value = value),
)
watch(
  show,
  async (value) => {
    emit('update:modelValue', value)
    if (!value) return destroyMap()
    selected.value = props.location ? { ...props.location } : null
    await nextTick()
    await initMap()
  },
  { immediate: true },
)

async function initMap() {
  await import('leaflet/dist/leaflet.css')
  if (!show.value || !mapElement.value) return
  let module = await import('leaflet')
  if (!show.value || !mapElement.value) return
  L = module.default ?? module
  map = L.map(mapElement.value).setView(
    selected.value
      ? [selected.value.latitude, selected.value.longitude]
      : [20, 0],
    selected.value ? 15 : 2,
  )
  map.attributionControl.setPrefix(false)
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>',
  }).addTo(map)
  map.on('click', (event) =>
    setPoint(event.latlng.lat, event.latlng.lng, false),
  )
  if (selected.value)
    setPoint(selected.value.latitude, selected.value.longitude, false)
  navigator.geolocation?.getCurrentPosition(
    (position) => {
      if (!selected.value && map)
        setPoint(position.coords.latitude, position.coords.longitude, true)
    },
    () => {},
    { enableHighAccuracy: true, timeout: 8000 },
  )
}

function setPoint(latitude, longitude, center) {
  selected.value = { latitude, longitude }
  if (marker) marker.setLatLng([latitude, longitude])
  else
    marker = L.marker([latitude, longitude], {
      draggable: true,
      icon: L.divIcon({
        className: 'crm-location-picker-marker',
        html: '<span class="block size-5 rounded-full border-2 border-white bg-blue-500 shadow"></span>',
        iconSize: [20, 20],
        iconAnchor: [10, 10],
      }),
    })
      .on('dragend', (event) => {
        let point = event.target.getLatLng()
        selected.value = { latitude: point.lat, longitude: point.lng }
      })
      .addTo(map)
  if (center) map.setView([latitude, longitude], 15)
}

function confirm() {
  if (!selected.value) return
  emit('select', { ...selected.value })
  show.value = false
}

function destroyMap() {
  map?.remove()
  map = null
  marker = null
}

onBeforeUnmount(destroyMap)
</script>
