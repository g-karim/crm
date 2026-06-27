<template>
  <div class="flex overflow-x-auto h-full">
    <Draggable
      v-if="columns"
      :list="columns"
      item-key="column"
      :delay="isTouchScreenDevice() ? 200 : 0"
      :disabled="options.manageColumns === false"
      class="flex sm:mx-2.5 mx-2 pb-3.5"
      @end="updateColumn"
    >
      <template #item="{ element: column }">
        <div
          v-if="!column.column.delete"
          class="flex flex-col gap-2.5 min-w-72 w-72 hover:bg-surface-gray-2 rounded-lg p-2.5"
        >
          <div class="flex gap-2 items-center group justify-between">
            <div class="flex items-center text-base">
              <Popover v-if="options.manageColumns !== false">
                <template #target="{ togglePopover }">
                  <Button
                    variant="ghost"
                    size="sm"
                    class="hover:!bg-surface-gray-2"
                    @click="togglePopover"
                  >
                    <IndicatorIcon :class="parseColor(column.column.color)" />
                  </Button>
                </template>
                <template #body>
                  <div
                    class="flex flex-col gap-3 px-3 py-2.5 min-w-40 rounded-lg bg-surface-modal shadow-2xl ring-1 ring-black ring-opacity-5 focus:outline-none"
                  >
                    <div class="flex gap-1">
                      <Button
                        v-for="color in colors"
                        :key="color"
                        variant="ghost"
                        @click="() => (column.column.color = color)"
                      >
                        <IndicatorIcon :class="parseColor(color)" />
                      </Button>
                    </div>
                    <div class="flex flex-row-reverse">
                      <Button
                        variant="solid"
                        :label="__('Apply')"
                        @click="updateColumn"
                      />
                    </div>
                  </div>
                </template>
              </Popover>
              <IndicatorIcon
                v-else
                class="mx-2"
                :class="parseColor(column.column.color)"
              />
              <div class="text-ink-gray-9">
                {{ __(column.column.label || column.column.name) }}
              </div>
            </div>
            <div class="flex">
              <Dropdown
                v-if="options.manageColumns !== false"
                :options="actions(column)"
              >
                <template #default>
                  <Button
                    class="opacity-0 group-hover:opacity-100 pointer-events-none group-hover:pointer-events-auto transition-opacity"
                    icon="more-horizontal"
                    variant="ghost"
                  />
                </template>
              </Dropdown>
              <Button
                icon="plus"
                variant="ghost"
                @click="options.onNewClick(column)"
              />
            </div>
          </div>
          <div class="overflow-y-auto flex flex-col gap-2 h-full">
            <Draggable
              :list="column.data"
              group="fields"
              item-key="name"
              class="flex flex-col gap-3.5 flex-1"
              :delay="isTouchScreenDevice() ? 200 : 0"
              :data-column="column.column.name"
              @end="updateColumn"
            >
              <template #item="{ element: fields }">
                <component
                  :is="options.getRoute ? 'router-link' : 'div'"
                  class="relative overflow-visible pt-3 px-3.5 pb-2.5 rounded-lg border bg-surface-white text-base flex flex-col text-ink-gray-9 transition-[background-color,border-color,box-shadow] duration-500 ease-out"
                  :class="freezeClass(cardMeta(fields))"
                  :style="freezeStyle(cardMeta(fields))"
                  :data-name="fields.name"
                  :title="cardMeta(fields)._freezeTooltip || undefined"
                  v-bind="{
                    to: options.getRoute ? options.getRoute(fields) : undefined,
                    onClick: options.onClick
                      ? () => options.onClick(fields)
                      : undefined,
                  }"
                >
                  <slot
                    name="title"
                    v-bind="{ fields, titleField, itemName: fields.name }"
                  >
                    <div class="h-5 flex items-center">
                      <div v-if="fields[titleField]">
                        {{ fields[titleField] }}
                      </div>
                      <div v-else class="text-ink-gray-4">
                        {{ __('No Title') }}
                      </div>
                    </div>
                  </slot>
                  <div class="border-b h-px my-2.5" />

                  <div class="flex flex-col gap-3.5">
                    <template v-for="value in column.fields" :key="value">
                      <slot
                        name="fields"
                        v-bind="{
                          fields,
                          fieldName: value,
                          itemName: fields.name,
                        }"
                      >
                        <div v-if="fields[value]" class="truncate">
                          {{ fields[value] }}
                        </div>
                      </slot>
                    </template>
                  </div>
                  <div class="border-b h-px mt-2.5 mb-2" />
                  <slot name="actions" v-bind="{ itemName: fields.name }">
                    <div class="flex gap-2 items-center justify-between">
                      <div></div>
                      <Button icon="plus" variant="ghost" @click.stop.prevent />
                    </div>
                  </slot>
                </component>
              </template>
            </Draggable>
            <div
              v-if="column.column.count < column.column.all_count"
              class="flex items-center justify-center"
            >
              <Button
                :label="__('Load More')"
                @click="emit('loadMore', column.column.name)"
              />
            </div>
          </div>
        </div>
      </template>
    </Draggable>
    <div v-if="options.manageColumns !== false" class="shrink-0 min-w-64">
      <Autocomplete
        value=""
        :options="deletedColumns"
        @change="(e) => addColumn(e)"
      >
        <template #target="{ togglePopover }">
          <Button
            class="w-full mt-2.5 mb-1 mr-5"
            :label="__('Add Column')"
            iconLeft="plus"
            @click="togglePopover()"
          />
        </template>
        <template #footer>
          <Button
            class="w-full"
            :label="__('Reload Columns')"
            :iconLeft="RefreshIcon"
            @click="updateColumn(null, true)"
          />
        </template>
      </Autocomplete>
    </div>
  </div>
</template>
<script setup>
import RefreshIcon from '@/components/Icons/RefreshIcon.vue'
import Autocomplete from '@/components/frappe-ui/Autocomplete.vue'
import IndicatorIcon from '@/components/Icons/IndicatorIcon.vue'
import { isTouchScreenDevice, colors, parseColor } from '@/utils'
import Draggable from 'vuedraggable'
import { Dropdown, Popover } from 'frappe-ui'
import { computed } from 'vue'

const props = defineProps({
  options: {
    type: Object,
    default: () => ({
      getRoute: null,
      onClick: null,
      onNewClick: null,
      manageColumns: true,
      getCardMeta: null,
    }),
  },
})

const emit = defineEmits(['update', 'loadMore'])

const kanban = defineModel({ type: Object })
const options = computed(() => props.options)

const titleField = computed(() => {
  return kanban.value?.data?.title_field
})

const columns = computed(() => {
  if (!kanban.value?.data?.data || kanban.value.data.view_type != 'kanban')
    return []
  let _columns = kanban.value.data.data

  let has_color = _columns.some((column) => column.column?.color)
  if (!has_color) {
    _columns.forEach((column, i) => {
      column.column['color'] = colors[i % colors.length]
    })
  }
  return _columns
})

const deletedColumns = computed(() => {
  const _columns = kanban.value?.data?.kanban_columns || []
  return _columns
    ?.filter((col) => col['delete'])
    .map((col) => {
      return { label: col.name, value: col.name }
    })
})

function actions(column) {
  return [
    {
      group: __('Options'),
      hideLabel: true,
      items: [
        {
          label: __('Delete'),
          icon: 'trash-2',
          onClick: () => {
            column.column['delete'] = true
            updateColumn()
          },
        },
      ],
    },
  ]
}

function addColumn(e) {
  let column = columns.value.find((col) => col.column.name == e.value)
  column.column['delete'] = false
  columns.value.splice(columns.value.indexOf(column), 1)
  columns.value.push(column)
  updateColumn()
}

function updateColumn(d, fetchNewColumns = false) {
  let toColumn = d?.to?.dataset.column
  let fromColumn = d?.from?.dataset.column
  let itemName = d?.item?.dataset.name

  let _columns = []
  columns.value.forEach((col) => {
    col.column['order'] = col.data.map((d) => d.name)
    if (col.column.page_length) {
      delete col.column.page_length
    }
    _columns.push(col.column)
  })

  let data = { kanban_columns: _columns, fetchNewColumns }

  if (toColumn != fromColumn) {
    data = { item: itemName, to: toColumn, kanban_columns: _columns }
  }

  emit('update', data)
}

function freezeClass(fields) {
  if (!fields?._freezeLevel) return ''
  return `kanban-card-freeze kanban-card-freeze-${fields._freezeLevel}`
}

function freezeStyle(fields) {
  if (!fields?._freezeLevel) return {}
  return { '--freeze-progress': fields._freezeProgress || 0 }
}

function cardMeta(fields) {
  return options.value.getCardMeta?.(fields) || fields
}
</script>

<style scoped>
.kanban-card-freeze {
  isolation: isolate;
  border-color: rgba(56, 189, 248, calc(0.76 + var(--freeze-progress) * 0.18));
  background: rgba(240, 249, 255, 0.94);
  box-shadow:
    inset 0 0 0 1px rgba(255, 255, 255, 0.92),
    inset 0 -16px 28px rgba(56, 189, 248, calc(0.1 + var(--freeze-progress) * 0.12));
}

.kanban-card-freeze > * {
  position: relative;
  z-index: 3;
}

.kanban-card-freeze::before,
.kanban-card-freeze::after {
  content: '';
  position: absolute;
  pointer-events: none;
  transition: opacity 500ms ease;
}

.kanban-card-freeze::before {
  z-index: 1;
  inset: 0;
  border-radius: inherit;
  opacity: calc(0.5 + var(--freeze-progress) * 0.16);
  background-image: url('../../images/ice-card-overlay.png');
  background-position: top center;
  background-size: auto 118%;
  background-repeat: no-repeat;
}

.kanban-card-freeze::after {
  z-index: 2;
  left: 0;
  right: 0;
  bottom: -12px;
  height: 42px;
  border-radius: 0;
  opacity: calc(0.74 + var(--freeze-progress) * 0.12);
  background-image: url('../../images/ice-card-edge.png');
  background-position: bottom center;
  background-size: calc(100% + 32px) auto;
  background-repeat: no-repeat;
}

.kanban-card-freeze-2 {
  border-color: rgba(2, 132, 199, 0.96);
  background: rgba(224, 242, 254, 0.96);
  box-shadow:
    inset 0 0 0 1px rgba(255, 255, 255, 0.98),
    inset 0 -22px 34px rgba(56, 189, 248, 0.24),
    inset 0 0 34px rgba(2, 132, 199, 0.16);
}

.kanban-card-freeze-2::before {
  opacity: 0.9;
  background-image: url('../../images/ice-card-overlay-heavy.png');
}

.kanban-card-freeze-2::after {
  bottom: -14px;
  height: 48px;
  opacity: 0.94;
  background-size: calc(100% + 36px) auto;
}
</style>
