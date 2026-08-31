<template>
  <div
    class="relative flex size-52 max-h-52 max-w-52 items-center justify-center overflow-hidden"
    :aria-label="__(title)"
  >
    <div
      ref="animationContainer"
      class="size-full"
      :class="ready && !reducedMotion ? 'block' : 'hidden'"
      aria-hidden="true"
    />
    <img
      v-if="(!ready || reducedMotion) && attachment.preview_url"
      :src="attachment.preview_url"
      :alt="__(title)"
      class="max-h-52 max-w-52 object-contain"
      loading="lazy"
    />
    <div
      v-else-if="!ready || reducedMotion"
      class="flex size-full items-center justify-center rounded-lg bg-surface-gray-2 p-3 text-center text-xs text-ink-gray-5"
    >
      {{ __('Sticker unavailable') }}
    </div>
  </div>
</template>

<script setup>
import { getMessengerAttachmentTitle } from '@/utils/messengerAttachments'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps({
  attachment: { type: Object, required: true },
})

const animationContainer = ref(null)
const ready = ref(false)
const reducedMotion = ref(false)
const title = computed(() =>
  getMessengerAttachmentTitle({
    ...props.attachment,
    type: props.attachment.type || 'sticker',
  }),
)
let animation = null
let abortController = null
let mediaQuery = null
let loadSequence = 0

function destroyAnimation() {
  abortController?.abort()
  abortController = null
  animation?.destroy()
  animation = null
  ready.value = false
  if (animationContainer.value) animationContainer.value.replaceChildren()
}

function isSafeAnimationData(data) {
  if (!data || typeof data !== 'object' || !Array.isArray(data.layers))
    return false
  if (!Array.isArray(data.assets || [])) return false
  return !(data.assets || []).some(
    (asset) =>
      !asset ||
      typeof asset !== 'object' ||
      Boolean(asset.p) ||
      Boolean(asset.u),
  )
}

async function loadAnimation() {
  let sequence = ++loadSequence
  destroyAnimation()
  if (reducedMotion.value || !props.attachment.url) return

  let source
  try {
    source = new URL(props.attachment.url, window.location.origin)
  } catch {
    return
  }
  if (source.origin !== window.location.origin) return

  abortController = new AbortController()
  try {
    let response = await fetch(source.href, {
      credentials: 'same-origin',
      redirect: 'error',
      signal: abortController.signal,
      headers: { Accept: 'application/json' },
    })
    if (!response.ok) return
    let animationData = await response.json()
    if (!isSafeAnimationData(animationData) || sequence !== loadSequence) return
    await nextTick()
    if (!animationContainer.value || sequence !== loadSequence) return

    let module = await import('lottie-web/build/player/lottie_light')
    let lottie = module.default || module
    animation = lottie.loadAnimation({
      container: animationContainer.value,
      renderer: 'svg',
      loop: true,
      autoplay: true,
      animationData,
      rendererSettings: {
        preserveAspectRatio: 'xMidYMid meet',
        runExpressions: false,
      },
    })
    animation.addEventListener('DOMLoaded', () => {
      if (sequence === loadSequence) ready.value = true
    })
    animation.addEventListener('data_failed', destroyAnimation)
    animation.addEventListener('error', destroyAnimation)
  } catch (error) {
    if (error?.name !== 'AbortError') destroyAnimation()
  }
}

function updateMotionPreference(event) {
  reducedMotion.value = Boolean(event.matches)
  loadAnimation()
}

onMounted(() => {
  mediaQuery = window.matchMedia?.('(prefers-reduced-motion: reduce)') || null
  reducedMotion.value = Boolean(mediaQuery?.matches)
  mediaQuery?.addEventListener?.('change', updateMotionPreference)
  loadAnimation()
})

watch(
  () => props.attachment.url,
  () => loadAnimation(),
)

onBeforeUnmount(() => {
  loadSequence += 1
  mediaQuery?.removeEventListener?.('change', updateMotionPreference)
  destroyAnimation()
})
</script>
