<template>
  <section
    class="space-y-4 rounded-xl border border-outline-gray-2 p-5"
    data-team-templates
  >
    <h2 class="text-lg font-semibold">
      {{ __('Team notification templates') }}
    </h2>
    <p class="text-sm leading-6 text-ink-gray-6">
      {{
        __(
          'A manager offers a template. You choose whether to copy it into your rules. Your channel switches stay unchanged; later template edits do not overwrite your personal rules.',
        )
      }}
    </p>
    <p v-if="error" role="alert" class="text-ink-red-7">{{ __(error) }}</p>
    <p v-if="feedback" role="status">{{ __(feedback) }}</p>
    <button
      v-if="pending"
      type="button"
      class="template-button"
      :disabled="busy"
      @click="execute(pending)"
    >
      {{ __('Retry the same request') }}
    </button>
    <article
      v-for="item in state?.offered || []"
      :key="`${item.author}:${item.id}`"
      class="space-y-2 rounded border border-outline-gray-2 p-3"
    >
      <h3 class="font-medium">{{ item.name }}</h3>
      <p class="text-sm">{{ item.rules.length }} · {{ __('Rules') }}</p>
      <p
        v-if="item.unavailable_selection_count"
        role="status"
        class="text-sm text-ink-gray-6"
      >
        {{
          __(
            'Some template records are unavailable. Ask your manager to update the selection.',
          )
        }}
      </p>
      <button
        type="button"
        class="template-button"
        :disabled="busy || !!pending || !!item.unavailable_selection_count"
        @click="apply(item)"
      >
        {{ __('Apply template to my rules') }}
      </button>
    </article>
    <p v-if="state && !state.offered.length" class="text-sm text-ink-gray-6">
      {{ __('No team templates are offered to you.') }}
    </p>
    <details
      v-if="state?.can_manage"
      class="rounded border border-outline-gray-2 p-3"
    >
      <summary class="flex min-h-11 cursor-pointer items-center font-medium">
        {{ __('Manage team templates') }}
      </summary>
      <form class="mt-3 space-y-3" @submit.prevent="publish">
        <p class="text-sm leading-6 text-ink-gray-6">
          {{
            __(
              'The current rule editor supplies the template content. Publishing does not enable notifications for anyone.',
            )
          }}
        </p>
        <label class="block space-y-1"
          ><span>{{ __('Template name') }}</span
          ><input
            v-model="name"
            required
            maxlength="100"
            class="template-input"
            :disabled="busy || !!pending"
        /></label>
        <fieldset class="space-y-2" :disabled="busy || !!pending">
          <legend>{{ __('Offer to existing roles') }}</legend>
          <label
            v-for="role in state.roles"
            :key="role"
            class="flex min-h-11 items-center gap-2"
            ><input v-model="roles" type="checkbox" :value="role" />{{
              __(role)
            }}</label
          >
        </fieldset>
        <Choices
          v-model="recipients"
          :label="__('Or selected CRM users')"
          :search="people"
          :disabled="busy || !!pending"
        />
        <button
          type="submit"
          class="template-button"
          :disabled="busy || !!pending || !rule?.name?.trim()"
        >
          {{ __('Publish current rule as template') }}
        </button>
      </form>
      <div
        v-for="item in state.owned"
        :key="item.id"
        class="mt-3 flex flex-wrap items-center justify-between gap-3 border-t border-outline-gray-2 pt-3"
      >
        <span
          >{{ item.name }} ·
          {{ __(item.enabled ? 'Enabled' : 'Disabled') }}</span
        >
        <button
          type="button"
          class="template-button"
          :disabled="busy || !!pending"
          @click="toggle(item)"
        >
          {{ __(item.enabled ? 'Withdraw template' : 'Offer template again') }}
        </button>
      </div>
    </details>
  </section>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { call, frappeRequest } from 'frappe-ui'
import Choices from './NotificationRuleChoices.vue'

const props = defineProps({
  viewer: { type: String, required: true },
  revision: { type: Number, required: true },
  rule: { type: Object, default: null },
  people: { type: Function, default: undefined },
})
const emit = defineEmits(['changed'])
const state = ref(null),
  error = ref(''),
  feedback = ref(''),
  busy = ref(false),
  pending = ref(null)
const name = ref(''),
  roles = ref([]),
  recipients = ref([])
const id = () => crypto.randomUUID().replaceAll('-', '')
async function reload() {
  state.value = await frappeRequest({
    url: 'crm.notification_rules.templates.catalog',
    method: 'GET',
    params: { expected_viewer: props.viewer },
  })
  if (state.value.viewer !== props.viewer) {
    state.value = null
    throw new Error('SessionChanged')
  }
}
async function execute(operation) {
  if (busy.value) return
  busy.value = true
  error.value = ''
  feedback.value = ''
  pending.value = operation
  try {
    const result = await call(
      `crm.notification_rules.templates.${operation.method}`,
      operation.args,
    )
    if (result.viewer !== props.viewer) throw new Error('SessionChanged')
    pending.value = null
    try {
      await reload()
    } catch {
      error.value = 'Saved. Could not refresh the template list.'
    }
    feedback.value =
      operation.method === 'apply_template'
        ? 'Template copied. Your channel switches are unchanged.'
        : 'Team template saved.'
    emit('changed')
  } catch (exception) {
    const text = `${exception?.exc_type || ''} ${exception?.exception || ''} ${exception?.message || ''}`
    if (
      /ValidationError|PermissionError|AuthenticationError|TimestampMismatch/.test(
        text,
      )
    ) {
      pending.value = null
      error.value =
        'Review the template audience, record access and current version.'
      try {
        await reload()
      } catch {
        state.value = null
      }
    } else error.value = 'The result is unknown. Retry the same request.'
  } finally {
    busy.value = false
  }
}
function save(values) {
  return execute({
    method: 'save_template',
    args: {
      values,
      expected_revision: state.value.revision,
      mutation_id: id(),
      expected_viewer: props.viewer,
    },
  })
}
function publish() {
  const value = JSON.parse(JSON.stringify(props.rule))
  delete value.unavailable_selection_count
  return save({
    id: id(),
    name: name.value,
    enabled: true,
    roles: roles.value,
    recipients: recipients.value,
    rules: [value],
  })
}
const toggle = (item) => save({ ...item, enabled: !item.enabled })
const apply = (item) =>
  execute({
    method: 'apply_template',
    args: {
      author: item.author,
      template_id: item.id,
      expected_template_revision: item.revision,
      expected_revision: props.revision,
      mutation_id: id(),
      expected_viewer: props.viewer,
    },
  })
onMounted(() =>
  reload().catch(() => {
    error.value = 'Could not load team templates.'
  }),
)
</script>

<style scoped>
.template-button {
  @apply min-h-11 rounded border border-outline-gray-2 px-3 disabled:opacity-50;
}
.template-input {
  @apply min-h-11 w-full min-w-0 rounded border border-outline-gray-3 bg-surface-base px-3;
}
</style>
