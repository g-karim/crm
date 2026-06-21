<template>
  <div v-if="brand?.logo" class="flex items-center">
    <img :src="brand.logo" class="h-full w-full object-contain" />
  </div>
  <CRMLogo v-else class="h-10 w-16 shrink-0 rounded object-contain" />
</template>

<script setup>
import CRMLogo from '@/components/Icons/CRMLogo.vue'

const brand = defineModel({ type: Object, default: () => ({}) })
</script>
