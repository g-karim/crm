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

    <div v-else class="flex min-h-0 flex-1 flex-col">
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

      <div
        ref="messagesEl"
        class="min-h-0 flex-1 overflow-y-auto px-4 py-5 sm:px-10"
      >
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
          <div
            v-for="message in messages"
            :key="message.name"
            class="flex"
            :class="
              message.direction === 'outbound' ? 'justify-end' : 'justify-start'
            "
          >
            <div
              class="max-w-[78%] rounded-md px-3 py-2 text-base shadow-sm"
              :class="
                message.direction === 'outbound'
                  ? 'bg-surface-blue-1 text-ink-gray-9'
                  : 'bg-surface-gray-1 text-ink-gray-9'
              "
            >
              <div class="mb-1 flex items-center gap-2">
                <span class="text-xs font-medium text-ink-gray-5">
                  {{ messageSender(message) }}
                </span>
                <Badge variant="subtle" :label="messageSource(message)" />
                <Badge
                  v-if="message.status === 'failed'"
                  theme="red"
                  variant="subtle"
                  :label="__('Ошибка')"
                />
              </div>
              <div
                v-if="shouldShowMessengerText(message)"
                class="whitespace-pre-wrap break-words"
              >
                {{ message.status === 'deleted' ? __('Сообщение удалено') : message.text || '' }}
              </div>
              <div v-if="message.attachments?.length" class="mt-2 grid gap-2">
                <a
                  v-for="attachment in message.attachments"
                  :key="attachment.name"
                  :href="attachment.url"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="block max-w-sm break-all text-sm text-ink-blue-link"
                >
                  <img
                    v-if="attachment.attachment_type === 'image' && attachment.url"
                    :src="attachment.url"
                    :alt="attachment.file_name || __('Изображение')"
                    class="max-h-64 rounded object-contain"
                  />
                  <span v-else>{{ attachment.file_name || attachment.url || __('Вложение недоступно') }}</span>
                </a>
              </div>
              <div
                class="mt-1 flex items-center justify-end gap-2 text-xs text-ink-gray-5"
              >
                <Tooltip
                  v-if="message.message_datetime"
                  :text="formatDate(message.message_datetime)"
                >
                  <span>{{
                    formatDate(message.message_datetime, 'HH:mm')
                  }}</span>
                </Tooltip>
                <Tooltip
                  v-if="deliveryState(message)"
                  :text="deliveryTooltip(message)"
                >
                  <span
                    class="inline-flex items-center"
                    :class="deliveryIconClass(message)"
                  >
                    <ClockIcon
                      v-if="['queued', 'sending', 'retrying'].includes(deliveryState(message))"
                      class="size-4"
                    />
                    <CheckIcon
                      v-else-if="deliveryState(message) === 'sent'"
                      class="size-4"
                    />
                    <DoubleCheckIcon
                      v-else-if="
                        ['delivered', 'read'].includes(deliveryState(message))
                      "
                      class="size-4"
                    />
                    <CircleAlertIcon
                      v-else-if="['failed', 'unknown'].includes(deliveryState(message))"
                      class="size-4"
                    />
                  </span>
                </Tooltip>
              </div>
              <div
                v-if="messageFailureReason(message)"
                class="mt-1 border-t border-outline-gray-1 pt-1 text-xs text-ink-red-4"
              >
                {{ messageFailureReason(message) }}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="border-t px-4 py-3 sm:px-10">
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
            :disabled="sendDisabled"
            :placeholder="__('Введите сообщение...')"
            @keydown.enter.stop="sendOnEnter"
          />
        </div>
        <div class="flex items-center justify-between gap-3">
          <div class="min-w-0 text-sm text-ink-gray-5">
            <div class="truncate">{{ composerHint }}</div>
            <div v-if="pendingAttachments.length" class="mt-1 flex flex-wrap gap-1">
              <span
                v-for="file in pendingAttachments"
                :key="file.name"
                class="inline-flex items-center gap-1"
              >
                <Badge variant="subtle" :label="file.file_name" />
                <Button variant="ghost" icon="x" @click="removeAttachment(file.name)" />
              </span>
            </div>
          </div>
          <div class="flex items-center gap-2">
            <FileUploader
              v-if="selectedCapabilities.supports_attachments"
              :upload-args="{ private: true }"
              @success="addAttachment"
            >
              <template #default="{ openFileSelector }">
                <Button
                  variant="ghost"
                  icon="paperclip"
                  :disabled="sendDisabled || pendingAttachments.length >= 10"
                  @click="openFileSelector()"
                />
              </template>
            </FileUploader>
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
import { formatDate } from '@/utils'
import {
  buildMessengerChannelOptions,
  getMessengerChannelType,
  getMessengerCapabilities,
  getMessengerDeliveryLabel,
  getMessengerDeliveryState,
  getMessengerPlatformLabel,
  shouldShowMessengerText,
} from '@/utils/messengerChannels'
import {
  Badge,
  Button,
  FileUploader,
  FormControl,
  Textarea,
  Tooltip,
  call,
  toast,
} from 'frappe-ui'
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import CircleAlertIcon from '~icons/lucide/circle-alert'
import ClockIcon from '~icons/lucide/clock-3'

const props = defineProps({
  leadName: { type: String, required: true },
  lead: { type: Object, default: () => ({}) },
  phone: { type: String, default: '' },
})

const loadingConversation = ref(false)
const loadingMessages = ref(false)
const loadingChannels = ref(false)
const sendingMessage = ref(false)
const conversations = ref([])
const messages = ref([])
const channels = ref([])
const selectedChannel = ref('')
const draftText = ref('')
const clientRequestId = ref('')
const pendingAttachments = ref([])
const sendWarning = ref('')
const genericError = ref('')
const messagesEl = ref(null)

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
const sendDisabled = computed(
  () =>
    sendingMessage.value ||
    missingPhone.value ||
    selectedRequiresInbound.value ||
    !channels.value.length ||
    !selectedChannel.value,
)
const channelOptions = computed(() =>
  buildMessengerChannelOptions(channels.value),
)
const contactLine = computed(() => {
  let title = props.lead?.lead_name || props.lead?.name || props.leadName
  return leadPhone.value ? `${title} · ${leadPhone.value}` : title
})
const composerHint = computed(() => {
  if (selectedRequiresInbound.value) {
    return __('Сначала должно прийти входящее сообщение в выбранном канале.')
  }
  if (missingPhone.value) return __('Добавьте телефон в карточке лида.')
  if (!channels.value.length) return __('Нет доступного канала отправки.')
  return __('Enter отправляет сообщение, Shift+Enter добавляет новую строку.')
})

onMounted(loadAll)

watch(
  () => props.leadName,
  () => loadAll(),
)

async function loadAll() {
  genericError.value = ''
  sendWarning.value = ''
  await Promise.all([loadChannels(), loadConversations(), loadMessages()])
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

async function loadMessages() {
  loadingMessages.value = true
  try {
    let result = await call('crm_messenger.api.messages.get_messages', {
      reference_doctype: 'CRM Lead',
      reference_name: props.leadName,
      limit: 200,
    })
    if (!result?.ok)
      throw new Error(result?.message || __('Не удалось загрузить сообщения.'))
    messages.value = result.messages || []
    await nextTick()
    scrollToBottom()
  } catch (error) {
    handleError(error, __('Не удалось загрузить сообщения.'))
  } finally {
    loadingMessages.value = false
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

    let result = await call('crm_messenger.api.messages.send_message', {
      conversation: conversation.name,
      text,
      channel: selectedChannel.value,
      client_request_id:
        clientRequestId.value ||
        (clientRequestId.value = makeClientRequestId()),
      attachments: pendingAttachments.value.map((file) => file.name),
    })

    draftText.value = ''
    pendingAttachments.value = []
    clientRequestId.value = ''
    if (result?.reason === 'not_configured') {
      sendWarning.value = integrationWarningMessage(result)
      toast.error(sendWarning.value)
    } else if (!result?.ok) {
      throw new Error(result?.message || __('Не удалось отправить сообщение.'))
    }
  } catch (error) {
    handleError(error, __('Не удалось отправить сообщение.'))
  } finally {
    sendingMessage.value = false
    await Promise.all([loadConversations(), loadMessages()])
  }
}

function addAttachment(file) {
  if (!file?.name || pendingAttachments.value.length >= 10) return
  if (selectedChannelType.value === 'max') {
    let isImage = isImageFile(file)
    let existingAreImages = pendingAttachments.value.every(isImageFile)
    if (
      (!isImage && pendingAttachments.value.length) ||
      (isImage && pendingAttachments.value.length && !existingAreImages)
    ) {
      toast.error(
        __('MAX поддерживает до 10 изображений либо один файл/аудио без смешивания.'),
      )
      return
    }
  }
  pendingAttachments.value = [...pendingAttachments.value, file]
}

function isImageFile(file) {
  let mime = `${file.file_type || file.mime_type || ''}`.toLowerCase()
  return mime.startsWith('image/') || /\.(png|jpe?g|gif|webp|heic)$/i.test(file.file_name || '')
}

function removeAttachment(name) {
  pendingAttachments.value = pendingAttachments.value.filter(
    (file) => file.name !== name,
  )
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

function scrollToBottom() {
  if (!messagesEl.value) return
  messagesEl.value.scrollTop = messagesEl.value.scrollHeight
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
