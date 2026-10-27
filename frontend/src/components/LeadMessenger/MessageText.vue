<template>
  <span data-message-text>
    <template v-for="(segment, index) in segments" :key="index">
      <a
        v-if="segment.href"
        :href="segment.href"
        target="_blank"
        rel="noopener noreferrer"
        class="text-ink-blue-6 underline hover:text-ink-blue-7"
        @click.stop
        @contextmenu.stop
        >{{ segment.text }}</a
      >
      <template v-else>{{ segment.text }}</template>
    </template>
  </span>
</template>

<script setup>
import { getMessengerTextSegments } from '@/utils/messengerTextLinks'
import { computed } from 'vue'

const props = defineProps({
  text: { type: String, default: '' },
})

const segments = computed(() => getMessengerTextSegments(props.text))
</script>
