<template>
  <div
    class="crm-rules mx-auto w-full max-w-5xl space-y-6 p-5 sm:p-8"
    data-crm-rules
  >
    <header class="flex flex-wrap items-start justify-between gap-4">
      <div>
        <h1 class="text-2xl font-semibold text-ink-gray-9">
          {{ __('CRM notifications') }}
        </h1>
        <p class="mt-2 max-w-2xl text-base leading-6 text-ink-gray-6">
          {{
            __(
              'Choose the records, events and delivery channels that matter to you.',
            )
          }}
        </p>
      </div>
      <Button
        class="min-h-11"
        :label="__('Refresh settings')"
        :disabled="busy"
        @click="control.reload()"
      />
    </header>
    <div
      v-if="error"
      role="alert"
      tabindex="-1"
      class="rounded border border-outline-red-3 bg-surface-red-1 p-4 text-base text-ink-red-8"
      data-rule-error
    >
      {{ __(error) }}
    </div>
    <p
      v-if="feedback"
      role="status"
      class="text-base text-ink-gray-7"
      data-rule-feedback
    >
      {{ __(feedback) }}
    </p>
    <div v-if="!state" role="status">{{ __('Loading…') }}</div>
    <template v-else>
      <section class="rule-panel" aria-labelledby="crm-delivery-heading">
        <h2 id="crm-delivery-heading" class="text-lg font-semibold">
          {{ __('My delivery channels') }}
        </h2>
        <p class="mt-2 text-sm leading-6 text-ink-gray-6">
          {{
            __(
              'Push, One and email are independent. Select all three to receive this event in every selected channel.',
            )
          }}
        </p>
        <p
          v-if="!state.push_service_available"
          class="mt-3 rounded bg-surface-gray-2 p-3 text-sm"
          role="status"
        >
          {{
            __('Push delivery is currently paused. Your choices will be saved.')
          }}
        </p>
        <fieldset
          :disabled="busy || !!pending"
          class="mt-3 space-y-1"
          @change="control.channelDirty.value = true"
        >
          <label class="rule-check"
            ><input v-model="channelDraft.crm_push" type="checkbox" />{{
              __('CRM push')
            }}</label
          >
          <label class="rule-check"
            ><input v-model="channelDraft.email" type="checkbox" />{{
              __('Email')
            }}</label
          >
          <label class="rule-check"
            ><input
              v-model="channelDraft.one_message"
              type="checkbox"
              @change="
                !channelDraft.one_message && (channelDraft.one_push = false)
              "
            />{{ __('Message in One') }}</label
          >
          <label v-if="channelDraft.one_message" class="block space-y-2 py-2"
            ><span>{{ __('Sender') }}</span>
            <select
              v-model="channelDraft.sender"
              class="rule-input"
              :required="channelDraft.one_message"
            >
              <option value="">{{ __('Choose a sender') }}</option>
              <option
                v-for="sender in state.senders"
                :key="sender.id"
                :value="sender.id"
              >
                {{ sender.label }}
              </option>
            </select></label
          >
          <label class="rule-check"
            ><input
              v-model="channelDraft.one_push"
              type="checkbox"
              :disabled="!channelDraft.one_message"
            />{{ __('Push for this One message') }}</label
          >
        </fieldset>
        <p
          v-if="
            channelDraft.email &&
            (!state.email_service_available || !state.email_global_enabled)
          "
          class="text-sm text-ink-gray-6"
          role="status"
        >
          {{
            __(
              'Email delivery is paused by the site or your global email preference. Your CRM choice will be saved.',
            )
          }}
        </p>
        <div
          v-if="channelConflict"
          role="status"
          class="mt-3 rounded border border-outline-gray-3 p-3 text-sm"
        >
          <p>
            {{
              __(
                'A newer settings version is available. Your draft is preserved.',
              )
            }}
          </p>
          <Button
            class="mt-2 min-h-11"
            :label="__('Use current version after review')"
            :disabled="busy || !!pending"
            @click="control.rebaseChannels()"
          />
        </div>
        <Button
          class="mt-3 min-h-11"
          :label="__('Save channels')"
          :disabled="
            busy ||
            (channelConflict && !pending) ||
            (!!pending && pending.method !== 'save_channels') ||
            (!channelDirty && !pending)
          "
          @click="control.saveChannels()"
        />
      </section>
      <DeliverySchedule :viewer="state.viewer" />
      <Templates
        :viewer="state.viewer"
        :revision="state.revision"
        :rule="mode === 'builder' ? draft : null"
        :people="control.people"
        @changed="control.reload()"
      />
      <div class="flex flex-wrap items-center justify-between gap-3">
        <h2 class="text-xl font-semibold">{{ __('My CRM rules') }}</h2>
        <div class="flex flex-wrap gap-2">
          <Button
            class="min-h-11"
            :label="__('Rules overview')"
            @click="mode = 'rules'"
          />
          <Button
            v-if="hasDraft && mode === 'rules'"
            class="min-h-11"
            :label="__('Continue editing')"
            @click="mode = 'builder'"
          />
          <Button
            class="min-h-11"
            variant="solid"
            :label="__('Add rule')"
            :disabled="busy || !!pending"
            @click="control.edit()"
          />
        </div>
      </div>
      <p
        v-if="state.legacy"
        class="rounded border border-outline-gray-3 p-4 text-base leading-6"
      >
        {{
          __(
            'Your previous task assignment settings are active. Creating your first rule switches CRM delivery to the visible rules below. Channel opt-outs stay unchanged.',
          )
        }}
      </p>
      <div v-show="mode === 'rules'" class="space-y-3" data-rule-list>
        <p
          v-if="!state.configuration.rules.length"
          class="rule-panel text-ink-gray-6"
        >
          {{
            __('No CRM rules yet. Start with a preset or add your own rule.')
          }}
        </p>
        <article
          v-for="rule in state.configuration.rules"
          :key="rule.id"
          class="rule-panel"
          :data-rule-id="rule.id"
        >
          <div class="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h3 class="text-lg font-medium">{{ rule.name }}</h3>
              <p class="mt-1 text-sm text-ink-gray-6">
                {{ rule.enabled ? __('Enabled') : __('Disabled') }} ·
                {{ __(objects[rule.object]) }} · {{ __(events[rule.event]) }}
              </p>
              <p
                v-if="rule.event === 'task_due_soon'"
                class="mt-1 text-sm text-ink-gray-6"
              >
                {{ reminderTiming(rule.reminder_minutes) }}
              </p>
              <p
                v-if="rule.event === 'record_inactive'"
                class="mt-1 text-sm text-ink-gray-6"
              >
                {{ rule.inactive_minutes }} ·
                {{ __('Minutes without record activity') }}
              </p>
              <p class="mt-2 text-sm text-ink-gray-7">
                {{ __(scopes[rule.scope]) }} · {{ rule.record_ids.length }}
                {{ __('selected records') }} · {{ channelSummary(rule) }}
              </p>
              <p
                v-if="rule.unavailable_selection_count"
                role="status"
                class="mt-2 text-sm text-ink-red-7"
              >
                {{ __('Some selected records are no longer available.') }}
              </p>
            </div>
            <div class="flex flex-wrap gap-2">
              <Button
                class="min-h-11"
                :label="__('Edit rule')"
                :disabled="busy || !!pending"
                @click="control.edit(rule)"
              />
              <Button
                class="min-h-11"
                :label="rule.enabled ? __('Disable rule') : __('Enable rule')"
                :disabled="
                  busy || !!pending || !!rule.unavailable_selection_count
                "
                @click="control.toggleRule(rule)"
              />
              <Button
                class="min-h-11"
                :label="__('Delete rule')"
                :disabled="busy || !!pending"
                @click="deleteCandidate = rule"
              />
            </div>
          </div>
        </article>
      </div>
      <section
        v-if="deleteCandidate"
        class="rule-panel"
        role="alertdialog"
        :aria-label="__('Delete rule')"
      >
        <p>
          {{ __('Delete this rule? Source notification history will stay.') }}
          <strong>{{ deleteCandidate.name }}</strong>
        </p>
        <div class="mt-3 flex gap-3">
          <Button
            class="min-h-11"
            :label="__('Confirm deletion')"
            @click="removeConfirmed"
          /><Button
            class="min-h-11"
            :label="__('Cancel')"
            @click="deleteCandidate = null"
          />
        </div>
      </section>
      <section class="rule-panel">
        <h3 class="font-medium">{{ __('Start with a preset') }}</h3>
        <p class="mt-1 text-sm text-ink-gray-6">
          {{
            __('Presets fill the editor. Nothing is enabled until you save.')
          }}
        </p>
        <div class="mt-3 flex flex-wrap gap-2">
          <Button
            v-for="preset in options?.presets || []"
            :key="preset.id"
            class="min-h-11"
            :label="__(preset.label)"
            :disabled="busy || !!pending"
            @click="applyPreset(preset)"
          />
        </div>
      </section>
      <form
        v-show="mode === 'builder'"
        class="rule-panel space-y-6"
        data-rule-builder
        @submit.prevent="control.saveRule()"
        @input="control.markDirty()"
      >
        <h2 class="text-xl font-semibold">{{ __('Rule editor') }}</h2>
        <fieldset :disabled="busy || !!pending" class="space-y-6">
          <label class="block space-y-2"
            ><span>{{ __('Rule name') }}</span
            ><input
              v-model="draft.name"
              class="rule-input"
              required
              maxlength="100"
              data-rule-name
          /></label>
          <div class="grid gap-5 sm:grid-cols-2">
            <label class="block space-y-2"
              ><span>{{ __('Record type') }}</span
              ><select
                v-model="draft.object"
                class="rule-input"
                @change="changeObject"
              >
                <option
                  v-for="(label, value) in objects"
                  :key="value"
                  :value="value"
                >
                  {{ __(label) }}
                </option>
              </select></label
            >
            <label class="block space-y-2"
              ><span>{{ __('Which records') }}</span
              ><select
                v-model="draft.scope"
                class="rule-input"
                @change="changeScope"
              >
                <option
                  v-for="(label, value) in scopes"
                  :key="value"
                  :value="value"
                >
                  {{ __(label) }}
                </option>
              </select></label
            >
          </div>
          <Choices
            v-if="draft.scope === 'selected'"
            v-model="draft.record_ids"
            :label="__('Selected records')"
            :search="searchRecords"
            :disabled="busy || !!pending"
            @update:model-value="control.markDirty()"
          />
          <label class="block space-y-2"
            ><span>{{ __('Event') }}</span
            ><select
              v-model="draft.event"
              class="rule-input"
              @change="changeEvent"
            >
              <option
                v-for="value in availableEvents"
                :key="value"
                :value="value"
              >
                {{ __(events[value]) }}
              </option>
            </select></label
          >
          <p class="rounded bg-surface-gray-2 p-3 text-sm leading-6">
            {{
              draft.event === 'record_inactive'
                ? __(
                    'Counts record edits and new messages or comments. New activity cancels the previous reminder. Old missed events are not backfilled.',
                  )
                : discussion
                  ? __(
                      'Mentions notify only the mentioned person. Comments follow your selected records and conditions. One comment creates at most one notification per channel.',
                    )
                  : reminder
                    ? __(
                        'Reminders go only to the assigned person. Completing, cancelling or rescheduling the task cancels the old delivery.',
                      )
                    : transition
                      ? __(
                          'A transition is a change to a selected new status. Editing other fields does not trigger it.',
                        )
                      : __(
                          'Assignment notifications are delivered only to the assigned person.',
                        )
            }}
          </p>
          <template v-if="reminder">
            <label
              v-if="draft.event === 'record_inactive'"
              class="block space-y-2"
              ><span>{{ __('Minutes without record activity') }}</span
              ><input
                v-model.number="draft.inactive_minutes"
                type="number"
                min="30"
                max="43200"
                step="1"
                required
                class="rule-input"
                data-inactive-minutes
            /></label>
            <label
              v-if="draft.event === 'task_due_soon'"
              class="block space-y-2"
              ><span>{{ __('Remind me before the deadline') }}</span
              ><select
                v-model="draft.reminder_minutes"
                class="rule-input"
                data-reminder-minutes
              >
                <option :value="15">{{ __('15 minutes before') }}</option>
                <option :value="60">{{ __('1 hour before') }}</option>
                <option :value="1440">{{ __('1 day before') }}</option>
              </select></label
            >
            <p
              v-if="draft.event !== 'record_inactive'"
              class="text-sm leading-6 text-ink-gray-6"
            >
              {{
                __(
                  'Uses the task date and time. Checked every minute, once per deadline and reminder time. Missed reminders expire after 15 minutes; saving a rule does not backfill old deadlines.',
                )
              }}
            </p>
            <p
              v-if="draft.event === 'record_inactive'"
              class="text-sm leading-6 text-ink-gray-6"
            >
              {{
                __(
                  'Counts record edits and new messages or comments. New activity cancels the previous reminder. Old missed events are not backfilled.',
                )
              }}
            </p>
            <p
              v-if="!state.reminders_available"
              role="status"
              class="rounded bg-surface-gray-2 p-3 text-sm"
            >
              {{
                __(
                  'Reminder processing is paused on this site. Your rule can be saved.',
                )
              }}
            </p>
          </template>
          <Choices
            v-if="transition"
            v-model="draft.to_statuses"
            :label="__('Transition to these statuses')"
            :options="statusOptions"
            :help="__('Leave empty for any new status.')"
            @update:model-value="control.markDirty()"
          />
          <details
            class="rounded border border-outline-gray-2 p-4"
            :open="hasConditions"
          >
            <summary class="min-h-11 cursor-pointer font-medium">
              {{ __('Additional conditions') }}
            </summary>
            <p class="mb-3 text-sm text-ink-gray-6">
              {{
                draft.object === 'CRM Task'
                  ? __('These conditions describe the standalone task.')
                  : __(
                      'For task events, these conditions describe the linked lead or deal, not the task status.',
                    )
              }}
            </p>
            <div class="space-y-5">
              <Conditions
                :model-value="draft.conditions || []"
                :fields="options?.condition_fields?.[draft.object] || []"
                :disabled="busy || !!pending"
                @update:model-value="changeConditions"
              />
              <Choices
                v-model="draft.statuses"
                :label="__('Current status at the event')"
                :options="statusOptions"
                @update:model-value="control.markDirty()"
              />
              <Choices
                v-model="draft.owners"
                :label="__('Responsible person')"
                :search="control.people"
                @update:model-value="control.markDirty()"
              />
              <Choices
                v-if="draft.object !== 'CRM Task'"
                v-model="draft.sources"
                :label="__('Lead source')"
                :options="options?.sources || []"
                @update:model-value="control.markDirty()"
              />
              <Choices
                v-if="draft.object === 'CRM Deal'"
                v-model="draft.pipelines"
                :label="__('Sales pipeline')"
                :options="options?.pipelines || []"
                @update:model-value="control.markDirty()"
              />
            </div>
          </details>
          <fieldset>
            <legend class="font-medium">
              {{ __('Delivery for this rule') }}
            </legend>
            <label class="rule-check"
              ><input v-model="draft.channels.crm_push" type="checkbox" />{{
                __('CRM push')
              }}</label
            >
            <label class="rule-check"
              ><input v-model="draft.channels.email" type="checkbox" />{{
                __('Email')
              }}</label
            >
            <label class="rule-check"
              ><input
                v-model="draft.channels.one_message"
                type="checkbox"
                @change="
                  !draft.channels.one_message &&
                  (draft.channels.one_push = false)
                "
              />{{ __('Message in One') }}</label
            >
            <label class="rule-check"
              ><input
                v-model="draft.channels.one_push"
                type="checkbox"
                :disabled="!draft.channels.one_message"
              />{{ __('Push for this One message') }}</label
            >
            <p class="text-sm leading-6 text-ink-gray-6">
              {{
                __(
                  'Push, One and email are independent. Select all three to receive this event in every selected channel.',
                )
              }}
            </p>
          </fieldset>
          <label v-if="!reminder" class="rule-check"
            ><input v-model="draft.include_self" type="checkbox" />{{
              __('Include my own manual changes')
            }}</label
          >
          <label class="rule-check"
            ><input v-model="draft.enabled" type="checkbox" />{{
              __('Rule enabled')
            }}</label
          >
        </fieldset>
        <div
          v-if="conflict"
          role="status"
          class="rounded border border-outline-gray-3 p-3 text-sm"
        >
          <p>
            {{
              __(
                'A newer settings version is available. Your draft is preserved.',
              )
            }}
          </p>
          <Button
            class="mt-2 min-h-11"
            :label="__('Use current version after review')"
            :disabled="busy || !!pending"
            @click="control.rebase()"
          />
        </div>
        <div class="flex flex-wrap gap-3">
          <Button
            class="min-h-11"
            type="submit"
            variant="solid"
            :label="
              pending?.method === 'save_rule'
                ? __('Retry the same save')
                : __('Save rule')
            "
            :disabled="
              busy ||
              (conflict && !pending) ||
              (!!pending && pending.method !== 'save_rule')
            "
          />
          <Button
            class="min-h-11"
            :label="__('Preview without sending')"
            :disabled="busy || !!pending"
            @click="control.previewRule()"
          />
          <Button
            class="min-h-11"
            :label="__('Rules overview')"
            @click="mode = 'rules'"
          />
        </div>
      </form>
      <section v-if="preview" class="rule-panel" data-rule-preview>
        <h2 class="font-semibold">{{ __('Why would I receive it?') }}</h2>
        <p class="mt-2 text-sm leading-6 text-ink-gray-6">
          {{
            __(
              'This is a hypothetical future event. The preview includes all active rules and channel opt-outs. No notifications are sent.',
            )
          }}
        </p>
        <p v-if="!preview.items.length" class="mt-3">
          {{ __('No accessible records match these conditions.') }}
        </p>
        <ul class="mt-3 space-y-3">
          <li
            v-for="item in preview.items"
            :key="item.id"
            class="border-t border-outline-gray-2 pt-3"
          >
            <strong>{{ item.label }}</strong>
            <p v-if="item.scheduled_at" class="text-sm">
              {{ __('Scheduled reminder') }}:
              {{ scheduledLabel(item.scheduled_at) }}
            </p>
            <p class="text-sm">
              {{ __('Matching rules') }}:
              {{ item.matched_rules.map(ruleName).join(', ') }}
            </p>
            <p class="text-sm">
              {{ __('Effective delivery') }}:
              {{
                channelSummary({ channels: item.effective_channels }) ||
                __('Off')
              }}
            </p>
          </li>
        </ul>
        <p class="mt-3 text-sm text-ink-gray-6">
          {{ __('Up to 20 accessible example records are shown.') }}
        </p>
      </section>
      <p class="text-sm text-ink-gray-6">
        {{
          __(
            'One server-side setting is shared by CRM, Home and One. Notification history and task completion stay separate.',
          )
        }}
      </p>
    </template>
  </div>
</template>
<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { Button } from 'frappe-ui'
import {
  newRule,
  useCRMNotificationRules,
} from '@/composables/useCRMNotificationRules'
import Choices from './NotificationRuleChoices.vue'
import Conditions from './NotificationConditions.vue'
import Templates from './CRMNotificationTemplates.vue'
import DeliverySchedule from './DeliverySchedule.vue'

const control = useCRMNotificationRules()
const {
  state,
  options,
  draft,
  busy,
  pending,
  error,
  feedback,
  preview,
  mode,
  channelDraft,
  channelDirty,
  channelConflict,
  conflict,
  hasDraft,
} = control
const objects = {
  'CRM Lead': 'Leads',
  'CRM Deal': 'Deals',
  'CRM Task': 'Standalone tasks',
}
const events = {
  record_inactive: 'No activity on a record',
  message_received: 'An incoming customer message is received',
  lead_status_changed: 'Lead status changed',
  task_assigned: 'A task was assigned to me',
  lead_assigned: 'A lead was assigned to me',
  deal_assigned: 'A deal was assigned to me',
  deal_stage_changed: 'Deal stage changed',
  task_due_soon: 'A task deadline is approaching',
  task_overdue: 'A task is overdue',
  record_mentioned: 'I am mentioned in a comment',
  comment_added: 'A comment is added',
}
const scopes = {
  owned: 'My records',
  followed: 'Followed records',
  selected: 'Selected records',
  all_accessible: 'All accessible records',
}
const deleteCandidate = ref(null),
  route = useRoute()
const availableEvents = computed(() =>
  Object.entries(options.value?.events || {})
    .filter(
      ([, value]) =>
        value.available && value.objects.includes(draft.value.object),
    )
    .map(([key]) => key),
)
const transition = computed(() =>
  ['lead_status_changed', 'deal_stage_changed'].includes(draft.value.event),
)
const discussion = computed(() =>
  ['record_mentioned', 'comment_added'].includes(draft.value.event),
)
const reminder = computed(() =>
  ['task_due_soon', 'task_overdue', 'record_inactive'].includes(
    draft.value.event,
  ),
)
const statusOptions = computed(() =>
  (options.value?.status_options[draft.value.object] || [])
    .filter(
      (item) =>
        !item.pipeline ||
        !draft.value.pipelines.length ||
        draft.value.pipelines.includes(item.pipeline),
    )
    .map((item) => ({ ...item, label: __(item.label) })),
)
const hasConditions = computed(
  () =>
    ['statuses', 'owners', 'sources', 'pipelines'].some(
      (key) => draft.value[key].length,
    ) || Boolean(draft.value.conditions?.length),
)
const searchRecords = computed(
  () => (query) => control.search(draft.value.object, query),
)
function changeConditions(value) {
  draft.value.conditions = value
  control.markDirty()
}
function changeScope() {
  if (draft.value.scope !== 'selected') draft.value.record_ids = []
  control.markDirty()
}
function changeObject() {
  Object.assign(draft.value, {
    record_ids: [],
    statuses: [],
    to_statuses: [],
    pipelines: [],
    sources: [],
    event:
      draft.value.object === 'CRM Lead'
        ? 'lead_status_changed'
        : draft.value.object === 'CRM Deal'
          ? 'deal_stage_changed'
          : 'task_assigned',
  })
  delete draft.value.reminder_minutes
  delete draft.value.conditions
  delete draft.value.inactive_minutes
  control.markDirty()
}
function changeEvent() {
  if (!transition.value) draft.value.to_statuses = []
  if (draft.value.event === 'task_due_soon') draft.value.reminder_minutes = 60
  else delete draft.value.reminder_minutes
  if (draft.value.event === 'record_inactive')
    draft.value.inactive_minutes = 1440
  else delete draft.value.inactive_minutes
  if (reminder.value) draft.value.include_self = false
  control.markDirty()
}
function scheduledLabel(value) {
  return new Date(value).toLocaleString(window.lang || 'en', {
    timeZone: window.timezone?.user || window.timezone?.system,
  })
}
function applyPreset(value) {
  control.edit({
    ...newRule(),
    name: __(value.label),
    object: value.object,
    event: value.event,
    scope: value.scope,
    ...(value.event === 'task_due_soon'
      ? { reminder_minutes: value.reminder_minutes }
      : {}),
  })
}
function reminderTiming(value) {
  return __(
    { 15: '15 minutes before', 60: '1 hour before', 1440: '1 day before' }[
      value
    ],
  )
}
function channelSummary(rule) {
  return Object.entries(rule.channels)
    .filter(([, enabled]) => enabled)
    .map(([key]) =>
      __(
        {
          crm_push: 'CRM push',
          one_message: 'Message in One',
          one_push: 'Push for this One message',
          email: 'Email',
        }[key],
      ),
    )
    .join(' · ')
}
function ruleName(id) {
  return id === draft.value.id
    ? draft.value.name
    : state.value.configuration.rules.find((rule) => rule.id === id)?.name ||
        __('Rule')
}
async function removeConfirmed() {
  const value = deleteCandidate.value
  deleteCandidate.value = null
  await control.deleteRule(value)
}
let initialized = false
watch(state, (value) => {
  if (
    initialized ||
    !value ||
    !route.query.record ||
    !objects[route.query.object]
  )
    return
  initialized = true
  const object = route.query.object
  control.edit({
    ...newRule(),
    name: __('Selected record notifications'),
    object,
    scope: route.query.preset === 'following' ? 'followed' : 'selected',
    record_ids:
      route.query.preset === 'following' ? [] : [String(route.query.record)],
    event:
      object === 'CRM Lead'
        ? 'lead_status_changed'
        : object === 'CRM Deal'
          ? 'deal_stage_changed'
          : 'task_assigned',
  })
})
</script>
<style scoped>
.rule-panel {
  @apply border border-outline-gray-2 bg-surface-base text-ink-gray-9;
  border-radius: 12px;
  padding: 24px;
}
.rule-input {
  display: block;
  min-height: 44px;
  width: 100%;
  @apply border border-outline-gray-3 bg-surface-base text-ink-gray-9;
  border-radius: 6px;
  padding: 9px 12px;
  font-size: 16px;
}
.rule-check {
  display: flex;
  min-height: 44px;
  align-items: center;
  gap: 10px;
  font-size: 16px;
  line-height: 1.5;
  cursor: pointer;
}
.rule-check input {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
  accent-color: #292f38;
}
.crm-rules :deep(:focus-visible) {
  outline: 3px solid var(--outline-gray-4, #087f96);
  outline-offset: 3px;
}
.crm-rules :deep(button) {
  white-space: normal;
}
.crm-rules fieldset {
  min-width: 0;
}
@media (max-width: 640px) {
  .rule-panel {
    padding: 18px;
  }
  .crm-rules {
    overflow-wrap: anywhere;
  }
}
</style>
