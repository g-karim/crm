<template>
  <Teleport to="body">
    <div
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/90"
      role="dialog"
      aria-modal="true"
      @click.self="emit('close')"
    >
      <div
        ref="viewport"
        data-lightbox-viewport
        class="flex size-full touch-none select-none items-center justify-center overflow-hidden p-2 sm:p-8"
        :class="scale > 1 ? (dragging ? 'cursor-grabbing' : 'cursor-grab') : ''"
        @wheel.prevent="onWheel"
        @pointerdown="startPan"
        @pointermove="movePan"
        @pointerup="endPan"
        @pointercancel="endPan"
      >
        <img
          ref="imageElement"
          data-lightbox-image
          :src="current.url"
          :alt="current.file_name || __('Изображение')"
          class="max-h-full max-w-full object-contain will-change-transform"
          :style="imageStyle"
          draggable="false"
          @dblclick.stop="resetView"
        />
      </div>

      <div
        class="absolute left-1/2 top-3 z-20 flex -translate-x-1/2 items-center gap-1 rounded-xl border border-white/20 bg-black/70 p-1.5 text-white shadow-lg backdrop-blur"
      >
        <a
          v-if="current.download_url"
          data-lightbox-download
          :href="current.download_url"
          class="grid size-9 place-items-center rounded-lg text-white transition duration-150 ease-out hover:scale-105 hover:bg-white/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/70 active:scale-90 active:bg-white/30"
          :aria-label="__('Скачать')"
          :title="__('Скачать')"
        >
          <DownloadIcon class="size-4" />
        </a>
        <button
          data-lightbox-zoom-out
          type="button"
          class="grid size-9 place-items-center rounded-lg transition duration-150 ease-out hover:scale-105 hover:bg-white/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/70 active:scale-90 active:bg-white/30 disabled:opacity-40 disabled:hover:scale-100"
          :disabled="scale <= MIN_SCALE"
          :aria-label="__('Уменьшить')"
          @click="setScale(scale - SCALE_STEP)"
        >
          <MinusIcon class="size-4" />
        </button>
        <button
          data-lightbox-reset
          type="button"
          class="min-w-14 rounded-lg px-2 py-2 text-xs font-medium transition duration-150 ease-out hover:scale-105 hover:bg-white/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/70 active:scale-90 active:bg-white/30"
          :aria-label="__('Сбросить масштаб')"
          @click="resetView"
        >
          {{ Math.round(scale * 100) }}%
        </button>
        <button
          data-lightbox-zoom-in
          type="button"
          class="grid size-9 place-items-center rounded-lg transition duration-150 ease-out hover:scale-105 hover:bg-white/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/70 active:scale-90 active:bg-white/30 disabled:opacity-40 disabled:hover:scale-100"
          :disabled="scale >= MAX_SCALE"
          :aria-label="__('Увеличить')"
          @click="setScale(scale + SCALE_STEP)"
        >
          <PlusIcon class="size-4" />
        </button>
        <button
          data-lightbox-close
          type="button"
          class="grid size-9 place-items-center rounded-lg transition duration-150 ease-out hover:scale-105 hover:bg-white/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/70 active:scale-90 active:bg-white/30"
          :aria-label="__('Закрыть')"
          @click="emit('close')"
        >
          <XIcon class="size-4" />
        </button>
      </div>

      <button
        v-if="images.length > 1"
        data-lightbox-previous
        type="button"
        class="absolute left-2 z-10 grid size-11 place-items-center rounded-full border border-white/20 bg-black/65 p-0 leading-none text-white shadow transition duration-150 ease-out hover:scale-105 hover:bg-black/85 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/70 active:scale-90 active:bg-white/20 sm:left-6"
        :aria-label="__('Предыдущее изображение')"
        @click="move(-1)"
      >
        <span class="grid size-full place-items-center leading-none">
          <ChevronLeftIcon class="block size-6 -translate-x-px" />
        </span>
      </button>
      <button
        v-if="images.length > 1"
        data-lightbox-next
        type="button"
        class="absolute right-2 z-10 grid size-11 place-items-center rounded-full border border-white/20 bg-black/65 p-0 leading-none text-white shadow transition duration-150 ease-out hover:scale-105 hover:bg-black/85 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/70 active:scale-90 active:bg-white/20 sm:right-6"
        :aria-label="__('Следующее изображение')"
        @click="move(1)"
      >
        <span class="grid size-full place-items-center leading-none">
          <ChevronRightIcon class="block size-6 translate-x-px" />
        </span>
      </button>
      <div
        v-if="images.length > 1"
        class="absolute bottom-3 rounded-full border border-white/20 bg-black/70 px-3 py-1 text-sm text-white"
      >
        {{ currentIndex + 1 }} / {{ images.length }}
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import ChevronLeftIcon from '~icons/lucide/chevron-left'
import ChevronRightIcon from '~icons/lucide/chevron-right'
import DownloadIcon from '~icons/lucide/download'
import MinusIcon from '~icons/lucide/minus'
import PlusIcon from '~icons/lucide/plus'
import XIcon from '~icons/lucide/x'

const MIN_SCALE = 1
const MAX_SCALE = 5
const SCALE_STEP = 0.25

const props = defineProps({
  images: { type: Array, default: () => [] },
  initialIndex: { type: Number, default: 0 },
})
const emit = defineEmits(['close'])
const currentIndex = ref(normalizedIndex(props.initialIndex))
const current = computed(() => props.images[currentIndex.value] || {})
const viewport = ref(null)
const imageElement = ref(null)
const scale = ref(MIN_SCALE)
const panX = ref(0)
const panY = ref(0)
const dragging = ref(false)
let dragStart = null
let previousOverflow = ''

const imageStyle = computed(() => ({
  transform: `translate3d(${panX.value}px, ${panY.value}px, 0) scale(${scale.value})`,
  transition: dragging.value ? 'none' : 'transform 120ms ease-out',
}))

function normalizedIndex(value) {
  if (!props.images.length) return 0
  let number = Number.isFinite(Number(value)) ? Number(value) : 0
  return Math.min(Math.max(Math.trunc(number), 0), props.images.length - 1)
}

function move(delta) {
  if (!props.images.length) return
  currentIndex.value =
    (currentIndex.value + delta + props.images.length) % props.images.length
}

function setScale(value, clientX, clientY) {
  let next = Math.min(Math.max(value, MIN_SCALE), MAX_SCALE)
  if (next === scale.value) return
  let rect = viewport.value?.getBoundingClientRect()
  if (rect && Number.isFinite(clientX) && Number.isFinite(clientY)) {
    let offsetX = clientX - (rect.left + rect.width / 2) - panX.value
    let offsetY = clientY - (rect.top + rect.height / 2) - panY.value
    let ratio = next / scale.value
    panX.value -= offsetX * (ratio - 1)
    panY.value -= offsetY * (ratio - 1)
  }
  scale.value = next
  clampPan()
}

function onWheel(event) {
  setScale(
    scale.value + (event.deltaY < 0 ? SCALE_STEP : -SCALE_STEP),
    event.clientX,
    event.clientY,
  )
}

function startPan(event) {
  if (scale.value <= MIN_SCALE || event.button !== 0) return
  dragging.value = true
  dragStart = {
    pointerId: event.pointerId,
    x: event.clientX,
    y: event.clientY,
    panX: panX.value,
    panY: panY.value,
  }
  viewport.value?.setPointerCapture?.(event.pointerId)
}

function movePan(event) {
  if (!dragging.value || event.pointerId !== dragStart?.pointerId) return
  panX.value = dragStart.panX + event.clientX - dragStart.x
  panY.value = dragStart.panY + event.clientY - dragStart.y
  clampPan()
}

function endPan(event) {
  if (!dragging.value || event.pointerId !== dragStart?.pointerId) return
  viewport.value?.releasePointerCapture?.(event.pointerId)
  dragging.value = false
  dragStart = null
}

function clampPan() {
  if (scale.value <= MIN_SCALE) {
    panX.value = 0
    panY.value = 0
    return
  }
  let container = viewport.value
  let image = imageElement.value
  if (!container || !image) return
  let maxX = Math.max((image.offsetWidth * scale.value - container.clientWidth) / 2, 0)
  let maxY = Math.max((image.offsetHeight * scale.value - container.clientHeight) / 2, 0)
  panX.value = Math.min(Math.max(panX.value, -maxX), maxX)
  panY.value = Math.min(Math.max(panY.value, -maxY), maxY)
}

function resetView() {
  scale.value = MIN_SCALE
  panX.value = 0
  panY.value = 0
  dragging.value = false
  dragStart = null
}

function onKeydown(event) {
  if (event.key === 'Escape') emit('close')
  else if (event.key === 'ArrowLeft' && props.images.length > 1) move(-1)
  else if (event.key === 'ArrowRight' && props.images.length > 1) move(1)
  else if (event.key === '+' || event.key === '=') setScale(scale.value + SCALE_STEP)
  else if (event.key === '-') setScale(scale.value - SCALE_STEP)
  else if (event.key === '0') resetView()
  else return
  event.preventDefault()
}

watch(currentIndex, async () => {
  resetView()
  await nextTick()
  clampPan()
})

watch(
  () => props.initialIndex,
  (value) => (currentIndex.value = normalizedIndex(value)),
)

onMounted(() => {
  previousOverflow = document.body.style.overflow
  document.body.style.overflow = 'hidden'
  window.addEventListener('keydown', onKeydown)
})

onBeforeUnmount(() => {
  document.body.style.overflow = previousOverflow
  window.removeEventListener('keydown', onKeydown)
})
</script>
