<template>
  <section
    data-testid="avito-subscription-notice"
    class="w-full max-w-lg rounded-2xl border border-outline-gray-2 bg-surface-gray-1 p-6 text-center shadow-sm sm:p-8"
    :aria-label="__('Continue the conversation on Avito')"
  >
    <div
      class="mx-auto mb-4 flex size-12 items-center justify-center rounded-full bg-surface-gray-3 text-ink-gray-6"
      aria-hidden="true"
    >
      <FeatherIcon name="lock" class="size-5" />
    </div>
    <h3 class="text-xl font-semibold text-ink-gray-9">
      {{ __('Continue the conversation on Avito') }}
    </h3>
    <p class="mt-3 text-sm leading-relaxed text-ink-gray-6">
      {{ __('This Avito account does not have a subscription for messaging in CRM.') }}
    </p>
    <p class="mt-2 text-sm leading-relaxed text-ink-gray-5">
      {{ __('The lead is synchronized automatically. Read and reply on Avito.') }}
    </p>

    <div
      v-if="item"
      class="mt-6 flex items-start gap-3 border-t border-outline-gray-2 pt-5 text-left"
    >
      <img
        v-if="item.image && failedImage !== item.image"
        :src="item.image"
        alt=""
        class="size-16 shrink-0 rounded-lg object-cover"
        referrerpolicy="no-referrer"
        @error="failedImage = item.image"
      />
      <div class="min-w-0 text-sm">
        <div class="break-words font-medium leading-relaxed text-ink-gray-8">
          {{ item.title || __('Avito listing') }}
        </div>
        <div v-if="item.price" class="mt-1 font-medium text-ink-gray-7">
          {{ item.price }}
        </div>
        <div class="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
          <span v-if="item.id" class="text-ink-gray-5">
            {{ __('Listing ID: {0}', [item.id]) }}
          </span>
          <a
            v-if="item.url"
            :href="item.url"
            target="_blank"
            rel="noopener noreferrer"
            class="text-ink-gray-6 underline underline-offset-2 hover:text-ink-gray-9"
          >{{ __('Open on Avito') }}</a>
        </div>
      </div>
    </div>

    <a
      :href="externalUrl"
      data-testid="avito-open-chat"
      target="_blank"
      rel="noopener noreferrer"
      class="mt-6 inline-flex min-h-10 w-full items-center justify-center gap-2 rounded-lg bg-surface-gray-10 px-4 py-2.5 text-sm font-medium text-ink-base transition-colors hover:bg-surface-gray-9 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-outline-gray-5"
    >
      {{ __('Open chat in Avito') }}
      <FeatherIcon name="external-link" class="size-4" aria-hidden="true" />
    </a>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import { FeatherIcon } from 'frappe-ui'
import { getAvitoItem } from '@/utils/messengerAvitoContext'
import { getProviderExternalChatUrl } from '@/utils/messengerExternalLinks'

const props = defineProps({ conversation: { type: Object, default: null } })
const item = computed(() => getAvitoItem(props.conversation))
const externalUrl = computed(() =>
  getProviderExternalChatUrl('avito_direct', props.conversation?.external_chat_id),
)
const failedImage = ref('')
</script>
