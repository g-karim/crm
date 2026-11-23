<template>
  <div class="overflow-x-auto" :aria-label="label" tabindex="0">
    <List :columns="tracks" :aria-label="label" :style="{ minWidth }">
      <ListHeader
        class="relative grid gap-x-4"
        :style="{
          gridTemplateColumns: tracks.join(' '),
          color: 'var(--ink-gray-6)',
        }"
      >
        <ListHeaderCell
          v-for="column in columns"
          :key="column.key"
          :class="column.numeric ? 'justify-end' : ''"
        >
          {{ column.label }}
        </ListHeaderCell>
      </ListHeader>
      <ListRows v-slot="{ item: row }" :items="rows" :row-key="rowKey">
        <ListRow
          class="relative grid min-h-12 gap-x-4"
          :style="{ gridTemplateColumns: tracks.join(' ') }"
        >
          <ListCell
            v-for="column in columns"
            :key="column.key"
            class="py-3 text-base text-ink-gray-8"
            :class="column.numeric ? 'justify-end tabular-nums' : ''"
          >
            <slot
              name="cell"
              :row="row"
              :column="column"
              :value="row[column.key]"
            >
              <span class="break-words">{{ row[column.key] }}</span>
            </slot>
          </ListCell>
        </ListRow>
      </ListRows>
    </List>
    <p v-if="!rows.length" class="py-6 text-center text-base text-ink-gray-6">
      {{ emptyText }}
    </p>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import 'frappe-ui/list-style.css'
import {
  List,
  ListRow,
  ListCell,
  ListHeader,
  ListHeaderCell,
  ListRows,
} from 'frappe-ui/list'
const props = defineProps({
  columns: { type: Array, required: true },
  rows: { type: Array, required: true },
  rowKey: { type: String, default: 'key' },
  label: { type: String, required: true },
  emptyText: { type: String, default: '' },
  minWidth: { type: String, default: '480px' },
})
const tracks = computed(() =>
  props.columns.map(
    (column, index) =>
      column.width ||
      (index === 0 ? 'minmax(150px, 2fr)' : 'minmax(90px, 1fr)'),
  ),
)
</script>
