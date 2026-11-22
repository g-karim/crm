// frappe-ui loads its remote Pulse module even when enabled=false. Gate plugin
// installation first so an opt-out also prevents downloading the remote code.
export async function initializeTelemetry(app, plugin, fetchConfig) {
  let config
  try {
    config = await fetchConfig()
  } catch {
    return false
  }
  if (
    config?.enabled !== true ||
    typeof config.host !== 'string' ||
    !config.host ||
    typeof config.key !== 'string' ||
    !config.key
  ) {
    return false
  }

  app.use(plugin, {
    app_name: 'crm',
    enabled: true,
    host: config.host,
    apiKey: config.key,
    site: config.site,
    clientUrl: config.client_url,
    getContext: () => ({ user: config.user, team: config.team }),
  })
  return true
}
