<template>
  <LayoutHeader>
    <template #left-header
      ><h1 class="text-lg font-semibold text-ink-gray-9">
        {{ __('Мессенджер') }}
      </h1></template
    >
    <template #right-header>
      <Button
        class="min-h-11 min-w-11 !text-ink-gray-9"
        icon="lucide-refresh-cw"
        variant="ghost"
        :aria-label="__('Обновить переписку')"
        :loading="loading"
        @click="refreshAll"
      />
      <Button
        v-if="isAdmin()"
        class="min-h-11 !text-ink-gray-9"
        icon-left="lucide-plug"
        :label="__('Каналы')"
        variant="ghost"
        @click="showAccounts = true"
      />
    </template>
  </LayoutHeader>
  <main
    class="inbox-workspace flex min-h-0 flex-1 flex-col overflow-hidden bg-surface-base text-ink-gray-9"
    data-testid="inbox-workspace"
  >
    <div
      class="flex shrink-0 gap-2 border-b border-outline-gray-2 px-4 py-3 sm:px-5"
      :class="selectedId ? 'hidden lg:flex' : ''"
    >
      <div class="min-w-0 flex-1">
        <FormControl
          v-model="query"
          type="search"
          :aria-label="__('Поиск по клиентам и переписке')"
          :placeholder="__('Клиент, тема или текст сообщения')"
          ><template #prefix
            ><FeatherIcon
              name="search"
              class="size-4 text-ink-gray-5" /></template
        ></FormControl>
      </div>
      <div class="w-36 shrink-0 sm:w-48">
        <FormControl
          v-model="account"
          type="select"
          :aria-label="__('Аккаунт')"
          :options="accountOptions"
        />
      </div>
    </div>
    <div
      v-if="route.query.reference_name"
      class="flex shrink-0 items-center justify-between gap-2 border-b border-outline-gray-2 px-5 py-2 text-sm"
    >
      <span>{{ __('Переписка выбранной карточки CRM') }}</span
      ><Button
        :label="__('Все клиенты')"
        variant="ghost"
        @click="clearReference"
      />
    </div>
    <nav
      class="flex shrink-0 gap-5 overflow-x-auto border-b border-outline-gray-2 px-4 sm:px-5"
      :class="selectedId ? 'hidden lg:flex' : ''"
      :aria-label="__('Очереди переписки')"
    >
      <button
        v-for="[key, label] in inboxViews"
        :key="key"
        class="flex min-h-12 shrink-0 items-center gap-2 border-b-2 text-sm"
        :class="
          view === key
            ? 'border-ink-gray-9 font-medium text-ink-gray-9'
            : 'border-transparent text-ink-gray-6 hover:text-ink-gray-9'
        "
        :aria-current="view === key ? 'page' : undefined"
        @click="changeView(key)"
      >
        {{ __(label)
        }}<span
          v-if="counts[key]"
          class="rounded bg-surface-gray-2 px-1.5 py-0.5 text-xs tabular-nums"
          >{{ counts[key] }}</span
        >
      </button>
    </nav>
    <p
      v-if="listError"
      role="alert"
      class="border-b border-outline-gray-2 px-5 py-3 text-sm text-ink-red-4"
    >
      {{ listError }}
    </p>
    <div class="flex min-h-0 flex-1 overflow-hidden">
      <section
        ref="listEl"
        class="min-h-0 w-full shrink-0 overflow-y-auto border-r border-outline-gray-2 lg:w-[19rem] xl:w-[22rem]"
        :class="selectedId ? 'hidden lg:block' : ''"
        :aria-label="__('Диалоги')"
      >
        <div
          v-if="loading && !items.length"
          class="p-5 text-sm text-ink-gray-6"
          role="status"
        >
          {{ __('Загрузка диалогов…') }}
        </div>
        <button
          v-for="item in items"
          :key="item.id"
          :data-thread-id="item.id"
          class="block min-h-28 w-full border-b border-outline-gray-1 p-4 text-left transition-colors hover:bg-surface-gray-1 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-ink-gray-9"
          :class="selectedId === item.id ? 'bg-surface-gray-2' : ''"
          :aria-current="selectedId === item.id ? 'true' : undefined"
          @click="open(item.id)"
        >
          <span class="flex items-start gap-3"
            ><span
              class="grid size-10 shrink-0 place-items-center rounded-full bg-surface-gray-3 text-sm font-semibold"
              aria-hidden="true"
              >{{ initials(item.title) }}</span
            ><span class="min-w-0 flex-1"
              ><span class="flex items-center gap-2"
                ><span class="min-w-0 flex-1 truncate text-base font-medium">{{
                  item.title
                }}</span
                ><time class="shrink-0 text-xs tabular-nums text-ink-gray-6">{{
                  shortTime(item.last_at)
                }}</time></span
              ><span
                class="mt-1 flex items-center gap-2 text-xs text-ink-gray-6"
                ><span>{{ channelLabel(item.channel) }}</span
                ><span aria-hidden="true">·</span
                ><span class="truncate">{{ item.account_label }}</span></span
              ><span
                v-if="item.subject"
                class="mt-2 block truncate text-sm font-medium"
                >{{ item.subject }}</span
              ><span
                class="mt-1 block truncate text-sm leading-5 text-ink-gray-6"
                >{{ item.preview }}</span
              ><span class="mt-2 flex items-center justify-between gap-2"
                ><span
                  class="truncate text-xs"
                  :class="
                    item.status === 'needs_reply'
                      ? 'font-medium text-ink-gray-8'
                      : 'text-ink-gray-5'
                  "
                  >{{ statusLabel(item.status) }}</span
                ><span
                  v-if="item.unread"
                  class="grid min-w-5 place-items-center rounded-full bg-surface-gray-3 px-1.5 text-xs leading-5 text-ink-gray-9"
                  :aria-label="`${item.unread} непрочитанных`"
                  >{{ item.unread }}</span
                ></span
              ></span
            ></span
          >
        </button>
        <div v-if="!loading && !items.length" class="px-6 py-14 text-center">
          <span
            class="lucide-inbox mx-auto mb-4 block size-8 text-ink-gray-4"
            aria-hidden="true"
          />
          <p class="font-medium">{{ __('Здесь пока тихо') }}</p>
          <p class="mt-2 text-sm leading-5 text-ink-gray-6">
            {{
              query
                ? __('По этому запросу ничего не найдено.')
                : __(
                    'Диалоги появятся после входящего сообщения или подключения почты.',
                  )
            }}
          </p>
          <Button
            v-if="view !== 'all'"
            class="mt-4 min-h-11"
            :label="__('Показать всю историю')"
            @click="changeView('all')"
          />
        </div>
        <Button
          v-if="hasMore"
          class="my-4 ml-4 min-h-11"
          :label="__('Ещё диалоги')"
          :loading="loading"
          @click="loadList(true)"
        />
      </section>

      <section
        v-if="selectedId"
        class="inbox-conversation flex min-h-0 min-w-0 flex-1 flex-col"
        :class="contextOpen ? 'hidden xl:flex' : ''"
        :aria-label="__('Переписка')"
      >
        <div
          v-if="detailLoading && !detail"
          class="p-6 text-sm text-ink-gray-6"
          role="status"
        >
          {{ __('Открываем переписку…') }}
        </div>
        <p v-if="detailError" role="alert" class="p-5 text-sm text-ink-red-4">
          {{ detailError
          }}<Button class="mt-3" :label="__('К списку')" @click="back" />
        </p>
        <template v-if="detail">
          <header class="shrink-0 border-b border-outline-gray-2 p-4">
            <div class="flex items-start gap-2">
              <Button
                class="min-h-11 min-w-11 lg:hidden"
                icon="lucide-arrow-left"
                variant="ghost"
                :aria-label="__('К списку диалогов')"
                @click="back"
              />
              <div class="min-w-0 flex-1">
                <h2 class="truncate text-lg font-semibold">
                  {{ detail.thread.title }}
                </h2>
                <p class="mt-1 truncate text-sm text-ink-gray-6">
                  {{ channelLabel(detail.thread.channel) }} ·
                  {{ detail.thread.account_label }}
                </p>
              </div>
              <Button
                class="min-h-11 min-w-11"
                icon="lucide-panel-right"
                variant="ghost"
                :aria-label="__('Карточка клиента')"
                :aria-expanded="contextOpen"
                @click="contextOpen = !contextOpen"
              />
            </div>
            <div class="mt-3 flex flex-wrap gap-2">
              <FormControl
                :model-value="detail.thread.status"
                type="select"
                class="min-w-36 flex-1"
                :aria-label="__('Статус обработки')"
                :options="inboxStatuses"
                :disabled="!detail.thread.can_operate || workSaving || sending"
                @update:modelValue="setStatus"
              />
              <FormControl
                :model-value="detail.thread.work.assigned_to"
                type="select"
                class="min-w-36 flex-1"
                :aria-label="__('Ответственный за диалог')"
                :options="peopleOptions"
                :disabled="!detail.thread.can_operate || workSaving || sending"
                @update:modelValue="assign"
              />
              <Button
                v-if="
                  !detail.thread.work.assigned_to && detail.thread.can_operate
                "
                class="min-h-8"
                :label="__('Взять себе')"
                :disabled="workSaving || sending"
                @click="assign(viewer)"
              />
            </div>
            <form
              v-if="snoozeOpen"
              class="mt-3 flex items-end gap-2"
              @submit.prevent="confirmSnooze"
            >
              <FormControl
                v-model="snoozeUntil"
                type="datetime-local"
                :label="__('Вернуть в очередь')"
                class="min-w-0 flex-1"
              /><Button
                type="submit"
                :label="__('Отложить')"
                :loading="workSaving"
              /><Button
                icon="x"
                :aria-label="__('Отмена')"
                @click="snoozeOpen = false"
              />
            </form>
          </header>
          <p
            v-if="detail.thread.demo"
            class="shrink-0 border-b border-outline-gray-2 bg-surface-gray-1 px-4 py-2 text-xs leading-5 text-ink-gray-6"
            data-testid="demo-notice"
          >
            {{
              __(
                'Локальный пример. Ответ останется на этом стенде и не будет отправлен клиенту.',
              )
            }}
          </p>
          <p
            v-if="workError"
            role="alert"
            class="shrink-0 px-4 py-2 text-sm text-ink-red-4"
          >
            {{ workError }}
          </p>
          <div
            ref="historyEl"
            class="min-h-0 flex-1 space-y-4 overflow-y-auto bg-surface-gray-1 px-4 py-5 sm:px-6"
            data-testid="message-history"
            @scroll="rememberScroll"
          >
            <div v-if="detail.page.has_more" class="text-center">
              <Button
                class="min-h-11"
                :label="__('Предыдущие сообщения')"
                :loading="detailLoading"
                @click="loadOlder"
              />
            </div>
            <p
              v-if="!detail.messages.length"
              class="py-10 text-center text-sm text-ink-gray-6"
            >
              {{ __('В этом диалоге пока нет сообщений.') }}
            </p>
            <article
              v-for="message in detail.messages"
              :key="message.name"
              :data-message-id="message.name"
              class="flex flex-col"
              :class="
                message.direction === 'outbound' ? 'items-end' : 'items-start'
              "
            >
              <div
                class="max-w-full rounded-xl border border-outline-gray-1 p-3 sm:max-w-[90%]"
                :class="
                  message.direction === 'outbound'
                    ? 'bg-surface-gray-3'
                    : 'bg-surface-base'
                "
              >
                <p
                  v-if="detail.thread.kind === 'email'"
                  class="mb-2 break-words text-xs text-ink-gray-6"
                >
                  {{ message.sender }} → {{ message.recipients
                  }}<span v-if="message.cc" class="block"
                    >CC: {{ message.cc }}</span
                  ><span v-if="message.bcc" class="block"
                    >BCC: {{ message.bcc }}</span
                  >
                </p>
                <h3 v-if="message.subject" class="mb-2 text-sm font-semibold">
                  {{ message.subject }}
                </h3>
                <p
                  v-if="message.content_unavailable"
                  class="text-sm text-ink-gray-6"
                >
                  {{ __('Содержимое недоступно по условиям канала.') }}
                </p>
                <MessageContent
                  v-else
                  :message="message"
                  :should-show-text="true"
                />
                <template v-if="detail.thread.kind === 'messenger'"
                  ><AttachmentRenderer
                    :attachments="message.attachments || []"
                    :provider="message.provider"
                    :outbound="message.direction === 'outbound'"
                /></template>
                <div v-else class="mt-2 space-y-2">
                  <a
                    v-for="file in message.attachments"
                    :key="file.name"
                    :href="
                      '/api/method/crm.api.inbox.email_attachment?file=' +
                      encodeURIComponent(file.name)
                    "
                    class="flex min-h-11 items-center gap-2 break-all text-sm underline underline-offset-2"
                    target="_blank"
                    rel="noopener noreferrer"
                    ><span
                      class="lucide-paperclip size-4 shrink-0"
                      aria-hidden="true"
                    />{{ file.file_name }}</a
                  >
                  <details
                    v-if="message.content"
                    class="text-sm text-ink-gray-6"
                  >
                    <summary class="cursor-pointer py-2">
                      {{ __('Форматированное письмо') }}
                    </summary>
                    <iframe
                      :title="__('Содержимое письма без внешних изображений')"
                      sandbox=""
                      :srcdoc="safeEmailDocument(message.content)"
                      class="h-64 w-full rounded bg-white"
                    />
                  </details>
                </div>
                <footer
                  class="mt-2 flex flex-wrap items-center justify-end gap-2 text-xs text-ink-gray-6"
                >
                  <time>{{ fullTime(message.message_datetime) }}</time
                  ><span v-if="message.direction === 'outbound'">{{
                    deliveryLabel(message, detail.thread.demo)
                  }}</span
                  ><button
                    v-if="detail.thread.kind === 'email'"
                    class="min-h-8 underline underline-offset-2"
                    @click="quoteMail(message)"
                  >
                    {{ __('Цитировать') }}
                  </button>
                </footer>
              </div>
            </article>
          </div>
          <form
            class="inbox-composer shrink-0 border-t border-outline-gray-2 bg-surface-base p-3 sm:p-4"
            @submit.prevent="submit"
          >
            <div class="mb-2 flex flex-wrap items-center gap-3 text-sm">
              <button
                type="button"
                class="min-h-9"
                :class="
                  draft.mode === 'reply' ? 'font-semibold' : 'text-ink-gray-6'
                "
                @click="draft.mode = 'reply'"
              >
                {{ __('Ответ клиенту') }}</button
              ><button
                type="button"
                class="min-h-9"
                :class="
                  draft.mode === 'note' ? 'font-semibold' : 'text-ink-gray-6'
                "
                @click="draft.mode = 'note'"
              >
                {{ __('Внутренняя заметка') }}</button
              ><span class="ml-auto text-xs text-ink-gray-5" role="status">{{
                draftStatus
              }}</span>
            </div>
            <p
              v-if="draft.mode === 'note'"
              class="mb-2 text-sm text-ink-gray-6"
            >
              {{
                detail.context
                  ? `Заметка сохранится: ${detail.context.doctype === 'CRM Lead' ? 'лид' : 'сделка'} · ${detail.context.title}`
                  : 'Сначала выберите связанную карточку клиента.'
              }}
            </p>
            <details
              v-if="draft.mode === 'reply' && detail.thread.kind === 'email'"
              class="mb-2 text-sm"
              :open="mailFieldsOpen"
            >
              <summary class="cursor-pointer py-1">
                {{ __('Получатели и тема') }}
              </summary>
              <div class="mt-2 grid grid-cols-2 gap-2">
                <FormControl
                  v-model="draft.to"
                  class="col-span-2"
                  :label="__('Кому')"
                /><FormControl v-model="draft.cc" label="CC" /><FormControl
                  v-model="draft.bcc"
                  label="BCC"
                /><FormControl
                  v-model="draft.subject"
                  class="col-span-2"
                  :label="__('Тема письма')"
                />
              </div>
            </details>
            <FormControl
              v-model="draft.text"
              type="textarea"
              :rows="3"
              :aria-label="
                draft.mode === 'note'
                  ? __('Текст внутренней заметки')
                  : __('Текст ответа')
              "
              :placeholder="
                draft.mode === 'note'
                  ? __('Что нужно знать коллегам?')
                  : __('Напишите ответ…')
              "
              :disabled="sending"
              @keydown.ctrl.enter.prevent="submit"
              @keydown.meta.enter.prevent="submit"
            />
            <div
              v-if="draft.attachments?.length"
              class="mt-2 flex flex-wrap gap-2"
            >
              <span
                v-for="file in draft.attachments"
                :key="file.name"
                class="flex items-center gap-1 rounded bg-surface-gray-2 px-2 text-xs"
                >{{ file.file_name
                }}<button
                  type="button"
                  class="min-h-9 min-w-9"
                  :aria-label="`Убрать ${file.file_name}`"
                  @click="removeAttachment(file.name)"
                >
                  ×
                </button></span
              >
            </div>
            <p
              v-if="sendError || draftError"
              role="alert"
              class="mt-2 text-sm text-ink-red-4"
            >
              {{ sendError || draftError }}
            </p>
            <div v-if="draftConflict" class="mt-2 flex flex-wrap gap-2">
              <Button
                type="button"
                :label="__('Сохранить мой черновик')"
                @click="resolveDraft(true)"
              />
              <Button
                type="button"
                :label="__('Загрузить последнюю версию')"
                @click="resolveDraft(false)"
              />
            </div>
            <div class="mt-2 flex flex-wrap items-center justify-between gap-2">
              <div class="flex items-center gap-1">
                <FileUploader
                  v-if="canAttach"
                  :upload-args="{
                    type: detail.thread.kind,
                    docname: detail.thread.name,
                    upload_endpoint: `/api/method/crm.api.inbox.upload_attachment?expected_viewer=${encodeURIComponent(viewer)}`,
                    is_private: true,
                  }"
                  @success="attach"
                  @error="uploadError"
                  ><template #default="{ openFileSelector, uploading }"
                    ><Button
                      type="button"
                      icon="lucide-paperclip"
                      class="min-h-11 min-w-11"
                      variant="ghost"
                      :aria-label="__('Прикрепить файл')"
                      :loading="uploading"
                      @click="openFileSelector" /></template
                ></FileUploader>
                <Button
                  type="button"
                  icon="lucide-text"
                  class="min-h-11 min-w-11"
                  variant="ghost"
                  :aria-label="__('Шаблоны ответа')"
                  :aria-expanded="templatesOpen"
                  @click="templatesOpen = !templatesOpen"
                />
                <Button
                  type="button"
                  icon="lucide-list-todo"
                  class="min-h-11 min-w-11"
                  variant="ghost"
                  :aria-label="__('Создать задачу')"
                  :disabled="!detail.can_task"
                  @click="taskOpen = true"
                />
              </div>
              <Button
                type="submit"
                variant="solid"
                class="min-h-11"
                :label="
                  draft.mode === 'note'
                    ? __('Сохранить заметку')
                    : detail.thread.demo
                      ? __('Сохранить тестовый ответ')
                      : __('Отправить')
                "
                :loading="sending"
                :disabled="!canSubmit"
              />
            </div>
            <p
              v-if="draft.mode === 'reply' && !detail.can_send"
              class="mt-2 text-xs text-ink-gray-6"
            >
              {{ detail.disabled_reason }}
            </p>
            <div
              v-if="templatesOpen"
              class="mt-2 space-y-2 rounded-lg border border-outline-gray-2 p-3"
            >
              <p class="text-sm font-medium">{{ __('Мои шаблоны') }}</p>
              <div class="flex flex-wrap gap-2">
                <Button
                  v-for="(template, index) in templates"
                  :key="index"
                  :label="template.label"
                  type="button"
                  @click="draft.text = template.text"
                />
              </div>
              <div class="flex gap-2">
                <FormControl
                  v-model="templateName"
                  class="min-w-0 flex-1"
                  :aria-label="__('Название шаблона')"
                  :placeholder="__('Название нового шаблона')"
                /><Button
                  type="button"
                  :label="__('Сохранить текст как шаблон')"
                  :disabled="!draft.text.trim() || !templateName.trim()"
                  @click="saveTemplate"
                />
              </div>
            </div>
          </form>
        </template>
      </section>
      <div
        v-else
        class="hidden min-w-0 flex-1 items-center justify-center px-8 lg:flex"
      >
        <div class="max-w-sm text-center">
          <span
            class="lucide-messages-square mx-auto mb-5 block size-10 text-ink-gray-4"
            aria-hidden="true"
          />
          <h2 class="text-xl font-semibold">
            {{ __('Все разговоры — под рукой') }}
          </h2>
          <p class="mt-3 text-base leading-6 text-ink-gray-6">
            {{
              __(
                'Выберите диалог. Здесь будет переписка, а рядом — нужная карточка клиента, заметки и задачи.',
              )
            }}
          </p>
          <p class="mt-5 text-sm text-ink-gray-5">
            {{ __('Telegram, ВКонтакте, MAX, Авито, WhatsApp и почта') }}
          </p>
        </div>
      </div>

      <aside
        v-if="contextOpen && detail"
        class="flex min-h-0 w-full shrink-0 flex-col overflow-y-auto border-l border-outline-gray-2 bg-surface-base p-4 lg:w-72 lg:flex-1 xl:w-80 xl:flex-none"
        :aria-label="__('Контекст клиента')"
        data-testid="inbox-context"
      >
        <div class="mb-5 flex items-center justify-between gap-2">
          <h2 class="font-semibold">{{ __('Клиент и дела') }}</h2>
          <Button
            class="min-h-11 min-w-11"
            icon="x"
            variant="ghost"
            :aria-label="__('Закрыть карточку клиента')"
            @click="contextOpen = false"
          />
        </div>
        <div
          v-if="
            detail.customer?.phone ||
            detail.customer?.email ||
            detail.customer?.organization
          "
          class="mb-5 space-y-3 border-b border-outline-gray-2 pb-5 text-sm"
        >
          <div
            v-if="detail.customer.phone"
            class="flex items-center justify-between gap-2"
          >
            <span class="break-all">{{ detail.customer.phone }}</span
            ><Button
              icon="lucide-phone"
              class="min-h-11 min-w-11 shrink-0"
              :aria-label="__('Позвонить клиенту')"
              variant="ghost"
              @click="prepareCustomerCall"
            />
          </div>
          <p v-if="detail.customer.email" class="break-all text-ink-gray-6">
            {{ detail.customer.email }}
          </p>
          <RouterLink
            v-if="detail.customer.organization?.path"
            :to="detail.customer.organization.path"
            class="block font-medium hover:underline"
            >{{ detail.customer.organization.title }}</RouterLink
          >
          <p v-else-if="detail.customer.organization" class="font-medium">
            {{ detail.customer.organization.title }}
          </p>
        </div>
        <RouterLink
          v-for="contact in detail.customer?.contacts || []"
          :key="contact.name"
          :to="contact.path"
          class="mb-3 rounded-lg border border-outline-gray-2 p-3 text-sm hover:bg-surface-gray-1"
          ><span class="mb-1 block text-xs text-ink-gray-5">{{
            __('Контакт')
          }}</span
          >{{ contact.title }}</RouterLink
        >
        <FormControl
          v-if="detail.contexts.length"
          :model-value="contextValue"
          type="select"
          :label="__('Сохранять заметки и задачи в')"
          :options="contextOptions"
          :disabled="!detail.thread.can_operate || workSaving || sending"
          @update:modelValue="chooseContext"
        />
        <p v-else class="text-sm leading-5 text-ink-gray-6">
          {{ __('Диалог пока не связан с лидом или сделкой.') }}
        </p>
        <div class="mt-4 space-y-2">
          <RouterLink
            v-for="context in detail.contexts"
            :key="context.doctype + context.name"
            :to="context.path"
            class="flex min-h-14 items-center justify-between gap-2 rounded-lg border border-outline-gray-2 p-3 text-sm hover:bg-surface-gray-1"
            ><span class="min-w-0 break-words"
              ><span class="mb-1 block text-xs text-ink-gray-5">{{
                context.doctype === 'CRM Lead' ? __('Лид') : __('Сделка')
              }}</span
              >{{ context.title }}</span
            ><span
              class="lucide-arrow-up-right size-4 shrink-0"
              aria-hidden="true"
          /></RouterLink>
        </div>
        <details
          v-if="isAdmin() && detail.thread.kind === 'messenger'"
          class="mt-3 text-sm"
        >
          <summary class="min-h-11 cursor-pointer py-3 text-ink-gray-6">
            {{ __('Изменить привязку диалога') }}
          </summary>
          <FormControl
            v-model="linkDoctype"
            type="select"
            :label="__('Тип карточки')"
            :options="[
              { value: 'CRM Lead', label: 'Лид' },
              { value: 'CRM Deal', label: 'Сделка' },
            ]"
          /><FormControl
            v-model="linkQuery"
            class="mt-2"
            type="search"
            :label="__('Найти карточку')"
          /><button
            v-for="item in linkResults"
            :key="item.name"
            class="mt-2 block min-h-11 w-full rounded border border-outline-gray-2 p-2 text-left"
            @click="linkCustomer(item)"
          >
            {{ item.title }}
          </button>
        </details>
        <div class="my-5 border-t border-outline-gray-2" />
        <div class="flex items-center justify-between gap-2">
          <h3 class="text-sm font-semibold">{{ __('Задачи') }}</h3>
          <Button
            class="min-h-11"
            icon-left="plus"
            :label="__('Добавить')"
            variant="ghost"
            :disabled="!detail.can_task"
            @click="taskOpen = true"
          />
        </div>
        <p
          v-if="!detail.materials.tasks.length"
          class="mt-2 text-sm text-ink-gray-5"
        >
          {{ __('В этой карточке задач пока нет.') }}
        </p>
        <RouterLink
          v-for="task in detail.materials.tasks"
          :key="task.name"
          :to="task.context.route"
          class="mt-2 rounded-lg border border-outline-gray-2 p-3 text-sm hover:bg-surface-gray-1"
          ><span class="block font-medium">{{ task.title }}</span
          ><span class="mt-1 block text-xs text-ink-gray-6"
            >{{ __(task.status)
            }}<template v-if="task.due_date">
              · {{ fullTime(task.due_date) }}</template
            ></span
          ></RouterLink
        >
        <h3 class="mb-1 mt-6 text-sm font-semibold">{{ __('Заметки') }}</h3>
        <p
          v-if="!detail.materials.notes.length"
          class="mt-2 text-sm text-ink-gray-5"
        >
          {{ __('В этой карточке заметок пока нет.') }}
        </p>
        <details
          v-for="note in detail.materials.notes"
          :key="note.name"
          class="mt-2 rounded-lg border border-outline-gray-2 p-3 text-sm"
        >
          <summary class="cursor-pointer font-medium">{{ note.title }}</summary>
          <p
            class="mt-2 whitespace-pre-wrap break-words leading-5 text-ink-gray-6"
          >
            {{ note.text }}
          </p>
        </details>
        <h3 class="mb-1 mt-6 text-sm font-semibold">{{ __('Звонки') }}</h3>
        <p
          v-if="!detail.materials.calls.length"
          class="mt-2 text-sm text-ink-gray-5"
        >
          {{ __('Связанных звонков пока нет.') }}
        </p>
        <RouterLink
          v-for="callItem in detail.materials.calls"
          :key="callItem.name"
          :to="{ name: 'Telephony', query: { open: callItem.name } }"
          class="mt-2 flex min-h-12 items-center gap-2 rounded-lg border border-outline-gray-2 p-3 text-sm"
          ><span class="lucide-phone size-4 shrink-0" aria-hidden="true" /><span
            >{{ __(callItem.type) }} · {{ __(callItem.status) }}</span
          ></RouterLink
        >
      </aside>
    </div>
  </main>
  <Dialog
    v-model:open="taskOpen"
    :options="{ title: __('Задача по переписке'), size: 'lg' }"
    ><template #body-content
      ><form id="inbox-task-form" class="space-y-4" @submit.prevent="saveTask">
        <p class="text-sm text-ink-gray-6">{{ detail?.context?.title }}</p>
        <FormControl
          v-model="taskTitle"
          :label="__('Что сделать')"
          required
        /><FormControl
          v-model="taskDue"
          type="date"
          :label="__('Срок')"
        /><FormControl
          v-model="taskAssignee"
          type="select"
          :label="__('Исполнитель')"
          :options="peopleOptions"
        />
        <p v-if="taskError" role="alert" class="text-sm text-ink-red-4">
          {{ taskError }}
        </p>
      </form></template
    ><template #actions
      ><Button
        type="submit"
        form="inbox-task-form"
        variant="solid"
        class="min-h-11"
        :label="__('Создать задачу')"
        :loading="taskSaving"
        :disabled="!taskTitle.trim() || !detail?.can_task" /></template
  ></Dialog>
  <Dialog
    v-model:open="showAccounts"
    :options="{ title: __('Каналы и почта'), size: 'lg' }"
    ><template #body-content
      ><div class="space-y-4">
        <p class="text-sm leading-5 text-ink-gray-6">
          {{
            __(
              'Отправка идёт через аккаунт выбранного диалога. Доступ к аккаунту и доступ к карточке клиента проверяются отдельно.',
            )
          }}
        </p>
        <div
          v-for="item in allAccounts"
          :key="item.kind + item.name"
          class="flex items-center justify-between gap-3 rounded-lg border border-outline-gray-2 p-3"
        >
          <span class="min-w-0 break-words text-sm"
            >{{ item.label
            }}<span class="mt-1 block text-xs text-ink-gray-6">{{
              channelLabel(item.channel)
            }}</span></span
          ><span class="text-xs text-ink-gray-6">{{
            item.enabled ? __('Включён') : __('Не подключён')
          }}</span>
        </div>
        <p v-if="!allAccounts.length" class="text-sm text-ink-gray-6">
          {{ __('Каналы пока не настроены.') }}
        </p>
        <div class="flex flex-wrap gap-2">
          <Button
            class="min-h-11"
            :label="__('Настроить мессенджеры')"
            @click="openSettings('messenger')"
          /><Button
            class="min-h-11"
            :label="__('Настроить почту')"
            @click="openSettings('email')"
          />
        </div>
        <details>
          <summary class="cursor-pointer py-2 text-sm">
            {{ __('Доступ сотрудников к аккаунту') }}
          </summary>
          <form class="mt-3 space-y-3" @submit.prevent="saveAccess">
            <FormControl
              v-model="accessAccount"
              type="select"
              :label="__('Аккаунт')"
              :options="
                allAccounts.map((a) => ({
                  value: `${a.kind}:${a.name}`,
                  label: a.label,
                }))
              "
            /><FormControl
              v-model="accessUser"
              :label="__('Email сотрудника')"
              type="email"
            /><label class="flex min-h-11 items-center gap-2 text-sm"
              ><input v-model="accessRead" type="checkbox" />{{
                __('Чтение')
              }}</label
            ><label class="flex min-h-11 items-center gap-2 text-sm"
              ><input
                v-model="accessSend"
                type="checkbox"
                :disabled="!accessRead"
              />{{ __('Ответы и обработка') }}</label
            >
            <p class="text-xs leading-5 text-ink-gray-6">
              {{
                __(
                  'Права на лид или сделку по-прежнему обязательны. Администратор видит все аккаунты; личная почта доступна также через штатные настройки пользователя.',
                )
              }}
            </p>
            <Button
              type="submit"
              class="min-h-11"
              :label="__('Сохранить доступ')"
              :loading="accessSaving"
              :disabled="!accessAccount || !accessUser"
            />
            <p v-if="accessResult" role="status" class="text-sm">
              {{ accessResult }}
            </p>
          </form>
        </details>
      </div></template
    ></Dialog
  >
</template>

<script setup>
import {
  Button,
  Dialog,
  FormControl,
  FeatherIcon,
  FileUploader,
  dayjsLocal,
  dayjs,
  getConfig,
  call,
} from 'frappe-ui'
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import LayoutHeader from '@/components/LayoutHeader.vue'
import MessageContent from '@/components/LeadMessenger/MessageContent.vue'
import AttachmentRenderer from '@/components/LeadMessenger/AttachmentRenderer.vue'
import { usersStore } from '@/stores/users'
import { globalStore } from '@/stores/global'
import { callbackDeadline } from '@/utils/callFollowups'
import { showSettings, activeSettingsPage } from '@/composables/settings'
import {
  inboxViews,
  inboxStatuses,
  channelLabel,
  draftKey,
  mergeMessages,
  deliveryLabel,
  safeEmailDocument,
  quoteMessage,
  restoreInboxDraft,
  draftFingerprint,
} from '@/utils/inbox'

const route = useRoute(),
  router = useRouter()
const { isAdmin } = usersStore()
const { prepareCall } = globalStore()
const viewer = ref(''),
  items = ref([]),
  counts = ref({}),
  allAccounts = ref([])
const query = ref(''),
  account = ref(''),
  loading = ref(false),
  hasMore = ref(false),
  listError = ref('')
const detail = ref(null),
  detailLoading = ref(false),
  detailError = ref(''),
  contextOpen = ref(false)
const draft = ref(blankDraft()),
  draftStatus = ref(''),
  draftError = ref(''),
  draftConflict = ref(false),
  sending = ref(false),
  sendError = ref('')
const historyEl = ref(null),
  listEl = ref(null),
  workSaving = ref(false),
  workError = ref('')
const snoozeOpen = ref(false),
  snoozeUntil = ref(''),
  mailFieldsOpen = ref(false)
const taskOpen = ref(false),
  taskTitle = ref(''),
  taskDue = ref(''),
  taskAssignee = ref(''),
  taskError = ref(''),
  taskSaving = ref(false)
const showAccounts = ref(false),
  accessAccount = ref(''),
  accessUser = ref(''),
  accessRead = ref(true),
  accessSend = ref(false),
  accessSaving = ref(false),
  accessResult = ref('')
const templatesOpen = ref(false),
  templateName = ref(''),
  templates = ref([
    {
      label: 'Получили запрос',
      text: 'Здравствуйте! Получили ваш запрос, уточняем детали и скоро вернёмся с ответом.',
    },
    {
      label: 'Уточнить время',
      text: 'Подскажите, когда вам удобно обсудить детали?',
    },
    { label: 'Моя подпись', text: 'С уважением,\nКоманда EXP' },
  ])
const linkDoctype = ref('CRM Lead'),
  linkQuery = ref(''),
  linkResults = ref([])
const selectedId = computed(() => String(route.query.open || ''))
const view = computed(() => String(route.query.view || 'open'))
const contextValue = computed(() =>
  detail.value?.context
    ? `${detail.value.context.doctype}:${detail.value.context.name}`
    : '',
)
const contextOptions = computed(
  () =>
    detail.value?.contexts.map((c) => ({
      value: `${c.doctype}:${c.name}`,
      label: `${c.doctype === 'CRM Lead' ? 'Лид' : 'Сделка'} · ${c.title}`,
    })) || [],
)
const accountOptions = computed(() => [
  { value: '', label: 'Все аккаунты' },
  ...allAccounts.value.map((a) => ({
    value: a.name,
    label: `${channelLabel(a.channel)} · ${a.label}`,
  })),
])
const peopleOptions = computed(() => [
  { value: '', label: 'Без ответственного' },
  ...(detail.value?.people || []),
])
const canSubmit = computed(
  () =>
    !!(
      detail.value &&
      draft.value.text?.trim() &&
      !sending.value &&
      !workSaving.value &&
      !draftConflict.value &&
      (draft.value.mode === 'note'
        ? detail.value.can_note
        : detail.value.can_send)
    ),
)
const canAttach = computed(
  () =>
    !!(
      detail.value &&
      draft.value.mode === 'reply' &&
      !detail.value.thread.demo &&
      detail.value.can_send &&
      detail.value.capabilities?.supports_attachments
    ),
)
let listRequest = 0,
  detailRequest = 0,
  searchTimer,
  draftTimer,
  linkTimer,
  disposed = false,
  restoring = false
const privateContexts = new Map(),
  scrolls = new Map()
let lastSend = null,
  lastTask = null

function blankDraft() {
  return {
    text: '',
    mode: 'reply',
    subject: '',
    to: '',
    cc: '',
    bcc: '',
    attachments: [],
  }
}
function errorText(error, fallback) {
  const text = error.messages?.[0] || error.message || fallback
  return new DOMParser().parseFromString(String(text), 'text/html').body
    .textContent
}
function initials(text) {
  return String(text)
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((s) => s[0])
    .join('')
    .toUpperCase()
}
function shortTime(value) {
  const d = dayjsLocal(value)
  return d.isValid()
    ? d.format(
        d.format('YYYY-MM-DD') === dayjsLocal().format('YYYY-MM-DD')
          ? 'HH:mm'
          : 'D MMM',
      )
    : ''
}
function fullTime(value) {
  const d = dayjsLocal(value)
  return d.isValid()
    ? d.format(String(value).length === 10 ? 'D MMM' : 'D MMM, HH:mm')
    : value
}
function statusLabel(value) {
  return inboxStatuses.find((s) => s.value === value)?.label || value
}
function prepareCustomerCall() {
  if (detail.value?.customer?.phone && detail.value.context)
    prepareCall(detail.value.customer.phone, {
      doctype: detail.value.context.doctype,
      name: detail.value.context.name,
    })
}
function args(id = selectedId.value) {
  const index = id.indexOf(':')
  return { kind: id.slice(0, index), name: id.slice(index + 1) }
}

function acceptViewer(user) {
  if (viewer.value && viewer.value !== user) {
    const ctx = currentPrivate()
    if (ctx && detail.value) cacheDraft(ctx, draft.value)
    disposed = true
    clearTimeout(draftTimer)
    detail.value = null
    items.value = []
    window.location.reload()
    return false
  }
  viewer.value = user
  return true
}

async function loadList(more = false, quiet = false) {
  const request = ++listRequest
  if (!quiet) loading.value = true
  try {
    const data = await call('crm.api.inbox.list_threads', {
      view: view.value,
      query: query.value,
      account: account.value,
      reference_doctype: route.query.reference_doctype || '',
      reference_name: route.query.reference_name || '',
      offset: more ? items.value.length : 0,
    })
    if (disposed || request !== listRequest) return
    if (!acceptViewer(data.viewer)) return
    items.value = more ? [...items.value, ...data.items] : data.items
    counts.value = data.counts
    hasMore.value = data.has_more
    allAccounts.value = data.accounts
    listError.value = ''
  } catch (e) {
    if (request === listRequest) {
      listError.value = errorText(e, 'Не удалось загрузить диалоги.')
      items.value = []
    }
  } finally {
    if (request === listRequest) loading.value = false
  }
}
function cacheDraft(ctx, value) {
  try {
    localStorage.setItem(
      draftKey(ctx.viewer, ctx.id),
      JSON.stringify({ draft: value, revision: ctx.revision }),
    )
  } catch {
    /* Server draft remains available. */
  }
}
function enqueuePrivate(ctx, value, cursor) {
  if (!ctx) return Promise.resolve()
  ctx.chain = (ctx.chain || Promise.resolve())
    .catch(() => {})
    .then(async () => {
      if (ctx.conflict) return
      const serialized = draftFingerprint(value)
      if (
        serialized === ctx.saved &&
        (!cursor || JSON.stringify(cursor) === ctx.read)
      ) {
        if (!disposed && selectedId.value === ctx.id)
          draftStatus.value = 'Черновик сохранён'
        return
      }
      try {
        const data = await call('crm.api.inbox.save_private', {
          ...args(ctx.id),
          expected_viewer: ctx.viewer,
          expected_revision: ctx.revision,
          draft: value,
          ...(cursor ? { read_cursor: cursor } : {}),
        })
        ctx.revision = data.revision
        ctx.saved = serialized
        if (cursor) ctx.read = JSON.stringify(cursor)
        try {
          const current = JSON.parse(
            localStorage.getItem(draftKey(ctx.viewer, ctx.id)),
          )
          if (draftFingerprint(current?.draft) === serialized)
            cacheDraft(ctx, value)
        } catch {
          /* Local fallback can be unavailable. */
        }
        if (!disposed && selectedId.value === ctx.id) {
          draftStatus.value = 'Черновик сохранён'
          draftError.value = ''
        }
      } catch (e) {
        if (e.exc_type === 'TimestampMismatchError') ctx.conflict = true
        if (!disposed && selectedId.value === ctx.id) {
          draftConflict.value = Boolean(ctx.conflict)
          draftStatus.value = 'Копия в браузере'
          draftError.value = errorText(
            e,
            'Черновик сохранён только в браузере.',
          )
        }
      }
    })
  return ctx.chain
}
function currentPrivate() {
  return privateContexts.get(selectedId.value)
}
function flushDraft() {
  clearTimeout(draftTimer)
  const ctx = currentPrivate()
  if (ctx && detail.value) {
    const value = JSON.parse(JSON.stringify(draft.value))
    cacheDraft(ctx, value)
    return enqueuePrivate(ctx, value)
  }
  return Promise.resolve()
}
async function loadDetail(quiet = false, older = false) {
  if (!selectedId.value) return
  const id = selectedId.value,
    request = ++detailRequest
  if (!quiet) detailLoading.value = true
  try {
    if (!detail.value) await privateContexts.get(id)?.chain
    const data = await call('crm.api.inbox.get_thread', {
      ...args(id),
      ...(older ? { before_cursor: detail.value.page.before_cursor } : {}),
    })
    if (disposed || request !== detailRequest || selectedId.value !== id) return
    if (!acceptViewer(data.viewer)) return
    const same = detail.value?.thread.id === id
    if (same) {
      data.messages = mergeMessages(detail.value.messages, data.messages)
      if (quiet) data.page = detail.value.page
    }
    detail.value = data
    detailError.value = ''
    if (!same) {
      restoring = true
      let local
      try {
        local = JSON.parse(localStorage.getItem(draftKey(data.viewer, id)))
      } catch {
        local = null
      }
      const last = data.messages.at(-1)
      const restored = restoreInboxDraft(local, data.private)
      draft.value = {
        ...blankDraft(),
        to:
          last?.direction === 'inbound'
            ? last?.sender || ''
            : last?.recipients || '',
        subject: data.thread.subject
          ? `Re: ${data.thread.subject.replace(/^Re:\s*/i, '')}`
          : '',
        ...restored.draft,
      }
      const ctx = {
        id,
        viewer: data.viewer,
        revision: data.private.revision,
        chain: Promise.resolve(),
        saved: draftFingerprint(data.private.draft),
        read: JSON.stringify(data.private.read_cursor),
        conflict: restored.conflict,
      }
      draftConflict.value = restored.conflict
      if (restored.conflict)
        draftError.value =
          'В другом окне есть новая версия. Выберите, какой черновик сохранить.'
      privateContexts.set(id, ctx)
      await nextTick()
      restoring = false
      await enqueuePrivate(
        ctx,
        JSON.parse(JSON.stringify(draft.value)),
        data.read_cursor,
      )
      if (historyEl.value)
        historyEl.value.scrollTop =
          scrolls.get(id) ?? historyEl.value.scrollHeight
      taskAssignee.value = data.thread.work.assigned_to || data.viewer
    } else if (quiet && document.visibilityState === 'visible') {
      enqueuePrivate(
        currentPrivate(),
        JSON.parse(JSON.stringify(draft.value)),
        data.read_cursor,
      )
    }
  } catch (e) {
    if (request === detailRequest) {
      detailError.value = errorText(e, 'Не удалось открыть диалог.')
      detail.value = null
    }
  } finally {
    if (request === detailRequest) detailLoading.value = false
  }
}
function rememberScroll() {
  if (historyEl.value && selectedId.value)
    scrolls.set(selectedId.value, historyEl.value.scrollTop)
}
async function resolveDraft(keepMine) {
  const id = selectedId.value,
    ctx = currentPrivate()
  if (!ctx) return
  try {
    await ctx.chain
    const data = await call('crm.api.inbox.get_thread', args(id))
    if (disposed || selectedId.value !== id || !acceptViewer(data.viewer))
      return
    ctx.revision = data.private.revision
    ctx.saved = draftFingerprint(data.private.draft)
    ctx.read = JSON.stringify(data.private.read_cursor)
    ctx.conflict = false
    draftConflict.value = false
    draftError.value = ''
    if (!keepMine) draft.value = { ...blankDraft(), ...data.private.draft }
    const value = JSON.parse(JSON.stringify(draft.value))
    cacheDraft(ctx, value)
    await enqueuePrivate(ctx, value, data.read_cursor)
  } catch (e) {
    draftError.value = errorText(e, 'Не удалось обновить черновик.')
  }
}
function open(id) {
  router.push({ query: { ...route.query, open: id } })
}
function back() {
  const q = { ...route.query }
  delete q.open
  router.push({ query: q })
  contextOpen.value = false
}
function changeView(value) {
  router.replace({ query: { ...route.query, view: value } })
}
function clearReference() {
  const q = { ...route.query }
  delete q.reference_doctype
  delete q.reference_name
  router.replace({ query: q })
}
async function refreshAll() {
  await loadList()
  if (selectedId.value) await loadDetail(true)
}
function loadOlder() {
  return loadDetail(false, true)
}

async function saveWork(values) {
  if (!detail.value || workSaving.value) return
  const id = selectedId.value,
    revision = detail.value.thread.work.revision
  workSaving.value = true
  workError.value = ''
  try {
    await call('crm.api.inbox.update_work', {
      ...args(id),
      expected_viewer: viewer.value,
      expected_revision: revision,
      ...values,
    })
    if (selectedId.value === id) await loadDetail(true)
    await loadList(false, true)
  } catch (e) {
    workError.value = errorText(e, 'Не удалось сохранить обработку диалога.')
  } finally {
    workSaving.value = false
  }
}
function assign(value) {
  return saveWork({ assigned_to: value || '' })
}
function setStatus(value) {
  if (value === 'snoozed') snoozeOpen.value = true
  else saveWork({ status: value })
}
async function confirmSnooze() {
  const date = callbackDeadline(
    snoozeUntil.value,
    dayjs,
    getConfig('systemTimezone'),
    getConfig('localTimezone') ||
      Intl.DateTimeFormat().resolvedOptions().timeZone,
  )
  await saveWork({ status: 'snoozed', snoozed_until: date })
  if (!workError.value) snoozeOpen.value = false
}
function chooseContext(value) {
  const index = value.indexOf(':')
  return saveWork({
    context_doctype: value.slice(0, index),
    context_name: value.slice(index + 1),
  })
}
function stableRequest(previous, payload) {
  const hash = JSON.stringify(payload)
  return previous?.hash === hash ? previous : { hash, id: crypto.randomUUID() }
}
async function submit() {
  if (!canSubmit.value) return
  const id = selectedId.value,
    data = detail.value,
    author = viewer.value,
    content = JSON.parse(JSON.stringify(draft.value))
  const payload =
    content.mode === 'note'
      ? {
          text: content.text,
          context_doctype: data.context.doctype,
          context_name: data.context.name,
        }
      : {
          text: content.text,
          subject: content.subject,
          to: content.to,
          cc: content.cc,
          bcc: content.bcc,
          attachments: content.attachments.map((f) => f.name),
        }
  lastSend = stableRequest(lastSend, { id, mode: content.mode, ...payload })
  sending.value = true
  sendError.value = ''
  try {
    await flushDraft()
    await call(
      `crm.api.inbox.${content.mode === 'note' ? 'add_note' : 'send_reply'}`,
      {
        ...args(id),
        ...payload,
        mutation_id: lastSend.id,
        expected_viewer: author,
      },
    )
    if (selectedId.value === id) {
      draft.value.text = ''
      draft.value.attachments = []
      lastSend = null
      await nextTick()
      await flushDraft()
      await loadDetail(true)
      if (content.mode !== 'note')
        await saveWork({ status: 'waiting_customer' })
      if (historyEl.value)
        historyEl.value.scrollTop = historyEl.value.scrollHeight
      if (content.mode === 'note') contextOpen.value = true
    }
    await loadList(false, true)
  } catch (e) {
    if (selectedId.value === id)
      sendError.value = errorText(
        e,
        'Не удалось сохранить. Текст оставлен в черновике.',
      )
  } finally {
    sending.value = false
  }
}
async function saveTask() {
  if (!detail.value?.can_task || !taskTitle.value.trim() || taskSaving.value)
    return
  const id = selectedId.value,
    context = detail.value.context
  const values = {
    title: taskTitle.value,
    description: '',
    status: 'Todo',
    priority: 'Medium',
    due_date: taskDue.value || null,
    assigned_to: taskAssignee.value || null,
    context_kind: context.doctype === 'CRM Lead' ? 'lead' : 'deal',
    context_name: context.name,
  }
  lastTask = stableRequest(lastTask, { id, values })
  taskSaving.value = true
  taskError.value = ''
  try {
    await call('crm.api.inbox.add_task', {
      ...args(id),
      expected_viewer: viewer.value,
      values,
      mutation_id: lastTask.id,
    })
    taskOpen.value = false
    taskTitle.value = ''
    lastTask = null
    await loadDetail(true)
    contextOpen.value = true
  } catch (e) {
    taskError.value = errorText(e, 'Не удалось создать задачу.')
  } finally {
    taskSaving.value = false
  }
}
function quoteMail(message) {
  draft.value.mode = 'reply'
  draft.value.text = quoteMessage(message.text) + draft.value.text
}
function attach(file) {
  if (draft.value.attachments.length >= 10) {
    sendError.value = 'Можно прикрепить до 10 файлов.'
    return
  }
  draft.value.attachments.push({
    name: file.name,
    file_name: file.file_name,
    file_url: file.file_url,
  })
}
function removeAttachment(name) {
  draft.value.attachments = draft.value.attachments.filter(
    (f) => f.name !== name,
  )
}
function uploadError(error) {
  sendError.value = errorText(error, 'Не удалось загрузить файл.')
}
function saveTemplate() {
  templates.value.push({
    label: templateName.value.trim().slice(0, 60),
    text: draft.value.text,
  })
  try {
    localStorage.setItem(
      draftKey(viewer.value, 'templates'),
      JSON.stringify(templates.value),
    )
  } catch {
    /* Current tab retains templates. */
  }
  templateName.value = ''
}
function openSettings(kind) {
  showAccounts.value = false
  activeSettingsPage.value =
    kind === 'messenger' ? __('Message Channels') : __('Email Accounts')
  showSettings.value = true
}
async function saveAccess() {
  accessSaving.value = true
  accessResult.value = ''
  try {
    const [kind, ...rest] = accessAccount.value.split(':')
    await call('crm.api.inbox.set_account_access', {
      kind,
      expected_viewer: viewer.value,
      account: rest.join(':'),
      user: accessUser.value,
      can_read: accessRead.value,
      can_send: accessSend.value,
    })
    accessResult.value = 'Доступ сохранён.'
  } catch (e) {
    accessResult.value = errorText(e, 'Не удалось сохранить доступ.')
  } finally {
    accessSaving.value = false
  }
}
async function linkCustomer(item) {
  const author = viewer.value
  try {
    await flushDraft()
    await call('crm.api.inbox.link_customer', {
      ...args(),
      expected_viewer: author,
      reference_doctype: item.doctype,
      reference_name: item.name,
    })
    await refreshAll()
  } catch (e) {
    workError.value = errorText(e, 'Не удалось изменить привязку.')
  }
}

watch(
  draft,
  () => {
    if (restoring || !detail.value) return
    const ctx = currentPrivate()
    if (!ctx) return
    const value = JSON.parse(JSON.stringify(draft.value))
    cacheDraft(ctx, value)
    draftStatus.value = 'Сохраняем…'
    clearTimeout(draftTimer)
    draftTimer = setTimeout(() => enqueuePrivate(ctx, value), 700)
  },
  { deep: true },
)
watch(
  selectedId,
  async (id, previous) => {
    if (previous && detail.value) {
      const ctx = privateContexts.get(previous)
      const value = JSON.parse(JSON.stringify(draft.value))
      if (ctx) {
        cacheDraft(ctx, value)
        enqueuePrivate(ctx, value)
      }
      if (historyEl.value) scrolls.set(previous, historyEl.value.scrollTop)
    }
    clearTimeout(draftTimer)
    detailRequest++
    detail.value = null
    detailError.value = ''
    draftError.value = ''
    draftConflict.value = false
    sendError.value = ''
    workError.value = ''
    templatesOpen.value = false
    snoozeOpen.value = false
    contextOpen.value = false
    taskOpen.value = false
    if (selectedId.value) await loadDetail()
  },
  { immediate: true },
)
watch([query, account, view, () => route.query.reference_name], () => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => loadList(), 250)
})
watch([linkQuery, linkDoctype], () => {
  clearTimeout(linkTimer)
  const q = linkQuery.value,
    dt = linkDoctype.value
  linkTimer = setTimeout(async () => {
    try {
      const rows = await call('crm.api.inbox.search_customers', {
        query: q,
        doctype: dt,
      })
      if (linkQuery.value === q && linkDoctype.value === dt)
        linkResults.value = rows
    } catch {
      linkResults.value = []
    }
  }, 250)
})
watch(viewer, (user) => {
  try {
    const saved = JSON.parse(localStorage.getItem(draftKey(user, 'templates')))
    if (Array.isArray(saved)) templates.value = saved
  } catch {
    /* Defaults remain available. */
  }
})
const poll = setInterval(() => {
  if (
    !disposed &&
    !sending.value &&
    !workSaving.value &&
    !taskSaving.value &&
    document.visibilityState === 'visible'
  ) {
    loadList(false, true)
    if (selectedId.value) loadDetail(true)
  }
}, 15000)
loadList()
onBeforeUnmount(() => {
  flushDraft()
  disposed = true
  clearInterval(poll)
  clearTimeout(searchTimer)
  clearTimeout(draftTimer)
  clearTimeout(linkTimer)
  listRequest++
  detailRequest++
})
</script>
<style scoped>
.inbox-composer {
  padding-bottom: max(0.75rem, env(safe-area-inset-bottom));
}
@media (max-width: 1023px) {
  .inbox-workspace :deep(button:not([data-thread-id])),
  .inbox-workspace :deep(input[type='search']),
  .inbox-workspace :deep(input[type='text']) {
    min-height: 44px;
  }
}
@media (max-height: 600px) {
  .inbox-conversation {
    overflow-y: auto;
  }
  .inbox-conversation [data-testid='message-history'] {
    flex: 0 0 auto;
    min-height: 10rem;
    max-height: 45dvh;
  }
}
.inbox-workspace :deep(button:focus-visible),
.inbox-workspace :deep(a:focus-visible) {
  outline: 2px solid currentColor;
  outline-offset: -2px;
}
@media (prefers-reduced-motion: reduce) {
  .inbox-workspace * {
    transition: none !important;
  }
}
</style>
