<template>
  <SettingsLayoutBase
    :title="__('Notification delivery')"
    :description="
      __('Choose optional delivery of CRM task assignments to EXP One.')
    "
  >
    <template #content>
      <div class="max-w-xl space-y-5 text-base leading-6">
        <ErrorMessage v-if="error" :message="error" role="alert" />
        <p v-if="loading && !state" role="status">{{ __('Loading...') }}</p>
        <form
          v-if="source && state"
          class="space-y-5"
          @submit.prevent="saveDraft"
        >
          <p>{{ __('This is the same setting in CRM, Home and EXP One.') }}</p>
          <p v-if="!state.one_available">
            {{ __('EXP One is unavailable for your account.') }}
          </p>
          <p v-else-if="source.reason === 'sender_unavailable'">
            {{ __('The selected sender is unavailable.') }}
          </p>
          <p role="status">
            {{ __(source.effective ? 'Delivery is on' : 'Delivery is off') }}
          </p>
          <Checkbox
            v-model="draft.enabled"
            :label="__('Receive task assignments in EXP One')"
            :disabled="locked || (!state.one_available && !source.enabled)"
            @update:modelValue="dirty = true"
          />
          <FormControl
            v-model="draft.sender"
            type="select"
            :label="__('Sender')"
            :placeholder="__('Choose a sender')"
            :options="
              state.senders.map((sender) => ({
                value: sender.id,
                label: sender.label,
              }))
            "
            :disabled="locked || !state.one_available"
            :required="draft.enabled"
            @update:modelValue="dirty = true"
          />
          <p class="text-ink-gray-6">
            {{
              __(
                'Messages arrive in your private chat with the selected sender.',
              )
            }}
          </p>
          <Checkbox
            v-model="draft.push"
            :label="__('Notify with push from EXP One')"
            :disabled="locked || !state.one_available"
            @update:modelValue="dirty = true"
          />
          <p class="text-ink-gray-6">
            {{
              __(
                'Turning this off keeps notification history and other channels. Reading the chat does not read the source notification.',
              )
            }}
          </p>
          <div class="flex flex-wrap gap-3">
            <Button
              type="submit"
              class="min-h-11"
              variant="solid"
              :disabled="saving || (!dirty && !pending)"
              :loading="saving"
              :label="__(pending ? 'Retry' : 'Save')"
            />
            <Button
              type="button"
              class="min-h-11"
              :disabled="saving"
              :label="__('Reload')"
              @click="reset"
            />
          </div>
        </form>
        <Button v-else-if="!loading" :label="__('Retry')" @click="reload" />
        <a
          href="/home?view=notifications"
          class="inline-flex min-h-11 items-center underline"
          >{{ __('Open notification center') }}</a
        >
      </div>
    </template>
  </SettingsLayoutBase>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { Button, Checkbox, ErrorMessage, FormControl } from 'frappe-ui'
import SettingsLayoutBase from '@/components/Layouts/SettingsLayoutBase.vue'
import { useNotificationDelivery } from '@/composables/useNotificationDelivery'

const {
  state,
  source,
  error,
  loading,
  saving,
  pending,
  reload,
  save,
  discardAndReload,
} = useNotificationDelivery()
const dirty = ref(false)
const draft = reactive({ enabled: false, sender: '', push: false, revision: 0 })
const locked = computed(() => saving.value || Boolean(pending.value))
function updateDraft() {
  if (!source.value) return
  Object.assign(draft, {
    enabled: source.value.enabled,
    sender: source.value.sender || state.value.senders[0]?.id || '',
    push: source.value.push_route === 'One',
    revision: source.value.revision,
  })
}
watch(source, () => {
  if (!dirty.value && !pending.value) updateDraft()
})
async function saveDraft() {
  if (await save(draft)) {
    dirty.value = false
    updateDraft()
  }
}
async function reset() {
  dirty.value = false
  await discardAndReload()
  updateDraft()
}
</script>
