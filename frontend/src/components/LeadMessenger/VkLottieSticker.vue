<template>
  <div
    class="relative flex size-full max-h-full max-w-full items-center justify-center overflow-hidden"
    :aria-label="__(title)"
  >
    <div
      ref="animationContainer"
      class="size-full"
      :class="ready && !reducedMotion ? 'block' : 'hidden'"
      aria-hidden="true"
    />
    <img
      v-if="
        (!ready || reducedMotion) && attachment.preview_url && !previewFailed
      "
      :src="attachment.preview_url"
      :alt="__(title)"
      class="size-full object-contain"
      loading="lazy"
      @error="previewFailed = true"
    />
    <div
      v-else-if="!ready || reducedMotion"
      class="flex size-full flex-col items-center justify-center gap-2 rounded-lg bg-surface-gray-2 p-3 text-center text-xs text-ink-gray-5"
    >
      <span :role="loading ? 'status' : undefined">{{
        loading ? __('Loading...') : __('Sticker unavailable')
      }}</span>
    </div>
    <button
      v-if="failed && !reducedMotion"
      type="button"
      class="absolute bottom-1 min-h-8 rounded bg-surface-base px-2 text-sm text-ink-blue-6 focus-visible:ring-2"
      @click.stop="loadAnimation"
    >
      {{ __('Try Again') }}
    </button>
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
const loading = ref(false)
const failed = ref(false)
const previewFailed = ref(false)
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
let loadTimer = null

function destroyAnimation() {
  clearTimeout(loadTimer)
  loadTimer = null
  abortController?.abort()
  abortController = null
  animation?.destroy()
  animation = null
  ready.value = false
  loading.value = false
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
  failed.value = false
  previewFailed.value = false
  if (reducedMotion.value || !props.attachment.url) return

  let source
  try {
    source = new URL(props.attachment.url, window.location.origin)
  } catch {
    return
  }
  if (source.origin !== window.location.origin) return

  abortController = new AbortController()
  loading.value = true
  const fail = () => {
    if (sequence !== loadSequence) return
    // Invalidate even a fetch/decoder which finishes after the deadline.
    loadSequence += 1
    failed.value = true
    destroyAnimation()
  }
  loadTimer = setTimeout(fail, 20000)
  try {
    let response = await fetch(source.href, {
      credentials: 'same-origin',
      redirect: 'error',
      signal: abortController.signal,
      headers: { Accept: 'application/json' },
    })
    if (sequence !== loadSequence) return
    if (!response.ok) return fail()
    let animationData = await response.json()
    if (sequence !== loadSequence) return
    if (!isSafeAnimationData(animationData)) return fail()
    await nextTick()
    if (!animationContainer.value || sequence !== loadSequence) return

    let module = await import('lottie-web/build/player/lottie_light')
    if (sequence !== loadSequence) return
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
      if (sequence === loadSequence) {
        clearTimeout(loadTimer)
        loadTimer = null
        loading.value = false
        ready.value = true
      }
    })
    animation.addEventListener('data_failed', fail)
    animation.addEventListener('error', fail)
  } catch (error) {
    if (error?.name !== 'AbortError') fail()
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
