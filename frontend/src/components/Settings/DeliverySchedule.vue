<template>
  <details
    class="rounded-xl border border-outline-gray-2 p-4"
    data-delivery-schedule
    @toggle="opened"
  >
    <summary class="flex min-h-11 cursor-pointer items-center font-medium">
      {{ __('Delivery hours and summaries') }}
    </summary>
    <div ref="host" class="mt-3 min-w-0" />
    <p v-if="error" role="alert">
      {{ __('Could not open delivery settings.') }}
      <a class="underline" href="/notification-schedule">{{
        __('Open settings')
      }}</a>
    </p>
  </details>
</template>

<script setup>
import { onBeforeUnmount, ref } from 'vue'
const props = defineProps({ viewer: { type: String, required: true } })
const host = ref(null),
  error = ref(false)
let started = false,
  disposed = false,
  cleanup
async function opened(event) {
  if (!event.target.open || started) return
  started = true
  try {
    const module = await import(
      /* @vite-ignore */ '/assets/exp_theme/js/notification_schedule_embed.js'
    )
    if (!disposed)
      cleanup = module.mount(host.value, {
        viewer: props.viewer,
        title: __('Delivery hours and summaries'),
      })
  } catch {
    if (!disposed) {
      error.value = true
      started = false
    }
  }
}
onBeforeUnmount(() => {
  disposed = true
  cleanup?.()
})
</script>
