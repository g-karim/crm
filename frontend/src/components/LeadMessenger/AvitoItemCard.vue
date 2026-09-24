<template>
  <section
    v-if="item"
    class="flex shrink-0 items-start gap-3 border-b px-4 py-3 sm:px-10"
    :aria-label="__('Listing for the selected conversation')"
    data-testid="avito-item-card"
  >
    <img
      v-if="item.image && failedImage !== item.image"
      :src="item.image"
      alt=""
      class="h-14 w-16 shrink-0 rounded-md object-cover"
      referrerpolicy="no-referrer"
      @error="failedImage = item.image"
    />
    <div class="min-w-0 text-sm">
      <div class="mb-1 text-xs text-ink-gray-5">
        {{ __('Listing for the selected conversation') }}
      </div>
      <div class="break-words font-medium text-ink-gray-8">
        {{ item.title || __('Avito listing') }}
      </div>
      <div v-if="item.price" class="mt-1 text-ink-gray-7">{{ item.price }}</div>
      <div v-if="!item.title && !item.id" class="mt-1 text-ink-gray-5">
        {{ __('Listing details are not available yet.') }}
      </div>
      <div class="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
        <span v-if="item.id" class="text-ink-gray-5">{{
          __('Listing ID: {0}', [item.id])
        }}</span>
        <a
          v-if="item.url"
          :href="item.url"
          target="_blank"
          rel="noopener noreferrer"
          class="text-ink-blue-6 underline"
        >
          {{ __('Open on Avito') }}
        </a>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import { getAvitoItem } from '@/utils/messengerAvitoContext'
const props = defineProps({ conversation: { type: Object, default: null } })
const item = computed(() => getAvitoItem(props.conversation))
const failedImage = ref('')
</script>
