<template>
  <section
    class="mt-5 rounded-lg border border-outline-gray-2 bg-surface-white p-4"
  >
    <div class="flex items-start justify-between gap-4">
      <div class="min-w-0">
        <div class="flex items-center gap-2">
          <FeatherIcon name="sparkles" class="size-4 text-ink-gray-7" />
          <h4 class="text-base-medium text-ink-gray-9">
            {{ __('Call Analysis') }}
          </h4>
          <Badge
            v-if="statusInfo.label"
            :label="__(statusInfo.label)"
            :theme="statusInfo.theme"
            variant="subtle"
          />
        </div>
        <p v-if="!hasResult" class="mt-1 text-p-sm text-ink-gray-5">
          {{
            analysisConfigured
              ? __(
                  'Get a transcript, concise summary, key points, and next steps.',
                )
              : __(
                  'Ask an administrator to configure call analysis in CRM settings.',
                )
          }}
        </p>
      </div>
      <Button
        v-if="analysisConfigured"
        size="sm"
        :variant="hasResult ? 'subtle' : 'solid'"
        :label="buttonLabel"
        :loading="starting || statusInfo.running"
        :disabled="statusInfo.running"
        @click="startAnalysis"
      />
    </div>

    <div
      v-if="status === 'Failed'"
      class="mt-3 rounded bg-surface-red-1 px-3 py-2 text-p-sm text-ink-red-4"
    >
      {{
        __(
          data.ai_analysis_error ||
            'The call could not be analyzed. Please try again.',
        )
      }}
    </div>

    <div v-if="hasResult" class="mt-4 space-y-4">
      <div v-if="data.ai_summary">
        <div class="text-sm-medium text-ink-gray-7">
          {{ __('Summary') }}
        </div>
        <p class="mt-1 whitespace-pre-wrap text-sm text-ink-gray-8">
          {{ data.ai_summary }}
        </p>
      </div>

      <div v-if="keyPoints.length">
        <div class="text-sm-medium text-ink-gray-7">
          {{ __('Key Points') }}
        </div>
        <ul class="mt-1 list-disc space-y-1 pl-5 text-sm text-ink-gray-8">
          <li v-for="item in keyPoints" :key="item">{{ item }}</li>
        </ul>
      </div>

      <div v-if="nextSteps.length">
        <div class="text-sm-medium text-ink-gray-7">
          {{ __('Next Steps') }}
        </div>
        <ul class="mt-1 list-disc space-y-1 pl-5 text-sm text-ink-gray-8">
          <li v-for="item in nextSteps" :key="item">{{ item }}</li>
        </ul>
      </div>

      <details
        v-if="data.ai_transcript"
        class="group border-t border-outline-gray-1 pt-3"
      >
        <summary
          class="flex cursor-pointer list-none items-center gap-1.5 text-sm-medium text-ink-gray-7"
        >
          <FeatherIcon
            name="chevron-right"
            class="size-4 transition-transform group-open:rotate-90"
          />
          {{ __('Transcript') }}
        </summary>
        <p
          class="mt-2 max-h-56 overflow-y-auto whitespace-pre-wrap text-sm text-ink-gray-7"
        >
          {{ data.ai_transcript }}
        </p>
      </details>
    </div>
  </section>
</template>

<script setup>
import {
  callAnalysisStatus,
  parseCallAnalysisItems,
} from '@/utils/callAnalysis'
import { globalStore } from '@/stores/global'
import { Badge, Button, FeatherIcon, call, toast } from 'frappe-ui'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps({
  callLog: { type: Object, required: true },
})

const { $socket } = globalStore()
const starting = ref(false)
let pollTimer = null

const data = computed(() => props.callLog?.data || {})
const status = computed(() => data.value.ai_analysis_status || '')
const statusInfo = computed(() => callAnalysisStatus(status.value))
const analysisConfigured = computed(() =>
  Boolean(data.value?._call_analysis?.configured),
)
const keyPoints = computed(() =>
  parseCallAnalysisItems(data.value.ai_key_points),
)
const nextSteps = computed(() =>
  parseCallAnalysisItems(data.value.ai_next_steps),
)
const hasResult = computed(
  () =>
    Boolean(data.value.ai_summary || data.value.ai_transcript) ||
    keyPoints.value.length > 0 ||
    nextSteps.value.length > 0,
)
const buttonLabel = computed(() =>
  statusInfo.value.running
    ? __('Analyzing…')
    : hasResult.value || status.value === 'Failed'
      ? __('Analyze Again')
      : __('Analyze Call'),
)

async function startAnalysis() {
  starting.value = true
  try {
    const result = await call('crm.call_analysis.api.start_analysis', {
      call_log_name: data.value.name,
      force: hasResult.value || status.value === 'Failed' ? 1 : 0,
    })
    await props.callLog?.reload?.()
    if (result?.queued) toast.success(__('Call analysis queued.'))
  } catch (error) {
    toast.error(
      __(error?.messages?.[0] || 'The call could not be queued for analysis.'),
    )
  } finally {
    starting.value = false
  }
}

function onAnalysisUpdate(payload) {
  if (payload?.call_log_name === data.value.name) props.callLog?.reload?.()
}

function stopPolling() {
  if (pollTimer) window.clearInterval(pollTimer)
  pollTimer = null
}

function syncPolling(running) {
  stopPolling()
  if (!running) return
  pollTimer = window.setInterval(() => props.callLog?.reload?.(), 3000)
}

watch(() => statusInfo.value.running, syncPolling, { immediate: true })

onMounted(() => $socket?.on('crm_call_analysis_update', onAnalysisUpdate))
onBeforeUnmount(() => {
  stopPolling()
  $socket?.off('crm_call_analysis_update', onAnalysisUpdate)
})
</script>
