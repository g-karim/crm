<template>
  <SettingsLayoutBase>
    <template #title>
      <Button
        :label="__('Exolve Settings')"
        icon-left="lucide-chevron-left"
        variant="ghost"
        class="text-xl"
        @click="emit('updateStep', 'telephony-settings')"
      />
    </template>
    <template #header-actions>
      <Button
        :label="__('Save')"
        variant="solid"
        :loading="saving"
        :disabled="loading || !settings"
        @click="save"
      />
    </template>
    <template #content>
      <div class="space-y-5">
        <p class="text-sm text-ink-gray-6">
          {{
            __(
              'Connect Exolve SIP accounts to CRM users. Provider numbers and routes are managed in Exolve.',
            )
          }}
        </p>
        <div v-if="error" role="alert"><ErrorMessage :message="error" /></div>
        <p v-if="loading" role="status">{{ __('Loading…') }}</p>
        <div v-if="settings" class="space-y-5">
          <FormControl
            v-model="settings.enabled"
            type="checkbox"
            :label="__('Enable Exolve Calling')"
          />
          <FormControl
            v-model="settings.history_enabled"
            type="checkbox"
            :label="__('Synchronize call history on the server')"
          />
          <FormControl
            v-if="settings.history_enabled"
            v-model="settings.history_start"
            type="date"
            :label="__('History start date')"
            :description="
              __(
                'Leave empty to recover the last 30 days. Synchronization continues while CRM is closed.',
              )
            "
          />
          <FormControl
            v-model="settings.application_id"
            :label="__('Application ID')"
            autocomplete="off"
          />
          <FormControl
            v-model="apiKey"
            type="password"
            :label="__('API Key')"
            autocomplete="new-password"
          />
          <p class="text-sm text-ink-gray-6">
            {{
              settings.api_key_configured
                ? __('Leave blank to keep the current key.')
                : __('Enter the API key from your Exolve application.')
            }}
          </p>
          <div class="flex items-center justify-between">
            <h3 class="font-medium text-ink-gray-9">
              {{ __('SIP Accounts') }}
            </h3>
            <Button
              :label="__('Add User')"
              icon-left="lucide-plus"
              @click="
                settings.agents.push({
                  user: '',
                  sip_resource_id: '',
                  enabled: true,
                })
              "
            />
          </div>
          <div
            v-for="(agent, index) in settings.agents"
            :key="index"
            class="space-y-3 rounded-lg border border-outline-gray-2 p-3"
          >
            <Link
              v-model="agent.user"
              doctype="User"
              :filters="{ enabled: 1 }"
              :label="__('User')"
            />
            <FormControl
              v-model="agent.sip_resource_id"
              :label="__('SIP Resource ID')"
              inputmode="numeric"
            />
            <div class="flex items-center justify-between">
              <FormControl
                v-model="agent.enabled"
                type="checkbox"
                :label="__('Enabled')"
              />
              <Button
                :label="__('Remove')"
                variant="ghost"
                @click="settings.agents.splice(index, 1)"
              />
            </div>
          </div>
          <p class="text-sm text-ink-gray-6">
            {{
              __(
                'Use the numeric resource ID from the SIP account card. SIP passwords are retrieved only for the mapped user.',
              )
            }}
          </p>
          <Button
            :label="__('Check Saved Connection')"
            :loading="checking"
            @click="checkConnection"
          />
          <div
            v-if="connection"
            class="space-y-2 rounded-lg bg-surface-gray-1 p-3 text-sm text-ink-gray-7"
            role="status"
          >
            <p>
              {{ __('Available numbers: {0}', [connection.numbers.length]) }}
            </p>
            <div v-for="sip in connection.sips" :key="sip.sip_resource_id">
              {{ __('SIP Resource ID') }}: {{ sip.sip_resource_id }} ·
              {{ sip.username }} · +{{ sip.number }}
            </div>
          </div>
        </div>
      </div>
    </template>
  </SettingsLayoutBase>
</template>

<script setup>
import { Button, ErrorMessage, FormControl, call, toast } from 'frappe-ui'
import { onMounted, ref } from 'vue'
import Link from '@/components/Controls/Link.vue'
import { setEnabled } from '@/composables/telephony'

const emit = defineEmits(['updateStep'])
const settings = ref(null)
const apiKey = ref('')
const error = ref('')
const loading = ref(true)
const saving = ref(false)
const checking = ref(false)
const connection = ref(null)

onMounted(async () => {
  try {
    settings.value = await call('crm.integrations.exolve.api.get_settings')
  } catch {
    error.value = __(
      'Could not load Exolve settings. Check site schema and permissions.',
    )
  } finally {
    loading.value = false
  }
})

async function save() {
  saving.value = true
  error.value = ''
  try {
    settings.value = await call('crm.integrations.exolve.api.save_settings', {
      application_id: settings.value.application_id,
      agents: settings.value.agents,
      enabled: settings.value.enabled,
      history_enabled: settings.value.history_enabled,
      history_start: settings.value.history_start || '',
      api_key: apiKey.value || undefined,
      expected_modified: settings.value.modified,
    })
    apiKey.value = ''
    connection.value = null
    setEnabled('exolve', settings.value.enabled)
    window.dispatchEvent(
      new CustomEvent(
        settings.value.connection_changed === false
          ? 'crm-exolve-history-settings-updated'
          : 'crm-exolve-settings-updated',
      ),
    )
    toast.success(__('Exolve settings saved.'))
  } catch {
    error.value = __(
      'Could not save Exolve settings. Check the application ID and unique user mappings, or reload after a concurrent change.',
    )
  } finally {
    saving.value = false
  }
}

async function checkConnection() {
  checking.value = true
  error.value = ''
  try {
    connection.value = await call('crm.integrations.exolve.api.test_connection')
  } catch {
    error.value = __('Could not read Exolve. Check the connection and API key.')
  } finally {
    checking.value = false
  }
}
</script>
