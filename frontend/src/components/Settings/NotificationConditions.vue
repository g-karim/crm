<template>
  <fieldset class="space-y-3" :disabled="disabled" data-advanced-conditions>
    <legend class="font-medium">{{ __('Field conditions') }}</legend>
    <p class="text-sm leading-6 text-ink-gray-6">
      {{
        __(
          'All conditions must match. Only fields you can read are available; delivery checks their current values again.',
        )
      }}
    </p>
    <div
      v-for="(condition, index) in modelValue"
      :key="index"
      class="space-y-2 rounded border border-outline-gray-2 p-3"
    >
      <label class="block space-y-1"
        ><span>{{ __('Field') }}</span>
        <select
          class="condition-input"
          :value="condition.field"
          @change="changeField(index, $event.target.value)"
        >
          <option v-if="!field(condition)" :value="condition.field">
            {{ __('Field no longer available') }}
          </option>
          <option v-for="item in fields" :key="item.value" :value="item.value">
            {{ item.label }}
          </option>
        </select>
      </label>
      <label class="block space-y-1"
        ><span>{{ __('Condition') }}</span>
        <select
          class="condition-input"
          :value="condition.operator"
          @change="changeOperator(index, $event.target.value)"
        >
          <option
            v-for="operator in field(condition)?.operators || []"
            :key="operator"
            :value="operator"
          >
            {{ __(labels[operator]) }}
          </option>
        </select>
      </label>
      <label v-if="!empty(condition)" class="block space-y-1"
        ><span>{{
          list(condition) ? __('Values separated by commas') : __('Value')
        }}</span>
        <select
          v-if="field(condition)?.kind === 'check'"
          class="condition-input"
          :value="String(condition.value)"
          @change="update(index, { value: $event.target.value === 'true' })"
        >
          <option value="true">{{ __('Yes') }}</option>
          <option value="false">{{ __('No') }}</option>
        </select>
        <select
          v-else-if="field(condition)?.options.length && !list(condition)"
          class="condition-input"
          :value="condition.value"
          @change="update(index, { value: $event.target.value })"
        >
          <option
            v-for="value in field(condition).options"
            :key="value"
            :value="value"
          >
            {{ __(value) }}
          </option>
        </select>
        <input
          v-else
          class="condition-input"
          :type="
            field(condition)?.kind === 'number'
              ? 'number'
              : field(condition)?.kind === 'date'
                ? field(condition)?.fieldtype === 'Date'
                  ? 'date'
                  : 'datetime-local'
                : 'text'
          "
          step="any"
          :value="
            list(condition) ? condition.value.join(', ') : condition.value
          "
          @input="
            update(index, {
              value: list(condition)
                ? $event.target.value
                    .split(',')
                    .map((v) => v.trim())
                    .filter(Boolean)
                : $event.target.value,
            })
          "
        />
      </label>
      <button
        type="button"
        class="min-h-11 rounded border border-outline-gray-2 px-3"
        @click="
          emit(
            'update:modelValue',
            modelValue.filter((_, i) => i !== index),
          )
        "
      >
        {{ __('Remove condition') }}
      </button>
    </div>
    <button
      type="button"
      class="min-h-11 rounded border border-outline-gray-2 px-3 disabled:opacity-50"
      :disabled="modelValue.length >= 12 || !fields.length"
      @click="add"
    >
      {{ __('Add condition') }}
    </button>
  </fieldset>
</template>

<script setup>
const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  fields: { type: Array, default: () => [] },
  disabled: Boolean,
})
const emit = defineEmits(['update:modelValue'])
const labels = {
  eq: 'Equals',
  neq: 'Does not equal',
  gt: 'Greater than',
  gte: 'At least',
  lt: 'Less than',
  lte: 'At most',
  contains: 'Contains',
  not_contains: 'Does not contain',
  in: 'One of',
  not_in: 'None of',
  is_set: 'Is set',
  is_not_set: 'Is not set',
  contains_any: 'Has any tag',
  contains_all: 'Has all tags',
  contains_none: 'Has none of these tags',
}
const field = (condition) =>
  props.fields.find((item) => item.value === condition.field)
const empty = (condition) =>
  ['is_set', 'is_not_set'].includes(condition.operator)
const list = (condition) =>
  ['in', 'not_in', 'contains_any', 'contains_all', 'contains_none'].includes(
    condition.operator,
  )
function update(index, values) {
  emit(
    'update:modelValue',
    props.modelValue.map((value, i) =>
      i === index ? { ...value, ...values } : value,
    ),
  )
}
function defaultValue(item, operator) {
  return ['is_set', 'is_not_set'].includes(operator)
    ? null
    : [
          'in',
          'not_in',
          'contains_any',
          'contains_all',
          'contains_none',
        ].includes(operator)
      ? []
      : item?.kind === 'check'
        ? false
        : item?.options[0] || ''
}
function changeField(index, value) {
  const item = props.fields.find((field) => field.value === value)
  const operator = item.operators.includes('eq') ? 'eq' : item.operators[0]
  update(index, { field: value, operator, value: defaultValue(item, operator) })
}
function changeOperator(index, operator) {
  const item = field(props.modelValue[index])
  update(index, { operator, value: defaultValue(item, operator) })
}
function add() {
  const item = props.fields[0]
  if (!item) return
  const operator = item.operators.includes('eq') ? 'eq' : item.operators[0]
  emit('update:modelValue', [
    ...props.modelValue,
    { field: item.value, operator, value: defaultValue(item, operator) },
  ])
}
</script>

<style scoped>
.condition-input {
  @apply min-h-11 w-full min-w-0 rounded border border-outline-gray-3 bg-surface-base px-3 text-base text-ink-gray-9;
}
</style>
