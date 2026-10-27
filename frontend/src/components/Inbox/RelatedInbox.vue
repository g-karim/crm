<template>
  <section class="flex h-full min-h-0 flex-1 flex-col p-5">
    <div class="mb-5 flex flex-wrap items-center justify-between gap-3">
      <div>
        <h2 class="text-lg font-semibold text-ink-gray-9">
          {{ __('Переписка клиента') }}
        </h2>
        <p class="mt-1 text-sm text-ink-gray-6">
          {{ __('Мессенджеры и почта в общем входящем ящике.') }}
        </p>
      </div>
      <Button
        class="min-h-11"
        variant="solid"
        :label="__('Открыть мессенджер')"
        @click="open()"
      />
    </div>
    <p v-if="error" role="alert" class="text-ink-red-4">{{ error }}</p>
    <p v-else-if="loading" role="status" class="text-ink-gray-6">
      {{ __('Загрузка переписки…') }}
    </p>
    <div v-else class="overflow-y-auto rounded-lg border border-outline-gray-2">
      <button
        v-for="item in items"
        :key="item.id"
        class="flex min-h-16 w-full items-center justify-between gap-3 border-b border-outline-gray-1 p-4 text-left last:border-0 hover:bg-surface-gray-2"
        @click="open(item)"
      >
        <span class="min-w-0"
          ><span class="block truncate font-medium text-ink-gray-9"
            >{{ channelLabel(item.channel) }} · {{ item.account_label }}</span
          ><span class="mt-1 block truncate text-sm text-ink-gray-6">{{
            item.subject || item.preview
          }}</span></span
        >
        <span class="lucide-chevron-right size-4 shrink-0" aria-hidden="true" />
      </button>
      <p v-if="!items.length" class="p-5 text-sm text-ink-gray-6">
        {{ __('Связанных диалогов пока нет.') }}
      </p>
    </div>
  </section>
</template>
<script setup>
import { Button, call } from 'frappe-ui'
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { channelLabel } from '@/utils/inbox'
const props = defineProps({
  doctype: { type: String, required: true },
  name: { type: String, required: true },
})
const router = useRouter()
const items = ref([]),
  loading = ref(false),
  error = ref('')
let request = 0
watch(
  () => [props.doctype, props.name],
  async () => {
    const version = ++request
    loading.value = true
    try {
      const data = await call('crm.api.inbox.list_threads', {
        view: 'all',
        reference_doctype: props.doctype,
        reference_name: props.name,
      })
      if (version === request) items.value = data.items
    } catch (e) {
      if (version === request)
        error.value = e.messages?.[0] || 'Не удалось загрузить переписку.'
    } finally {
      if (version === request) loading.value = false
    }
  },
  { immediate: true },
)
function open(item) {
  router.push({
    name: 'Messenger',
    query: item
      ? { open: item.id }
      : {
          reference_doctype: props.doctype,
          reference_name: props.name,
          view: 'all',
        },
  })
}
</script>
