import { defineStore } from 'pinia'
import { createResource } from 'frappe-ui'
import { reactive } from 'vue'

export const enrichmentStore = defineStore('crm-enrichment', () => {
  // A record page is remounted when its tab changes. Keep queued runs here so
  // the new button can resume waiting for the same background job.
  const pending = reactive({})
  const settings = createResource({
    url: 'crm.domain_enrichment.api.get_settings_flags',
    cache: 'enrichment-settings',
    auto: true,
  })

  function isEnabled(doctype) {
    return Boolean(settings.data?.enabled && settings.data?.doctypes?.[doctype])
  }

  return { settings, isEnabled, pending }
})
