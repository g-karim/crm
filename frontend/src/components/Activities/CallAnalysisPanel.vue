<template>
  <CallInsightsPanel v-if="name" :key="name" :name="name" />
</template>
<script setup>
import { computed } from 'vue'
import CallInsightsPanel from '@/components/Telephony/CallInsightsPanel.vue'
const props = defineProps({ callLog: { type: Object, required: true } })
const name = computed(() => props.callLog?.data?.name)
</script>
