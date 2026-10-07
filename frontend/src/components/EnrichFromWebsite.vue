<template>
  <!-- While running, the spinner replaces the icon (no crawl details). -->
  <Button
    v-if="isEnabled(doctype)"
    :label="__('Enrich')"
    :loading="running"
    :loadingText="__('Enriching')"
    :tooltip="running ? __('Enriching…') : __('Enrich from website')"
    iconLeft="zap"
    @click="enrich"
  />
</template>

<script setup>
import { computed, onBeforeUnmount, watch } from 'vue'
import { Button, call, toast } from 'frappe-ui'
import { useTelemetry } from 'frappe-ui/frappe'
import { globalStore } from '@/stores/global'
import { organizationsStore } from '@/stores/organizations'
import { enrichmentStore } from '@/stores/enrichment'

const props = defineProps({
  doctype: { type: String, required: true },
  docname: { type: String, required: true },
  website: { type: String, default: '' },
})

const emit = defineEmits(['done'])

const { $socket } = globalStore()
const { organizations } = organizationsStore()
const { isEnabled, pending } = enrichmentStore()
const { capture } = useTelemetry()
const EVENT = 'domain_enrichment_progress'

const recordKey = computed(() => JSON.stringify([props.doctype, props.docname]))
const running = computed(() => Boolean(pending[recordKey.value]))
let pollTimer
let generation = 0

function isForThisDoc(data) {
  return (
    data &&
    data.reference_doctype === props.doctype &&
    data.reference_name === props.docname
  )
}

function cleanup() {
  generation += 1
  clearTimeout(pollTimer)
  $socket.off(EVENT, onProgress)
}

function finish() {
  cleanup()
  delete pending[recordKey.value]
}

function onProgress(data) {
  if (!running.value || !isForThisDoc(data)) return
  // Intermediate steps are intentionally ignored — the button shows only a
  // spinner, never the crawl details. We act only on terminal states.
  if (data.status === 'completed') {
    finish()
    // Re-validate the cached organizations store so list views (whose logos/names
    // are read from it) reflect this update even if no list page was open to catch
    // the event — otherwise navigating back to a list serves stale cached data.
    organizations.reload()
    const filled = (data.payload && data.payload.filled_fields) || []
    const notes = (data.payload && data.payload.notes) || []
    if (filled.length) {
      toast.success(
        __('Enriched. Filled: {0}', [
          filled.map((label) => __(label)).join(', '),
        ]),
      )
    } else if (notes.length) {
      // Nothing extracted — explain why (blocked / JS-only site).
      toast.warning(__(notes[0]))
    } else {
      toast.success(__('Enrichment complete.'))
    }
    emit('done') // parent reloads the document + side panel — no manual refresh
  } else if (data.status === 'error') {
    finish()
    toast.error(__(data.message || 'Enrichment failed.'))
  }
}

function pollProgress(queuedAt, token) {
  if (!queuedAt || !running.value || token !== generation) return
  pollTimer = setTimeout(async () => {
    try {
      const data = await call('crm.domain_enrichment.api.get_progress', {
        reference_doctype: props.doctype,
        reference_name: props.docname,
        queued_at: queuedAt,
      })
      if (token !== generation || !running.value) return
      onProgress({
        ...data,
        reference_doctype: props.doctype,
        reference_name: props.docname,
      })
    } catch {
      // A temporary network failure must not discard a queued background job.
    }
    pollProgress(queuedAt, token)
  }, 3000)
}

async function enrich() {
  if (running.value) return
  if (!(props.website || '').trim()) {
    toast.warning(__('Set a Website on this record before enriching.'))
    return
  }

  capture('enrichment_triggered', { doctype: props.doctype })
  const key = recordKey.value
  pending[key] = { queuedAt: null }

  try {
    const result = await call('crm.domain_enrichment.api.enrich', {
      reference_doctype: props.doctype,
      reference_name: props.docname,
    })
    // This response may arrive after a tab change unmounted this button. The
    // shared state lets the replacement button pick up polling in that case.
    if (pending[key]) pending[key].queuedAt = result?.queued_at
  } catch (error) {
    if (!pending[key]) return
    delete pending[key]
    toast.error(error.messages?.[0] || __('Could not start enrichment.'))
  }
}

watch(
  () => [recordKey.value, pending[recordKey.value]?.queuedAt, running.value],
  () => {
    cleanup()
    if (!running.value) return
    // Subscribe before enqueueing, and resume on a remounted record page.
    $socket.on(EVENT, onProgress)
    pollProgress(pending[recordKey.value]?.queuedAt, generation)
  },
  { immediate: true, flush: 'sync' },
)
onBeforeUnmount(cleanup)
</script>
