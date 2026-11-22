<template>
  <div class="flex h-full min-h-0 min-w-0 w-full flex-col text-ink-gray-8">
    <!-- Header -->
    <div
      class="flex shrink-0 flex-wrap items-start justify-between gap-3 p-4 text-ink-gray-8 sm:p-6"
    >
      <div
        class="flex min-w-0 basis-full flex-col gap-1 md:basis-auto md:flex-1"
      >
        <slot name="title">
          <h2
            class="flex min-w-0 gap-2 text-2xl-semibold leading-6 [overflow-wrap:anywhere]"
          >
            {{ title }}
          </h2>
        </slot>
        <slot
          v-if="Boolean($slots['description']) || Boolean(description)"
          name="description"
        >
          <p class="text-p-base text-ink-gray-6">
            {{ description }}
          </p>
        </slot>
      </div>
      <slot v-if="Boolean($slots['header-actions'])" name="header-actions" />
    </div>
    <div
      v-if="Boolean($slots['header-bottom'])"
      class="shrink-0 px-4 pb-4 sm:px-6"
    >
      <slot name="header-bottom" />
    </div>
    <div
      class="min-h-0 min-w-0 flex-1 overflow-y-auto px-4 pb-4 sm:px-6 sm:pb-6"
    >
      <slot name="content" />
    </div>
  </div>
</template>

<script setup>
defineProps({
  title: { type: String, default: '' },
  description: { type: String, default: '' },
})
</script>
