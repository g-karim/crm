<template>
  <div class="flex h-full min-h-0 flex-col bg-surface-base">
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
        class="mx-4 mt-4 rounded border border-outline-gray-1 bg-surface-gray-1 px-3 py-2 text-sm text-ink-red-6 sm:mx-10"
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
        v-if="conversationNotice.message"
        class="mx-4 mt-4 rounded border px-3 py-2 text-sm sm:mx-10"
        :class="
          conversationNotice.type === 'warning'
            ? 'border-outline-red-1 bg-surface-red-1 text-ink-red-6'
            : 'border-outline-gray-1 bg-surface-gray-1 text-ink-gray-7'
        "
      >
        {{ __(conversationNotice.message) }}
      </div>
      <div
        v-if="permissions.can_operate && missingPhone"
        class="mx-4 mt-4 rounded border border-outline-gray-1 bg-surface-gray-1 px-3 py-2 text-sm text-ink-gray-7 sm:mx-10"
      >
        {{
          __(
            'У лида не указан телефон. Добавьте телефон, чтобы начать переписку.',
          )
        }}
      </div>
      <div
        v-if="permissions.can_operate && !channels.length"
        class="mx-4 mt-4 rounded border border-outline-gray-1 bg-surface-gray-1 px-3 py-2 text-sm text-ink-gray-7 sm:mx-10"
      >
        {{ __('Нет активных каналов для отправки сообщений.') }}
      </div>
      <div
        v-if="permissions.can_operate && selectedRequiresInbound"
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
              {{
                permissions.can_operate
                  ? __(
                      'Выберите канал и отправьте первое сообщение этому лиду.',
                    )
                  : __('Для этого лида пока нет доступных сообщений.')
              }}
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
                :data-message-id="item.message.name"
                class="flex"
                :class="
                  item.message.direction === 'outbound'
                    ? 'justify-end'
                    : 'justify-start'
                "
              >
                <div
                  data-message-bubble
                  class="min-w-0 max-w-[94%] rounded-md px-3 py-2 text-base shadow-sm sm:max-w-[78%]"
                  :class="[
                    item.message.direction === 'outbound'
                      ? 'bg-surface-blue-1 text-ink-gray-9'
                      : 'bg-surface-gray-1 text-ink-gray-9',
                    messageBubbleWidthClass(item.message),
                    item.messages.some(
                      (message) => highlightedMessage === message.name,
                    )
                      ? 'ring-2 ring-outline-blue-3'
                      : '',
                  ]"
                  @contextmenu="openReactionPicker(item.message, $event)"
                >
                  <span
                    v-for="groupMessage in item.messages.slice(0, -1)"
                    :key="`anchor:${groupMessage.name}`"
                    :data-message-id="groupMessage.name"
                    class="block h-0 overflow-hidden"
                    aria-hidden="true"
                  />
                  <MessageMetadata
                    :message="item.message"
                    :sender="messageSender(item.message)"
                    :source="messageSource(item.message)"
                    :failed="messageFailed(item.message)"
                    :editing="
                      messageActionState.editingMessage === item.message.name
                    "
                    :loading="
                      messageActionState.pendingMessage === item.message.name
                    "
                    @start-edit="startMessageEdit(item.message)"
                    @delete="confirmDeleteMessage(item.message)"
                    @retry="retryMessage(item.message)"
                    @reply="startReply(item.message)"
                  />
                  <MessageReplyQuote
                    v-if="item.message.reply_context"
                    class="mb-2"
                    :context="item.message.reply_context"
                    :client-name="clientDisplayName"
                    @navigate="navigateToReply"
                  />
                  <MessageForwardStack
                    v-for="groupMessage in item.messages.filter(
                      (message) =>
                        message.status !== 'deleted' && message.forward_context,
                    )"
                    :key="`forward:${groupMessage.name}`"
                    class="mb-2 last:mb-0"
                    :context="groupMessage.forward_context"
                    :playback-scope="videoPlaybackScope"
                    :provider="groupMessage.provider"
                  />
                  <MessageContent
                    :message="item.message"
                    :editing="
                      messageActionState.editingMessage === item.message.name
                    "
                    :draft="messageActionState.draft"
                    :loading="
                      messageActionState.pendingMessage === item.message.name
                    "
                    :error="messageActionState.errors[item.message.name] || ''"
                    :shouldShowText="shouldShowMessengerText(item.message)"
                    @update:draft="messageActions.setDraft"
                    @save-edit="messageActions.saveEdit(item.message)"
                    @cancel-edit="messageActions.cancelEdit"
                    @editor-element="
                      setEditorElement(item.message.name, $event)
                    "
                  />
                  <AttachmentRenderer
                    v-if="item.message.status !== 'deleted'"
                    :attachments="item.message.attachments"
                    :playback-scope="videoPlaybackScope"
                    :provider="item.message.provider"
                  />
                  <MessageReactions
                    v-if="
                      item.message.status !== 'deleted' &&
                      item.message.channel_info?.capabilities?.reactions
                        ?.receive
                    "
                    :ref="
                      (component) =>
                        setReactionComponent(item.message.name, component)
                    "
                    :message="item.message"
                    :can-send="Boolean(item.message.can_react)"
                    @changed="handleReactionsChanged(item.message, $event)"
                  />
                  <MessageFooterMetadata :message="item.message" />
                  <div
                    v-if="messageFailureReason(item.message)"
                    class="mt-1 border-t border-outline-gray-1 pt-1 text-xs"
                    :class="messageStatusNoteClass(item.message)"
                  >
                    {{ messageFailureReason(item.message) }}
                  </div>
                </div>
              </div>
            </template>
            <div
              v-if="typingActive"
              class="w-fit rounded-md bg-surface-gray-1 px-3 py-2 text-sm italic text-ink-gray-5"
            >
              {{ __('{0} печатает…', [clientDisplayName]) }}
            </div>
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
        v-if="permissions.can_operate"
        class="relative border-t px-4 py-3 sm:px-10"
        @dragover="handleComposerDragOver"
        @dragleave="draggingFiles = false"
        @drop="handleComposerDrop"
      >
        <div v-if="replyTarget" class="mb-2 flex items-start gap-2">
          <MessageReplyQuote
            class="min-w-0 flex-1"
            :context="replyComposerContext"
            :client-name="clientDisplayName"
            @navigate="navigateToReply"
          />
          <Button
            variant="ghost"
            icon="x"
            :aria-label="__('Отменить ответ')"
            @click="cancelReply"
          />
        </div>
        <div
          v-if="draggingFiles"
          class="pointer-events-none absolute inset-1 z-10 flex items-center justify-center rounded-lg border-2 border-dashed border-outline-blue-3 bg-surface-blue-1/90 text-sm font-medium text-ink-blue-6"
        >
          {{ __('Перетащите файлы сюда') }}
        </div>
        <div class="mb-2 grid gap-2 sm:grid-cols-2">
          <FormControl
            v-model="selectedChannel"
            type="select"
            :options="channelOptions"
            :disabled="
              !channels.length ||
              sendingMessage ||
              voiceActive ||
              replyTarget ||
              preparedHandoff
            "
            :placeholder="__('Платформа')"
          />
          <FormControl
            v-if="conversationCandidates.length > 1"
            v-model="selectedConversationName"
            type="select"
            :options="conversationOptions"
            :disabled="
              sendingMessage ||
              voiceActive ||
              Boolean(replyTarget) ||
              Boolean(preparedHandoff)
            "
            :placeholder="__('Внешний чат')"
          />
        </div>
        <div
          v-if="preparedHandoff"
          data-testid="prepared-handoff"
          class="mb-2 rounded-md border border-outline-gray-2 bg-surface-gray-1 p-3"
        >
          <div class="mb-2 text-xs font-medium text-ink-gray-5">
            {{ __('Подготовлен переход. Текст нельзя изменить.') }}
          </div>
          <div class="whitespace-pre-wrap text-sm text-ink-gray-8">
            {{ preparedHandoff.message }}
          </div>
          <div class="mt-3 flex justify-end">
            <Button
              :label="__('Отменить')"
              variant="ghost"
              :loading="handoffCancelling"
              :disabled="sendingMessage"
              @click="cancelPreparedHandoff"
            />
          </div>
        </div>
        <Textarea
          v-else
          ref="textareaRef"
          v-model="draftText"
          class="mb-2 min-h-20 w-full"
          :rows="3"
          :disabled="baseSendDisabled || Boolean(pendingLocation)"
          :placeholder="__('Введите сообщение...')"
          @keydown.enter.stop="sendOnEnter"
          @update:modelValue="handleComposerInput"
          @paste.stop="handleComposerPaste"
        />
        <ComposerAttachments
          v-if="!preparedHandoff"
          ref="composerAttachments"
          :supportsAttachments="selectedCapabilities.supports_attachments"
          :channelType="selectedChannelType"
          :maxFiles="selectedCapabilities.max_attachment_count"
          :conversation="selectedConversation?.name || ''"
          :disabled="
            baseSendDisabled || voiceActive || Boolean(pendingLocation)
          "
          @change="pendingAttachments = $event"
        />
        <div
          v-if="pendingLocation"
          class="mb-2 flex items-center justify-between rounded-md border border-outline-gray-2 bg-surface-gray-1 px-3 py-2 text-sm"
        >
          <span class="tabular-nums">
            {{ pendingLocation.latitude.toFixed(6) }},
            {{ pendingLocation.longitude.toFixed(6) }}
          </span>
          <Button
            variant="ghost"
            icon="x"
            :aria-label="__('Удалить геопозицию')"
            @click="pendingLocation = null"
          />
        </div>
        <ComposerVoiceRecorder
          v-if="!preparedHandoff && selectedCapabilities.voice.send"
          ref="voiceRecorder"
          :conversation="selectedConversation?.name || ''"
          :channel="selectedChannel"
          reference-doctype="CRM Lead"
          :reference-name="props.leadName"
          :reply-to-message="replyTarget?.name || ''"
          :disabled="
            baseSendDisabled ||
            Boolean(pendingAttachments.length) ||
            Boolean(pendingLocation)
          "
          :show-trigger="false"
          :max-duration-seconds="
            selectedCapabilities.voice.max_duration_seconds
          "
          :max-size-bytes="selectedCapabilities.voice.max_size_bytes"
          :scope-key="voiceScopeKey"
          @active-change="voiceActive = $event"
          @queued="voiceQueued"
        />
        <div
          v-if="!preparedHandoff && handoffChannelOptions.length"
          class="mb-2 grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto]"
        >
          <FormControl
            v-model="handoffTargetChannel"
            type="select"
            :options="handoffChannelOptions"
            :disabled="handoffLoading || sendingMessage || voiceActive"
            :placeholder="__('Перейти в другой мессенджер')"
          />
          <Button
            :label="__('Подготовить переход')"
            :loading="handoffLoading"
            :disabled="
              !handoffTargetChannel ||
              !selectedConversation ||
              sendingMessage ||
              voiceActive
            "
            @click="prepareHandoff"
          />
        </div>
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div class="min-w-0 flex-1 basis-40 text-sm text-ink-gray-5">
            <div class="truncate">{{ composerHint }}</div>
          </div>
          <div class="ml-auto flex flex-wrap items-center justify-end gap-2">
            <Button
              v-if="!preparedHandoff && selectedCapabilities.voice.send"
              variant="ghost"
              icon="mic"
              :aria-label="__('Записать голосовое сообщение')"
              :disabled="
                baseSendDisabled ||
                voiceActive ||
                Boolean(pendingAttachments.length) ||
                Boolean(pendingLocation)
              "
              @click="voiceRecorder?.start()"
            />
            <Button
              v-if="!preparedHandoff && selectedCapabilities.location.send"
              variant="ghost"
              icon="map-pin"
              :aria-label="__('Добавить геопозицию')"
              :disabled="
                baseSendDisabled ||
                voiceActive ||
                Boolean(pendingAttachments.length) ||
                Boolean(draftText.trim()) ||
                Boolean(replyTarget)
              "
              @click="locationPickerOpen = true"
            />
            <Button
              v-if="
                !preparedHandoff && selectedCapabilities.supports_attachments
              "
              variant="ghost"
              icon="paperclip"
              :disabled="
                baseSendDisabled ||
                voiceActive ||
                Boolean(pendingLocation) ||
                pendingAttachments.length >=
                  selectedCapabilities.max_attachment_count
              "
              @click="composerAttachments?.openFileSelector()"
            />
            <Button
              variant="solid"
              :label="__('Отправить')"
              iconLeft="send"
              :loading="sendingMessage"
              :disabled="
                sendDisabled ||
                voiceActive ||
                (!preparedHandoff &&
                  !draftText.trim() &&
                  !pendingAttachments.length &&
                  !pendingLocation)
              "
              @click="sendMessage"
            />
          </div>
        </div>
      </div>
      <div v-else class="border-t px-4 py-4 text-sm text-ink-gray-5 sm:px-10">
        {{ __('Только чтение') }}
      </div>
    </div>
    <LocationPickerDialog
      v-model="locationPickerOpen"
      :location="pendingLocation"
      @select="selectLocation"
    />
  </div>
</template>

<script setup>
import CommentIcon from '@/components/Icons/CommentIcon.vue'
import LoadingIndicator from '@/components/Icons/LoadingIndicator.vue'
import AttachmentRenderer from '@/components/LeadMessenger/AttachmentRenderer.vue'
import ComposerAttachments from '@/components/LeadMessenger/ComposerAttachments.vue'
import ComposerVoiceRecorder from '@/components/LeadMessenger/ComposerVoiceRecorder.vue'
import LocationPickerDialog from '@/components/LeadMessenger/LocationPickerDialog.vue'
import MessageContent from '@/components/LeadMessenger/MessageContent.vue'
import MessageFooterMetadata from '@/components/LeadMessenger/MessageFooterMetadata.vue'
import MessageForwardStack from '@/components/LeadMessenger/MessageForwardStack.vue'
import MessageMetadata from '@/components/LeadMessenger/MessageMetadata.vue'
import MessageReactions from '@/components/LeadMessenger/MessageReactions.vue'
import MessageReplyQuote from '@/components/LeadMessenger/MessageReplyQuote.vue'
import { globalStore } from '@/stores/global'
import { usersStore } from '@/stores/users'
import {
  buildMessengerMessageItems,
  buildMessengerChannelOptions,
  getMessengerChannelType,
  getMessengerCapabilities,
  getMessengerConversationNotice,
  getMessengerDeliveryState,
  getMessengerPlatformLabel,
  shouldShowMessengerText,
} from '@/utils/messengerChannels'
import {
  getSingleImageBubbleWidthClass,
  isSingleImageAttachmentSet,
  isSingleLocationAttachmentSet,
  isSingleStickerAttachmentSet,
} from '@/utils/messengerAttachments'
import {
  countNewMessengerMessages,
  createMessengerSyncController,
} from '@/utils/messengerSync'
import { isVideoFile, validateComposerFileMix } from '@/utils/messengerComposer'
import {
  getForwardedContentKind,
  isStickerOnlyForwardContext,
} from '@/utils/messengerForwarding'
import { createMessengerReadController } from '@/utils/messengerRead'
import { createMessengerTypingController } from '@/utils/messengerTyping'
import { getMessengerClientDisplayName } from '@/utils/messengerClientIdentity'
import {
  createMessengerMessageActions,
  openMessengerMessageEditor,
} from '@/utils/messengerMessageActions'
import {
  messengerConversationOption,
  messengerConversationsForChannel,
  resolveMessengerHandoffAction,
  resolveMessengerConversationSelection,
  resolveMessengerReplyConversation,
} from '@/utils/messengerRouting'
import {
  isMessengerViewportNearBottom,
  shouldFollowMessengerTyping,
} from '@/utils/messengerViewport'
import { Button, FormControl, Textarea, call, toast } from 'frappe-ui'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

const props = defineProps({
  leadName: { type: String, required: true },
  lead: { type: Object, default: () => ({}) },
  phone: { type: String, default: '' },
  active: { type: Boolean, default: true },
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
const selectedConversationName = ref('')
const handoffTargetChannel = ref('')
const handoffLoading = ref(false)
const handoffCancelling = ref(false)
const preparedHandoff = ref(null)
const draftText = ref('')
const clientRequestId = ref('')
const clientRequestFingerprint = ref('')
const pendingAttachments = ref([])
const pendingLocation = ref(null)
const locationPickerOpen = ref(false)
const voiceActive = ref(false)
const sendWarning = ref('')
const genericError = ref('')
const permissions = ref({
  can_read: false,
  can_operate: false,
  can_administer: false,
})
const messagesEl = ref(null)
const newMessageCount = ref(0)
const composerAttachments = ref(null)
const voiceRecorder = ref(null)
const textareaRef = ref(null)
const draggingFiles = ref(false)
const replyTarget = ref(null)
const typingActive = ref(false)
const highlightedMessage = ref('')
const messageActionState = ref({
  editingMessage: '',
  draft: '',
  pendingMessage: '',
  pendingAction: '',
  errors: {},
})
const messageEditorElements = new Map()
const reactionComponents = new Map()
let typingTimer = null
let highlightTimer = null
let preserveComposerScope = false
let notificationReadPending = false
let appliedRouteConversation = ''

const composerTyping = createMessengerTypingController({
  send(conversation) {
    return call('crm_messenger.api.messages.send_typing', { conversation })
  },
})

const { $dialog, $socket } = globalStore()
const { getUser } = usersStore()
const route = useRoute()

const leadPhone = computed(
  () => props.phone || props.lead?.mobile_no || props.lead?.phone || '',
)
const loading = computed(
  () =>
    loadingConversation.value || loadingMessages.value || loadingChannels.value,
)
const conversationCandidates = computed(() =>
  messengerConversationsForChannel(conversations.value, selectedChannel.value),
)
const selectedConversation = computed(() => {
  return (
    conversationCandidates.value.find(
      (conversation) => conversation.name === selectedConversationName.value,
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
const conversationNotice = computed(() =>
  getMessengerConversationNotice(selectedConversation.value || {}),
)
const missingPhone = computed(
  () =>
    Boolean(selectedChannelType.value) &&
    selectedCapabilities.value.requires_phone &&
    !leadPhone.value,
)
const needsConversationChoice = computed(
  () => conversationCandidates.value.length > 1 && !selectedConversation.value,
)
const selectedRequiresInbound = computed(
  () =>
    selectedCapabilities.value.requires_inbound &&
    !conversationCandidates.value.length &&
    !selectedConversation.value?.external_chat_id,
)
const baseSendDisabled = computed(
  () =>
    !permissions.value.can_operate ||
    sendingMessage.value ||
    missingPhone.value ||
    selectedRequiresInbound.value ||
    needsConversationChoice.value ||
    conversationNotice.value.blocksSend ||
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
      maxAttachmentCount: selectedCapabilities.value.max_attachment_count,
    }).error || ''
  )
})
const channelOptions = computed(() =>
  buildMessengerChannelOptions(channels.value),
)
const conversationOptions = computed(() =>
  conversationCandidates.value.map(messengerConversationOption),
)
const handoffChannelOptions = computed(() =>
  buildMessengerChannelOptions(
    channels.value.filter((channel) => channel.name !== selectedChannel.value),
  ),
)
const messageItems = computed(() => buildMessengerMessageItems(messages.value))
const videoPlaybackScope = computed(
  () =>
    `${props.leadName}:${selectedConversation.value?.name || ''}:${props.active}`,
)
const voiceScopeKey = computed(
  () =>
    `${props.leadName}:${selectedChannel.value}:${
      selectedConversation.value?.name || ''
    }:${props.active}`,
)
const clientDisplayName = computed(() =>
  getMessengerClientDisplayName({
    lead: props.lead,
    conversation: selectedConversation.value,
  }),
)
const contactLine = computed(() => {
  return leadPhone.value
    ? `${clientDisplayName.value} · ${leadPhone.value}`
    : clientDisplayName.value
})
const composerHint = computed(() => {
  if (attachmentMixError.value) return __(attachmentMixError.value)
  if (conversationNotice.value.blocksSend)
    return __(conversationNotice.value.message)
  if (needsConversationChoice.value)
    return __('Выберите конкретный внешний чат.')
  if (selectedRequiresInbound.value) {
    return __('Сначала должно прийти входящее сообщение в выбранном канале.')
  }
  if (missingPhone.value) return __('Добавьте телефон в карточке лида.')
  if (!channels.value.length) return __('Нет доступного канала отправки.')
  if (
    selectedCapabilities.value.video.send_fallback === 'document' &&
    pendingAttachments.value.some((item) => isVideoFile(item.file))
  ) {
    return __(
      'VK отправит видео как документ: получателю потребуется скачать файл; нативного плеера VK не будет.',
    )
  }
  return __('Enter отправляет сообщение, Shift+Enter добавляет новую строку.')
})
const replyComposerContext = computed(() => {
  if (!replyTarget.value) return null
  return {
    message: replyTarget.value.name,
    state: 'available',
    snapshot: {
      version: 1,
      direction: replyTarget.value.direction,
      sender_name: messageSender(replyTarget.value),
      text: `${replyTarget.value.text || ''}`.slice(0, 500) || null,
      message_type: replyTarget.value.message_type || 'text',
      attachment_types: (replyTarget.value.attachments || []).map((item) =>
        item.is_voice ? 'voice' : item.type,
      ),
      forwarded_content_kind: replyTarget.value.forward_context
        ? getForwardedContentKind(replyTarget.value.forward_context)
        : undefined,
    },
  }
})

const messageSync = createMessengerSyncController({
  socket: $socket,
  call,
  visibilityTarget: document,
  onPermissions: applyPermissions,
  onBeforeChange({ kind, messages: currentMessages }) {
    if (kind === 'history') {
      return {
        kind,
        height: messagesEl.value?.scrollHeight || 0,
        top: messagesEl.value?.scrollTop || 0,
      }
    } else if (kind === 'delta') {
      return {
        kind,
        nearBottom: isNearBottom(),
        previousLastMessage: currentMessages.at(-1) || null,
      }
    }
  },
  async onChange(change) {
    messages.value = change.messages
    await nextTick()
    if (change.kind === 'snapshot') {
      scrollToBottom()
    } else if (
      change.kind === 'history' &&
      change.changeSnapshot?.kind === 'history'
    ) {
      let addedHeight =
        (messagesEl.value?.scrollHeight || 0) - change.changeSnapshot.height
      if (messagesEl.value) {
        messagesEl.value.scrollTop = change.changeSnapshot.top + addedHeight
      }
    } else if (change.kind === 'delta' && change.inserted.length) {
      if (change.changeSnapshot?.nearBottom) scrollToBottom()
      else
        newMessageCount.value += countNewMessengerMessages({
          messages: change.messages,
          inserted: change.inserted,
          previousLastMessage: change.changeSnapshot?.previousLastMessage,
        })
    }
    scheduleMessengerNotificationRead()
  },
  onDeltaApplied(_merge, incoming) {
    let hasInbound = incoming.some((message) => message.direction === 'inbound')
    if (
      hasInbound &&
      incoming.some(
        (message) =>
          message.conversation === selectedConversation.value?.name &&
          message.direction === 'inbound',
      )
    ) {
      clearTyping()
    }
    if (
      incoming.some(
        (message) =>
          message.conversation &&
          !conversationByName.value[message.conversation],
      )
    ) {
      loadConversations()
    }
  },
  onError(error) {
    handleError(error, __('Не удалось синхронизировать сообщения.'))
  },
  onTyping(payload) {
    if (payload.conversation !== selectedConversation.value?.name) return
    if (!props.active || document.visibilityState !== 'visible') return
    if (payload.active === false) clearTyping()
    else showTyping(payload.expires_in_ms)
  },
  onConversationStateChanged() {
    loadConversations()
  },
})

const readController = createMessengerReadController({
  call,
  isEnabled: () =>
    permissions.value.can_operate &&
    props.active &&
    document.visibilityState === 'visible' &&
    isNearBottom(),
  getConversation: () => selectedConversation.value,
  getMessages: () => messages.value,
  onConfirmed(result) {
    let conversation = conversations.value.find(
      (item) => item.name === result.conversation,
    )
    if (conversation) conversation.unread_count = result.unread_count
  },
  onError(error) {
    toast.error(
      __(error?.message || 'Не удалось отметить сообщения прочитанными.'),
    )
  },
})

const messageActions = createMessengerMessageActions({
  call,
  sync: () => messageSync.syncDelta(),
  onChange(state) {
    messageActionState.value = state
  },
  onError(message) {
    toast.error(__(message))
  },
})

function setEditorElement(messageName, element) {
  if (element) messageEditorElements.set(messageName, element)
  else messageEditorElements.delete(messageName)
}

function startMessageEdit(message) {
  if (!permissions.value.can_operate) return false
  return openMessengerMessageEditor(message, {
    startEdit: messageActions.startEdit,
    nextTick,
    scrollContainer: () => messagesEl.value,
    getEditorElement: (messageName) => messageEditorElements.get(messageName),
  })
}

onMounted(() => {
  initialize()
  document.addEventListener('visibilitychange', handleVisibilityChange)
})

onBeforeUnmount(() => {
  resetComposer()
  messageSync.stop()
  readController.stop()
  clearTyping()
  clearTimeout(highlightTimer)
  composerTyping.reset()
  document.removeEventListener('visibilitychange', handleVisibilityChange)
})

watch(
  () => props.leadName,
  () => initialize(true),
)

watch(
  () => selectedCapabilities.value.location.send,
  (supported) => {
    if (supported) return
    pendingLocation.value = null
    locationPickerOpen.value = false
  },
)

async function initialize(leadChanged = false) {
  genericError.value = ''
  sendWarning.value = ''
  newMessageCount.value = 0
  loadingMessages.value = true
  if (leadChanged) {
    await resetComposer()
    applyPermissions()
    messages.value = []
    conversations.value = []
    selectedChannel.value = ''
    selectedConversationName.value = ''
    handoffTargetChannel.value = ''
    messageEditorElements.clear()
  }
  try {
    await Promise.all([
      loadChannels(),
      loadConversations(),
      leadChanged
        ? messageSync.setLead(props.leadName)
        : messageSync.start(props.leadName),
    ])
    scheduleMessengerNotificationRead()
  } catch (error) {
    handleError(error, __('Не удалось загрузить сообщения.'))
  } finally {
    loadingMessages.value = false
  }
}

function confirmDeleteMessage(message) {
  if (
    !permissions.value.can_operate ||
    !message?.can_delete ||
    messageActionState.value.pendingMessage
  )
    return
  $dialog({
    title: __('Удалить сообщение для всех?'),
    message: __(
      'Сообщение будет удалено у всех участников. В CRM останется отметка об удалении.',
    ),
    actions: [
      {
        label: __('Удалить для всех'),
        variant: 'solid',
        theme: 'red',
        onClick: async (close) => {
          if (await messageActions.deleteMessage(message)) close()
        },
      },
    ],
  })
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
      reference_doctype: 'CRM Lead',
      reference_name: props.leadName,
    })
    if (!result?.ok)
      throw new Error(result?.message || __('Не удалось загрузить каналы.'))
    channels.value = result.channels || []
    applyPermissions(result.permissions)
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
    applyPermissions(result.permissions)
    ensureSelectedChannel()
    applyRequestedConversation()
  } catch (error) {
    handleError(error, __('Не удалось загрузить переписку.'))
  } finally {
    loadingConversation.value = false
  }
}

function ensureSelectedChannel() {
  if (!selectedChannel.value || !channelByName.value[selectedChannel.value]) {
    selectedChannel.value =
      conversations.value.find((row) => row.channel)?.channel ||
      channels.value[0]?.name ||
      ''
  }
  ensureSelectedConversation()
}

function ensureSelectedConversation() {
  let resolved = resolveMessengerConversationSelection({
    conversations: conversations.value,
    channel: selectedChannel.value,
    selectedConversation: selectedConversationName.value,
  })
  selectedConversationName.value = resolved.conversation?.name || ''
}

function applyRequestedConversation() {
  let requested = `${route.query.messenger_conversation || ''}`
  if (!requested || requested === appliedRouteConversation) return
  let conversation = conversations.value.find((row) => row.name === requested)
  if (!conversation) return
  selectedChannel.value = conversation.channel
  selectedConversationName.value = conversation.name
  appliedRouteConversation = requested
}

function handleComposerInput(value) {
  composerTyping.input({
    text: value,
    conversation: selectedConversation.value?.name,
    enabled:
      props.active &&
      document.visibilityState === 'visible' &&
      selectedCapabilities.value.typing.send &&
      !baseSendDisabled.value &&
      !voiceActive.value &&
      !pendingAttachments.value.length,
  })
}

async function sendMessage() {
  if (!permissions.value.can_operate) return
  let handoff = preparedHandoff.value
  let text = handoff?.message || draftText.value.trim()
  if (
    voiceActive.value ||
    (!text && !pendingAttachments.value.length && !pendingLocation.value) ||
    sendDisabled.value
  )
    return

  if (
    pendingLocation.value &&
    (text || pendingAttachments.value.length || replyTarget.value)
  ) {
    genericError.value = __(
      'Геолокацию можно отправить только отдельным сообщением.',
    )
    return
  }

  genericError.value = ''
  sendWarning.value = ''
  sendingMessage.value = true
  let attachmentNames = composerAttachments.value?.freeze() || []
  let accepted = false

  try {
    let conversation = await resolveConversationForSend()
    if (!conversation?.name) return

    let fingerprint = JSON.stringify({
      conversation: conversation.name,
      channel: selectedChannel.value,
      text,
      attachments: attachmentNames,
      location: pendingLocation.value,
      reply: replyTarget.value?.name || '',
    })
    if (
      !clientRequestId.value ||
      clientRequestFingerprint.value !== fingerprint
    ) {
      clientRequestId.value = makeClientRequestId()
      clientRequestFingerprint.value = fingerprint
    }
    let result = await call('crm_messenger.api.messages.send_message', {
      conversation: conversation.name,
      text,
      channel: selectedChannel.value,
      client_request_id: clientRequestId.value,
      handoff: handoff?.handoff || undefined,
      attachments: attachmentNames,
      location: pendingLocation.value || undefined,
      reply_to_message: replyTarget.value?.name || undefined,
      reference_doctype: 'CRM Lead',
      reference_name: props.leadName,
    })
    accepted = Boolean(result?.name)
    if (accepted) {
      composerTyping.reset()
      draftText.value = ''
      composerAttachments.value?.release()
      pendingLocation.value = null
      clientRequestId.value = ''
      clientRequestFingerprint.value = ''
      cancelReply()
    }

    if (result?.name && handoff) preparedHandoff.value = null
    if (result?.reason === 'not_configured') {
      clientRequestId.value = ''
      clientRequestFingerprint.value = ''
      cancelReply()
      sendWarning.value = integrationWarningMessage(result)
      toast.error(sendWarning.value)
    } else if (!result?.ok) {
      clientRequestId.value = ''
      clientRequestFingerprint.value = ''
      if (
        handoff &&
        ['handoff_revoked', 'handoff_expired', 'handoff_consumed'].includes(
          result?.reason,
        )
      )
        preparedHandoff.value = null
      throw new Error(result?.message || __('Не удалось отправить сообщение.'))
    } else {
      composerTyping.reset()
    }
  } catch (error) {
    handleError(error, __('Не удалось отправить сообщение.'))
  } finally {
    if (!accepted) composerAttachments.value?.unfreeze()
    sendingMessage.value = false
    await Promise.all([loadConversations(), messageSync.syncDelta()])
  }
}

async function resolveConversationForSend() {
  if (selectedConversation.value && !replyTarget.value)
    return selectedConversation.value

  let result = await call(
    'crm_messenger.api.conversations.resolve_send_target',
    {
      reference_doctype: 'CRM Lead',
      reference_name: props.leadName,
      channel: selectedChannel.value,
      reply_to_message: replyTarget.value?.name || undefined,
    },
  )
  if (result?.ok && result.conversation?.name) {
    preserveComposerDuringScopeChange(() => {
      selectedChannel.value =
        result.conversation.channel ||
        result.channel?.name ||
        selectedChannel.value
      selectedConversationName.value = result.conversation.name
    })
    return (
      conversations.value.find(
        (conversation) => conversation.name === result.conversation.name,
      ) || result.conversation
    )
  }
  if (result?.reason === 'missing_channel_conversation' && result.can_create)
    return createConversation()

  genericError.value =
    result?.reason === 'ambiguous_conversation'
      ? __('Выберите конкретный внешний чат.')
      : result?.message ||
        __('Для выбранного канала ещё нет переписки с этим лидом.')
  return null
}

async function prepareHandoff() {
  if (!permissions.value.can_operate) return
  if (!handoffTargetChannel.value || !selectedConversation.value) return
  genericError.value = ''
  let handoffAction = resolveMessengerHandoffAction(
    conversations.value,
    handoffTargetChannel.value,
  )
  if (handoffAction.state === 'switch') {
    selectedChannel.value = handoffTargetChannel.value
    selectedConversationName.value = handoffAction.conversation.name
    handoffTargetChannel.value = ''
    toast.success(__('Переключились на существующий внешний чат.'))
    return
  }
  if (handoffAction.state === 'ambiguous') {
    selectedChannel.value = handoffTargetChannel.value
    selectedConversationName.value = ''
    handoffTargetChannel.value = ''
    genericError.value = __('Выберите конкретный внешний чат.')
    return
  }
  if (
    draftText.value.trim() ||
    pendingAttachments.value.length ||
    pendingLocation.value ||
    replyTarget.value
  ) {
    genericError.value = __(
      'Очистите текущий черновик и вложения перед подготовкой перехода.',
    )
    return
  }

  handoffLoading.value = true
  try {
    let result = await call('crm_messenger.api.handoffs.create_handoff', {
      reference_name: props.leadName,
      source_conversation: selectedConversation.value.name,
      target_channel: handoffTargetChannel.value,
    })
    if (!result?.ok)
      throw new Error(result?.message || __('Не удалось подготовить переход.'))
    preparedHandoff.value = {
      handoff: result.handoff,
      message: result.message || '',
      sourceConversation: selectedConversation.value.name,
      targetChannel: result.target_channel,
      expiresAt: result.expires_at,
    }
    handoffTargetChannel.value = ''
  } catch (error) {
    handleError(error, __('Не удалось подготовить переход.'))
  } finally {
    handoffLoading.value = false
  }
}

async function cancelPreparedHandoff() {
  if (!preparedHandoff.value || handoffCancelling.value) return
  genericError.value = ''
  handoffCancelling.value = true
  try {
    let result = await call('crm_messenger.api.handoffs.revoke_handoff', {
      handoff: preparedHandoff.value.handoff,
    })
    if (!result?.ok)
      throw new Error(result?.message || __('Не удалось отменить переход.'))
    preparedHandoff.value = null
    clientRequestId.value = ''
    clientRequestFingerprint.value = ''
    nextTick(() => textareaRef.value?.el?.focus?.())
  } catch (error) {
    handleError(error, __('Не удалось отменить переход.'))
  } finally {
    handoffCancelling.value = false
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
  if (conversation?.name) {
    preserveComposerDuringScopeChange(() => {
      selectedConversationName.value = conversation.name
    })
  }
  return conversation
}

function makeClientRequestId() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID()
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function sendOnEnter(event) {
  if (event.isComposing || event.shiftKey) return
  event.preventDefault()
  sendMessage()
}

function handleComposerPaste(event) {
  if (baseSendDisabled.value || voiceActive.value || pendingLocation.value)
    return
  composerAttachments.value?.handlePaste(event)
}

function handleComposerDragOver(event) {
  if (preparedHandoff.value) return
  if (baseSendDisabled.value || voiceActive.value || pendingLocation.value)
    return
  if (!Array.from(event.dataTransfer?.types || []).includes('Files')) return
  event.preventDefault()
  draggingFiles.value = true
}

function handleComposerDrop(event) {
  if (preparedHandoff.value) return
  draggingFiles.value = false
  if (baseSendDisabled.value || voiceActive.value || pendingLocation.value)
    return
  composerAttachments.value?.handleDrop(event)
}

async function voiceQueued() {
  cancelReply()
  await Promise.all([loadConversations(), messageSync.syncDelta()])
}

function scrollToBottom() {
  if (!messagesEl.value) return
  messagesEl.value.scrollTop = messagesEl.value.scrollHeight
  newMessageCount.value = 0
  readController.schedule()
  scheduleMessengerNotificationRead()
}

function isNearBottom() {
  return isMessengerViewportNearBottom(messagesEl.value)
}

async function handleMessagesScroll() {
  if (isNearBottom()) {
    newMessageCount.value = 0
    readController.schedule()
    scheduleMessengerNotificationRead()
  }
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

function startReply(message) {
  if (
    !permissions.value.can_operate ||
    !message?.can_reply ||
    messageActionState.value.pendingMessage
  )
    return
  if (pendingLocation.value) {
    genericError.value = __('Удалите геолокацию перед подготовкой ответа.')
    return
  }
  let conversation = resolveMessengerReplyConversation(
    conversations.value,
    message,
  )
  if (!conversation) {
    genericError.value = __(
      'Не удалось определить внешний чат исходного сообщения.',
    )
    return
  }
  resetComposer()
  preserveComposerDuringScopeChange(() => {
    selectedChannel.value = conversation.channel
    selectedConversationName.value = conversation.name
  })
  replyTarget.value = message
  nextTick(() => textareaRef.value?.el?.focus?.())
}

function cancelReply() {
  replyTarget.value = null
}

function selectLocation(location) {
  if (
    draftText.value.trim() ||
    pendingAttachments.value.length ||
    replyTarget.value
  ) {
    genericError.value = __(
      'Геолокацию можно отправить только отдельным сообщением.',
    )
    return
  }
  pendingLocation.value = location
}

function retryMessage(message) {
  if (
    !permissions.value.can_operate ||
    !message?.can_retry ||
    messageActionState.value.pendingMessage
  )
    return
  if (!message.retry_requires_confirmation) {
    messageActions.retryMessage(message)
    return
  }
  $dialog({
    title: __('Повторить отправку?'),
    message: __(
      'VK мог уже принять сообщение. Повторная отправка использует тот же идентификатор запроса.',
    ),
    actions: [
      {
        label: __('Повторить отправку'),
        variant: 'solid',
        onClick: async (close) => {
          if (await messageActions.retryMessage(message, true)) close()
        },
      },
    ],
  })
}

async function navigateToReply(messageName) {
  if (!messageName) return
  if (!messages.value.some((item) => item.name === messageName)) {
    try {
      let result = await call('crm_messenger.api.messages.get_message', {
        message: messageName,
      })
      if (
        !result?.ok ||
        result.message?.conversation !== selectedConversation.value?.name
      )
        return
      messageSync.mergeExternal(result.message)
    } catch (error) {
      handleError(error, __('Не удалось загрузить исходное сообщение.'))
      return
    }
  }
  await nextTick()
  let selector = `[data-message-id="${CSS.escape(messageName)}"]`
  let element = messagesEl.value?.querySelector(selector)
  element?.scrollIntoView?.({ behavior: 'smooth', block: 'center' })
  highlightedMessage.value = messageName
  clearTimeout(highlightTimer)
  highlightTimer = setTimeout(() => (highlightedMessage.value = ''), 1400)
}

async function showTyping(expiresInMs = 6000) {
  let followTyping = shouldFollowMessengerTyping({
    active: true,
    wasNearBottom: isNearBottom(),
  })
  typingActive.value = true
  clearTimeout(typingTimer)
  typingTimer = setTimeout(
    clearTyping,
    Math.min(Math.max(Number(expiresInMs) || 6000, 1000), 15000),
  )
  if (followTyping) {
    await nextTick()
    scrollToBottom()
  }
}

function clearTyping() {
  clearTimeout(typingTimer)
  typingTimer = null
  typingActive.value = false
}

function handleVisibilityChange() {
  if (document.visibilityState !== 'visible') {
    clearTyping()
    composerTyping.reset()
  } else {
    readController.schedule()
    scheduleMessengerNotificationRead()
  }
}

async function markMessengerNotificationsRead() {
  if (
    notificationReadPending ||
    !props.active ||
    document.visibilityState !== 'visible' ||
    !selectedConversation.value?.name ||
    !isNearBottom()
  )
    return
  let lastInbound = messages.value
    .filter(
      (message) =>
        message.conversation === selectedConversation.value.name &&
        message.direction === 'inbound' &&
        message.status !== 'deleted' &&
        message.ingest_source !== 'provider_history',
    )
    .at(-1)
  if (!lastInbound?.name) return
  notificationReadPending = true
  try {
    await call('crm.api.notifications.mark_messenger_as_read', {
      conversation: selectedConversation.value.name,
      last_event_id: lastInbound.name,
    })
  } catch {
    // Notifications are auxiliary and must not interrupt the conversation UI.
  } finally {
    notificationReadPending = false
  }
}

function scheduleMessengerNotificationRead() {
  nextTick(() => markMessengerNotificationsRead())
}

watch(
  () => props.active,
  (active) => {
    if (!active) {
      clearTyping()
      composerTyping.reset()
    } else {
      readController.schedule()
      scheduleMessengerNotificationRead()
    }
  },
)

watch(
  () => route.query.messenger_conversation,
  () => {
    appliedRouteConversation = ''
    applyRequestedConversation()
  },
)

watch(
  () => selectedConversation.value?.name,
  (conversationName, previousConversation) => {
    if (
      previousConversation !== undefined &&
      conversationName !== previousConversation &&
      !preserveComposerScope
    )
      resetComposer()
    composerTyping.reset()
    if (
      replyTarget.value &&
      replyTarget.value.conversation !== conversationName
    )
      cancelReply()
    clearTyping()
    readController.reset()
    readController.schedule()
  },
)

watch(
  () => selectedChannel.value,
  (channel, previousChannel) => {
    if (
      previousChannel !== undefined &&
      channel !== previousChannel &&
      !preserveComposerScope
    )
      resetComposer()
    composerTyping.reset()
    ensureSelectedConversation()
    handoffTargetChannel.value = ''
  },
)

watch(
  () => [voiceActive.value, pendingAttachments.value.length],
  ([recording, attachmentCount]) => {
    if (recording || attachmentCount) composerTyping.reset()
  },
)

function messageSender(message) {
  if (message.direction === 'outbound')
    return message.crm_user
      ? getUser(message.crm_user)?.full_name || __('Оператор')
      : __('Оператор')
  return clientDisplayName.value
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

function messageBubbleWidthClass(message) {
  if (isSingleStickerAttachmentSet(message.attachments)) {
    return 'w-[14.5rem] !max-w-[94%] sm:!max-w-[14.5rem]'
  }
  if (isStickerOnlyForwardContext(message.forward_context)) {
    return 'w-64 !max-w-[94%] sm:!max-w-64'
  }
  if (isSingleLocationAttachmentSet(message.attachments)) {
    return 'w-[21.5rem] !max-w-[94%] sm:!max-w-[21.5rem]'
  }
  if (!isSingleImageAttachmentSet(message.attachments)) return 'w-fit'
  return getSingleImageBubbleWidthClass(message.attachments[0])
}

function messageFailureReason(message) {
  return message.failure_reason || message.error || ''
}

function messageFailed(message) {
  return message.direction === 'outbound'
    ? getMessengerDeliveryState(message) === 'failed'
    : message.status === 'failed'
}

function handleReactionsChanged(message, reactionState) {
  message.reactions = reactionState
  messageSync.syncDelta().catch(() => {})
}

function setReactionComponent(messageName, component) {
  if (component) reactionComponents.set(messageName, component)
  else reactionComponents.delete(messageName)
}

function openReactionPicker(message, event) {
  if (message.status === 'deleted') return
  if (!permissions.value.can_operate || !message.can_react) return
  if (reactionComponents.get(message.name)?.openPicker(event))
    event.preventDefault()
}

function applyPermissions(value = {}) {
  let next = {
    can_read: Boolean(value?.can_read),
    can_operate: Boolean(value?.can_operate),
    can_administer: Boolean(value?.can_administer),
  }
  let lostOperatorAccess = permissions.value.can_operate && !next.can_operate
  permissions.value = next
  if (!lostOperatorAccess) return

  for (let message of messages.value) {
    message.can_reply = false
    message.can_edit = false
    message.can_delete = false
    message.can_retry = false
    message.can_react = false
  }
  resetComposer()
}

function preserveComposerDuringScopeChange(change) {
  preserveComposerScope = true
  change()
  nextTick(() => {
    preserveComposerScope = false
  })
}

async function resetComposer() {
  let handoff = preparedHandoff.value
  preparedHandoff.value = null
  draftText.value = ''
  pendingLocation.value = null
  locationPickerOpen.value = false
  handoffTargetChannel.value = ''
  clientRequestId.value = ''
  clientRequestFingerprint.value = ''
  draggingFiles.value = false
  sendWarning.value = ''
  cancelReply()
  clearTyping()
  composerTyping.reset()
  voiceRecorder.value?.reset?.()
  messageActions.cancelEdit()
  let cleanup = composerAttachments.value?.discard?.()
  let revoke = handoff?.handoff
    ? call('crm_messenger.api.handoffs.revoke_handoff', {
        handoff: handoff.handoff,
      })
    : null
  await Promise.allSettled([cleanup, revoke].filter(Boolean))
}

function messageStatusNoteClass(message) {
  let status =
    message?.direction === 'outbound'
      ? getMessengerDeliveryState(message)
      : message?.status
  return ['failed', 'unknown'].includes(status)
    ? 'text-ink-red-8'
    : 'text-ink-gray-5'
}

function handleError(error, fallback) {
  let message = error?.messages?.[0] || error?.message || fallback
  genericError.value = __(message)
  toast.error(genericError.value)
}
</script>
