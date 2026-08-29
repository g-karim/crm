<template>
  <div class="min-h-full space-y-6 p-6 text-ink-gray-8">
    <div class="flex flex-wrap items-start justify-between gap-3 px-2 pt-2">
      <div class="flex min-w-0 flex-1 flex-col gap-1">
        <div class="flex min-w-0 flex-wrap items-center gap-2">
          <Button
            v-if="editorOpen"
            variant="ghost"
            icon-left="chevron-left"
            :label="
              displayPipelineName(draft.pipeline_name) || __('Sales Pipelines')
            "
            size="md"
            class="-ml-4 min-w-0 !max-w-full !justify-start !pr-0 text-xl font-semibold hover:bg-transparent hover:opacity-70 focus:bg-transparent focus:outline-none focus:ring-0 active:bg-transparent"
            @click="goBack"
          />
          <h2 v-else class="flex h-5 gap-2 text-xl font-semibold leading-none">
            {{ __('Sales Pipelines') }}
          </h2>
          <Badge
            v-if="editorOpen && isDirty"
            :label="__('Not Saved')"
            theme="orange"
            variant="subtle"
          />
          <Badge
            v-if="editorOpen && selectedPipeline?.is_default"
            :label="__('Default')"
            theme="blue"
            variant="subtle"
          />
          <Badge
            v-if="editorOpen && selectedPipeline?.archived"
            :label="__('Archived')"
            theme="gray"
            variant="subtle"
          />
        </div>
        <p v-if="!editorOpen" class="text-p-base text-ink-gray-6">
          {{
            __(
              'Configure deal pipelines and their stages for different sales processes.',
            )
          }}
        </p>
        <p v-else class="text-p-base text-ink-gray-6">
          {{ getStageCount(selectedPipelineName) }}
          {{ __('Pipeline stages count suffix') }}
          <span v-if="dealCounts[selectedPipelineName]">
            · {{ dealCounts[selectedPipelineName] }}
            {{ __('Pipeline deals count suffix') }}
          </span>
        </p>
      </div>
      <div class="flex shrink-0 flex-wrap items-center justify-end gap-2">
        <template v-if="!editorOpen">
          <div class="flex items-center gap-2">
            <Switch v-model="showArchived" size="sm" />
            <span class="text-p-sm text-ink-gray-6">{{ __('Archived') }}</span>
          </div>
          <Button
            :label="__('New')"
            icon-left="plus"
            variant="solid"
            @click="createPipeline"
          />
        </template>
        <template v-else>
          <Button
            v-if="selectedPipeline"
            :label="__('Duplicate')"
            icon-left="copy"
            @click="duplicateSelectedPipeline"
          />
          <Button
            v-if="selectedPipeline"
            :label="selectedPipeline.archived ? __('Restore') : __('Archive')"
            :icon-left="selectedPipeline.archived ? 'rotate-ccw' : 'archive'"
            @click="openPipelineArchiveDialog"
          />
          <Button
            :label="__('Save')"
            variant="solid"
            :disabled="!isDirty && !draftingNewPipeline"
            :loading="saving"
            @click="saveSelectedPipeline"
          />
        </template>
      </div>
    </div>

    <div
      v-if="settings.loading"
      class="flex flex-1 items-center justify-center"
    >
      <LoadingIndicator class="size-8" />
    </div>

    <div v-else-if="!editorOpen" class="flex flex-col px-2">
      <div
        v-if="!pipelines.length"
        class="flex flex-1 items-center justify-center text-p-base text-ink-gray-5"
      >
        {{ __('No pipelines yet') }}
      </div>

      <div v-else class="overflow-x-hidden">
        <div
          class="grid grid-cols-[minmax(260px,1fr)_80px_80px_88px] gap-3 px-3 py-2 text-p-sm font-medium text-ink-gray-5"
        >
          <div>{{ __('Pipeline') }}</div>
          <div class="text-center">{{ __('Stages') }}</div>
          <div class="text-center">{{ __('Deals') }}</div>
          <div class="text-right">{{ __('Actions') }}</div>
        </div>
        <div class="h-px border-t border-outline-gray-modals" />
        <div
          v-for="pipeline in pipelines"
          :key="pipeline.name"
          class="grid grid-cols-[minmax(260px,1fr)_80px_80px_88px] items-center gap-3 rounded px-3 py-3 hover:bg-surface-menu-bar"
        >
          <button
            class="flex min-w-0 items-center gap-3 text-left"
            @click="openEditor(pipeline.name)"
          >
            <div
              class="size-2.5 shrink-0 rounded-full"
              :style="{ backgroundColor: getColorValue(pipeline.color) }"
            />
            <div
              v-if="pipeline.icon"
              class="flex size-8 shrink-0 items-center justify-center text-2xl leading-none"
            >
              {{ pipeline.icon }}
            </div>
            <div class="min-w-0">
              <div class="flex min-w-0 flex-wrap items-center gap-2">
                <span class="truncate text-p-base font-medium text-ink-gray-8">
                  {{ displayPipelineName(pipeline.pipeline_name) }}
                </span>
                <Badge
                  v-if="pipeline.is_default"
                  :label="__('Default')"
                  theme="blue"
                  variant="subtle"
                />
                <Badge
                  v-if="pipeline.archived"
                  :label="__('Archived')"
                  theme="gray"
                  variant="subtle"
                />
                <Badge
                  v-if="!pipeline.enabled"
                  :label="__('Disabled')"
                  theme="gray"
                  variant="subtle"
                />
              </div>
              <div
                v-if="pipeline.description"
                class="truncate text-p-sm text-ink-gray-5"
              >
                {{ __(pipeline.description) }}
              </div>
            </div>
          </button>
          <div class="text-center text-p-base text-ink-gray-7">
            {{ getStageCount(pipeline.name) }}
          </div>
          <div class="text-center text-p-base text-ink-gray-7">
            {{ dealCounts[pipeline.name] || 0 }}
          </div>
          <div class="flex justify-end gap-1">
            <Button
              icon="external-link"
              variant="subtle"
              @click="openEditor(pipeline.name)"
            />
            <Dropdown
              :options="getPipelineActions(pipeline)"
              :button="{ icon: 'more-horizontal', variant: 'ghost' }"
            />
          </div>
        </div>
      </div>
    </div>

    <div v-else class="space-y-5 px-2">
      <section class="grid grid-cols-[minmax(0,1fr)_18rem] items-start gap-6">
        <div class="flex min-w-0 flex-col gap-4">
          <div
            class="grid min-w-0 grid-cols-[minmax(220px,2fr)_minmax(110px,1fr)_64px] items-start gap-3"
          >
            <FormControl
              :model-value="displayPipelineName(draft.pipeline_name)"
              :label="__('Pipeline Name')"
              :placeholder="__('Pipeline Name')"
              required
              @update:model-value="
                (value) => (draft.pipeline_name = canonicalPipelineName(value))
              "
            />
            <FormControl
              v-model="draft.position"
              type="number"
              :label="__('Position')"
            />
            <div class="flex min-w-0 flex-col gap-1.5">
              <div class="text-base text-ink-gray-5">{{ __('Color') }}</div>
              <Popover placement="bottom-start">
                <template #target="{ isOpen, togglePopover }">
                  <button
                    type="button"
                    class="flex size-8 items-center justify-center rounded bg-surface-gray-2 hover:bg-surface-gray-3"
                    :class="isOpen ? 'ring-2 ring-outline-gray-3' : ''"
                    :title="getColorLabel(draft.color)"
                    :aria-label="getColorLabel(draft.color)"
                    @click="togglePopover"
                  >
                    <span
                      class="size-4 rounded-full border border-outline-gray-2"
                      :style="{ backgroundColor: getColorValue(draft.color) }"
                    />
                  </button>
                </template>
                <template #body="{ togglePopover }">
                  <div
                    class="my-1 rounded-lg bg-surface-modal p-2 shadow-2xl ring-1 ring-black ring-opacity-5"
                  >
                    <div class="grid grid-cols-7 gap-1.5">
                      <button
                        v-for="option in colorOptions"
                        :key="option.value"
                        type="button"
                        class="size-5 rounded-full border transition"
                        :class="
                          draft.color === option.value
                            ? 'border-ink-gray-8 shadow-sm ring-2 ring-outline-gray-3'
                            : 'border-outline-gray-2 hover:border-ink-gray-5'
                        "
                        :style="{ backgroundColor: option.hex }"
                        :title="option.label"
                        :aria-label="option.label"
                        @click="selectColor(draft, option.value, togglePopover)"
                      />
                    </div>
                  </div>
                </template>
              </Popover>
            </div>
          </div>

          <div
            class="grid min-w-0 grid-cols-[5.5rem_minmax(0,1fr)] items-start gap-3"
          >
            <div class="flex flex-col gap-1.5">
              <div class="text-base text-ink-gray-5">{{ __('Icon') }}</div>
              <div class="flex gap-2">
                <IconPicker v-slot="{ togglePopover }" v-model="draft.icon">
                  <button
                    type="button"
                    class="flex size-11 items-center justify-center rounded bg-surface-gray-2 text-2xl leading-none hover:bg-surface-gray-3"
                    @click="togglePopover"
                  >
                    <span class="block leading-none">
                      {{ draft.icon || '+' }}
                    </span>
                  </button>
                </IconPicker>
                <Button
                  v-if="draft.icon"
                  icon="x"
                  variant="subtle"
                  class="size-11"
                  @click="draft.icon = ''"
                />
              </div>
            </div>
            <FormControl
              v-model="draft.description"
              type="textarea"
              :label="__('Description')"
            />
          </div>
          <label
            class="flex items-center justify-between gap-3 rounded border border-outline-gray-2 px-3 py-2.5"
          >
            <div class="flex min-w-0 flex-col gap-0.5">
              <span class="text-p-base font-medium text-ink-gray-7">
                {{ __('Deal card ice effect') }}
              </span>
              <span class="text-p-sm text-ink-gray-5">
                {{
                  __('Show ice on inactive deal cards in this pipeline kanban.')
                }}
              </span>
            </div>
            <Switch v-model="draft.enable_kanban_freeze_effect" size="sm" />
          </label>
        </div>
        <div
          class="flex flex-col gap-3 rounded border border-outline-gray-2 p-3"
        >
          <label class="flex items-center justify-between gap-2 text-p-sm">
            <span>{{ __('Enabled') }}</span>
            <Switch v-model="draft.enabled" size="sm" />
          </label>
          <label class="flex items-center justify-between gap-2 text-p-sm">
            <span>{{ __('Default') }}</span>
            <Switch v-model="draft.is_default" size="sm" />
          </label>
          <div class="border-t border-outline-gray-2" />
          <div
            class="flex items-center gap-1.5 text-p-sm font-medium text-ink-gray-8"
          >
            <span>{{ __('Transition Rules') }}</span>
            <div class="group relative flex">
              <button
                type="button"
                class="flex size-5 items-center justify-center rounded-full text-ink-gray-5 hover:bg-surface-gray-2 hover:text-ink-gray-8"
                :aria-label="__('Transition Rules Help')"
              >
                ?
              </button>
              <div
                class="pointer-events-none absolute left-1/2 top-7 z-20 hidden w-72 -translate-x-1/2 rounded-lg border border-outline-gray-2 bg-surface-modal px-3 py-2 text-p-xs font-normal leading-5 text-ink-gray-8 shadow-lg group-hover:block"
              >
                {{ transitionRulesHelpText }}
              </div>
            </div>
          </div>
          <FormControl
            v-model="draft.stage_skip_rule"
            type="select"
            :label="__('Stage skipping')"
            :options="ruleOptions"
          />
          <FormControl
            v-model="draft.stage_backwards_rule"
            type="select"
            :label="__('Moving backwards')"
            :options="ruleOptions"
          />
          <FormControl
            v-model="draft.closing_fields_rule"
            type="select"
            :label="__('Required fields for closing deals')"
            :options="ruleOptions"
          />
          <div
            v-if="draft.closing_fields_rule !== 'Allow'"
            class="flex flex-col gap-1.5"
          >
            <div class="text-base text-ink-gray-5">
              {{ __('Required fields') }}
            </div>
            <div
              v-if="requiredClosingFields.length"
              class="flex flex-wrap gap-1.5"
            >
              <div
                v-for="field in requiredClosingFields"
                :key="field.fieldname"
                class="flex max-w-full items-center gap-1 rounded bg-surface-gray-2 py-1 pl-2 pr-1 text-p-sm text-ink-gray-7"
              >
                <span class="truncate">{{ __(field.label) }}</span>
                <Button
                  icon="x"
                  variant="ghost"
                  class="!h-5 !w-5"
                  @click="removeRequiredClosingField(field.fieldname)"
                />
              </div>
            </div>
            <Autocomplete
              value=""
              :options="requiredClosingFieldOptions"
              :placeholder="__('Search fields')"
              @change="addRequiredClosingField"
            >
              <template #target="{ togglePopover }">
                <Button
                  class="w-full !justify-start"
                  :label="__('Add Field')"
                  icon-left="plus"
                  @click="togglePopover()"
                />
              </template>
              <template #item-label="{ option }">
                <div class="flex min-w-0 flex-col gap-0.5 text-ink-gray-9">
                  <div class="truncate">{{ option.label }}</div>
                  <div class="truncate text-sm text-ink-gray-4">
                    {{ `${option.fieldname} - ${__(option.fieldtype)}` }}
                  </div>
                </div>
              </template>
            </Autocomplete>
          </div>
          <ErrorMessage :message="errorMessage" />
        </div>
      </section>

      <section class="flex flex-col">
        <div class="mb-3 flex items-center justify-between">
          <div>
            <h3 class="text-lg font-semibold text-ink-gray-8">
              {{ __('Stages') }}
            </h3>
          </div>
          <div class="flex items-center gap-2">
            <Button
              :label="__('Add Stage')"
              icon-left="plus"
              :disabled="!selectedPipelineName"
              @click="addStage"
            />
            <Button
              :label="__('Save Stages')"
              variant="solid"
              :disabled="!stagesDirty"
              :loading="savingStages"
              @click="saveStages"
            />
          </div>
        </div>

        <div
          class="grid grid-cols-[minmax(180px,1fr)_110px_120px_64px_108px] gap-3 px-3 py-2 text-p-sm font-medium text-ink-gray-5"
        >
          <div>{{ __('Stage') }}</div>
          <div :title="__('System meaning of this stage')">
            {{ __('Type') }}
          </div>
          <div :title="__('Forecast probability for deals in this stage')">
            {{ __('Probability') }}
          </div>
          <div class="text-center">{{ __('Color') }}</div>
          <div class="text-center">{{ __('Actions') }}</div>
        </div>
        <div class="h-px border-t border-outline-gray-modals" />

        <div>
          <div
            v-for="(stage, index) in stageDrafts"
            :key="stage.name || stage.local_id"
            class="grid grid-cols-[minmax(180px,1fr)_110px_120px_64px_108px] items-center gap-3 rounded px-3 py-2 hover:bg-surface-menu-bar"
            :class="stage.archived ? 'opacity-60' : ''"
          >
            <FormControl
              :model-value="displayStageName(stage.deal_status)"
              :placeholder="__('Stage name')"
              @update:model-value="
                (value) => (stage.deal_status = canonicalStageName(value))
              "
            />
            <FormControl
              v-model="stage.type"
              type="select"
              :options="typeOptions"
            />
            <FormControl v-model="stage.probability" type="number" />
            <Popover placement="bottom-start" class="flex justify-center">
              <template #target="{ isOpen, togglePopover }">
                <button
                  type="button"
                  class="flex size-8 items-center justify-center rounded bg-surface-gray-2 hover:bg-surface-gray-3"
                  :class="isOpen ? 'ring-2 ring-outline-gray-3' : ''"
                  :title="getColorLabel(stage.color)"
                  :aria-label="getColorLabel(stage.color)"
                  @click="togglePopover"
                >
                  <span
                    class="size-4 rounded-full border border-outline-gray-2"
                    :style="{ backgroundColor: getColorValue(stage.color) }"
                  />
                </button>
              </template>
              <template #body="{ togglePopover }">
                <div
                  class="my-1 rounded-lg bg-surface-modal p-2 shadow-2xl ring-1 ring-black ring-opacity-5"
                >
                  <div class="grid grid-cols-7 gap-1.5">
                    <button
                      v-for="option in colorOptions"
                      :key="option.value"
                      type="button"
                      class="size-5 rounded-full border transition"
                      :class="
                        stage.color === option.value
                          ? 'border-ink-gray-8 shadow-sm ring-2 ring-outline-gray-3'
                          : 'border-outline-gray-2 hover:border-ink-gray-5'
                      "
                      :style="{ backgroundColor: option.hex }"
                      :title="option.label"
                      :aria-label="option.label"
                      @click="selectColor(stage, option.value, togglePopover)"
                    />
                  </div>
                </div>
              </template>
            </Popover>
            <div class="flex justify-center gap-1">
              <Button
                icon="chevron-up"
                variant="ghost"
                :disabled="index === 0"
                @click="moveStage(index, -1)"
              />
              <Button
                icon="chevron-down"
                variant="ghost"
                :disabled="index === stageDrafts.length - 1"
                @click="moveStage(index, 1)"
              />
              <Dropdown
                :options="getStageActions(stage)"
                :button="{ icon: 'more-horizontal', variant: 'ghost' }"
              />
            </div>
          </div>
        </div>
      </section>
    </div>

    <ConfirmDialog
      v-model="confirmDialog.show"
      :title="confirmDialog.title"
      :message="confirmDialog.message"
      :onConfirm="confirmDialog.onConfirm"
      :onCancel="() => (confirmDialog.show = false)"
    />
  </div>
</template>

<script setup>
import { call, createResource, toast } from 'frappe-ui'
import {
  Badge,
  Button,
  ConfirmDialog,
  Dropdown,
  ErrorMessage,
  FormControl,
  LoadingIndicator,
  Popover,
  Switch,
} from 'frappe-ui'
import { computed, reactive, ref, watch } from 'vue'
import { statusesStore } from '@/stores/statuses'
import IconPicker from '@/components/IconPicker.vue'
import Autocomplete from '@/components/frappe-ui/Autocomplete.vue'

const colorOptions = [
  'black',
  'gray',
  'blue',
  'green',
  'red',
  'pink',
  'orange',
  'amber',
  'yellow',
  'cyan',
  'teal',
  'violet',
  'purple',
].map((color) => ({
  label: __(color),
  value: color,
  hex: getColorValue(color),
}))

const typeOptions = ['Open', 'Ongoing', 'On Hold', 'Won', 'Lost'].map(
  (type) => ({ label: __(type), value: type }),
)

const ruleOptions = ['Allow', 'Warn', 'Block'].map((mode) => ({
  label: __(mode),
  value: mode,
}))

const transitionRulesHelpText = __(
  'Transition rules control what happens when a deal changes stage. Allow lets the move happen, Warn saves the deal and shows a warning, Block prevents the move. Required fields for closing deals checks selected fields before moving a deal to Won or Lost.',
)

const standardPipelineNames = ['Default Deal Pipeline']
const standardStageNames = [
  'Qualification',
  'Demo/Making',
  'Proposal/Quotation',
  'Negotiation',
  'Ready to Close',
  'Won',
  'Lost',
]

const standardNameAliases = {
  'Воронка продаж по умолчанию': 'Default Deal Pipeline',
  'Воронка сделок по умолчанию': 'Default Deal Pipeline',
  Квалифицирована: 'Qualification',
  Квалификация: 'Qualification',
  'Демонстрация/подготовка': 'Demo/Making',
  'Коммерческое предложение': 'Proposal/Quotation',
  'Предложение/расчет': 'Proposal/Quotation',
  Переговоры: 'Negotiation',
  'Подготовка к закрытию': 'Ready to Close',
  'Готово к закрытию': 'Ready to Close',
  'Закрыта успешно': 'Won',
  Успешно: 'Won',
  Потеряна: 'Lost',
  Проиграно: 'Lost',
}

const showArchived = ref(false)
const selectedPipelineName = ref('')
const editorOpen = ref(false)
const draftingNewPipeline = ref(false)
const saving = ref(false)
const savingStages = ref(false)
const errorMessage = ref('')
const draft = reactive(getEmptyPipeline())
const stageDrafts = ref([])
const confirmDialog = ref({
  show: false,
  title: '',
  message: '',
  onConfirm: null,
})

const { dealStatuses } = statusesStore()

const settings = createResource({
  url: 'crm.api.sales_pipeline.get_pipeline_settings',
  makeParams() {
    return {
      show_archived: showArchived.value ? 1 : 0,
    }
  },
  auto: true,
  onSuccess() {
    if (editorOpen.value && selectedPipelineName.value) {
      syncDrafts()
    }
  },
})

const pipelines = computed(() => settings.data?.pipelines || [])
const stages = computed(() => settings.data?.stages || [])
const dealCounts = computed(() => settings.data?.deal_counts || {})
const activeDealCounts = computed(() => settings.data?.active_deal_counts || {})
const stageDealCounts = computed(() => settings.data?.stage_deal_counts || {})
const canForceArchivePipeline = computed(
  () => settings.data?.can_force_archive || false,
)
const ACTIVE_DEAL_STAGE_TYPES = new Set(['Open', 'Ongoing', 'On Hold'])

const dealFields = createResource({
  url: 'crm.api.doc.get_fields',
  cache: ['fields', 'CRM Deal', 'pipelineClosingRules'],
  params: {
    doctype: 'CRM Deal',
  },
  auto: true,
  transform: (data) => {
    return data.filter((field) => {
      return field.fieldname && !field.hidden && !field.read_only
    })
  },
})

const selectedPipeline = computed(() => getPipeline(selectedPipelineName.value))

const selectedStages = computed(() =>
  stages.value.filter((stage) => stage.pipeline === selectedPipelineName.value),
)

const requiredClosingFieldnames = computed(() =>
  parseRequiredClosingFields(draft.required_fields_before_closing),
)

const requiredClosingFields = computed(() => {
  return requiredClosingFieldnames.value.map((fieldname) => {
    const field = getDealField(fieldname)
    return {
      label: field?.label || fieldname,
      fieldname,
      fieldtype: field?.fieldtype || '',
    }
  })
})

const requiredClosingFieldOptions = computed(() => {
  const selected = new Set(requiredClosingFieldnames.value)
  return (dealFields.data || [])
    .filter((field) => !selected.has(field.fieldname))
    .map((field) => ({
      label: __(field.label || field.fieldname),
      value: field.fieldname,
      fieldname: field.fieldname,
      fieldtype: field.fieldtype,
    }))
})

const isDirty = computed(() => {
  if (draftingNewPipeline.value) return Boolean(draft.pipeline_name?.trim())
  if (!selectedPipeline.value) return false
  return (
    JSON.stringify(normalizePipeline(draft)) !==
    JSON.stringify(normalizePipeline(selectedPipeline.value))
  )
})

const stagesDirty = computed(() => {
  return (
    JSON.stringify(stageDrafts.value.map(normalizeStage)) !==
    JSON.stringify(selectedStages.value.map(normalizeStage))
  )
})

watch(showArchived, () => settings.reload())
watch(selectedPipelineName, syncDrafts)

function getPipeline(name) {
  return pipelines.value.find((pipeline) => pipeline.name === name)
}

function displayPipelineName(name) {
  return displayCanonicalName(name, standardPipelineNames)
}

function displayStageName(name) {
  return displayCanonicalName(name, standardStageNames)
}

function displayCanonicalName(name, canonicalNames) {
  if (!name) return ''
  const canonicalName = canonicalNameFromDisplay(name, canonicalNames)
  return canonicalNames.includes(canonicalName) ? __(canonicalName) : name
}

function canonicalPipelineName(value) {
  return canonicalNameFromDisplay(value, standardPipelineNames)
}

function canonicalStageName(value) {
  return canonicalNameFromDisplay(value, standardStageNames)
}

function canonicalNameFromDisplay(value, canonicalNames) {
  const normalizedValue = String(value || '').trim()
  return (
    standardNameAliases[normalizedValue] ||
    canonicalNames.find((name) => __(name) === normalizedValue) ||
    normalizedValue
  )
}

function pipelineRuleMode(pipeline, fieldname, legacyFieldname) {
  const mode = pipeline?.[fieldname]
  if (['Allow', 'Warn', 'Block'].includes(mode)) return mode
  return pipeline?.[legacyFieldname] ? 'Warn' : 'Allow'
}

function openEditor(name) {
  draftingNewPipeline.value = false
  selectedPipelineName.value = name
  editorOpen.value = true
  syncDrafts()
}

function goBack() {
  editorOpen.value = false
  draftingNewPipeline.value = false
  selectedPipelineName.value = ''
  errorMessage.value = ''
}

function syncDrafts() {
  errorMessage.value = ''
  if (draftingNewPipeline.value) return
  Object.assign(draft, getEmptyPipeline(), selectedPipeline.value || {})
  stageDrafts.value = selectedStages.value.map((stage) => ({ ...stage }))
}

function createPipeline() {
  editorOpen.value = true
  draftingNewPipeline.value = true
  selectedPipelineName.value = ''
  Object.assign(draft, getEmptyPipeline(), {
    pipeline_name: getUniquePipelineName(__('New Pipeline')),
    position: pipelines.value.length + 1,
  })
  stageDrafts.value = []
}

async function saveSelectedPipeline() {
  errorMessage.value = ''
  if (!draft.pipeline_name?.trim()) {
    errorMessage.value = __('Pipeline name is required')
    return
  }

  saving.value = true
  try {
    const saved = await call('crm.api.sales_pipeline.save_pipeline', {
      pipeline: normalizePipeline(draft),
    })
    draftingNewPipeline.value = false
    selectedPipelineName.value = saved.name
    await settings.reload()
    editorOpen.value = true
    toast.success(__('Pipeline saved successfully'))
  } catch (error) {
    showError(error, __('Failed to save pipeline'))
  } finally {
    saving.value = false
  }
}

async function duplicateSelectedPipeline() {
  if (!selectedPipeline.value) return

  saving.value = true
  try {
    const saved = await call('crm.api.sales_pipeline.duplicate_pipeline', {
      name: selectedPipeline.value.name,
      pipeline_name: getUniquePipelineName(
        `${selectedPipeline.value.pipeline_name} ${__('Copy')}`,
      ),
    })
    selectedPipelineName.value = saved.name
    await settings.reload()
    dealStatuses.reload()
    editorOpen.value = true
    toast.success(__('Pipeline duplicated successfully'))
  } catch (error) {
    showError(error, __('Failed to duplicate pipeline'))
  } finally {
    saving.value = false
  }
}

function openPipelineArchiveDialog(pipeline = selectedPipeline.value) {
  if (!pipeline) return

  const restoring = Boolean(pipeline.archived)
  const activeDeals = activeDealCounts.value[pipeline.name] || 0

  if (!restoring && activeDeals && !canForceArchivePipeline.value) {
    const message = __(
      'This pipeline has {0} active deals. Move them to Won/Lost stages or another pipeline before archiving.',
      [activeDeals],
    )
    errorMessage.value = message
    toast.error(message)
    return
  }

  confirmDialog.value = {
    show: true,
    title: restoring ? __('Restore Pipeline') : __('Archive Pipeline'),
    message: restoring
      ? __('This pipeline will appear in active pipeline lists again.')
      : activeDeals
        ? __(
            'This pipeline has {0} active deals. Force archive will hide the pipeline, but those deals will keep their current stages. Continue?',
            [activeDeals],
          )
        : __(
            'This pipeline will be hidden from active pipeline lists. Existing deals will stay in the system and will not be archived.',
          ),
    onConfirm: async () => {
      confirmDialog.value.show = false
      await togglePipelineArchive(pipeline, { force: Boolean(activeDeals) })
    },
  }
}

async function togglePipelineArchive(pipeline, options = {}) {
  if (!pipeline) return

  saving.value = true
  try {
    await call('crm.api.sales_pipeline.archive_pipeline', {
      name: pipeline.name,
      archived: pipeline.archived ? 0 : 1,
      force: options.force ? 1 : 0,
    })
    await settings.reload()
    if (!showArchived.value && pipeline.name === selectedPipelineName.value) {
      goBack()
    }
    toast.success(
      pipeline.archived
        ? __('Pipeline restored successfully')
        : __('Pipeline archived successfully'),
    )
  } catch (error) {
    showError(error, __('Failed to update pipeline'))
  } finally {
    saving.value = false
  }
}

function addStage() {
  if (!selectedPipelineName.value) return
  stageDrafts.value.push({
    local_id: `new-stage-${Date.now()}-${stageDrafts.value.length}`,
    deal_status: getUniqueStageName(__('New Stage')),
    pipeline: selectedPipelineName.value,
    type: 'Open',
    position: stageDrafts.value.length + 1,
    probability: 0,
    color: 'gray',
    archived: 0,
  })
}

function moveStage(index, direction) {
  const newIndex = index + direction
  if (newIndex < 0 || newIndex >= stageDrafts.value.length) return
  const drafts = [...stageDrafts.value]
  const [stage] = drafts.splice(index, 1)
  drafts.splice(newIndex, 0, stage)
  stageDrafts.value = drafts.map((stage, position) => ({
    ...stage,
    position: position + 1,
  }))
}

async function saveStages() {
  if (!selectedPipelineName.value) {
    await saveSelectedPipeline()
    if (!selectedPipelineName.value) return
  }

  savingStages.value = true
  try {
    const savedStages = []
    for (const [index, stage] of stageDrafts.value.entries()) {
      if (!stage.deal_status?.trim()) {
        throw new Error(__('Stage name is required'))
      }
      const savedStage = await call('crm.api.sales_pipeline.save_stage', {
        stage: normalizeStage({
          ...stage,
          pipeline: selectedPipelineName.value,
        }),
      })
      savedStages.push({ ...savedStage, _index: index })
    }

    const savedStageNames = savedStages.map((stage) => stage.name)
    if (savedStageNames.length) {
      await call('crm.api.sales_pipeline.reorder_stages', {
        pipeline: selectedPipelineName.value,
        names: savedStageNames,
      })
    }

    stageDrafts.value = stageDrafts.value.map((stage, index) => {
      const saved = savedStages.find((item) => item._index === index)
      if (!saved) return stage

      const cleanSavedStage = { ...saved }
      delete cleanSavedStage._index
      return {
        ...stage,
        ...cleanSavedStage,
      }
    })

    await settings.reload()
    dealStatuses.reload()
    toast.success(__('Stages saved successfully'))
  } catch (error) {
    showError(error, __('Failed to save stages'))
  } finally {
    savingStages.value = false
  }
}

function openStageArchiveDialog(stage) {
  if (!stage.name) {
    stageDrafts.value = stageDrafts.value.filter((row) => row !== stage)
    return
  }

  const restoring = Boolean(stage.archived)
  const isActiveType = ACTIVE_DEAL_STAGE_TYPES.has(stage.type)
  const activeDeals = isActiveType ? stageDealCounts.value[stage.name] || 0 : 0

  if (
    !restoring &&
    isActiveType &&
    activeDeals &&
    !canForceArchivePipeline.value
  ) {
    const message = __(
      'This stage has {0} active deals. Move them to Won/Lost stages or another stage before archiving.',
      [activeDeals],
    )
    errorMessage.value = message
    toast.error(message)
    return
  }

  confirmDialog.value = {
    show: true,
    title: restoring ? __('Restore Stage') : __('Archive Stage'),
    message: restoring
      ? __('This stage will appear in the pipeline kanban again.')
      : isActiveType && activeDeals
        ? __(
            'This stage has {0} active deals. Force archive will hide it from active kanban columns and status dropdowns. Existing deals will keep their current stage. Continue?',
            [activeDeals],
          )
        : __(
            'This stage will be hidden from active kanban columns and status dropdowns. Existing deals will stay in the system and keep their current stage.',
          ),
    onConfirm: async () => {
      confirmDialog.value.show = false
      await archiveStage(stage, {
        force: Boolean(
          !restoring &&
          isActiveType &&
          activeDeals &&
          canForceArchivePipeline.value,
        ),
      })
    },
  }
}

async function archiveStage(stage, options = {}) {
  savingStages.value = true
  try {
    await call('crm.api.sales_pipeline.archive_stage', {
      name: stage.name,
      archived: stage.archived ? 0 : 1,
      force: options.force ? 1 : 0,
    })
    await settings.reload()
    dealStatuses.reload()
    toast.success(
      stage.archived
        ? __('Stage restored successfully')
        : __('Stage archived successfully'),
    )
  } catch (error) {
    showError(error, __('Failed to update stage'))
  } finally {
    savingStages.value = false
  }
}

function getPipelineActions(pipeline) {
  return [
    {
      label: __('Duplicate'),
      icon: 'copy',
      onClick: () => {
        selectedPipelineName.value = pipeline.name
        duplicateSelectedPipeline()
      },
    },
    {
      label: pipeline.archived ? __('Restore') : __('Archive'),
      icon: pipeline.archived ? 'rotate-ccw' : 'archive',
      onClick: () => openPipelineArchiveDialog(pipeline),
    },
  ]
}

function getStageActions(stage) {
  return [
    {
      label: stage.archived ? __('Restore') : __('Archive'),
      icon: stage.archived ? 'rotate-ccw' : 'archive',
      onClick: () => openStageArchiveDialog(stage),
    },
  ]
}

function getStageCount(pipeline) {
  return stages.value.filter((stage) => stage.pipeline === pipeline).length
}

function getUniquePipelineName(base) {
  const names = new Set(
    pipelines.value.map((pipeline) => pipeline.pipeline_name),
  )
  if (!names.has(base)) return base

  let index = 2
  while (names.has(`${base} ${index}`)) {
    index += 1
  }
  return `${base} ${index}`
}

function getUniqueStageName(base) {
  const names = new Set(stageDrafts.value.map((stage) => stage.deal_status))
  if (!names.has(base)) return base

  let index = 2
  while (names.has(`${base} ${index}`)) {
    index += 1
  }
  return `${base} ${index}`
}

function normalizePipeline(pipeline) {
  const stageSkipRule = pipelineRuleMode(
    pipeline,
    'stage_skip_rule',
    'warn_on_stage_skip',
  )
  const stageBackwardsRule = pipelineRuleMode(
    pipeline,
    'stage_backwards_rule',
    'warn_on_stage_backwards',
  )
  const closingFieldsRule = pipelineRuleMode(
    pipeline,
    'closing_fields_rule',
    'warn_on_closing_without_required_fields',
  )

  return {
    name: pipeline.name,
    pipeline_name: canonicalPipelineName(pipeline.pipeline_name),
    enabled: pipeline.enabled ? 1 : 0,
    is_default: pipeline.is_default ? 1 : 0,
    position: Number(pipeline.position) || 0,
    color: pipeline.color || 'gray',
    icon: pipeline.icon || '',
    archived: pipeline.archived ? 1 : 0,
    description: pipeline.description || '',
    enable_kanban_freeze_effect:
      pipeline.enable_kanban_freeze_effect === undefined ||
      pipeline.enable_kanban_freeze_effect
        ? 1
        : 0,
    stage_skip_rule: stageSkipRule,
    stage_backwards_rule: stageBackwardsRule,
    closing_fields_rule: closingFieldsRule,
    warn_on_stage_skip: stageSkipRule !== 'Allow' ? 1 : 0,
    warn_on_stage_backwards: stageBackwardsRule !== 'Allow' ? 1 : 0,
    warn_on_closing_without_required_fields:
      closingFieldsRule !== 'Allow' ? 1 : 0,
    required_fields_before_closing:
      pipeline.required_fields_before_closing || '',
  }
}

function normalizeStage(stage) {
  return {
    name: stage.name,
    deal_status: canonicalStageName(stage.deal_status),
    pipeline: stage.pipeline,
    type: stage.type || 'Open',
    position: Number(stage.position) || 0,
    probability: Number(stage.probability) || 0,
    color: stage.color || 'gray',
    archived: stage.archived ? 1 : 0,
  }
}

function parseRequiredClosingFields(value) {
  const fieldnames = []
  for (const row of String(value || '')
    .replaceAll(',', '\n')
    .split('\n')) {
    const fieldname = row.trim()
    if (fieldname && !fieldnames.includes(fieldname)) {
      fieldnames.push(fieldname)
    }
  }
  return fieldnames
}

function setRequiredClosingFields(fieldnames) {
  draft.required_fields_before_closing = fieldnames.join(', ')
}

function addRequiredClosingField(option) {
  const fieldname = option?.fieldname || option?.value
  if (!fieldname) return

  const fieldnames = requiredClosingFieldnames.value
  if (!fieldnames.includes(fieldname)) {
    setRequiredClosingFields([...fieldnames, fieldname])
  }
}

function removeRequiredClosingField(fieldname) {
  setRequiredClosingFields(
    requiredClosingFieldnames.value.filter((name) => name !== fieldname),
  )
}

function getDealField(fieldname) {
  return (dealFields.data || []).find((field) => field.fieldname === fieldname)
}

function getEmptyPipeline() {
  return {
    name: '',
    pipeline_name: '',
    enabled: 1,
    is_default: 0,
    position: 1,
    color: 'gray',
    icon: '',
    archived: 0,
    description: '',
    enable_kanban_freeze_effect: 1,
    stage_skip_rule: 'Allow',
    stage_backwards_rule: 'Allow',
    closing_fields_rule: 'Allow',
    warn_on_stage_skip: 0,
    warn_on_stage_backwards: 0,
    warn_on_closing_without_required_fields: 0,
    required_fields_before_closing: '',
  }
}

function selectColor(record, color, close) {
  record.color = color
  close?.()
}

function getColorLabel(color) {
  return colorOptions.find((option) => option.value === color)?.label || color
}

function getColorValue(color) {
  const colors = {
    black: '#171717',
    gray: '#6b7280',
    blue: '#3b82f6',
    green: '#22c55e',
    red: '#ef4444',
    pink: '#ec4899',
    orange: '#f97316',
    amber: '#f59e0b',
    yellow: '#eab308',
    cyan: '#06b6d4',
    teal: '#14b8a6',
    violet: '#8b5cf6',
    purple: '#a855f7',
  }
  return colors[color] || colors.gray
}

function showError(error, fallback) {
  const message = __(error?.messages?.[0] || error?.message || fallback)
  errorMessage.value = message
  toast.error(message)
}
</script>
