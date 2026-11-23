/** Keep list data scoped to the page context, including the selected pipeline. */
export function viewCacheKey(doctype, viewName, viewType, filters = {}) {
  return [doctype, viewName, viewType, filters]
}

/** An explicit pipeline selection wins over the pipeline stored in a saved view. */
export function viewFilters(doctype, savedFilters = {}, defaults = {}) {
  const filters = { ...savedFilters }
  if (doctype === 'CRM Deal' && defaults.pipeline) {
    filters.pipeline = defaults.pipeline
  }
  return filters
}
