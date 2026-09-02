<template>
  <SettingsLayoutBase
    :title="__('Call Analysis')"
    :description="
      __(
        'Turn call recordings into transcripts, concise summaries, key points, and next steps.',
      )
    "
  >
    <template #header-actions>
      <Button
        :label="__('Save Settings')"
        variant="solid"
        :disabled="!dirty"
        :loading="saving"
        @click="saveSettings"
      />
    </template>

    <template #content>
      <div v-if="loading" class="flex h-full items-center justify-center">
        <LoadingIndicator class="size-6" />
      </div>
      <div v-else class="flex max-w-3xl flex-col gap-6">
        <section
          class="rounded-lg border border-outline-gray-1 bg-surface-cards"
        >
          <div class="flex items-center justify-between gap-6 p-4">
            <div>
              <div class="text-base-medium text-ink-gray-8">
                {{ __('Analyze Call Recordings') }}
              </div>
              <div class="mt-1 text-p-sm text-ink-gray-5">
                {{
                  __(
                    'Recordings are sent to the configured AI service only after a user clicks Analyze Call.',
                  )
                }}
              </div>
            </div>
            <Switch v-model="settings.enabled" size="sm" />
          </div>
        </section>

        <section class="grid grid-cols-1 gap-4 md:grid-cols-2">
          <FormControl
            v-model="settings.api_base_url"
            class="md:col-span-2"
            type="text"
            :label="__('AI Service URL')"
            placeholder="https://openrouter.ai/api/v1"
          />
          <FormControl
            v-model="settings.api_key"
            class="md:col-span-2"
            type="password"
            :label="__('API Key')"
            :placeholder="
              settings.api_key_configured
                ? __('Configured — leave blank to keep it')
                : __('Enter API key')
            "
            :description="
              __(
                'The API key is encrypted and is never returned to the browser.',
              )
            "
          />
          <FormControl
            v-model="settings.transcription_model"
            type="text"
            :label="__('Transcription Model')"
            placeholder="openai/whisper-large-v3"
          />
          <FormControl
            v-model="settings.summary_model"
            type="text"
            :label="__('Summary Model')"
            placeholder="google/gemini-3.1-flash-lite-preview"
          />
          <FormControl
            v-model="settings.language"
            type="select"
            :label="__('Preferred Language')"
            :options="languageOptions"
          />
          <FormControl
            v-model="settings.max_recording_mb"
            type="number"
            min="1"
            max="25"
            :label="__('Maximum Recording Size (MB)')"
            :description="__('The maximum supported value is 25 MB.')"
          />
        </section>

        <div
          class="rounded-lg border border-outline-amber-2 bg-surface-amber-1 px-4 py-3 text-p-sm text-ink-gray-7"
        >
          {{
            __(
              'Call recordings and transcripts may contain personal data. Make sure your AI service and customer agreements allow this processing.',
            )
          }}
        </div>
      </div>
    </template>
  </SettingsLayoutBase>
</template>

<script setup>
import SettingsLayoutBase from '@/components/Layouts/SettingsLayoutBase.vue'
import {
  Button,
  FormControl,
  LoadingIndicator,
  Switch,
  call,
  toast,
} from 'frappe-ui'
import { computed, onMounted, reactive, ref } from 'vue'

const defaults = () => ({
  enabled: false,
  api_base_url: 'https://openrouter.ai/api/v1',
  api_key: '',
  api_key_configured: false,
  transcription_model: 'openai/whisper-large-v3',
  summary_model: 'google/gemini-3.1-flash-lite-preview',
  language: 'Auto',
  max_recording_mb: 25,
})

const settings = reactive(defaults())
const loading = ref(true)
const saving = ref(false)
const snapshot = ref('')

const languageOptions = [
  { label: __('Auto Detect'), value: 'Auto' },
  { label: __('Russian'), value: 'Russian' },
  { label: __('English'), value: 'English' },
]

function state() {
  return JSON.stringify({
    enabled: Boolean(settings.enabled),
    api_base_url: settings.api_base_url || '',
    api_key: settings.api_key || '',
    transcription_model: settings.transcription_model || '',
    summary_model: settings.summary_model || '',
    language: settings.language || 'Auto',
    max_recording_mb: Number(settings.max_recording_mb || 25),
  })
}

const dirty = computed(
  () => Boolean(snapshot.value) && snapshot.value !== state(),
)

async function loadSettings() {
  loading.value = true
  try {
    const result = await call('crm.call_analysis.api.get_analysis_settings')
    Object.assign(settings, defaults(), result || {})
    settings.api_key = ''
    snapshot.value = state()
  } catch (error) {
    toast.error(
      __(error?.messages?.[0] || 'Could not load call analysis settings.'),
    )
  } finally {
    loading.value = false
  }
}

async function saveSettings() {
  saving.value = true
  try {
    const result = await call('crm.call_analysis.api.save_analysis_settings', {
      enabled: Boolean(settings.enabled),
      api_base_url: settings.api_base_url || '',
      api_key: settings.api_key || '',
      transcription_model: settings.transcription_model || '',
      summary_model: settings.summary_model || '',
      language: settings.language || 'Auto',
      max_recording_mb: Number(settings.max_recording_mb || 25),
    })
    Object.assign(settings, defaults(), result || {})
    settings.api_key = ''
    snapshot.value = state()
    toast.success(__('Call analysis settings saved.'))
  } catch (error) {
    toast.error(
      __(error?.messages?.[0] || 'Could not save call analysis settings.'),
    )
  } finally {
    saving.value = false
  }
}

onMounted(loadSettings)
</script>
