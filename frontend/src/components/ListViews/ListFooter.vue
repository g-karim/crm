<template>
  <FrappeListFooter
    :modelValue="modelValue"
    :options="options"
    @update:modelValue="(value) => emit('update:modelValue', value)"
    @loadMore="emit('loadMore')"
  >
    <template #right>
      <div class="flex items-center">
        <Button
          v-if="showLoadMore"
          :label="__('Load More')"
          @click="emit('loadMore')"
        />
        <div v-if="showLoadMore" class="mx-3 h-[80%] border-l" />
        <div class="flex items-center gap-1 text-base text-ink-gray-5">
          <div>{{ options.rowCount || '0' }}</div>
          <div>{{ __('of') }}</div>
          <div>{{ options.totalCount || '0' }}</div>
        </div>
      </div>
    </template>
  </FrappeListFooter>
</template>

<script setup>
import { Button, ListFooter as FrappeListFooter } from 'frappe-ui'
import { computed } from 'vue'

const props = defineProps({
  modelValue: {
    type: Number,
    default: 20,
  },
  options: {
    type: Object,
    default: () => ({
      rowCount: 0,
      totalCount: 0,
      pageLengthOptions: [20, 50, 100],
    }),
  },
})

const emit = defineEmits(['update:modelValue', 'loadMore'])

const showLoadMore = computed(() => {
  return (
    props.options.rowCount &&
    props.options.totalCount &&
    props.options.rowCount < props.options.totalCount
  )
})
</script>
