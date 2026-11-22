<template>
  <div class="flex flex-col h-full">
    <!-- header -->
    <div class="flex flex-wrap justify-between gap-4 text-ink-gray-8">
      <div
        class="flex min-w-0 basis-full flex-col gap-1 md:basis-auto md:flex-1"
      >
        <h2 class="flex gap-2 text-2xl-semibold leading-6">
          {{ __('Email Accounts') }}
        </h2>
        <p class="text-p-base text-ink-gray-6">
          {{
            __(
              'Manage your email accounts to send and receive emails directly from CRM. You can add multiple accounts and set one as default for incoming and outgoing emails.',
            )
          }}
        </p>
      </div>
      <div class="flex shrink-0 items-center gap-2">
        <Button
          :label="__('Add Account')"
          theme="gray"
          variant="solid"
          icon-left="lucide-plus"
          @click="emit('update:step', 'email-add')"
        />
      </div>
    </div>

    <!-- list accounts -->
    <div
      v-if="!emailAccounts.loading && Boolean(emailAccounts.data?.length)"
      class="mt-4"
    >
      <div
        v-for="(emailAccount, i) in emailAccounts.data"
        :key="emailAccount.name"
      >
        <EmailAccountCard
          :emailAccount="emailAccount"
          @click="emit('update:step', 'email-edit', emailAccount)"
        />
        <div
          v-if="emailAccounts.data.length !== i + 1"
          class="h-px border-t mx-2 border-outline-elevation-2"
        />
      </div>
    </div>
    <!-- fallback if no email accounts -->
    <EmptyState
      v-else
      name="Email Accounts"
      :description="__('Add one to get started.')"
      :icon="Email2Icon"
    />
  </div>
</template>

<script setup>
import Email2Icon from '@/components/Icons/Email2Icon.vue'
import EmptyState from '../ListViews/EmptyState.vue'
import EmailAccountCard from './EmailAccountCard.vue'
import { createListResource } from 'frappe-ui'

const emit = defineEmits(['update:step'])

const emailAccounts = createListResource({
  doctype: 'Email Account',
  cache: true,
  fields: ['*'],
  filters: {
    email_id: ['Not Like', '%example%'],
  },
  pageLength: 10,
  auto: true,
  onSuccess: (accounts) => {
    // convert 0 to false to handle boolean fields
    accounts.forEach((account) => {
      account.enable_incoming = Boolean(account.enable_incoming)
      account.enable_outgoing = Boolean(account.enable_outgoing)
      account.default_incoming = Boolean(account.default_incoming)
      account.default_outgoing = Boolean(account.default_outgoing)
    })
  },
})
</script>
