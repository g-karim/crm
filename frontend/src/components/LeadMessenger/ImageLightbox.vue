<template>
  <Teleport to="body">
    <div
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/90 p-3 sm:p-8"
      role="dialog"
      aria-modal="true"
      @click.self="emit('close')"
    >
      <Button
        class="absolute right-3 top-3 !text-white"
        variant="ghost"
        icon="x"
        :aria-label="__('Закрыть')"
        @click="emit('close')"
      />
      <Button
        v-if="images.length > 1"
        class="absolute left-2 z-10 !text-white sm:left-6"
        variant="ghost"
        icon="chevron-left"
        @click="move(-1)"
      />
      <img
        :src="current.url"
        :alt="current.file_name || __('Изображение')"
        class="max-h-full max-w-full select-none object-contain"
      />
      <Button
        v-if="images.length > 1"
        class="absolute right-2 z-10 !text-white sm:right-6"
        variant="ghost"
        icon="chevron-right"
        @click="move(1)"
      />
      <div
        v-if="images.length > 1"
        class="absolute bottom-3 rounded-full bg-black/60 px-3 py-1 text-sm text-white"
      >
        {{ currentIndex + 1 }} / {{ images.length }}
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { Button } from 'frappe-ui'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

const props = defineProps({
  images: { type: Array, default: () => [] },
  initialIndex: { type: Number, default: 0 },
})
const emit = defineEmits(['close'])
const currentIndex = ref(props.initialIndex)
const current = computed(() => props.images[currentIndex.value] || {})
let previousOverflow = ''

function move(delta) {
  currentIndex.value =
    (currentIndex.value + delta + props.images.length) % props.images.length
}

function onKeydown(event) {
  if (event.key === 'Escape') emit('close')
  if (event.key === 'ArrowLeft' && props.images.length > 1) move(-1)
  if (event.key === 'ArrowRight' && props.images.length > 1) move(1)
}

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
