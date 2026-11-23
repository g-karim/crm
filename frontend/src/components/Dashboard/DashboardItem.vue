<template>
  <div class="h-full w-full">
    <div
      v-if="item.data?.unavailable || item.data?.error"
      role="status"
      class="p-4 text-sm text-ink-gray-7"
    >
      {{ item.data.message || item.data.error }}
    </div>
    <div
      v-else-if="item.type === 'number_chart' && item.data?.value == null"
      class="flex h-full flex-col justify-center gap-2 rounded border border-outline-gray-2 bg-surface-cards p-4"
      role="status"
    >
      <span class="text-sm text-ink-gray-7">{{
        __(item.data?.title || '')
      }}</span>
      <strong class="text-xl font-medium text-ink-gray-9">{{
        __('No data')
      }}</strong>
    </div>
    <div
      v-else-if="item.type == 'number_chart'"
      class="flex h-full w-full rounded shadow overflow-hidden cursor-pointer"
    >
      <Tooltip :text="__(item.data?.tooltip || '')">
        <NumberChart
          v-if="item.data"
          :key="index"
          class="!items-start"
          :config="item.data"
        />
      </Tooltip>
    </div>
    <div
      v-else-if="item.type == 'spacer'"
      class="rounded bg-surface-base h-full overflow-hidden text-ink-gray-5 flex items-center justify-center"
      :class="editing ? 'border border-dashed border-outline-gray-2' : ''"
    >
      {{ editing ? __('Spacer') : '' }}
    </div>
    <div
      v-else-if="item.type == 'axis_chart'"
      class="h-full w-full rounded-md bg-surface-base shadow"
    >
      <AxisChart v-if="item.data" :config="item.data" />
    </div>
    <div
      v-else-if="item.type == 'donut_chart'"
      class="h-full w-full rounded-md bg-surface-base shadow overflow-hidden"
    >
      <DonutChart v-if="item.data" :config="item.data" />
    </div>
  </div>
</template>
<script setup>
import { AxisChart, DonutChart, NumberChart, Tooltip } from 'frappe-ui'

defineProps({
  index: { type: Number, required: true },
  item: { type: Object, required: true },
  editing: { type: Boolean, default: false },
})
</script>
