<template>
  <div class="flex h-full min-h-0 flex-col bg-surface-white">
    <div
      class="flex min-h-[64px] items-center justify-between gap-3 border-b px-4 py-3 sm:px-10"
    >
      <div class="min-w-0">
        <div class="text-xl font-semibold text-ink-gray-8">
          {{ __('Переписка') }}
        </div>
        <div class="mt-1 truncate text-sm text-ink-gray-5">
          {{ contactLine }}
        </div>
      </div>
      <Button
        :label="__('Обновить')"
        iconLeft="refresh-cw"
        :loading="loading"
        @click="loadAll"
      />
    </div>

    <div
      v-if="loading && !messages.length"
      class="flex flex-1 flex-col items-center justify-center gap-3 text-xl font-medium text-ink-gray-4"
    >
      <LoadingIndicator class="h-6 w-6" />
      <span>{{ __('Загрузка...') }}</span>
    </div>

    <div v-else class="relative flex min-h-0 flex-1 flex-col">
      <div
        v-if="genericError"
        class="mx-4 mt-4 rounded border border-outline-gray-1 bg-surface-gray-1 px-3 py-2 text-sm text-ink-red-3 sm:mx-10"
      >
        {{ genericError }}
      </div>
      <div
        v-if="sendWarning"
        class="mx-4 mt-4 rounded border border-outline-gray-1 bg-surface-gray-1 px-3 py-2 text-sm text-ink-gray-7 sm:mx-10"
      >
        {{ sendWarning }}
      </div>
      <div
        v-if="missingPhone"
        class="mx-4 mt-4 rounded border border-outline-gray-1 bg-surface-gray-1 px-3 py-2 text-sm text-ink-gray-7 sm:mx-10"
      >
        {{
          __(
            'У лида не указан телефон. Добавьте телефон, чтобы начать переписку.',
          )
        }}
      </div>
      <div
        v-if="!channels.length"
        class="mx-4 mt-4 rounded border border-outline-gray-1 bg-surface-gray-1 px-3 py-2 text-sm text-ink-gray-7 sm:mx-10"
      >
        {{ __('Нет активных каналов для отправки сообщений.') }}
      </div>
      <div
        v-if="selectedRequiresInbound"
        class="mx-4 mt-4 rounded border border-outline-gray-1 bg-surface-gray-1 px-3 py-2 text-sm text-ink-gray-7 sm:mx-10"
      >
        {{ __('Сначала должно прийти входящее сообщение в выбранном канале.') }}
      </div>

      <div class="relative min-h-0 flex-1">
        <div
          ref="messagesEl"
          class="h-full overflow-y-auto px-4 py-5 sm:px-10"
          @scroll.passive="handleMessagesScroll"
        >
        <div
          v-if="loadingHistory"
          class="flex justify-center pb-3 text-ink-gray-4"
        >
          <LoadingIndicator class="size-5" />
        </div>
        <div
          v-if="!messages.length"
          class="flex h-full min-h-[260px] flex-col items-center justify-center gap-2 text-center"
        >
          <CommentIcon class="size-8 text-ink-gray-4" />
          <div class="text-lg font-medium text-ink-gray-8">
            {{ __('Переписки пока нет') }}
          </div>
          <div class="max-w-md text-base text-ink-gray-5">
            {{ __('Выберите канал и отправьте первое сообщение этому лиду.') }}
          </div>
        </div>

        <div v-else class="flex flex-col gap-3">
          <template v-for="item in messageItems" :key="item.message.name">
            <div
              v-if="item.dateLabel"
              class="flex items-center justify-center py-1"
            >
              <span class="text-xs font-medium text-ink-gray-5">
                {{ item.dateLabel }}
              </span>
            </div>
            <div
              class="flex"
              :class="
                item.message.direction === 'outbound'
                  ? 'justify-end'
                  : 'justify-start'
              "
            >
              <div
                class="min-w-0 max-w-[94%] rounded-md px-3 py-2 text-base shadow-sm sm:max-w-[78%]"
                :class="
                  item.message.direction === 'outbound'
                    ? 'bg-surface-blue-1 text-ink-gray-9'
                    : 'bg-surface-gray-1 text-ink-gray-9'
                "
              >
                <div class="mb-1 flex items-center gap-2">
                  <span class="text-xs font-medium text-ink-gray-5">
                    {{ messageSender(item.message) }}
                  </span>
                  <Badge
                    variant="subtle"
                    :label="messageSource(item.message)"
                  />
                  <Badge
                    v-if="item.message.status === 'failed'"
                    theme="red"
                    variant="subtle"
                    :label="__('Ошибка')"
                  />
                </div>
                <div
                  v-if="shouldShowMessengerText(item.message)"
                  class="whitespace-pre-wrap break-words"
                >
                  {{
                    item.message.status === 'deleted'
                      ? __('Сообщение удалено')
                      : item.message.text || ''
                  }}
                </div>
                <AttachmentRenderer :attachments="item.message.attachments" />
                <div
                  class="mt-1 flex items-center justify-end gap-2 text-xs text-ink-gray-5"
                >
                  <Tooltip
                    v-if="item.message.message_datetime"
                    :text="formatDate(item.message.message_datetime)"
                  >
                    <span>{{
                      formatDate(item.message.message_datetime, 'HH:mm')
                    }}</span>
                  </Tooltip>
                  <Tooltip
                    v-if="deliveryState(item.message)"
                    :text="deliveryTooltip(item.message)"
                  >
                    <span
                      class="inline-flex items-center"
                      :class="deliveryIconClass(item.message)"
                    >
                      <ClockIcon
                        v-if="
                          ['queued', 'sending', 'retrying'].includes(
                            deliveryState(item.message),
                          )
                        "
                        class="size-4"
                      />
                      <CheckIcon
                        v-else-if="deliveryState(item.message) === 'sent'"
                        class="size-4"
                      />
                      <DoubleCheckIcon
                        v-else-if="
                          ['delivered', 'read'].includes(
                            deliveryState(item.message),
                          )
                        "
                        class="size-4"
                      />
                      <CircleAlertIcon
                        v-else-if="
                          ['failed', 'unknown'].includes(
                            deliveryState(item.message),
                          )
                        "
                        class="size-4"
                      />
                    </span>
                  </Tooltip>
                </div>
                <div
                  v-if="messageFailureReason(item.message)"
                  class="mt-1 border-t border-outline-gray-1 pt-1 text-xs text-ink-red-4"
                >
                  {{ messageFailureReason(item.message) }}
                </div>
              </div>
            </div>
          </template>
        </div>
        </div>

        <div
          v-if="newMessageCount"
          class="pointer-events-none absolute inset-x-0 bottom-3 flex justify-center px-3"
        >
          <Button
            class="pointer-events-auto max-w-full shadow-md"
            variant="solid"
            iconLeft="arrow-down"
            :label="__('Новые сообщения: {0}', [newMessageCount])"
            @click="scrollToBottom"
          />
        </div>
      </div>

      <div
        class="relative border-t px-4 py-3 sm:px-10"
        @dragover="handleComposerDragOver"
        @dragleave="draggingFiles = false"
        @drop="handleComposerDrop"
      >
        <div
          v-if="draggingFiles"
          class="pointer-events-none absolute inset-1 z-10 flex items-center justify-center rounded-lg border-2 border-dashed border-outline-blue-2 bg-surface-blue-1/90 text-sm font-medium text-ink-blue-3"
        >
          {{ __('Перетащите файлы сюда') }}
        </div>
        <div class="mb-2 grid gap-2 sm:grid-cols-[220px_minmax(0,1fr)]">
          <FormControl
            v-model="selectedChannel"
            type="select"
            :options="channelOptions"
            :disabled="!channels.length || sendingMessage"
            :placeholder="__('Платформа')"
          />
          <Textarea
            ref="textareaRef"
            v-model="draftText"
            class="min-h-20 w-full"
            :rows="3"
            :disabled="baseSendDisabled"
            :placeholder="__('Введите сообщение...')"
            @keydown.enter.stop="sendOnEnter"
            @paste.stop="handleComposerPaste"
          />
        </div>
        <ComposerAttachments
          ref="composerAttachments"
          :supportsAttachments="selectedCapabilities.supports_attachments"
          :channelType="selectedChannelType"
          @change="pendingAttachments = $event"
        />
        <div class="flex items-center justify-between gap-3">
          <div class="min-w-0 text-sm text-ink-gray-5">
            <div class="truncate">{{ composerHint }}</div>
          </div>
          <div class="flex items-center gap-2">
            <Button
              v-if="selectedCapabilities.supports_attachments"
              variant="ghost"
              icon="paperclip"
              :disabled="baseSendDisabled || pendingAttachments.length >= 10"
              @click="composerAttachments?.openFileSelector()"
            />
            <Button
              variant="solid"
              :label="__('Отправить')"
              iconLeft="send"
              :loading="sendingMessage"
              :disabled="sendDisabled || (!draftText.trim() && !pendingAttachments.length)"
              @click="sendMessage"
            />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import CheckIcon from '@/components/Icons/CheckIcon.vue'
import CommentIcon from '@/components/Icons/CommentIcon.vue'
import DoubleCheckIcon from '@/components/Icons/DoubleCheckIcon.vue'
import LoadingIndicator from '@/components/Icons/LoadingIndicator.vue'
import AttachmentRenderer from '@/components/LeadMessenger/AttachmentRenderer.vue'
import ComposerAttachments from '@/components/LeadMessenger/ComposerAttachments.vue'
import { globalStore } from '@/stores/global'
import { formatDate } from '@/utils'
import {
  buildMessengerMessageItems,
  buildMessengerChannelOptions,
  getMessengerChannelType,
  getMessengerCapabilities,
  getMessengerDeliveryLabel,
  getMessengerDeliveryState,
  getMessengerPlatformLabel,
  shouldShowMessengerText,
} from '@/utils/messengerChannels'
import { createMessengerSyncController } from '@/utils/messengerSync'
import { validateComposerFileMix } from '@/utils/messengerComposer'
import {
  Badge,
  Button,
  FormControl,
  Textarea,
  Tooltip,
  call,
  toast,
} from 'frappe-ui'
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from 'vue'
import CircleAlertIcon from '~icons/lucide/circle-alert'
import ClockIcon from '~icons/lucide/clock-3'

const props = defineProps({
  leadName: { type: String, required: true },
  lead: { type: Object, default: () => ({}) },
  phone: { type: String, default: '' },
})

const loadingConversation = ref(false)
const loadingMessages = ref(false)
const loadingHistory = ref(false)
const loadingChannels = ref(false)
const sendingMessage = ref(false)
const conversations = ref([])
const messages = ref([])
const channels = ref([])
const selectedChannel = ref('')
const draftText = ref('')
const clientRequestId = ref('')
const clientRequestFingerprint = ref('')
const pendingAttachments = ref([])
const sendWarning = ref('')
const genericError = ref('')
const messagesEl = ref(null)
const newMessageCount = ref(0)
const composerAttachments = ref(null)
const draggingFiles = ref(false)
let scrollSnapshot = null

const { $socket } = globalStore()

const leadPhone = computed(
  () => props.phone || props.lead?.mobile_no || props.lead?.phone || '',
)
const loading = computed(
  () =>
    loadingConversation.value || loadingMessages.value || loadingChannels.value,
)
const selectedConversation = computed(() => {
  if (!conversations.value.length) return null
  if (!selectedChannel.value) return conversations.value[0]
  return (
    conversations.value.find(
      (conversation) => conversation.channel === selectedChannel.value,
    ) || null
  )
})
const channelByName = computed(() => {
  let map = {}
  channels.value.forEach((channel) => {
    map[channel.name] = channel
  })
  conversations.value.forEach((conversation) => {
    if (conversation.channel && conversation.channel_info) {
      map[conversation.channel] = {
        ...(map[conversation.channel] || {}),
        ...conversation.channel_info,
      }
    }
  })
  return map
})
const conversationByName = computed(() => {
  let map = {}
  conversations.value.forEach((conversation) => {
    map[conversation.name] = conversation
  })
  return map
})
const selectedChannelDoc = computed(
  () => channelByName.value[selectedChannel.value] || null,
)
const selectedChannelType = computed(() =>
  getMessengerChannelType(
    selectedChannelDoc.value || selectedConversation.value,
  ),
)
const selectedCapabilities = computed(() =>
  getMessengerCapabilities(
    selectedChannelDoc.value || selectedConversation.value || {},
  ),
)
const missingPhone = computed(
  () =>
    Boolean(selectedChannelType.value) &&
    selectedCapabilities.value.requires_phone &&
    !leadPhone.value,
)
const selectedRequiresInbound = computed(
  () =>
    selectedCapabilities.value.requires_inbound &&
    !selectedConversation.value?.external_chat_id,
)
const baseSendDisabled = computed(
  () =>
    sendingMessage.value ||
    missingPhone.value ||
    selectedRequiresInbound.value ||
    !channels.value.length ||
    !selectedChannel.value,
)
const sendDisabled = computed(
  () =>
    baseSendDisabled.value ||
    Boolean(attachmentMixError.value) ||
    pendingAttachments.value.some((item) => item.status !== 'uploaded'),
)
const attachmentMixError = computed(() => {
  if (!pendingAttachments.value.length) return ''
  return (
    validateComposerFileMix([], pendingAttachments.value, {
      supportsAttachments: selectedCapabilities.value.supports_attachments,
      channelType: selectedChannelType.value,
    }).error || ''
  )
})
const channelOptions = computed(() =>
  buildMessengerChannelOptions(channels.value),
)
const messageItems = computed(() => buildMessengerMessageItems(messages.value))
const contactLine = computed(() => {
  let title = props.lead?.lead_name || props.lead?.name || props.leadName
  return leadPhone.value ? `${title} · ${leadPhone.value}` : title
})
const composerHint = computed(() => {
  if (attachmentMixError.value) return __(attachmentMixError.value)
  if (selectedRequiresInbound.value) {
    return __('Сначала должно прийти входящее сообщение в выбранном канале.')
  }
  if (missingPhone.value) return __('Добавьте телефон в карточке лида.')
  if (!channels.value.length) return __('Нет доступного канала отправки.')
  return __('Enter отправляет сообщение, Shift+Enter добавляет новую строку.')
})

const messageSync = createMessengerSyncController({
  socket: $socket,
  call,
  visibilityTarget: document,
  onBeforeChange({ kind }) {
    if (kind === 'history') {
      scrollSnapshot = {
        kind,
        height: messagesEl.value?.scrollHeight || 0,
        top: messagesEl.value?.scrollTop || 0,
      }
    } else if (kind === 'delta') {
      scrollSnapshot = { kind, nearBottom: isNearBottom() }
    }
  },
  async onChange(change) {
    messages.value = change.messages
    await nextTick()
    if (change.kind === 'snapshot') {
      scrollToBottom()
    } else if (change.kind === 'history' && scrollSnapshot?.kind === 'history') {
      let addedHeight = (messagesEl.value?.scrollHeight || 0) - scrollSnapshot.height
      if (messagesEl.value) {
        messagesEl.value.scrollTop = scrollSnapshot.top + addedHeight
      }
    } else if (change.kind === 'delta' && change.inserted.length) {
      if (scrollSnapshot?.nearBottom) scrollToBottom()
      else newMessageCount.value += change.inserted.length
    }
    scrollSnapshot = null
  },
  onDeltaApplied(_merge, incoming) {
    if (
      incoming.some(
        (message) =>
          message.conversation && !conversationByName.value[message.conversation],
      )
    ) {
      loadConversations()
    }
  },
  onError(error) {
    handleError(error, __('Не удалось синхронизировать сообщения.'))
  },
})

onMounted(initialize)

onBeforeUnmount(() => {
  messageSync.stop()
})

watch(
  () => props.leadName,
  () => initialize(true),
)

async function initialize(leadChanged = false) {
  genericError.value = ''
  sendWarning.value = ''
  newMessageCount.value = 0
  loadingMessages.value = true
  if (leadChanged) {
    messages.value = []
    conversations.value = []
    draftText.value = ''
    composerAttachments.value?.clear()
    clientRequestId.value = ''
    clientRequestFingerprint.value = ''
  }
  try {
    await Promise.all([
      loadChannels(),
      loadConversations(),
      leadChanged
        ? messageSync.setLead(props.leadName)
        : messageSync.start(props.leadName),
    ])
  } catch (error) {
    handleError(error, __('Не удалось загрузить сообщения.'))
  } finally {
    loadingMessages.value = false
  }
}

async function loadAll() {
  genericError.value = ''
  sendWarning.value = ''
  loadingMessages.value = true
  try {
    await Promise.all([
      loadChannels(),
      loadConversations(),
      messageSync.loadSnapshot(),
    ])
  } catch (error) {
    handleError(error, __('Не удалось обновить сообщения.'))
  } finally {
    loadingMessages.value = false
  }
}

async function loadChannels() {
  loadingChannels.value = true
  try {
    let result = await call('crm_messenger.api.channels.get_channels', {
      active_only: 1,
    })
    if (!result?.ok)
      throw new Error(result?.message || __('Не удалось загрузить каналы.'))
    channels.value = result.channels || []
    ensureSelectedChannel()
  } catch (error) {
    handleError(error, __('Не удалось загрузить каналы.'))
  } finally {
    loadingChannels.value = false
  }
}

async function loadConversations() {
  loadingConversation.value = true
  try {
    let result = await call(
      'crm_messenger.api.conversations.get_conversations',
      {
        reference_doctype: 'CRM Lead',
        reference_name: props.leadName,
        limit: 50,
      },
    )
    if (!result?.ok)
      throw new Error(result?.message || __('Не удалось загрузить переписку.'))
    conversations.value = result.conversations || []
    ensureSelectedChannel()
  } catch (error) {
    handleError(error, __('Не удалось загрузить переписку.'))
  } finally {
    loadingConversation.value = false
  }
}

function ensureSelectedChannel() {
  if (selectedChannel.value && channelByName.value[selectedChannel.value])
    return
  selectedChannel.value =
    conversations.value.find((row) => row.channel)?.channel ||
    channels.value[0]?.name ||
    ''
}

async function sendMessage() {
  let text = draftText.value.trim()
  if ((!text && !pendingAttachments.value.length) || sendDisabled.value) return

  genericError.value = ''
  sendWarning.value = ''
  sendingMessage.value = true

  try {
    let conversation =
      selectedConversation.value || (await createConversation())
    if (!conversation?.name) return

    let attachmentNames = composerAttachments.value?.readyFileNames() || []
    let fingerprint = JSON.stringify({
      conversation: conversation.name,
      channel: selectedChannel.value,
      text,
      attachments: attachmentNames,
    })
    if (!clientRequestId.value || clientRequestFingerprint.value !== fingerprint) {
      clientRequestId.value = makeClientRequestId()
      clientRequestFingerprint.value = fingerprint
    }
    let result = await call('crm_messenger.api.messages.send_message', {
      conversation: conversation.name,
      text,
      channel: selectedChannel.value,
      client_request_id: clientRequestId.value,
      attachments: attachmentNames,
    })

    if (result?.reason === 'not_configured') {
      clientRequestId.value = ''
      clientRequestFingerprint.value = ''
      sendWarning.value = integrationWarningMessage(result)
      toast.error(sendWarning.value)
    } else if (!result?.ok) {
      clientRequestId.value = ''
      clientRequestFingerprint.value = ''
      throw new Error(result?.message || __('Не удалось отправить сообщение.'))
    } else {
      draftText.value = ''
      composerAttachments.value?.clear()
      clientRequestId.value = ''
      clientRequestFingerprint.value = ''
    }
  } catch (error) {
    handleError(error, __('Не удалось отправить сообщение.'))
  } finally {
    sendingMessage.value = false
    await Promise.all([loadConversations(), messageSync.syncDelta()])
  }
}

function integrationWarningMessage(result = {}) {
  let channel =
    channelByName.value[result.channel] ||
    selectedChannelDoc.value ||
    selectedConversation.value?.channel_info ||
    selectedConversation.value ||
    {}
  let provider = (channel.provider || '').toLowerCase()
  let type = getMessengerChannelType(channel)
  let resultMessage = `${result.message || ''} ${
    result.provider_result?.message || ''
  }`.toLowerCase()

  if (
    type === 'avito' ||
    channel.platform === 'avito' ||
    provider === 'avito_direct' ||
    resultMessage.includes('avito')
  ) {
    return __(
      'Интеграция Avito не настроена: укажите Avito account id и API token. Сообщение сохранено локально со статусом ошибки.',
    )
  }

  if (provider === 'wazzup' || resultMessage.includes('wazzup')) {
    return __(
      'Интеграция Wazzup не настроена: включите интеграцию и укажите API token. Сообщение сохранено локально со статусом ошибки.',
    )
  }

  return __(
    'Интеграция мессенджера не настроена. Сообщение сохранено локально со статусом ошибки.',
  )
}

async function createConversation() {
  if (selectedCapabilities.value.requires_inbound) {
    genericError.value = __(
      'Сначала должно прийти входящее сообщение в выбранном канале.',
    )
    return null
  }

  let result = await call(
    'crm_messenger.api.conversations.get_or_create_lead_conversation',
    {
      reference_name: props.leadName,
      channel: selectedChannel.value,
    },
  )

  if (result?.reason === 'missing_phone') {
    genericError.value = __('У лида не указан телефон.')
    return null
  }
  if (!result?.ok) {
    throw new Error(result?.message || __('Не удалось создать переписку.'))
  }

  let conversation = result.conversation
  if (
    conversation?.name &&
    !conversations.value.find((row) => row.name === conversation.name)
  ) {
    conversations.value = [conversation, ...conversations.value]
  }
  return conversation
}

function makeClientRequestId() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID()
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function sendOnEnter(event) {
  if (event.shiftKey) return
  event.preventDefault()
  sendMessage()
}

function handleComposerPaste(event) {
  composerAttachments.value?.handlePaste(event)
}

function handleComposerDragOver(event) {
  if (!Array.from(event.dataTransfer?.types || []).includes('Files')) return
  event.preventDefault()
  draggingFiles.value = true
}

function handleComposerDrop(event) {
  draggingFiles.value = false
  composerAttachments.value?.handleDrop(event)
}

function scrollToBottom() {
  if (!messagesEl.value) return
  messagesEl.value.scrollTop = messagesEl.value.scrollHeight
  newMessageCount.value = 0
}

function isNearBottom() {
  if (!messagesEl.value) return true
  return (
    messagesEl.value.scrollHeight -
      messagesEl.value.scrollTop -
      messagesEl.value.clientHeight <
    96
  )
}

async function handleMessagesScroll() {
  if (isNearBottom()) newMessageCount.value = 0
  if (
    !messagesEl.value ||
    messagesEl.value.scrollTop > 80 ||
    loadingHistory.value ||
    !messageSync.hasMoreHistory()
  )
    return
  loadingHistory.value = true
  try {
    await messageSync.loadOlder()
  } catch (error) {
    handleError(error, __('Не удалось загрузить предыдущие сообщения.'))
  } finally {
    loadingHistory.value = false
  }
}

function messageSender(message) {
  if (message.direction === 'outbound') return __('Вы')
  return message.sender_name || props.lead?.lead_name || props.leadName
}

function messageSource(message) {
  let conversation = conversationByName.value[message.conversation]
  let channel =
    message.channel_info ||
    channelByName.value[message.channel] ||
    conversation?.channel_info ||
    conversation
  return __(getMessengerPlatformLabel(channel))
}

function deliveryState(message) {
  return getMessengerDeliveryState(message)
}

function deliveryTooltip(message) {
  let label = getMessengerDeliveryLabel(message)
  let reason = messageFailureReason(message)
  return reason ? `${__(label)}: ${reason}` : __(label)
}

function deliveryIconClass(message) {
  let state = deliveryState(message)
  if (state === 'read') return 'text-ink-blue-2'
  if (['failed', 'unknown'].includes(state)) return 'text-ink-red-4'
  return 'text-ink-gray-5'
}

function messageFailureReason(message) {
  return message.failure_reason || message.error || ''
}

function handleError(error, fallback) {
  let message = error?.messages?.[0] || error?.message || fallback
  genericError.value = __(message)
  toast.error(genericError.value)
}
</script>
