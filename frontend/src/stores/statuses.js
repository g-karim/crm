import IndicatorIcon from '@/components/Icons/IndicatorIcon.vue'
import { parseColor, isTranslatable } from '@/utils'
import { defineStore } from 'pinia'
import { useTelemetry } from 'frappe-ui/frappe'
import { createResource } from 'frappe-ui'
import { reactive, h } from 'vue'

export const statusesStore = defineStore('crm-statuses', () => {
  let leadStatusesByName = reactive({})
  let dealStatusesByName = reactive({})
  let communicationStatusesByName = reactive({})

  const { capture } = useTelemetry()

  const leadStatuses = createResource({
    url: 'crm.api.statuses.get_lead_statuses',
    cache: 'lead-statuses-v2',
    initialData: [],
    auto: true,
    transform(statuses) {
      return setStatusesByName(leadStatusesByName, statuses)
    },
  })

  const dealStatuses = createResource({
    url: 'crm.api.statuses.get_deal_statuses',
    cache: 'deal-statuses-v3',
    initialData: [],
    auto: true,
    transform(statuses) {
      return setStatusesByName(dealStatusesByName, statuses)
    },
  })

  const communicationStatuses = createResource({
    url: 'crm.api.statuses.get_communication_statuses',
    cache: 'communication-statuses-v2',
    initialData: [],
    auto: true,
    transform(statuses) {
      return setStatusesByName(communicationStatusesByName, statuses, false)
    },
  })

  function setStatusesByName(
    statusesByName,
    statuses,
    parseStatusColor = true,
  ) {
    Object.keys(statusesByName).forEach((name) => {
      delete statusesByName[name]
    })

    for (let status of statuses) {
      if (parseStatusColor) {
        status.color = parseColor(status.color)
      }
      statusesByName[status.name] = status
    }
    return statuses
  }

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
