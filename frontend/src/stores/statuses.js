import IndicatorIcon from '@/components/Icons/IndicatorIcon.vue'
import { parseColor, isTranslatable } from '@/utils'
import { defineStore } from 'pinia'
import { useTelemetry } from 'frappe-ui/frappe'
import { createListResource } from 'frappe-ui'
import { reactive, h } from 'vue'

export const statusesStore = defineStore('crm-statuses', () => {
  let leadStatusesByName = reactive({})
  let dealStatusesByName = reactive({})
  let communicationStatusesByName = reactive({})

  const { capture } = useTelemetry()

  const leadStatuses = createListResource({
    doctype: 'CRM Lead Status',
    fields: ['name', 'color', 'position', 'type'],
    orderBy: 'position asc',
    cache: 'lead-statuses',
    initialData: [],
    auto: true,
    transform(statuses) {
      for (let status of statuses) {
        status.color = parseColor(status.color)
        leadStatusesByName[status.name] = status
      }
      return statuses
    },
  })

  const dealStatuses = createListResource({
    doctype: 'CRM Deal Status',
    fields: [
      'name',
      'deal_status',
      'pipeline',
      'color',
      'position',
      'type',
      'archived',
    ],
    orderBy: 'position asc',
    cache: 'deal-statuses-v2',
    initialData: [],
    auto: true,
    transform(statuses) {
      for (let status of statuses) {
        status.color = parseColor(status.color)
        dealStatusesByName[status.name] = status
      }
      return statuses
    },
  })

  const communicationStatuses = createListResource({
    doctype: 'CRM Communication Status',
    fields: ['name'],
    cache: 'communication-statuses',
    initialData: [],
    auto: true,
    transform(statuses) {
      for (let status of statuses) {
        communicationStatusesByName[status.name] = status
      }
      return statuses
    },
  })

  function getLeadStatus(name) {
    if (!name) {
      name = leadStatuses.data?.[0]?.name
    }
    if (!name) return null
    return leadStatusesByName[name]
  }

  function getDealStatus(name) {
    if (!name) {
      name = dealStatuses.data?.[0]?.name
    }
    if (!name) return null
    return dealStatusesByName[name]
  }

  function getCommunicationStatus(name) {
    if (!name) {
      name = communicationStatuses.data?.[0]?.name
    }
    if (!name) return null
    return communicationStatusesByName[name]
  }

  function statusOptions(
    doctype,
    statuses = [],
    triggerStatusChange = null,
    filters = {},
  ) {
    let statusesByName =
      doctype == 'deal' ? dealStatusesByName : leadStatusesByName

    if (statuses?.length) {
      statusesByName = statuses.reduce((acc, status) => {
        acc[status] = statusesByName[status]
        return acc
      }, {})
    }

    if (doctype == 'deal' && filters.pipeline) {
      statusesByName = Object.keys(statusesByName).reduce((acc, status) => {
        if (
          statusesByName[status]?.pipeline === filters.pipeline &&
          !statusesByName[status]?.archived
        ) {
          acc[status] = statusesByName[status]
        }
        return acc
      }, {})
    }

    let translatable = isTranslatable(
      doctype == 'deal' ? 'CRM Deal Status' : 'CRM Lead Status',
    )

    let options = []
    for (const status in statusesByName) {
      options.push({
        label: translatable
          ? __(
              statusesByName[status]?.deal_status ||
                statusesByName[status]?.name,
            )
          : statusesByName[status]?.deal_status || statusesByName[status]?.name,
        value: statusesByName[status]?.name,
        icon: () => h(IndicatorIcon, { class: statusesByName[status]?.color }),
        onClick: async () => {
          await triggerStatusChange?.(statusesByName[status]?.name)
          capture('status_changed', { doctype, status })
        },
      })
    }
    return options
  }

  return {
    leadStatuses,
    dealStatuses,
    communicationStatuses,
    getLeadStatus,
    getDealStatus,
    getCommunicationStatus,
    statusOptions,
  }
})
