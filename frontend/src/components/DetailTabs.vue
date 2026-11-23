<template>
  <div
    class="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden text-ink-gray-9"
  >
    <div
      ref="navigation"
      class="shrink-0 border-b border-outline-gray-2 bg-surface-base"
    >
      <div
        v-if="compact"
        class="grid gap-3 px-3 py-3"
        :class="activeGroup?.views.length > 1 ? 'grid-cols-2' : 'grid-cols-1'"
      >
        <label class="min-w-0 text-xs font-medium text-ink-gray-6">
          {{ __('Card section') }}
          <select
            :id="id + '-section'"
            :aria-label="__('Card section')"
            :value="activeGroup?.name"
            class="detail-select mt-1"
            @change="selectGroup($event.target.value)"
          >
            <option
              v-for="group in groups"
              :key="group.name"
              :value="group.name"
            >
              {{ __(group.label) }}
            </option>
          </select>
        </label>
        <label
          v-if="activeGroup?.views.length > 1"
          class="min-w-0 text-xs font-medium text-ink-gray-6"
        >
          {{ __('Show') }}
          <select
            :value="modelValue"
            :aria-label="__('Show')"
            class="detail-select mt-1"
            @change="selectView(Number($event.target.value))"
          >
            <option
              v-for="view in activeGroup.views"
              :key="view.name"
              :value="view.index"
            >
              {{ __(detailViewLabel(view)) }}
            </option>
          </select>
        </label>
      </div>
      <div
        v-else
        role="tablist"
        :aria-label="__('Card section')"
        class="flex min-h-12 items-stretch gap-1 px-4"
      >
        <button
          v-for="group in groups"
          :id="id + '-' + group.name"
          :key="group.name"
          type="button"
          role="tab"
          :aria-selected="group.name === activeGroup?.name"
          :aria-controls="id + '-panel'"
          :tabindex="group.name === activeGroup?.name ? 0 : -1"
          class="relative flex min-h-12 items-center gap-2 whitespace-nowrap px-3 text-sm font-medium outline-none transition-colors focus-visible:rounded focus-visible:ring-2 focus-visible:ring-outline-gray-4"
          :class="
            group.name === activeGroup?.name
              ? 'text-ink-gray-9'
              : 'text-ink-gray-5 hover:text-ink-gray-9'
          "
          @click="selectGroup(group.name)"
          @keydown="onGroupKeydown($event, group.name)"
        >
          <FeatherIcon :name="group.icon" class="size-4" aria-hidden="true" />
          {{ __(group.label) }}
          <span
            v-if="group.name === activeGroup?.name"
            class="absolute inset-x-3 bottom-0 h-0.5 rounded bg-surface-gray-10"
          />
        </button>
      </div>
      <nav
        v-if="!compact && activeGroup?.views.length > 1"
        :aria-label="__(activeGroup.label)"
        class="flex flex-wrap gap-1 border-t border-outline-gray-2 px-5 py-2"
      >
        <button
          v-for="view in activeGroup.views"
          :key="view.name"
          type="button"
          :aria-pressed="view.index === modelValue"
          class="min-h-9 rounded-md px-3 text-sm outline-none transition-colors focus-visible:ring-2 focus-visible:ring-outline-gray-4"
          :class="
            view.index === modelValue
              ? 'bg-surface-gray-3 font-medium text-ink-gray-9'
              : 'text-ink-gray-6 hover:bg-surface-gray-2 hover:text-ink-gray-9'
          "
          @click="selectView(view.index)"
        >
          {{ __(detailViewLabel(view)) }}
        </button>
      </nav>
    </div>
    <section
      :id="id + '-panel'"
      :role="compact ? 'region' : 'tabpanel'"
      :aria-labelledby="compact ? undefined : id + '-' + activeGroup?.name"
      :aria-label="compact ? __(activeGroup?.label || 'Activity') : undefined"
      class="flex min-h-0 flex-1 flex-col overflow-auto [container-type:inline-size]"
    >
      <slot name="tab-panel" :tab="tabs[modelValue] || tabs[0]" />
    </section>
  </div>
</template>

<script setup>
import { computed, nextTick, ref, useId } from 'vue'
import { useElementSize } from '@vueuse/core'
import { FeatherIcon } from 'frappe-ui'
import { detailViewLabel, groupDetailTabs } from '@/utils/detailTabs'

const props = defineProps({
  tabs: { type: Array, default: () => [] },
  modelValue: { type: Number, default: 0 },
})
const emit = defineEmits(['update:modelValue'])
const id = 'detail-' + useId()
const navigation = ref(null)
const { width } = useElementSize(navigation)
const compact = computed(() => width.value > 0 && width.value < 520)
const groups = computed(() => groupDetailTabs(props.tabs))
const activeGroup = computed(
  () =>
    groups.value.find((group) =>
      group.views.some((view) => view.index === props.modelValue),
    ) || groups.value[0],
)

function selectView(index) {
  if (props.tabs[index]) emit('update:modelValue', index)
}

function selectGroup(name) {
  if (name === activeGroup.value?.name) return
  const group = groups.value.find((group) => group.name === name)
  if (group) selectView(group.views[0].index)
}

async function onGroupKeydown(event, name) {
  const index = groups.value.findIndex((group) => group.name === name)
  let next
  if (event.key === 'ArrowRight') next = (index + 1) % groups.value.length
  else if (event.key === 'ArrowLeft')
    next = (index - 1 + groups.value.length) % groups.value.length
  else if (event.key === 'Home') next = 0
  else if (event.key === 'End') next = groups.value.length - 1
  else return
  event.preventDefault()
  const target = groups.value[next]
  selectGroup(target.name)
  await nextTick()
  document.getElementById(id + '-' + target.name)?.focus()
}
</script>

<style scoped>
.detail-select {
  @apply block min-h-11 w-full min-w-0 rounded-md border border-outline-gray-2 bg-surface-gray-2 px-2 text-sm font-normal text-ink-gray-9 focus:border-outline-gray-4 focus:ring-0 dark:[color-scheme:dark];
}
</style>
