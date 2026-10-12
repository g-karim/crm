<template>
  <SettingsLayoutBase
    :title="__('Message Channels')"
    :description="
      __(
        'Connect Telegram, VK, MAX, Avito, WhatsApp, and other channels, and reply to customers from lead records.',
      )
    "
  >
    <template #header-actions>
      <div class="flex items-center gap-2">
        <Button
          :label="__('Save Settings')"
          variant="subtle"
          :disabled="!settingsDirty"
          :loading="savingSettings"
          @click="saveGlobalSettings"
        />
        <Button
          :label="__('New Channel')"
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
                {{ __('Messaging') }}
              </div>
              <div class="mt-1 text-p-sm text-ink-gray-5">
                {{
                  __(
                    'Controls incoming and outgoing messages for all connected channels.',
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
                {{ __('Create leads from new conversations') }}
              </div>
              <div class="mt-1 text-p-sm text-ink-gray-5">
                {{
                  __(
                    'Create a new lead when an incoming conversation is not linked to CRM.',
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
                {{ __('Store detailed webhook payloads') }}
              </div>
              <div class="mt-1 text-p-sm text-ink-gray-5">
                {{
                  __(
                    'Applies only to future events. Detailed payloads can contain message text and customer personal data; secrets are always redacted. Enable only for diagnostics.',
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
            {{ __('Webhooks') }}
          </button>
          <div
            v-if="showAdvanced"
            class="mt-3 grid grid-cols-1 gap-4 rounded-lg border border-outline-gray-1 p-4 md:grid-cols-2"
          >
            <FormControl
              v-model="settings.webhook_secret"
              type="password"
              :label="__('Shared Webhook Secret')"
              :placeholder="
                secretPlaceholder(settings.webhook_secret_configured)
              "
              :description="__('Leave blank to keep the current secret.')"
            />
          </div>
        </section>

        <section class="min-h-0">
          <div class="mb-3 flex items-end justify-between">
            <div>
              <h3 class="text-lg-semibold text-ink-gray-8">
                {{ __('Connected Channels') }}
              </h3>
              <p class="mt-1 text-p-sm text-ink-gray-5">
                {{
                  __('Each channel represents one account, community, or bot.')
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
            v-if="loadError"
            class="flex flex-col items-center rounded-lg border border-dashed border-outline-gray-2 px-6 py-12 text-center"
          >
            <div class="text-base-medium text-ink-red-3">
              {{ __('Could not load message channel settings.') }}
            </div>
            <Button
              class="mt-4"
              :label="__('Try Again')"
              variant="subtle"
              @click="loadSettings(true, true)"
            />
          </div>

          <div
            v-else-if="!visibleChannels.length"
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
              {{ __('No channels yet') }}
            </div>
            <div class="mt-1 max-w-md text-p-sm text-ink-gray-5">
              {{ __('Select a messenger and complete its connection.') }}
            </div>
            <Button
              class="mt-4"
              :label="__('Create Channel')"
              variant="solid"
              @click="openNewChannel"
            />
          </div>

          <div
            v-else
            class="overflow-hidden rounded-lg border border-outline-gray-1"
          >
            <button
              v-for="(channel, index) in visibleChannels"
              :key="channel.name"
              type="button"
              class="flex w-full items-center gap-4 px-4 py-3 text-left hover:bg-surface-gray-1"
              :class="index && 'border-t border-outline-gray-1'"
              @click="openChannel(channel)"
            >
              <div
                class="flex size-9 shrink-0 items-center justify-center rounded-lg bg-surface-gray-2 text-sm-medium text-ink-gray-7"
              >
                {{ providerInitial(channel) }}
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
    :dismissible="!partnerBusy"
    :show-close-button="!partnerBusy"
    :options="{
      title: channelDraft.channel ? __('Channel Settings') : __('New Channel'),
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
              {{ localizedProviderLabel(channelDraft.provider) }}
            </div>
          </div>
          <Badge
            :label="__(draftChannelState.label)"
            :theme="draftChannelState.theme"
            variant="outline"
          />
        </div>

        <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
          <FormControl
            :model-value="channelDraft.provider"
            type="select"
            required
            :disabled="Boolean(channelDraft.channel) || partnerBusy"
            :options="providerOptions"
            :label="__('Provider')"
            @update:modelValue="changeProvider"
          />
          <FormControl
            v-model="channelDraft.custom_display_name"
            type="text"
            :label="__('Channel Name')"
            :placeholder="__('For example, Sales')"
            :disabled="
              isPartnerDraft && (partnerBusy || Boolean(channelDraft.channel))
            "
          />

          <FormControl
            v-if="channelDraft.provider === 'wazzup'"
            v-model="channelDraft.platform"
            type="select"
            required
            :options="wazzupPlatforms"
            :label="__('Platform')"
          />
          <FormControl
            v-if="channelDraft.provider === 'wazzup'"
            v-model="channelDraft.provider_channel_id"
            type="text"
            required
            :label="__('Channel ID')"
            :placeholder="__('Wazzup channel UUID')"
            :description="
              __('Use channelId from Wazzup, not a phone number or username.')
            "
          />

          <FormControl
            v-if="
              channelDraft.provider === 'wazzup' &&
              !channelDraft.channel &&
              wazzupKeySources.length > 1
            "
            v-model="channelDraft.api_token_source_channel"
            type="select"
            :options="wazzupKeySources"
            :label="__('API key source')"
            :description="
              __(
                'The saved key is reused securely without displaying it. An entered API key takes priority.',
              )
            "
          />

          <FormControl
            v-if="channelDraft.provider === 'vk_direct'"
            v-model="channelDraft.external_account_id"
            type="text"
            required
            :label="__('VK Community')"
            :placeholder="__('Community ID or short name')"
          />

          <FormControl
            v-if="channelDraft.provider === 'avito_direct'"
            v-model="channelDraft.client_id"
            type="text"
            required
            :label="__('Client ID')"
          />

          <FormControl
            v-if="showsApiToken"
            v-model="channelDraft.api_token"
            type="password"
            :required="
              !channelDraft.api_token_configured &&
              !channelDraft.api_token_source_channel
            "
            :label="__(apiTokenLabel)"
            :placeholder="secretPlaceholder(channelDraft.api_token_configured)"
            :description="
              channelDraft.api_token_source_channel
                ? __('Leave blank to use the saved API key.')
                : __('Leave blank to keep the current token.')
            "
          />
          <FormControl
            v-if="channelDraft.provider === 'avito_direct'"
            v-model="channelDraft.client_secret"
            type="password"
            :required="!channelDraft.client_secret_configured"
            :label="__('Client Secret')"
            :placeholder="
              secretPlaceholder(channelDraft.client_secret_configured)
            "
            :description="__('Leave blank to keep the current secret.')"
          />
        </div>

        <WazzupPartnerConnection
          v-if="showChannelDialog && isPartnerDraft"
          :key="channelDraft.provider"
          :channel="partnerChannel"
          :platform="partnerPlatform"
          :display-name="channelDraft.custom_display_name"
          :available="settings.wazzup_partner_available"
          @busy="partnerBusy = $event"
          @updated="updatePartnerChannel"
          @deleted="deletePartnerChannel"
        />

        <section
          v-if="channelDraft.provider === 'wazzup'"
          data-testid="wazzup-settings"
          class="rounded-lg border border-outline-gray-1 bg-surface-gray-1 p-4"
        >
          <div class="text-base-medium text-ink-gray-8">
            {{ __('Wazzup connection') }}
          </div>
          <p class="mt-1 text-p-sm text-ink-gray-5">
            {{
              __(
                'Connect the messenger in Wazzup first, then select its channel here. Telegram uses personal chats; Telegram bots have a separate direct integration.',
              )
            }}
          </p>
          <Button
            class="mt-3"
            :label="__('Load Wazzup channels')"
            variant="subtle"
            :loading="loadingWazzupChannels"
            :disabled="channelBusy || !hasWazzupKey"
            @click="loadWazzupChannels"
          />
          <FormControl
            v-if="wazzupRemoteChannels.length"
            class="mt-3"
            :model-value="channelDraft.provider_channel_id"
            type="select"
            :options="wazzupRemoteChannelOptions"
            :label="__('Available Wazzup channels')"
            @update:modelValue="selectWazzupChannel"
          />
          <p
            v-else-if="wazzupChannelsLoaded"
            class="mt-2 text-p-sm text-ink-gray-5"
          >
            {{
              __(
                'No WhatsApp or personal Telegram channels are available for this API key.',
              )
            }}
          </p>
          <p class="mt-2 text-p-sm text-ink-gray-5">
            {{
              __(
                'Loading channels uses the entered or saved API key without saving changes.',
              )
            }}
          </p>
          <Switch
            v-model="channelDraft.enabled"
            class="mt-4"
            :label="__('Active in CRM')"
            :description="
              __(
                'Allows this channel to send and receive messages in CRM. This switch does not verify the connection.',
              )
            "
          />

          <div
            v-if="channelDraft.channel"
            class="mt-4 border-t border-outline-gray-1 pt-4"
          >
            <div class="flex flex-wrap items-center justify-between gap-2">
              <div class="text-base-medium text-ink-gray-8">
                {{ __('Saved configuration diagnostics') }}
              </div>
              <Button
                :label="__('Check saved configuration')"
                variant="subtle"
                :loading="channelAction === 'wazzup_check'"
                :disabled="channelBusy || channelDirty || settingsDirty"
                @click="checkWazzupChannel"
              />
            </div>
            <p
              v-if="channelDirty || settingsDirty"
              class="mt-2 text-p-sm text-ink-orange-7"
            >
              {{
                __(
                  'Save channel and messaging settings before checking the connection.',
                )
              }}
            </p>
            <p
              v-if="wazzupConnection?.last_checked_at"
              class="mt-2 text-p-sm text-ink-gray-5"
            >
              {{ __('Last checked') }}: {{ wazzupConnection.last_checked_at }}
            </p>
            <dl
              class="mt-3 flex flex-col gap-2"
              data-testid="wazzup-diagnostics"
            >
              <div
                v-for="row in wazzupDiagnosticRows"
                :key="row.key"
                :data-diagnostic="row.key"
                class="flex flex-wrap items-center justify-between gap-2"
              >
                <dt class="text-p-sm text-ink-gray-7">{{ __(row.title) }}</dt>
                <dd
                  class="flex flex-wrap items-center gap-2 text-p-sm text-ink-gray-5"
                >
                  <span v-if="row.received_at"
                    >{{ row.received_at
                    }}<template v-if="row.event_label">
                      · {{ __(row.event_label) }}</template
                    ></span
                  >
                  <Badge
                    :label="__(row.label)"
                    :theme="row.theme"
                    variant="outline"
                  />
                </dd>
              </div>
            </dl>
            <p
              v-if="
                wazzupConnection?.local_config?.integration_enabled === false
              "
              class="mt-2 text-p-sm text-ink-orange-7"
            >
              {{ __('Messaging is disabled in CRM.') }}
            </p>
            <p
              v-if="wazzupConnection?.local_config?.channel_enabled === false"
              class="mt-2 text-p-sm text-ink-gray-5"
            >
              {{ __('This channel is inactive in CRM.') }}
            </p>
            <p
              v-if="wazzupConnection?.remote_event?.received_at"
              class="mt-2 text-p-sm text-ink-gray-5"
            >
              {{ __('Last channel update') }}:
              {{ wazzupConnection.remote_event.received_at }}
            </p>
            <div
              class="mt-3 text-p-sm text-ink-gray-5"
              data-testid="wazzup-queue-diagnostics"
            >
              <template v-if="wazzupOperations">
                <p>
                  {{
                    __('Webhook events: {0} pending, {1} failed.', [
                      wazzupOperations.events_pending,
                      wazzupOperations.events_failed,
                    ])
                  }}
                </p>
                <p>
                  {{
                    __('Attachments: {0} pending, {1} failed.', [
                      wazzupOperations.media_pending,
                      wazzupOperations.media_failed,
                    ])
                  }}
                </p>
              </template>
              <p v-else>{{ __('Operational diagnostics are unavailable.') }}</p>
            </div>
            <p class="mt-3 text-p-sm text-ink-gray-5">
              {{
                __(
                  'API and webhook configuration checks do not prove message delivery. A real incoming message, status, or channel update confirms that CRM received an authenticated event.',
                )
              }}
            </p>
          </div>
          <p class="mt-3 text-p-sm text-ink-gray-5">
            {{
              __(
                'Receiving events requires a public HTTPS CRM address, a saved Shared Webhook Secret, and a Wazzup webhook subscription configured for this CRM. Checking does not change the Wazzup subscription.',
              )
            }}
          </p>
          <p class="mt-2 text-p-sm text-ink-gray-5">
            {{
              __(
                'The Shared Webhook Secret must match the crmKey configured for the Wazzup integration; it is different from the Wazzup API key.',
              )
            }}
          </p>
        </section>

        <section
          v-if="channelDraft.provider === 'avito_direct'"
          class="rounded-lg border border-outline-gray-1 bg-surface-gray-1 p-4"
        >
          <div class="text-base-medium text-ink-gray-8">
            {{ __('Avito chat import') }}
          </div>
          <p class="mt-1 text-p-sm text-ink-gray-5">
            {{
              __(
                'Choose which past chats create leads when the channel connects or this setting is saved. Chats created after connection are processed automatically.',
              )
            }}
          </p>
          <p
            v-if="!settings.auto_create_lead"
            class="mt-2 text-p-sm text-ink-orange-7"
          >
            {{
              __(
                'Turn on Create leads from new conversations above to create Avito leads.',
              )
            }}
          </p>
          <div class="mt-3 grid gap-2">
            <label
              v-for="option in avitoImportOptions"
              :key="option.value"
              class="flex cursor-pointer items-start gap-3 rounded-lg border bg-surface-cards p-3"
              :class="
                channelDraft.avito_import_mode === option.value
                  ? 'border-outline-blue-3'
                  : 'border-outline-gray-2'
              "
            >
              <input
                v-model="channelDraft.avito_import_mode"
                type="radio"
                name="avito-import-mode"
                :value="option.value"
                class="mt-1 accent-blue-600"
              />
              <span>
                <span class="block text-p-medium text-ink-gray-8">{{
                  __(option.label)
                }}</span>
                <span class="mt-0.5 block text-p-sm text-ink-gray-5">{{
                  __(option.description)
                }}</span>
              </span>
            </label>
          </div>
          <div
            v-if="channelDraft.avito_import_mode === 'period'"
            class="mt-4 grid gap-3 md:grid-cols-2"
          >
            <FormControl
              v-model="channelDraft.avito_import_from_date"
              type="date"
              :label="__('From date')"
              data-avito-import-date
              required
            />
            <FormControl
              v-model="channelDraft.avito_import_to_date"
              type="date"
              :label="__('Through date')"
              data-avito-import-date
              required
            />
          </div>
          <p class="mt-3 text-p-sm text-ink-gray-5">
            {{
              __(
                'Dates use the CRM time zone and the chat’s last activity. Available messages from selected chats are loaded. If Avito hides message details, later activity in old chats may remain unverified.',
              )
            }}
          </p>
          <p v-if="channelDraft.channel" class="mt-2 text-p-sm text-ink-gray-5">
            {{
              __(
                'Changing this selection does not remove leads already created from Avito chats.',
              )
            }}
          </p>
          <div
            v-if="
              channelDraft.channel &&
              channelDraft.enabled &&
              ['connected', 'degraded'].includes(channelDraft.state)
            "
            class="mt-4 border-t border-outline-gray-2 pt-3"
          >
            <div class="flex flex-wrap items-center justify-between gap-2">
              <div class="text-p-medium text-ink-gray-8">
                {{ __('Import status') }}
              </div>
              <div class="flex gap-2">
                <Button
                  :label="__('Refresh import status')"
                  variant="subtle"
                  :loading="loadingAvitoImport"
                  @click="loadAvitoImportStatus"
                />
                <Button
                  :label="__('Scan chats now')"
                  variant="subtle"
                  :disabled="channelBusy || channelDirty"
                  :loading="scanningAvitoImport"
                  @click="scanAvitoChats"
                />
              </div>
            </div>
            <p
              v-if="avitoImportStatus"
              data-testid="avito-import-status"
              class="mt-2 text-p-sm text-ink-gray-6"
            >
              {{ __(avitoImportStatusLabel(avitoImportStatus.status)) }}
              <span
                v-if="
                  avitoImportActive && hasAvitoImportCounts(avitoImportStatus)
                "
              >
                ·
                {{
                  __('Chats checked in current scan: {0}', [
                    avitoImportCheckedCount(avitoImportStatus),
                  ])
                }}</span
              >
            </p>
            <p
              v-if="avitoImportStatus?.last_completed_at"
              data-testid="avito-import-completed"
              class="mt-2 text-p-sm text-ink-gray-5"
            >
              {{ __('Last completed scan') }}:
              {{ avitoImportStatus.last_completed_at }}
              <span v-if="avitoImportActive && avitoImportSummary">
                · {{ __(avitoImportStatusLabel(avitoImportSummary.status)) }}
              </span>
            </p>
            <p
              v-if="hasAvitoImportCounts(avitoImportSummary)"
              data-testid="avito-import-counts"
              class="mt-2 text-p-sm text-ink-gray-6"
            >
              {{
                __('Chats checked: {0}', [
                  avitoImportCheckedCount(avitoImportSummary),
                ])
              }}
              <span>
                ·
                {{
                  __('New chats in last scan: {0}', [
                    avitoImportSummary.counts.chat_created || 0,
                  ])
                }}</span
              >
              <span v-if="avitoImportSummary.counts?.chat_unchanged">
                ·
                {{
                  __('Unchanged chats: {0}', [
                    avitoImportSummary.counts.chat_unchanged,
                  ])
                }}</span
              >
              <span v-if="avitoImportSummary.counts?.chat_skipped">
                ·
                {{
                  __('Skipped chats: {0}', [
                    avitoImportSummary.counts.chat_skipped,
                  ])
                }}</span
              >
              <span v-if="avitoImportSummary.counts?.chat_unverified">
                ·
                {{
                  __('Chats awaiting verification: {0}', [
                    avitoImportSummary.counts.chat_unverified,
                  ])
                }}</span
              >
            </p>
            <p
              v-if="avitoImportSummary?.incomplete"
              class="mt-2 text-p-sm text-ink-orange-7"
            >
              {{ __(avitoImportIncompleteMessage(avitoImportSummary)) }}
            </p>
            <p
              v-if="avitoImportRefreshError"
              data-testid="avito-import-refresh-error"
              class="mt-2 text-p-sm text-ink-orange-7"
            >
              {{ __('Could not refresh the Avito chat scan status.') }}
            </p>
          </div>
        </section>

        <div
          v-if="showWebhookUrlWarning"
          data-testid="webhook-url-warning"
          class="rounded-lg border border-outline-blue-4 bg-surface-blue-2 px-3 py-2 text-p-sm font-semibold text-ink-blue-9"
        >
          {{
            __(
              'CRM must be available at a public HTTPS address to connect webhooks.',
            )
          }}
        </div>

        <div
          v-if="channelError || channelDraft.auth_error"
          data-testid="channel-auth-error"
          class="rounded-lg border border-outline-red-4 bg-surface-red-2 px-3 py-2 text-p-sm font-semibold text-ink-red-8"
        >
          {{ channelError || channelProviderMessage(channelDraft.auth_error) }}
        </div>

        <div
          v-if="channelDraft.channel && hasConnectionActions"
          class="flex flex-wrap gap-2 border-t border-outline-gray-1 pt-4"
        >
          <Button
            v-if="usesCommonConnectionActions"
            :label="__('Test')"
            variant="subtle"
            :loading="channelAction === 'test'"
            :disabled="channelBusy"
            @click="runChannelAction('test')"
          />
          <Button
            v-if="usesCommonConnectionActions"
            :label="__('Connect / Repair')"
            variant="solid"
            :loading="channelAction === 'connect'"
            :disabled="channelBusy"
            @click="runChannelAction('connect')"
          />
          <Button
            v-if="usesCommonConnectionActions"
            :label="__('Refresh Status')"
            variant="subtle"
            :loading="channelAction === 'status'"
            :disabled="channelBusy"
            @click="runChannelAction('status')"
          />
          <Button
            v-if="usesCommonConnectionActions && channelDraft.enabled"
            :label="__('Disconnect')"
            variant="subtle"
            theme="red"
            :loading="channelAction === 'disconnect'"
            :disabled="channelBusy"
            @click="runChannelAction('disconnect')"
          />
        </div>
      </div>
    </template>
    <template #actions>
      <div class="flex w-full justify-end gap-2">
        <Button
          :label="__('Close')"
          variant="subtle"
          :disabled="partnerBusy"
          @click="showChannelDialog = false"
        />
        <Button
          v-if="!isPartnerDraft"
          :label="channelDraft.channel ? __('Save') : __('Create Channel')"
          variant="solid"
          :loading="savingChannel"
          :disabled="Boolean(channelAction)"
          @click="saveChannel"
        />
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import SettingsLayoutBase from '@/components/Layouts/SettingsLayoutBase.vue'
import WazzupPartnerConnection from '@/components/Settings/WazzupPartnerConnection.vue'
import { isWazzupPartnerChannel } from '@/utils/wazzupPartnerConnection'
import {
  applyMessengerProviderDefaults,
  buildMessengerChannelPayload,
  callWazzupSettings,
  isDirectMessengerProvider,
  makeMessengerChannelDraft,
  messengerChannelState,
  messengerProviderLabel,
  messengerChannelCreationOptions,
  validateMessengerChannelDraft,
  wazzupConnectionMessage,
  wazzupConnectionRows,
  wazzupOperationalCounts,
} from '@/utils/messengerSettings'
import {
  Badge,
  Button,
  Dialog,
  FeatherIcon,
  FormControl,
  LoadingIndicator,
  Switch,
  call,
  toast,
} from 'frappe-ui'
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'

const defaultSettings = () => ({
  enabled: false,
  auto_create_lead: false,
  enable_provider_history_tombstones: true,
  log_raw_webhooks: false,
  webhook_secret: '',
  webhook_secret_configured: false,
  webhook_base_url: '',
  webhook_base_url_is_public_https: false,
  wazzup_partner_available: false,
  wazzup_legacy_ui_enabled: false,
})

const settings = reactive(defaultSettings())
const channels = ref([])
const loading = ref(true)
const refreshing = ref(false)
const loadError = ref(false)
const savingSettings = ref(false)
const settingsSnapshot = ref('')
const showAdvanced = ref(false)

const showChannelDialog = ref(false)
const partnerChannel = ref(null)
const partnerBusy = ref(false)
const visibleChannels = computed(() =>
  channels.value.filter(
    (channel) =>
      channel.provider !== 'wazzup' ||
      isWazzupPartnerChannel(channel) ||
      settings.wazzup_legacy_ui_enabled,
  ),
)
const channelDraft = ref(makeMessengerChannelDraft())
const channelSnapshot = ref('')
const savingChannel = ref(false)
const channelAction = ref('')
const channelError = ref('')
const wazzupConnection = ref(null)
const wazzupOperations = ref(null)
const wazzupRemoteChannels = ref([])
const wazzupChannelsLoaded = ref(false)
const loadingWazzupChannels = ref(false)
const avitoImportStatus = ref(null)
const loadingAvitoImport = ref(false)
const scanningAvitoImport = ref(false)
const avitoImportRefreshError = ref(false)
const avitoImportActive = computed(() =>
  ['queued', 'running'].includes(avitoImportStatus.value?.status),
)
const avitoImportSummary = computed(
  () =>
    avitoImportStatus.value?.last_completed ||
    (avitoImportActive.value ? null : avitoImportStatus.value),
)
const AVITO_IMPORT_POLL_INTERVAL_MS = 5000
let avitoImportPollTimer = null
let avitoImportRequest = null
let avitoImportGeneration = 0
const avitoImportOptions = [
  {
    value: 'all',
    label: 'All available chats',
    description: 'Create leads from all past chats available through Avito.',
  },
  {
    value: 'period',
    label: 'Chats in a date range',
    description:
      'Create leads from chats last active between the selected dates.',
  },
  {
    value: 'new_activity',
    label: 'Only new customer activity',
    description: 'Skip past chats until new customer activity can be verified.',
  },
]
const channelBusy = computed(
  () =>
    savingChannel.value ||
    Boolean(channelAction.value) ||
    loadingWazzupChannels.value,
)
const channelDirty = computed(() => channelState() !== channelSnapshot.value)
const isPartnerDraft = computed(() =>
  ['partner_whatsapp', 'partner_telegram'].includes(
    channelDraft.value.provider,
  ),
)
const partnerPlatform = computed(() =>
  channelDraft.value.provider === 'partner_telegram' ? 'telegram' : 'whatsapp',
)
const draftChannelState = computed(() =>
  isPartnerDraft.value
    ? messengerChannelState(partnerChannel.value || {})
    : messengerChannelState(
        channelDraft.value.provider === 'wazzup' && channelDirty.value
          ? { ...channelDraft.value, state: 'unchecked' }
          : channelDraft.value.provider === 'wazzup'
            ? {
                ...channelDraft.value,
                integration: { wazzup_connection: wazzupConnection.value },
              }
            : channelDraft.value,
      ),
)
const wazzupDiagnosticRows = computed(() =>
  wazzupConnectionRows(wazzupConnection.value || {}),
)
const wazzupKeySources = computed(() => [
  { label: __('Enter a new API key'), value: '' },
  ...channels.value
    .filter(
      (channel) =>
        channel.provider === 'wazzup' && channel.api_token_configured,
    )
    .map((channel) => ({ label: channelTitle(channel), value: channel.name })),
])
const hasWazzupKey = computed(() =>
  Boolean(
    channelDraft.value.api_token.trim() ||
    channelDraft.value.api_token_configured ||
    channelDraft.value.api_token_source_channel,
  ),
)
const wazzupRemoteChannelOptions = computed(() => [
  { label: __('Select a Wazzup channel'), value: '' },
  ...wazzupRemoteChannels.value.map((channel) => ({
    label: channel.display_name,
    value: channel.provider_channel_id,
  })),
])

const wazzupPlatforms = computed(() => [
  { label: __('WhatsApp'), value: 'whatsapp' },
  { label: __('Telegram personal chats'), value: 'telegram' },
])
const providerOptions = computed(() =>
  messengerChannelCreationOptions(settings.wazzup_legacy_ui_enabled).map(
    (option) => ({ value: option.value, label: __(option.label) }),
  ),
)

const settingsDirty = computed(
  () => settingsSnapshot.value && settingsSnapshot.value !== settingsState(),
)
const showsApiToken = computed(() => {
  return ['telegram_bot', 'vk_direct', 'max_direct', 'wazzup'].includes(
    channelDraft.value.provider,
  )
})
const apiTokenLabel = computed(() => {
  if (channelDraft.value.provider === 'telegram_bot') return 'Bot Token'
  if (channelDraft.value.provider === 'vk_direct')
    return 'Community Access Token'
  if (channelDraft.value.provider === 'max_direct') return 'Bot Token'
  if (channelDraft.value.provider === 'wazzup') return 'Wazzup API key'
  return 'API Token'
})
const hasConnectionActions = computed(
  () =>
    isDirectMessengerProvider(channelDraft.value.provider) ||
    channelDraft.value.provider === 'avito_direct',
)
const usesCommonConnectionActions = computed(() =>
  isDirectMessengerProvider(channelDraft.value.provider),
)
const showWebhookUrlWarning = computed(
  () =>
    isDirectMessengerProvider(channelDraft.value.provider) &&
    !settings.webhook_base_url_is_public_https,
)

function settingsState() {
  return JSON.stringify({
    enabled: Boolean(settings.enabled),
    auto_create_lead: Boolean(settings.auto_create_lead),
    enable_provider_history_tombstones: Boolean(
      settings.enable_provider_history_tombstones,
    ),
    log_raw_webhooks: Boolean(settings.log_raw_webhooks),
    webhook_secret: settings.webhook_secret || '',
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
      settingsSnapshot.value = settingsState()
    } else {
      settings.wazzup_partner_available = Boolean(
        result.settings?.wazzup_partner_available,
      )
      settings.wazzup_legacy_ui_enabled = Boolean(
        result.settings?.wazzup_legacy_ui_enabled,
      )
    }
    channels.value = result.channels || []
    loadError.value = false
    return true
  } catch (error) {
    loadError.value = true
    toast.error(
      clientProviderMessage(
        error?.messages?.[0] || 'Could not load message channel settings.',
      ),
    )
    return false
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

async function saveGlobalSettings() {
  savingSettings.value = true
  try {
    const save = settings.webhook_secret.trim() ? callWazzupSettings : call
    let result = await save('crm_messenger.api.settings.save_settings', {
      enabled: Boolean(settings.enabled),
      auto_create_lead: Boolean(settings.auto_create_lead),
      enable_provider_history_tombstones: Boolean(
        settings.enable_provider_history_tombstones,
      ),
      log_raw_webhooks: Boolean(settings.log_raw_webhooks),
      webhook_secret: settings.webhook_secret || '',
    })
    Object.assign(settings, result || {})
    settings.webhook_secret = ''
    settingsSnapshot.value = settingsState()
    if (channels.value.some((channel) => channel.provider === 'wazzup')) {
      const draft = channelDraft.value
      const reloaded = await loadSettings(true, true)
      if (!reloaded) {
        channels.value = channels.value.map((channel) =>
          channel.provider === 'wazzup'
            ? {
                ...channel,
                state: 'unchecked',
                auth_error: null,
                integration: {
                  ...channel.integration,
                  wazzup_connection: null,
                },
              }
            : channel,
        )
      }
      if (
        channelDraft.value === draft &&
        draft.provider === 'wazzup' &&
        draft.channel
      ) {
        const fresh = reloaded
          ? channels.value.find((channel) => channel.name === draft.channel)
          : null
        wazzupConnection.value = fresh?.integration?.wazzup_connection || null
        draft.state = fresh?.state || 'unchecked'
        draft.auth_error = fresh?.auth_error || null
        loadWazzupOperations()
      }
    }
    toast.success(__('Message channel settings saved.'))
  } catch (error) {
    toast.error(
      clientProviderMessage(
        error?.messages?.[0] || 'Could not save message channel settings.',
      ),
    )
  } finally {
    savingSettings.value = false
  }
}

function openNewChannel() {
  resetAvitoImportTracking()
  wazzupConnection.value = null
  wazzupOperations.value = null
  resetWazzupChannels()
  channelDraft.value = makeMessengerChannelDraft()
  changeProvider('partner_whatsapp')
  channelSnapshot.value = channelState()
  channelError.value = ''
  showChannelDialog.value = true
}

function openChannel(channel) {
  const partner = isWazzupPartnerChannel(channel)
  if (
    channel.provider === 'wazzup' &&
    !partner &&
    !settings.wazzup_legacy_ui_enabled
  )
    return
  resetAvitoImportTracking()
  wazzupConnection.value = channel.integration?.wazzup_connection || null
  wazzupOperations.value = null
  resetWazzupChannels()
  channelDraft.value = {
    ...makeMessengerChannelDraft(channel),
    provider: partner
      ? channel.platform === 'telegram'
        ? 'partner_telegram'
        : 'partner_whatsapp'
      : channel.provider,
    state: channel.state,
    auth_error: channel.auth_error,
    provider_display_name: channel.provider_display_name,
    label: channel.label,
  }
  partnerChannel.value = partner ? channel : null
  partnerBusy.value = false
  channelSnapshot.value = channelState()
  channelError.value = ''
  showChannelDialog.value = true
  if (channel.provider === 'wazzup' && !partner) loadWazzupOperations()
  if (
    channel.provider === 'avito_direct' &&
    channel.enabled &&
    ['connected', 'degraded'].includes(channel.state)
  ) {
    loadAvitoImportStatus()
  }
}

function updatePartnerChannel(channel) {
  partnerChannel.value = channel
  Object.assign(channelDraft.value, {
    channel: channel.name,
    platform: channel.platform,
    custom_display_name: channel.custom_display_name,
    provider_display_name: channel.provider_display_name,
    state: channel.state,
    enabled: channel.enabled,
  })
  const index = channels.value.findIndex((row) => row.name === channel.name)
  if (index < 0) channels.value.push(channel)
  else channels.value[index] = { ...channels.value[index], ...channel }
}

function deletePartnerChannel(name) {
  showChannelDialog.value = false
  channels.value = channels.value.filter((channel) => channel.name !== name)
}

function changeProvider(provider) {
  if (partnerBusy.value || channelDraft.value.channel) return
  partnerChannel.value = null
  channelDraft.value.provider = provider
  applyMessengerProviderDefaults(channelDraft.value)
  if (isPartnerDraft.value) channelDraft.value.platform = partnerPlatform.value
}

function wazzupCredentialIdentity() {
  const draft = channelDraft.value
  return JSON.stringify([
    draft.provider,
    draft.channel,
    draft.api_token,
    draft.api_token_source_channel,
  ])
}

function resetWazzupChannels() {
  wazzupRemoteChannels.value = []
  wazzupChannelsLoaded.value = false
}
watch(wazzupCredentialIdentity, resetWazzupChannels)

async function loadWazzupChannels() {
  if (channelBusy.value || !hasWazzupKey.value) return
  const draft = channelDraft.value
  const identity = wazzupCredentialIdentity()
  const params = draft.api_token.trim()
    ? { api_token: draft.api_token.trim() }
    : { channel: draft.api_token_source_channel || draft.channel }
  loadingWazzupChannels.value = true
  channelError.value = ''
  try {
    const result = await callWazzupSettings(
      'crm_messenger.api.wazzup_connection.list_channels',
      params,
    )
    if (
      channelDraft.value !== draft ||
      identity !== wazzupCredentialIdentity() ||
      !showChannelDialog.value
    )
      return
    if (!result.ok) {
      channelError.value = __(wazzupConnectionMessage(result.message))
      wazzupRemoteChannels.value = []
      wazzupChannelsLoaded.value = false
      return
    }
    wazzupRemoteChannels.value = (result.channels || []).filter((channel) =>
      ['whatsapp', 'telegram'].includes(channel.platform),
    )
    wazzupChannelsLoaded.value = true
  } catch (error) {
    if (
      channelDraft.value === draft &&
      identity === wazzupCredentialIdentity() &&
      showChannelDialog.value
    ) {
      channelError.value = __(wazzupConnectionMessage(error?.messages?.[0]))
    }
  } finally {
    loadingWazzupChannels.value = false
  }
}

function selectWazzupChannel(id) {
  const selected = wazzupRemoteChannels.value.find(
    (channel) => channel.provider_channel_id === id,
  )
  if (!selected) return
  channelDraft.value.provider_channel_id = selected.provider_channel_id
  channelDraft.value.platform = selected.platform
}

async function loadWazzupOperations() {
  const draft = channelDraft.value
  try {
    const result = await call(
      'crm_messenger.api.diagnostics.get_health_summary',
    )
    if (channelDraft.value !== draft || !showChannelDialog.value) return
    wazzupOperations.value = wazzupOperationalCounts(
      (result.channels || []).find(
        (channel) =>
          channel.name === draft.channel && channel.provider === 'wazzup',
      ),
    )
  } catch {
    if (channelDraft.value === draft) wazzupOperations.value = null
  }
}

async function checkWazzupChannel() {
  if (
    channelBusy.value ||
    !channelDraft.value.channel ||
    channelDirty.value ||
    settingsDirty.value
  )
    return
  const draft = channelDraft.value
  const snapshot = channelState()
  channelAction.value = 'wazzup_check'
  channelError.value = ''
  try {
    const result = await callWazzupSettings(
      'crm_messenger.api.wazzup_connection.check_channel',
      { channel: draft.channel },
    )
    const reloaded = await loadSettings(true, true)
    if (
      channelDraft.value !== draft ||
      channelState() !== snapshot ||
      !showChannelDialog.value
    )
      return
    const fresh = reloaded
      ? channels.value.find((channel) => channel.name === draft.channel)
      : null
    if (fresh) openChannel(fresh)
    wazzupConnection.value =
      fresh?.integration?.wazzup_connection || result.connection || null
    channelDraft.value.state = fresh?.state || result.state || 'unchecked'
    channelDraft.value.auth_error = fresh?.auth_error || null
    if (!result.ok)
      channelError.value = __(wazzupConnectionMessage(result.message))
    else toast.success(__('Wazzup diagnostics refreshed.'))
    if (!fresh) loadWazzupOperations()
  } catch (error) {
    if (
      channelDraft.value === draft &&
      channelState() === snapshot &&
      showChannelDialog.value
    ) {
      channelError.value = __(wazzupConnectionMessage(error?.messages?.[0]))
    }
  } finally {
    channelAction.value = ''
  }
}

async function saveChannel() {
  if (channelBusy.value) return
  let error = validateMessengerChannelDraft(channelDraft.value)
  if (error) {
    channelError.value = __(error)
    return
  }

  savingChannel.value = true
  channelError.value = ''
  const draft = channelDraft.value
  const snapshot = channelState()
  let wasNew = !channelDraft.value.channel
  try {
    const isWazzup = channelDraft.value.provider === 'wazzup'
    const save = isWazzup ? callWazzupSettings : call
    let result = await save(
      'crm_messenger.api.settings.save_channel',
      buildMessengerChannelPayload(channelDraft.value),
    )
    const reloaded = await loadSettings(true, true)
    let fresh =
      isWazzup && !reloaded
        ? result
        : channels.value.find((row) => row.name === result.name) || result
    if (
      channelDraft.value === draft &&
      showChannelDialog.value &&
      channelState() === snapshot
    ) {
      openChannel(fresh)
    }
    toast.success(wasNew ? __('Channel created.') : __('Channel saved.'))
  } catch (saveError) {
    if (channelDraft.value === draft && showChannelDialog.value) {
      channelError.value = channelProviderMessage(
        saveError?.messages?.[0] || 'Could not save the channel.',
      )
    }
  } finally {
    savingChannel.value = false
  }
}

async function runChannelAction(action) {
  if (channelBusy.value) return
  if (channelDirty.value) {
    channelError.value = __(
      'Save channel changes before running connection actions.',
    )
    return
  }
  let draft = channelDraft.value
  let snapshot = channelState()
  let methods = {
    test: 'crm_messenger.api.channels.test_provider_connection',
    connect: 'crm_messenger.api.channels.register_provider_webhook',
    status: 'crm_messenger.api.channels.get_provider_webhook_status',
    disconnect: 'crm_messenger.api.channels.remove_provider_webhook',
  }
  channelAction.value = action
  channelError.value = ''
  try {
    let params = { channel: channelDraft.value.channel }
    let result = await call(methods[action], params)
    if (!result?.ok) {
      throw new Error(providerActionFailureMessage(result))
    }
    if (result.authorization_url) {
      window.open(result.authorization_url, '_blank', 'noopener')
    }
    await loadSettings(true, true)
    let fresh = channels.value.find((row) => row.name === draft.channel)
    if (
      fresh &&
      showChannelDialog.value &&
      channelDraft.value === draft &&
      channelState() === snapshot
    ) {
      openChannel(fresh)
    }
    toast.success(
      clientProviderMessage(result.message || 'Operation completed.'),
    )
  } catch (error) {
    if (channelDraft.value === draft) {
      channelError.value = clientProviderMessage(
        error?.messages?.[0] ||
          error?.message ||
          'The provider operation failed.',
      )
    }
  } finally {
    channelAction.value = ''
  }
}

function avitoImportDialogActive(draft = channelDraft.value) {
  return (
    showChannelDialog.value &&
    channelDraft.value === draft &&
    draft.provider === 'avito_direct' &&
    draft.channel &&
    draft.enabled &&
    ['connected', 'degraded'].includes(draft.state)
  )
}

function clearAvitoImportPoll() {
  clearTimeout(avitoImportPollTimer)
  avitoImportPollTimer = null
}

function resetAvitoImportTracking() {
  clearAvitoImportPoll()
  avitoImportGeneration += 1
  avitoImportRequest = null
  avitoImportStatus.value = null
  avitoImportRefreshError.value = false
  loadingAvitoImport.value = false
  scanningAvitoImport.value = false
}

function scheduleAvitoImportPoll() {
  clearAvitoImportPoll()
  if (!avitoImportDialogActive() || !avitoImportActive.value) return
  avitoImportPollTimer = setTimeout(() => {
    avitoImportPollTimer = null
    loadAvitoImportStatus()
  }, AVITO_IMPORT_POLL_INTERVAL_MS)
}

function loadAvitoImportStatus() {
  const draft = channelDraft.value
  if (!avitoImportDialogActive(draft)) return Promise.resolve()
  if (avitoImportRequest) return avitoImportRequest.promise
  clearAvitoImportPoll()
  const request = { draft, generation: avitoImportGeneration }
  avitoImportRequest = request
  loadingAvitoImport.value = true
  const current = () =>
    request.generation === avitoImportGeneration &&
    avitoImportDialogActive(draft)
  request.promise = (async () => {
    try {
      const result = await call(
        'crm_messenger.api.provider_sync.get_channel_sync_status',
        { channel: draft.channel },
      )
      if (!current()) return
      if (!result?.ok) throw new Error('status_unavailable')
      avitoImportStatus.value = result
      avitoImportRefreshError.value = false
    } catch {
      if (current()) avitoImportRefreshError.value = true
    } finally {
      if (avitoImportRequest === request) {
        avitoImportRequest = null
        loadingAvitoImport.value = false
        scheduleAvitoImportPoll()
      }
    }
  })()
  return request.promise
}

async function scanAvitoChats() {
  if (
    channelBusy.value ||
    scanningAvitoImport.value ||
    channelDirty.value ||
    !avitoImportDialogActive()
  )
    return
  const draft = channelDraft.value
  const generation = avitoImportGeneration
  scanningAvitoImport.value = true
  try {
    const result = await call(
      'crm_messenger.api.provider_sync.enqueue_channel_sync',
      {
        channel: draft.channel,
      },
    )
    if (!result?.ok)
      throw new Error(result?.message || 'Could not start the Avito chat scan.')
    if (!avitoImportDialogActive(draft) || generation !== avitoImportGeneration)
      return
    // A status request started before enqueue may still report the old run.
    // Discard that response, then read the new run without overlapping reads.
    avitoImportGeneration += 1
    clearAvitoImportPoll()
    avitoImportStatus.value = {
      ...avitoImportStatus.value,
      status: result.status || 'queued',
      counts: {},
      incomplete: false,
    }
    toast.success(__('Avito chat scan started.'))
    if (avitoImportRequest) await avitoImportRequest.promise
    if (!avitoImportDialogActive(draft)) return
    await loadAvitoImportStatus()
  } catch (error) {
    if (avitoImportDialogActive(draft)) {
      toast.error(
        clientProviderMessage(
          error?.message || 'Could not start the Avito chat scan.',
        ),
      )
    }
  } finally {
    if (channelDraft.value === draft) scanningAvitoImport.value = false
  }
}

function hasAvitoImportCounts(status) {
  return Boolean(status?.counts && Object.keys(status.counts).length)
}

function avitoImportCheckedCount(status) {
  return [
    'chat_created',
    'chat_changed',
    'chat_unchanged',
    'chat_skipped',
    'chat_unverified',
  ].reduce((total, key) => total + (Number(status?.counts?.[key]) || 0), 0)
}

function avitoImportIncompleteMessage(status) {
  if (
    status.truncated ||
    (status.incomplete_reason || status.reason) === 'max_offset_reached'
  ) {
    return 'The Avito API pagination limit was reached. Chats beyond this limit may not have been checked.'
  }
  return 'The scan is incomplete. Some chats could not be verified or are unavailable through the Avito API.'
}

function avitoImportStatusLabel(status) {
  return (
    {
      never: 'No chat scan yet',
      queued: 'Chat scan queued',
      running: 'Scanning chats',
      succeeded: 'Chat scan completed',
      incomplete: 'Chat scan incomplete',
      failed: 'Chat scan failed',
    }[status] || 'No chat scan yet'
  )
}

function channelState() {
  return JSON.stringify(buildMessengerChannelPayload(channelDraft.value))
}

function channelTitle(channel) {
  return (
    channel.custom_display_name ||
    channel.provider_display_name ||
    (channel.provider === 'wazzup' &&
      __(
        channel.platform === 'telegram'
          ? 'Telegram personal chats'
          : 'WhatsApp',
      )) ||
    channel.label ||
    localizedProviderLabel(channel.provider)
  )
}

function providerDescription(channel) {
  if (channel.provider === 'wazzup')
    return __(
      channel.platform === 'telegram' ? 'Telegram personal chats' : 'WhatsApp',
    )
  let parts = [localizedProviderLabel(channel.provider)]
  if (channel.platform) parts.push(channel.platform)
  if (channel.external_account_id) parts.push(channel.external_account_id)
  else if (channel.provider_channel_id) parts.push(channel.provider_channel_id)
  return parts.join(' · ')
}

function providerInitial(channel) {
  let label =
    channel.provider === 'wazzup'
      ? channel.platform === 'telegram'
        ? 'Telegram'
        : 'WhatsApp'
      : messengerProviderLabel(channel.provider)
  return label === 'Telegram Bot' ? 'TG' : label.slice(0, 2).toUpperCase()
}

function localizedProviderLabel(provider) {
  return __(messengerProviderLabel(provider))
}

function secretPlaceholder(configured) {
  return configured ? __('Secret already saved') : __('Enter secret')
}

function clientProviderMessage(message) {
  let text = String(message || '')
  if (!text) return ''
  if (/wazzup(?:24)?/i.test(text)) return __('The provider operation failed.')
  return __(text)
}

function channelProviderMessage(message) {
  return channelDraft.value.provider === 'wazzup'
    ? __(wazzupConnectionMessage(message))
    : clientProviderMessage(message)
}

function providerActionFailureMessage(result = {}) {
  if (result.reason === 'messenger_subscription_required') {
    if (result.response?.chat_discovery_available) {
      return __(
        'Chat discovery is available. Connect this channel to create Avito leads automatically; read and reply on Avito.',
      )
    }
    return __(
      'This account does not have access to the Avito Messenger API. Switch to a subscription that includes the Messenger API, then try again.',
    )
  }
  return result.message || __('The provider operation failed.')
}

onMounted(() => loadSettings())
watch(
  showChannelDialog,
  (open) => {
    if (!open) resetAvitoImportTracking()
  },
  { flush: 'sync' },
)
onUnmounted(resetAvitoImportTracking)
</script>
