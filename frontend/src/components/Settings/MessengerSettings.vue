<template>
  <SettingsLayoutBase
    :title="__('Каналы сообщений')"
    :description="
      __(
        'Подключайте Telegram, VK, MAX, Avito и Wazzup и отвечайте клиентам из карточки лида.',
      )
    "
  >
    <template #header-actions>
      <div class="flex items-center gap-2">
        <Button
          :label="__('Сохранить настройки')"
          variant="subtle"
          :disabled="!settingsDirty"
          :loading="savingSettings"
          @click="saveGlobalSettings"
        />
        <Button
          :label="__('Новый канал')"
          icon-left="lucide-plus"
          variant="solid"
          @click="openNewChannel"
        />
      </div>
    </template>

    <template #content>
      <div v-if="loading" class="flex h-full items-center justify-center">
        <LoadingIndicator class="size-6" />
      </div>

      <div v-else class="flex max-w-5xl flex-col gap-7">
        <section
          class="rounded-lg border border-outline-gray-1 bg-surface-cards"
        >
          <div class="flex items-center justify-between gap-6 p-4">
            <div>
              <div class="text-base-medium text-ink-gray-8">
                {{ __('Включить Messenger') }}
              </div>
              <div class="mt-1 text-p-sm text-ink-gray-5">
                {{
                  __(
                    'Главный переключатель приёма и отправки сообщений через подключённые каналы.',
                  )
                }}
              </div>
            </div>
            <Switch v-model="settings.enabled" size="sm" />
          </div>
          <div class="border-t border-outline-gray-1" />
          <div class="flex items-center justify-between gap-6 p-4">
            <div>
              <div class="text-base-medium text-ink-gray-8">
                {{ __('Создавать лиды из новых диалогов') }}
              </div>
              <div class="mt-1 text-p-sm text-ink-gray-5">
                {{
                  __(
                    'Если входящий диалог ещё не связан с CRM, Messenger создаст новый лид.',
                  )
                }}
              </div>
            </div>
            <Switch v-model="settings.auto_create_lead" size="sm" />
          </div>
          <div class="border-t border-outline-gray-1" />
          <div class="flex items-center justify-between gap-6 p-4">
            <div>
              <div class="text-base-medium text-ink-gray-8">
                {{ __('Хранить сырые webhook-события') }}
              </div>
              <div class="mt-1 text-p-sm text-ink-gray-5">
                {{
                  __(
                    'Нужно только для диагностики. В рабочем режиме рекомендуется оставить выключенным.',
                  )
                }}
              </div>
            </div>
            <Switch v-model="settings.log_raw_webhooks" size="sm" />
          </div>
        </section>

        <section>
          <button
            class="flex items-center gap-2 text-base-medium text-ink-gray-7"
            type="button"
            @click="showAdvanced = !showAdvanced"
          >
            <FeatherIcon
              name="chevron-right"
              class="size-4 transition-transform"
              :class="showAdvanced && 'rotate-90'"
            />
            {{ __('Webhook и Avito OAuth') }}
          </button>
          <div
            v-if="showAdvanced"
            class="mt-3 grid grid-cols-1 gap-4 rounded-lg border border-outline-gray-1 p-4 md:grid-cols-2"
          >
            <FormControl
              v-model="settings.webhook_secret"
              type="password"
              :label="__('Общий Webhook Secret')"
              :placeholder="
                secretPlaceholder(settings.webhook_secret_configured)
              "
              :description="
                __('Оставьте пустым, чтобы сохранить текущий секрет.')
              "
            />
            <FormControl
              v-model="settings.oauth_site_url"
              type="text"
              label="OAuth Site URL"
              placeholder="https://crm.example.com"
            />
            <FormControl
              v-model="settings.avito_oauth_broker_url"
              type="text"
              label="Avito OAuth Broker URL"
              placeholder="https://broker.example.com"
            />
            <FormControl
              v-model="settings.avito_oauth_broker_secret"
              type="password"
              label="Avito OAuth Broker Secret"
              :placeholder="
                secretPlaceholder(settings.avito_oauth_broker_secret_configured)
              "
              :description="
                __('Оставьте пустым, чтобы сохранить текущий секрет.')
              "
            />
          </div>
        </section>

        <section class="min-h-0">
          <div class="mb-3 flex items-end justify-between">
            <div>
              <h3 class="text-lg-semibold text-ink-gray-8">
                {{ __('Подключённые каналы') }}
              </h3>
              <p class="mt-1 text-p-sm text-ink-gray-5">
                {{
                  __(
                    'Один канал соответствует одному аккаунту, сообществу или боту.',
                  )
                }}
              </p>
            </div>
            <Button
              icon="lucide-refresh-cw"
              variant="ghost"
              :loading="refreshing"
              @click="loadSettings(true, true)"
            />
          </div>

          <div
            v-if="!channels.length"
            class="flex flex-col items-center rounded-lg border border-dashed border-outline-gray-2 px-6 py-12 text-center"
          >
            <div
              class="flex size-10 items-center justify-center rounded-full bg-surface-gray-2"
            >
              <FeatherIcon
                name="message-circle"
                class="size-5 text-ink-gray-5"
              />
            </div>
            <div class="mt-3 text-base-medium text-ink-gray-7">
              {{ __('Каналов пока нет') }}
            </div>
            <div class="mt-1 max-w-md text-p-sm text-ink-gray-5">
              {{
                __(
                  'Создайте канал, сохраните токен и завершите подключение к провайдеру.',
                )
              }}
            </div>
            <Button
              class="mt-4"
              :label="__('Создать канал')"
              variant="solid"
              @click="openNewChannel"
            />
          </div>

          <div
            v-else
            class="overflow-hidden rounded-lg border border-outline-gray-1"
          >
            <button
              v-for="(channel, index) in channels"
              :key="channel.name"
              type="button"
              class="flex w-full items-center gap-4 px-4 py-3 text-left hover:bg-surface-gray-1"
              :class="index && 'border-t border-outline-gray-1'"
              @click="openChannel(channel)"
            >
              <div
                class="flex size-9 shrink-0 items-center justify-center rounded-lg bg-surface-gray-2 text-sm-medium text-ink-gray-7"
              >
                {{ providerInitial(channel.provider) }}
              </div>
              <div class="min-w-0 flex-1">
                <div class="truncate text-base-medium text-ink-gray-8">
                  {{ channelTitle(channel) }}
                </div>
                <div class="mt-0.5 truncate text-p-sm text-ink-gray-5">
                  {{ providerDescription(channel) }}
                </div>
              </div>
              <Badge
                :label="__(messengerChannelState(channel).label)"
                :theme="messengerChannelState(channel).theme"
                variant="outline"
                size="md"
              />
              <FeatherIcon
                name="chevron-right"
                class="size-4 text-ink-gray-4"
              />
            </button>
          </div>
        </section>
      </div>
    </template>
  </SettingsLayoutBase>

  <Dialog
    v-model:open="showChannelDialog"
    :options="{
      title: channelDraft.channel ? __('Настройка канала') : __('Новый канал'),
    }"
    size="xl"
  >
    <template #body-content>
      <div class="flex max-h-[65vh] flex-col gap-4 overflow-y-auto pr-1">
        <div
          v-if="channelDraft.channel"
          class="flex items-center justify-between rounded-lg bg-surface-gray-1 px-3 py-2"
        >
          <div>
            <div class="text-base-medium text-ink-gray-8">
              {{ channelTitle(channelDraft) }}
            </div>
            <div class="text-p-sm text-ink-gray-5">
              {{ messengerProviderLabel(channelDraft.provider) }}
            </div>
          </div>
          <Badge
            :label="__(messengerChannelState(channelDraft).label)"
            :theme="messengerChannelState(channelDraft).theme"
            variant="outline"
          />
        </div>

        <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
          <FormControl
            :model-value="channelDraft.provider"
            type="select"
            required
            :disabled="Boolean(channelDraft.channel)"
            :options="MESSENGER_PROVIDER_OPTIONS"
            :label="__('Провайдер')"
            @update:modelValue="changeProvider"
          />
          <FormControl
            v-model="channelDraft.custom_display_name"
            type="text"
            :label="__('Название канала')"
            :placeholder="__('Например, Отдел продаж')"
          />

          <FormControl
            v-if="channelDraft.provider === 'wazzup'"
            v-model="channelDraft.platform"
            type="select"
            required
            :options="wazzupPlatforms"
            :label="__('Платформа')"
          />
          <FormControl
            v-if="channelDraft.provider === 'wazzup'"
            v-model="channelDraft.provider_channel_id"
            type="text"
            required
            :label="__('ID канала Wazzup')"
            placeholder="channelId / plainId"
          />

          <FormControl
            v-if="channelDraft.provider === 'vk_direct'"
            v-model="channelDraft.external_account_id"
            type="text"
            required
            :label="__('Сообщество VK')"
            :placeholder="__('ID или короткое имя сообщества')"
          />

          <FormControl
            v-if="channelDraft.provider === 'avito_direct'"
            v-model="channelDraft.auth_type"
            type="select"
            :options="avitoAuthTypes"
            :label="__('Способ подключения Avito')"
          />
          <FormControl
            v-if="
              channelDraft.provider === 'avito_direct' &&
              channelDraft.auth_type !== 'authorization_code'
            "
            v-model="channelDraft.external_account_id"
            type="text"
            required
            label="Avito Account ID"
          />
          <FormControl
            v-if="
              channelDraft.provider === 'avito_direct' &&
              channelDraft.auth_type === 'client_credentials'
            "
            v-model="channelDraft.client_id"
            type="text"
            required
            label="Client ID"
          />

          <FormControl
            v-if="showsApiToken"
            v-model="channelDraft.api_token"
            type="password"
            :required="!channelDraft.api_token_configured"
            :label="apiTokenLabel"
            :placeholder="secretPlaceholder(channelDraft.api_token_configured)"
            :description="__('Оставьте пустым, чтобы сохранить текущий токен.')"
          />
          <FormControl
            v-if="
              channelDraft.provider === 'avito_direct' &&
              channelDraft.auth_type === 'client_credentials'
            "
            v-model="channelDraft.client_secret"
            type="password"
            :required="!channelDraft.client_secret_configured"
            label="Client Secret"
            :placeholder="
              secretPlaceholder(channelDraft.client_secret_configured)
            "
            :description="
              __('Оставьте пустым, чтобы сохранить текущий секрет.')
            "
          />
        </div>

        <div
          v-if="isDirectMessengerProvider(channelDraft.provider)"
          class="rounded-lg bg-surface-blue-1 px-3 py-2 text-p-sm text-ink-blue-3"
        >
          {{
            __(
              'Для подключения webhook CRM должна быть доступна провайдеру по публичному HTTPS-адресу.',
            )
          }}
        </div>

        <div
          v-if="channelDraft.auth_error"
          class="rounded-lg bg-surface-red-1 px-3 py-2 text-p-sm text-ink-red-3"
        >
          {{ channelDraft.auth_error }}
        </div>

        <div
          v-if="channelDraft.channel && hasConnectionActions"
          class="flex flex-wrap gap-2 border-t border-outline-gray-1 pt-4"
        >
          <Button
            v-if="isDirectMessengerProvider(channelDraft.provider)"
            :label="__('Проверить')"
            variant="subtle"
            :loading="channelAction === 'test'"
            @click="runChannelAction('test')"
          />
          <Button
            v-if="isDirectMessengerProvider(channelDraft.provider)"
            :label="__('Подключить / исправить')"
            variant="solid"
            :loading="channelAction === 'connect'"
            @click="runChannelAction('connect')"
          />
          <Button
            v-if="isDirectMessengerProvider(channelDraft.provider)"
            :label="__('Обновить статус')"
            variant="subtle"
            :loading="channelAction === 'status'"
            @click="runChannelAction('status')"
          />
          <Button
            v-if="
              channelDraft.provider === 'avito_direct' &&
              channelDraft.auth_type === 'authorization_code'
            "
            :label="__('Подключить Avito')"
            variant="solid"
            :loading="channelAction === 'avito-oauth'"
            @click="runChannelAction('avito-oauth')"
          />
          <Button
            v-if="
              channelDraft.provider === 'avito_direct' &&
              channelDraft.auth_type !== 'authorization_code'
            "
            :label="__('Зарегистрировать webhook')"
            variant="subtle"
            :loading="channelAction === 'avito-webhook'"
            @click="runChannelAction('avito-webhook')"
          />
          <Button
            v-if="
              isDirectMessengerProvider(channelDraft.provider) &&
              channelDraft.enabled
            "
            :label="__('Отключить')"
            variant="subtle"
            theme="red"
            :loading="channelAction === 'disconnect'"
            @click="runChannelAction('disconnect')"
          />
        </div>

        <ErrorMessage v-if="channelError" :message="channelError" />
      </div>
    </template>
    <template #actions>
      <div class="flex w-full justify-end gap-2">
        <Button
          :label="__('Закрыть')"
          variant="subtle"
          @click="showChannelDialog = false"
        />
        <Button
          :label="channelDraft.channel ? __('Сохранить') : __('Создать канал')"
          variant="solid"
          :loading="savingChannel"
          @click="saveChannel"
        />
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import SettingsLayoutBase from '@/components/Layouts/SettingsLayoutBase.vue'
import {
  MESSENGER_PROVIDER_OPTIONS,
  applyMessengerProviderDefaults,
  buildMessengerChannelPayload,
  isDirectMessengerProvider,
  makeMessengerChannelDraft,
  messengerChannelState,
  messengerProviderLabel,
  validateMessengerChannelDraft,
} from '@/utils/messengerSettings'
import {
  Badge,
  Button,
  Dialog,
  ErrorMessage,
  FeatherIcon,
  FormControl,
  LoadingIndicator,
  Switch,
  call,
  toast,
} from 'frappe-ui'
import { computed, onMounted, reactive, ref } from 'vue'

const defaultSettings = () => ({
  enabled: false,
  auto_create_lead: false,
  enable_provider_history_tombstones: true,
  log_raw_webhooks: false,
  webhook_secret: '',
  webhook_secret_configured: false,
  avito_oauth_broker_url: '',
  avito_oauth_broker_secret: '',
  avito_oauth_broker_secret_configured: false,
  oauth_site_url: '',
})

const settings = reactive(defaultSettings())
const channels = ref([])
const loading = ref(true)
const refreshing = ref(false)
const savingSettings = ref(false)
const settingsSnapshot = ref('')
const showAdvanced = ref(false)

const showChannelDialog = ref(false)
const channelDraft = ref(makeMessengerChannelDraft())
const savingChannel = ref(false)
const channelAction = ref('')
const channelError = ref('')

const wazzupPlatforms = [
  { label: 'WhatsApp', value: 'whatsapp' },
  { label: 'Telegram', value: 'telegram' },
]
const avitoAuthTypes = [
  { label: 'OAuth', value: 'authorization_code' },
  { label: 'Client ID / Secret', value: 'client_credentials' },
  { label: 'API Token', value: 'api_token' },
]

const settingsDirty = computed(
  () => settingsSnapshot.value && settingsSnapshot.value !== settingsState(),
)
const showsApiToken = computed(() => {
  if (channelDraft.value.provider === 'avito_direct') {
    return channelDraft.value.auth_type === 'api_token'
  }
  return ['telegram_bot', 'vk_direct', 'max_direct', 'wazzup'].includes(
    channelDraft.value.provider,
  )
})
const apiTokenLabel = computed(() => {
  if (channelDraft.value.provider === 'telegram_bot') return 'Bot Token'
  if (channelDraft.value.provider === 'vk_direct')
    return 'Community Access Token'
  if (channelDraft.value.provider === 'max_direct') return 'Bot Token'
  return 'API Token'
})
const hasConnectionActions = computed(
  () =>
    isDirectMessengerProvider(channelDraft.value.provider) ||
    channelDraft.value.provider === 'avito_direct',
)

function settingsState() {
  return JSON.stringify({
    enabled: Boolean(settings.enabled),
    auto_create_lead: Boolean(settings.auto_create_lead),
    enable_provider_history_tombstones: Boolean(
      settings.enable_provider_history_tombstones,
    ),
    log_raw_webhooks: Boolean(settings.log_raw_webhooks),
    avito_oauth_broker_url: settings.avito_oauth_broker_url || '',
    oauth_site_url: settings.oauth_site_url || '',
    webhook_secret: settings.webhook_secret || '',
    avito_oauth_broker_secret: settings.avito_oauth_broker_secret || '',
  })
}

async function loadSettings(isRefresh = false, channelsOnly = false) {
  if (isRefresh) refreshing.value = true
  else loading.value = true
  try {
    let result = await call('crm_messenger.api.settings.get_settings')
    if (!channelsOnly) {
      Object.assign(settings, defaultSettings(), result.settings || {})
      settings.webhook_secret = ''
      settings.avito_oauth_broker_secret = ''
      settingsSnapshot.value = settingsState()
    }
    channels.value = result.channels || []
  } catch (error) {
    toast.error(
      error?.messages?.[0] || __('Не удалось загрузить настройки Messenger.'),
    )
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

async function saveGlobalSettings() {
  savingSettings.value = true
  try {
    let result = await call('crm_messenger.api.settings.save_settings', {
      enabled: Boolean(settings.enabled),
      auto_create_lead: Boolean(settings.auto_create_lead),
      enable_provider_history_tombstones: Boolean(
        settings.enable_provider_history_tombstones,
      ),
      log_raw_webhooks: Boolean(settings.log_raw_webhooks),
      avito_oauth_broker_url: settings.avito_oauth_broker_url || '',
      oauth_site_url: settings.oauth_site_url || '',
      webhook_secret: settings.webhook_secret || '',
      avito_oauth_broker_secret: settings.avito_oauth_broker_secret || '',
    })
    Object.assign(settings, result || {})
    settings.webhook_secret = ''
    settings.avito_oauth_broker_secret = ''
    settingsSnapshot.value = settingsState()
    toast.success(__('Настройки Messenger сохранены.'))
  } catch (error) {
    toast.error(
      error?.messages?.[0] || __('Не удалось сохранить настройки Messenger.'),
    )
  } finally {
    savingSettings.value = false
  }
}

function openNewChannel() {
  channelDraft.value = makeMessengerChannelDraft()
  channelError.value = ''
  showChannelDialog.value = true
}

function openChannel(channel) {
  channelDraft.value = {
    ...makeMessengerChannelDraft(channel),
    state: channel.state,
    auth_error: channel.auth_error,
    provider_display_name: channel.provider_display_name,
    label: channel.label,
  }
  channelError.value = ''
  showChannelDialog.value = true
}

function changeProvider(provider) {
  channelDraft.value.provider = provider
  applyMessengerProviderDefaults(channelDraft.value)
}

async function saveChannel() {
  let error = validateMessengerChannelDraft(channelDraft.value)
  if (error) {
    channelError.value = __(error)
    return
  }

  savingChannel.value = true
  channelError.value = ''
  let wasNew = !channelDraft.value.channel
  try {
    let result = await call(
      'crm_messenger.api.settings.save_channel',
      buildMessengerChannelPayload(channelDraft.value),
    )
    await loadSettings(true, true)
    let fresh = channels.value.find((row) => row.name === result.name) || result
    openChannel(fresh)
    toast.success(wasNew ? __('Канал создан.') : __('Канал сохранён.'))
  } catch (saveError) {
    channelError.value =
      saveError?.messages?.[0] || __('Не удалось сохранить канал.')
  } finally {
    savingChannel.value = false
  }
}

async function runChannelAction(action) {
  let methods = {
    test: 'crm_messenger.api.channels.test_provider_connection',
    connect: 'crm_messenger.api.channels.register_provider_webhook',
    status: 'crm_messenger.api.channels.get_provider_webhook_status',
    disconnect: 'crm_messenger.api.channels.remove_provider_webhook',
    'avito-webhook': 'crm_messenger.api.channels.register_avito_webhook',
    'avito-oauth': 'crm_messenger.api.avito_oauth.start_connection',
  }
  channelAction.value = action
  channelError.value = ''
  try {
    let params = { channel: channelDraft.value.channel }
    if (action === 'avito-oauth') params.return_url = window.location.href
    let result = await call(methods[action], params)
    if (!result?.ok) {
      throw new Error(
        result?.message || __('Операция провайдера завершилась ошибкой.'),
      )
    }
    if (result.authorization_url) {
      window.open(result.authorization_url, '_blank', 'noopener')
    }
    await loadSettings(true, true)
    let fresh = channels.value.find(
      (row) => row.name === channelDraft.value.channel,
    )
    if (fresh) openChannel(fresh)
    toast.success(result.message || __('Операция выполнена.'))
  } catch (error) {
    channelError.value =
      error?.messages?.[0] ||
      error?.message ||
      __('Операция провайдера завершилась ошибкой.')
  } finally {
    channelAction.value = ''
  }
}

function channelTitle(channel) {
  return (
    channel.custom_display_name ||
    channel.provider_display_name ||
    channel.label ||
    messengerProviderLabel(channel.provider)
  )
}

function providerDescription(channel) {
  let parts = [messengerProviderLabel(channel.provider)]
  if (channel.platform) parts.push(channel.platform)
  if (channel.external_account_id) parts.push(channel.external_account_id)
  else if (channel.provider_channel_id) parts.push(channel.provider_channel_id)
  return parts.join(' · ')
}

function providerInitial(provider) {
  let label = messengerProviderLabel(provider)
  return label === 'Telegram Bot' ? 'TG' : label.slice(0, 2).toUpperCase()
}

function secretPlaceholder(configured) {
  return configured ? __('Секрет уже сохранён') : __('Введите секрет')
}

onMounted(() => loadSettings())
</script>
