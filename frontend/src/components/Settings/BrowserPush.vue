<template>
  <section v-if="selected" ref="host" hidden></section>
</template>
<script setup>
import { onMounted, onBeforeUnmount, ref } from 'vue'
import { initCommonPush } from '@/utils/commonPush'
const selected = Boolean((window.frappe?.boot || window.boot || window)?.exp_common_push_test)
const host = ref(null)
let dispose, closed = false
onMounted(async () => {
  try {
    const client = await initCommonPush()
    if (!closed && client && host.value) dispose = window.ExpCommonPush.mount(host.value, client, (window.frappe?.boot || window.boot || window)?.lang || 'en')
  } catch {
    if (host.value) { host.value.hidden = false; host.value.setAttribute('role', 'alert'); host.value.textContent = __('Could not load browser notifications. Reload the page.') }
  }
})
onBeforeUnmount(() => { closed = true; dispose?.() })
</script>
