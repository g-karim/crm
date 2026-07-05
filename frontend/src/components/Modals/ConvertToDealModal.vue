<template>
  <Dialog v-model="show" :options="{ size: 'xl' }">
    <template #body-header>
      <div class="mb-6 flex items-center justify-between">
        <div>
          <h3 class="text-2xl font-semibold leading-6 text-ink-gray-9">
            {{ __('Convert to Deal') }}
          </h3>
        </div>
        <div class="flex items-center gap-1">
          <Button
            v-if="isManager() && !isMobileView"
            variant="ghost"
            :tooltip="__('Edit deal\'s mandatory fields layout')"
            :icon="EditIcon"
            @click="openQuickEntryModal"
          />
          <Button icon="x" variant="ghost" @click="show = false" />
        </div>
      </div>
    </template>
    <template #body-content>
      <div class="mb-4 flex items-center gap-2 text-ink-gray-5">
        <OrganizationsIcon class="h-4 w-4" />
        <label class="block text-base">{{ __('Organization') }}</label>
      </div>
      <div class="ml-6 text-ink-gray-9">
        <div class="flex items-center justify-between text-base">
          <div>{{ __('Choose Existing') }}</div>
          <Switch v-model="existingOrganizationChecked" />
        </div>
        <Link
          v-if="existingOrganizationChecked"
          class="form-control mt-2.5"
          size="md"
          :value="existingOrganization"
          doctype="CRM Organization"
          @change="(data) => (existingOrganization = data)"
        />
        <div v-else class="mt-2.5 text-base">
          {{
            __(
              'New organization will be created based on the data in details section',
            )
          }}
        </div>
      </div>

      <div class="mb-4 mt-6 flex items-center gap-2 text-ink-gray-5">
        <ContactsIcon class="h-4 w-4" />
        <label class="block text-base">{{ __('Contact') }}</label>
      </div>
      <div class="ml-6 text-ink-gray-9">
        <div class="flex items-center justify-between text-base">
          <div>{{ __('Choose Existing') }}</div>
          <Switch v-model="existingContactChecked" />
        </div>
        <Link
          v-if="existingContactChecked"
          class="form-control mt-2.5"
          size="md"
          :value="existingContact"
          doctype="Contact"
          @change="(data) => (existingContact = data)"
        />
        <div v-else class="mt-2.5 text-base">
          {{ __("New contact will be created based on the person's details") }}
        </div>
      </div>

      <div v-if="dealTabs.data?.length" class="h-px w-full border-t my-6" />

      <FieldLayout
        v-if="dealTabs.data?.length"
        :tabs="dealTabs.data"
        :data="deal.doc"
        doctype="CRM Deal"
      />
      <ErrorMessage class="mt-4" :message="error" />
    </template>
    <template #actions>
      <div class="flex justify-end">
        <Button :label="__('Convert')" variant="solid" @click="convertToDeal" />
      </div>
    </template>
  </Dialog>
</template>
<script setup>
import OrganizationsIcon from '@/components/Icons/OrganizationsIcon.vue'
import ContactsIcon from '@/components/Icons/ContactsIcon.vue'
import EditIcon from '@/components/Icons/EditIcon.vue'
import FieldLayout from '@/components/FieldLayout/FieldLayout.vue'
import Link from '@/components/Controls/Link.vue'
import { useDocument } from '@/data/document'
import { usersStore } from '@/stores/users'
import { sessionStore } from '@/stores/session'
import { statusesStore } from '@/stores/statuses'
import { showQuickEntryModal, quickEntryProps } from '@/composables/modals'
import { isMobileView } from '@/composables/settings'
import { useOnboarding, useTelemetry } from 'frappe-ui/frappe'
import {
  Switch,
  Dialog,
  createListResource,
  createResource,
  call,
} from 'frappe-ui'
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'

const props = defineProps({
  lead: { type: Object, required: true },
})

const show = defineModel({ type: Boolean })

const router = useRouter()

const { statusOptions, getDealStatus } = statusesStore()
const { isManager } = usersStore()
const { user } = sessionStore()
const { updateOnboardingStep } = useOnboarding('frappecrm')

const existingContactChecked = ref(false)
const existingOrganizationChecked = ref(false)

const existingContact = ref('')
const existingOrganization = ref('')
const error = ref('')
const { capture } = useTelemetry()

const { triggerConvertToDeal } = useDocument('CRM Lead', props.lead.name)
const { document: deal } = useDocument('CRM Deal')

const salesPipelines = createListResource({
  doctype: 'CRM Sales Pipeline',
  fields: ['name', 'pipeline_name', 'is_default', 'position'],
  filters: { enabled: 1, archived: 0 },
  orderBy: 'position asc, modified asc',
  cache: 'crm-sales-pipelines',
  initialData: [],
  auto: true,
})

const defaultPipeline = computed(() => {
  let pipelines = salesPipelines.data || []
  return (
    props.lead.planned_deal_pipeline ||
    pipelines.find((pipeline) => pipeline.is_default)?.name ||
    pipelines[0]?.name
  )
})

async function convertToDeal() {
  error.value = ''

  if (existingContactChecked.value && !existingContact.value) {
    error.value = __('Please select an existing contact')
    return
  }

  if (existingOrganizationChecked.value && !existingOrganization.value) {
    error.value = __('Please select an existing organization')
    return
  }

  if (!existingContactChecked.value && existingContact.value) {
    existingContact.value = ''
  }

  if (!existingOrganizationChecked.value && existingOrganization.value) {
    existingOrganization.value = ''
  }

  await triggerConvertToDeal?.(props.lead, deal.doc, () => (show.value = false))

  let _deal = await call('crm.fcrm.doctype.crm_lead.crm_lead.convert_to_deal', {
    lead: props.lead.name,
    deal: deal.doc,
    existing_contact: existingContact.value,
    existing_organization: existingOrganization.value,
  }).catch((err) => {
    if (err.exc_type == 'MandatoryError') {
      const errorMessage = err.messages
        .map((msg) => {
          let arr = msg.split(': ')
          return arr[arr.length - 1].trim()
        })
        .join(', ')

      if (errorMessage.toLowerCase().includes('required')) {
        error.value = __(errorMessage)
      } else {
        error.value = __('{0} is required', [errorMessage])
      }
      return
    }
    error.value = __('Error converting to deal: {0}', [err.messages?.[0]])
  })
  if (_deal) {
    show.value = false
    existingContactChecked.value = false
    existingOrganizationChecked.value = false
    existingContact.value = ''
    existingOrganization.value = ''
    error.value = ''
    updateOnboardingStep('convert_lead_to_deal', true, false, () => {
      localStorage.setItem('firstDeal' + user, _deal)
    })
    capture('convert_lead_to_deal')
    router.push({ name: 'Deal', params: { dealId: _deal } })
  }
}

const dealStatuses = computed(() =>
  statusOptions('deal', [], null, { pipeline: deal.doc.pipeline }),
)

watch(dealStatuses, () => {
  updateDealStatusFields()
  if (!deal.doc.status && dealStatuses.value[0]?.value) {
    deal.doc.status = dealStatuses.value[0].value
  }
})

watch(defaultPipeline, (pipeline) => {
  if (!deal.doc.pipeline && pipeline) {
    deal.doc.pipeline = pipeline
  }
})

watch(
  () => deal.doc.pipeline,
  (pipeline, oldPipeline) => {
    if (!pipeline || pipeline === oldPipeline) return
    let currentStatus = getDealStatus(deal.doc.status)
    if (currentStatus?.pipeline !== pipeline) {
      deal.doc.status = dealStatuses.value[0]?.value || ''
    }
  },
)

const dealTabs = createResource({
  url: 'crm.fcrm.doctype.crm_fields_layout.crm_fields_layout.get_fields_layout',
  cache: ['RequiredFields', 'CRM Deal'],
  params: { doctype: 'CRM Deal', type: 'Required Fields' },
  auto: true,
  transform: (_tabs) => {
    let hasFields = false
    ensureDealPipelineField(_tabs)
    let parsedTabs = _tabs?.forEach((tab) => {
      tab.sections?.forEach((section) => {
        section.columns?.forEach((column) => {
          column.fields?.forEach((field) => {
            hasFields = true
            prepareDealField(field)

            if (field.fieldtype === 'Table') {
              deal.doc[field.fieldname] = []
            }
          })
        })
      })
    })
    return hasFields ? parsedTabs : []
  },
})

function prepareDealField(field) {
  if (field.fieldname == 'pipeline') {
    field.disable_create = true
  }

  if (field.fieldname == 'status') {
    field.fieldtype = 'Select'
    field.options = dealStatuses.value
    field.prefix = getDealStatus(deal.doc.status)?.color
  }
}

function updateDealStatusFields() {
  dealTabs.data?.forEach((tab) => {
    tab.sections?.forEach((section) => {
      section.columns?.forEach((column) => {
        column.fields?.forEach((field) => prepareDealField(field))
      })
    })
  })
}

function ensureDealPipelineField(_tabs) {
  let hasPipelineField = _tabs.some((tab) =>
    tab.sections?.some((section) =>
      section.columns?.some((column) =>
        column.fields?.some((field) => field.fieldname === 'pipeline'),
      ),
    ),
  )
  if (hasPipelineField) return

  let section = _tabs.at(-1)?.sections?.at(-1)
  let column = section?.columns?.[0]
  if (!column) return

  column.fields.unshift({
    fieldname: 'pipeline',
    fieldtype: 'Link',
    label: __('Sales Pipeline'),
    options: 'CRM Sales Pipeline',
    reqd: 1,
    disable_create: true,
  })
}

onMounted(() => {
  if (defaultPipeline.value) {
    deal.doc.pipeline = defaultPipeline.value
  }
  if (!deal.doc.status && dealStatuses.value[0]?.value) {
    deal.doc.status = dealStatuses.value[0].value
  }
})

function openQuickEntryModal() {
  showQuickEntryModal.value = true
  quickEntryProps.value = {
    doctype: 'CRM Deal',
    onlyRequired: true,
  }
  show.value = false
}
</script>
