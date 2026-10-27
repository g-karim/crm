<template>
  <section
    :class="
      item.kind === 'note'
        ? 'flex min-h-[20rem] flex-col'
        : 'rounded-lg border border-outline-gray-2 p-3'
    "
    :data-work-item="item.kind"
    :data-record-name="item.name || ''"
  >
    <div class="mb-3 flex shrink-0 items-center justify-between gap-3">
      <h3 class="min-w-0 break-words text-base font-semibold text-ink-gray-9">
        <label v-if="item.kind === 'note'" :for="`call-note-${item.key}`">{{
          __('Call note')
        }}</label>
        <template v-else>{{
          item.name && !expanded ? item.values.title : __('New task')
        }}</template>
      </h3>
      <div class="flex shrink-0 items-center gap-2">
        <span
          v-if="item.name && !itemDirty(item)"
          role="status"
          class="inline-flex items-center gap-1 text-sm text-ink-gray-6"
        >
          <span class="lucide-check size-3" aria-hidden="true" />{{
            __('Saved')
          }}
        </span>
        <span v-else-if="itemDirty(item)" class="text-sm text-ink-gray-6">{{
          __('Draft')
        }}</span>
        <Button
          v-if="item.kind === 'note'"
          icon="lucide-pencil"
          :aria-label="__('Edit note title')"
          :tooltip="__('Edit note title')"
          variant="ghost"
          class="min-h-11 min-w-11"
          :aria-expanded="showTitle"
          @click="showTitle = !showTitle"
        />
      </div>
    </div>
    <template v-if="item.kind === 'note'">
      <FormControl
        v-if="showTitle"
        v-model="fields.title"
        :label="__('Note title')"
        maxlength="140"
        class="mb-3"
      />
      <textarea
        :id="`call-note-${item.key}`"
        v-model="fields.text"
        :aria-label="__('Note text')"
        :placeholder="__('Write down the essentials of the conversation…')"
        rows="9"
        class="min-h-56 w-full flex-1 resize-y rounded-lg border border-outline-gray-2 bg-surface-base p-4 text-base leading-6 text-ink-gray-9 placeholder:text-ink-gray-4 focus:border-outline-gray-5 focus:outline-none focus:ring-2 focus:ring-outline-gray-3"
      />
    </template>
    <template v-else-if="expanded">
      <div class="space-y-3">
        <FormControl
          v-model="fields.title"
          :label="__('Task title')"
          :placeholder="__('For example, send a proposal')"
          maxlength="140"
        />
        <FormControl
          v-model="fields.due_date"
          type="datetime-local"
          :label="__('Due Date')"
        />
        <Button
          :label="__('Task details')"
          :icon-left="showDetails ? 'lucide-chevron-up' : 'lucide-chevron-down'"
          variant="ghost"
          class="min-h-10"
          :aria-expanded="showDetails"
          @click="showDetails = !showDetails"
        />
        <div v-if="showDetails" class="space-y-3">
          <FormControl
            v-model="fields.description"
            type="textarea"
            :label="__('Description')"
            :rows="3"
          />
          <FormControl
            v-model="fields.assigned_to"
            type="select"
            :label="__('Task assignee')"
            :options="people"
            :disabled="!options"
          />
          <div class="grid grid-cols-2 gap-3">
            <FormControl
              v-model="fields.priority"
              type="select"
              :label="__('Priority')"
              :options="priorities"
            />
            <FormControl
              v-model="fields.status"
              type="select"
              :label="__('Status')"
              :options="statuses"
            />
          </div>
        </div>
      </div>
    </template>
    <div v-else class="space-y-3">
      <p class="flex flex-wrap gap-x-3 gap-y-1 text-sm text-ink-gray-6">
        <span>{{ __(item.values.status) }}</span
        ><span v-if="dueSummary">{{ dueSummary }}</span>
      </p>
      <Button
        :label="__('Edit task')"
        icon-left="lucide-pencil"
        variant="ghost"
        class="min-h-11"
        @click="editing = true"
      />
    </div>
    <p
      v-if="item.error"
      role="alert"
      class="mt-3 shrink-0 rounded bg-surface-red-1 p-3 text-sm leading-5 text-ink-gray-9"
    >
      {{ __(item.error) }}
    </p>
    <div
      v-if="expanded"
      class="mt-4 flex shrink-0 flex-wrap items-center gap-2"
    >
      <Button
        :label="saveLabel"
        :loading="item.saving"
        :disabled="!canSave"
        variant="solid"
        class="min-h-11"
        @click="store.save(work, item)"
      />
      <Button
        v-if="
          item.kind === 'task' && item.name && !itemDirty(item) && !item.error
        "
        :label="__('Collapse task')"
        variant="ghost"
        class="min-h-11"
        @click="editing = false"
      />
      <Button
        v-if="item.conflict && item.name"
        :label="__('Load latest version')"
        :disabled="item.saving"
        @click="store.reload(work, item)"
      />
      <Button
        v-if="item.backup"
        :label="__('Restore my draft')"
        @click="restoreDraft"
      />
    </div>
    <p
      v-if="!work.context && expanded"
      class="mt-3 shrink-0 text-sm leading-5 text-ink-gray-6"
    >
      {{ __('Choose a customer record to save. Your text stays here.') }}
    </p>
    <p
      v-if="item.backup"
      class="mt-3 shrink-0 text-sm leading-5 text-ink-gray-6"
    >
      {{
        __('The latest version is loaded. Your previous draft can be restored.')
      }}
    </p>
  </section>
</template>
<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { Button, FormControl } from 'frappe-ui'
import { callWorkStore } from '@/stores/callWork'
import { itemDirty } from '@/utils/callWork'

const props = defineProps({
  work: { type: Object, required: true },
  item: { type: Object, required: true },
  options: { type: Object, default: null },
})
const store = callWorkStore()
const showTitle = ref(false)
const showDetails = ref(false)
const editing = ref(!props.item.name)
const expanded = computed(
  () =>
    props.item.kind === 'note' ||
    editing.value ||
    itemDirty(props.item) ||
    props.item.error ||
    props.item.backup,
)
const dueSummary = computed(() => {
  if (!props.item.values.due_date) return ''
  const date = new Date(props.item.values.due_date.replace(' ', 'T'))
  return Number.isNaN(date.getTime())
    ? ''
    : date.toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' })
})
watch(
  () => props.item.saving,
  (saving, wasSaving) => {
    if (
      wasSaving &&
      !saving &&
      props.item.kind === 'task' &&
      props.item.name &&
      !itemDirty(props.item) &&
      !props.item.error &&
      !props.item.backup
    )
      editing.value = false
  },
)

const fields = reactive(
  Object.fromEntries(
    [
      'title',
      'text',
      'description',
      'assigned_to',
      'due_date',
      'priority',
      'status',
    ].map((field) => [
      field,
      computed({
        get: () => props.item.values[field] || '',
        set: (value) => store.setField(props.item, field, value),
      }),
    ]),
  ),
)
const people = computed(() => [
  { value: '', label: __('Unassigned') },
  ...(props.options?.people || []),
])
const priorities = computed(() =>
  (props.options?.priorities || ['Low', 'Medium', 'High']).map((value) => ({
    value,
    label: __(value),
  })),
)
const statuses = computed(() =>
  (
    props.options?.statuses || [
      'Backlog',
      'Todo',
      'In Progress',
      'Done',
      'Canceled',
    ]
  ).map((value) => ({ value, label: __(value) })),
)
const saveLabel = computed(() =>
  props.item.pending
    ? __('Retry saving')
    : props.item.name
      ? __('Save changes')
      : props.item.kind === 'note'
        ? __('Save note')
        : __('Create task'),
)
const canSave = computed(() =>
  Boolean(
    props.work.context &&
    !props.work.resolving &&
    props.options?.[props.item.kind === 'note' ? 'can_note' : 'can_task'] &&
    !props.item.saving &&
    !props.item.conflict &&
    itemDirty(props.item) &&
    (props.item.pending ||
      (props.item.values.title.trim() &&
        (props.item.kind !== 'note' || props.item.values.text.trim()))),
  ),
)
function restoreDraft() {
  store.restoreDraft(props.item)
}
</script>
