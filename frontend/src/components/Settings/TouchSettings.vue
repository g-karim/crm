<template>
  <SettingsLayoutBase
    :title="__('Touches and interactions')"
    :description="
      __('Choose which actions update the last interaction date on this site.')
    "
  >
    <template #header-actions>
      <div class="flex shrink-0 gap-2">
        <Button
          :label="dirty ? __('Discard and reload') : __('Reload')"
          :disabled="loading || saving"
          @click="load"
        />
        <Button
          :label="__('Save')"
          variant="solid"
          :disabled="!dirty || loading"
          :loading="saving"
          @click="save"
        />
      </div>
    </template>
    <template #content>
      <div v-if="loading" class="flex justify-center p-8">
        <LoadingIndicator class="size-6" />
      </div>
      <div v-else-if="!form" class="space-y-3">
        <ErrorMessage :message="error" />
        <Button :label="__('Retry')" @click="load" />
      </div>
      <div v-else class="max-w-4xl space-y-6">
        <ErrorMessage :message="error" />
        <div
          class="flex items-center justify-between gap-4 rounded-lg border border-outline-gray-1 p-4"
        >
          <div>
            <h3 class="text-base-medium">{{ __('Enable touch tracking') }}</h3>
            <p class="mt-1 text-p-sm text-ink-gray-5">
              {{
                __(
                  'Rules apply to future actions. Existing records are not recalculated.',
                )
              }}
            </p>
          </div>
          <Switch
            v-model="form.enabled"
            :disabled="saving"
            :label="__('Enable touch tracking')"
            class="[&_[data-slot=label]]:sr-only"
          />
        </div>
        <div class="flex gap-2" role="tablist" :aria-label="__('Record type')">
          <Button
            v-for="tab in tabs"
            :key="tab.prefix"
            :label="__(tab.label)"
            :variant="active === tab.prefix ? 'solid' : 'subtle'"
            role="tab"
            :aria-selected="active === tab.prefix"
            @click="selectTab(tab.prefix)"
          />
          <span
            v-if="dirty"
            class="ml-auto self-center text-p-sm text-ink-orange-3"
            >{{ __('Not Saved') }}</span
          >
        </div>
        <div class="flex items-center justify-between gap-4">
          <h3 class="text-base-medium">
            {{ active === 'lead' ? __('Track leads') : __('Track deals') }}
          </h3>
          <Switch
            v-model="form[active === 'lead' ? 'track_leads' : 'track_deals']"
            :disabled="!form.enabled || saving"
            :label="active === 'lead' ? __('Track leads') : __('Track deals')"
            class="[&_[data-slot=label]]:sr-only"
          />
        </div>
        <div
          v-for="name in missingFields"
          :key="name"
          class="flex items-center justify-between gap-3 rounded border border-outline-gray-2 p-2 text-p-sm"
        >
          <span>{{ __('Field unavailable: {0}', [name]) }}</span>
          <Button
            :label="__('Remove')"
            :disabled="saving"
            @click="
              form[`${active}_fields`] = form[`${active}_fields`].filter(
                (field) => field !== name,
              )
            "
          />
        </div>
        <fieldset :disabled="inactive || saving" class="space-y-6">
          <section class="space-y-3">
            <h3 class="text-base-medium">{{ __('Record changes') }}</h3>
            <label class="flex items-center gap-2 text-p-base"
              ><input type="checkbox" checked disabled />{{
                __('Record created')
              }}</label
            >
            <label class="flex items-center gap-2 text-p-base"
              ><input
                v-model="form[`${active}_status_changes`]"
                type="checkbox"
              />{{ __('Status changed') }}</label
            >
            <FormControl
              v-model="search"
              type="text"
              :placeholder="__('Search fields')"
            />
            <div class="grid gap-3 sm:grid-cols-2">
              <label
                v-for="field in filteredFields"
                :key="field.value"
                class="flex items-center gap-2 text-p-base"
              >
                <input
                  v-model="form[`${active}_fields`]"
                  type="checkbox"
                  :value="field.value"
                />{{ __(field.label) }}
              </label>
            </div>
            <p v-if="!filteredFields.length" class="text-p-sm text-ink-gray-5">
              {{ __('No matching fields') }}
            </p>
          </section>
          <section class="space-y-3 border-t border-outline-gray-1 pt-5">
            <h3 class="text-base-medium">
              {{ __('Comments, notes and tasks') }}
            </h3>
            <p class="text-p-sm text-ink-gray-5">
              {{
                __(
                  'Changing a task date counts at the time of the edit, not at the planned date. Completion and other status changes are separate rules.',
                )
              }}
            </p>
            <div class="grid gap-3 sm:grid-cols-2">
              <label
                v-for="event in data.events"
                :key="event.value"
                class="flex items-center gap-2 text-p-base"
              >
                <input
                  v-model="form[`${active}_events`]"
                  type="checkbox"
                  :value="event.value"
                />{{ __(event.label) }}
              </label>
            </div>
          </section>
          <section class="space-y-3 border-t border-outline-gray-1 pt-5">
            <h3 class="text-base-medium">{{ __('Action sources') }}</h3>
            <p class="text-p-sm text-ink-gray-5">
              {{
                __(
                  'Selected actions from CRM users are counted. Allow background jobs, imports and token API actions separately.',
                )
              }}
            </p>
            <label class="flex items-center gap-2 text-p-base"
              ><input
                v-model="form[`${active}_allow_automation`]"
                type="checkbox"
              />{{ __('Allow automated field and internal changes') }}</label
            >
          </section>
        </fieldset>
        <section class="space-y-4 border-t border-outline-gray-1 pt-5">
          <h3 class="text-base-medium">
            {{ __('Messaging, calls and email') }}
          </h3>
          <div
            v-for="channel in data.channels"
            :key="channel.key"
            class="space-y-3 rounded-lg border border-outline-gray-1 p-4"
          >
            <div class="flex items-center justify-between gap-3">
              <h4 class="text-base-medium">{{ __(channel.label) }}</h4>
              <Badge
                :label="
                  channel.installed
                    ? channel.available
                      ? __('Channel checks passed')
                      : __('Channel checks required')
                    : __('App not installed')
                "
              />
            </div>
            <p class="text-p-sm text-ink-gray-5">
              {{ __(channel.description) }}
            </p>
            <p v-if="!channel.available" class="text-p-sm text-ink-gray-5">
              {{
                __(
                  'Provider events must be checked before enabling these rules. Manual call logging is available separately.',
                )
              }}
            </p>
            <div class="grid gap-3 sm:grid-cols-2">
              <label
                v-for="rule in channel.rules"
                :key="rule.value"
                class="flex items-center gap-2 text-p-base"
                ><input
                  v-model="form[`${active}_channels`]"
                  type="checkbox"
                  :value="rule.value"
                  :disabled="
                    inactive ||
                    saving ||
                    (!rule.available &&
                      !form[`${active}_channels`].includes(rule.value))
                  "
                />{{ __(rule.label) }}</label
              >
            </div>
            <label
              v-if="channel.automation"
              class="flex items-center gap-2 text-p-base"
            >
              <input
                v-model="form[`${active}_${channel.automation}`]"
                type="checkbox"
                :disabled="
                  inactive ||
                  saving ||
                  !form[`${active}_channels`].includes(
                    channel.key === 'email' ? 'email_sent' : 'message_sent',
                  )
                "
              />
              {{
                channel.key === 'email'
                  ? __('Automated outgoing emails')
                  : __('Automated outgoing messages')
              }}
            </label>
          </div>
        </section>
        <p class="text-p-sm text-ink-gray-5">
          {{
            __(
              'New standard lists use the last touch date. Saved views and your chosen sort order are preserved.',
            )
          }}
        </p>
      </div>
    </template>
  </SettingsLayoutBase>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import {
  Badge,
  call,
  ErrorMessage,
  FormControl,
  LoadingIndicator,
  Switch,
  toast,
} from 'frappe-ui'
import SettingsLayoutBase from '@/components/Layouts/SettingsLayoutBase.vue'
import { touchSettingsDirty, withTouchTimeout } from '@/utils/touchTracking'

const data = ref(null)
const form = ref(null)
const active = ref('lead')
const search = ref('')
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const tabs = [
  { prefix: 'lead', label: 'Leads' },
  { prefix: 'deal', label: 'Deals' },
]
const dirty = computed(() =>
  touchSettingsDirty(form.value, data.value?.settings),
)
const inactive = computed(
  () =>
    !form.value?.enabled ||
    !form.value?.[active.value === 'lead' ? 'track_leads' : 'track_deals'],
)
const fields = computed(
  () =>
    data.value?.fields[active.value === 'lead' ? 'CRM Lead' : 'CRM Deal'] || [],
)
const filteredFields = computed(() =>
  fields.value.filter((field) =>
    field.label.toLowerCase().includes(search.value.toLowerCase()),
  ),
)
const missingFields = computed(
  () =>
    form.value?.[`${active.value}_fields`]?.filter(
      (name) => !fields.value.some((field) => field.value === name),
    ) || [],
)

function selectTab(prefix) {
  active.value = prefix
  search.value = ''
}

function accept(result) {
  data.value = result
  form.value = structuredClone(result.settings)
  // API Check fields are 0/1; checkbox inputs use Boolean values consistently.
  for (const [key, value] of Object.entries(form.value)) {
    if (!Array.isArray(value)) form.value[key] = Boolean(value)
  }
  data.value.settings = JSON.parse(JSON.stringify(form.value))
}
function message(err) {
  return __(err.messages?.[0] || err.message || 'Could not load touch settings')
}
async function load() {
  loading.value = true
  error.value = ''
  try {
    accept(
      await withTouchTimeout(() => call('crm.touch_tracking_ui.get_settings')),
    )
  } catch (err) {
    error.value = message(err)
  } finally {
    loading.value = false
  }
}
async function save() {
  if (saving.value || !dirty.value) return
  saving.value = true
  error.value = ''
  try {
    const values = Object.fromEntries(
      Object.entries(form.value).map(([key, value]) => [
        key,
        Array.isArray(value) ? value : Number(value),
      ]),
    )
    accept(
      await withTouchTimeout(() =>
        call('crm.touch_tracking_ui.save_settings', {
          settings: values,
          expected_modified: data.value.modified,
        }),
      ),
    )
    toast.success(__('Touch settings saved'))
  } catch (err) {
    error.value = message(err)
  } finally {
    saving.value = false
  }
}
onMounted(load)
</script>
