<template>
  <div class="flex h-[100dvh] w-screen">
    <MobileSidebar />
    <div
      class="flex h-full min-h-0 min-w-0 flex-1 flex-col overflow-auto bg-surface-base"
    >
      <MobileAppHeader />
      <slot />
    </div>
    <GlobalModals />
  </div>
</template>
<script setup>
import MobileSidebar from '@/components/Mobile/MobileSidebar.vue'
import MobileAppHeader from '@/components/Mobile/MobileAppHeader.vue'
import GlobalModals from '@/components/Modals/GlobalModals.vue'
</script>
