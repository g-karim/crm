<template>
  <div
    class="flex h-[100dvh] w-screen"
    data-crm-layout
    :data-layout="isMobileLayout ? 'mobile' : 'desktop'"
  >
    <!-- Keep the desktop sidebar's settings dialog mounted while it is hidden. -->
    <div class="hidden shrink-0 sm:block" data-desktop-sidebar>
      <AppSidebar />
    </div>
    <MobileSidebar v-if="isMobileLayout" />
    <div
      class="flex h-full min-h-0 min-w-0 flex-1 flex-col overflow-auto bg-surface-base"
    >
      <div class="flex flex-wrap pr-3 sm:flex-nowrap sm:border-b sm:pr-5">
        <div class="z-20 ml-2 flex items-center justify-center sm:hidden">
          <Button
            class="size-11"
            variant="ghost"
            :aria-label="__('Menu')"
            :aria-expanded="mobileSidebarOpened"
            @click="mobileSidebarOpened = !mobileSidebarOpened"
          >
            <MenuIcon class="h-4 text-ink-gray-9" />
          </Button>
        </div>
        <!-- Route headers teleport here: this node must survive every resize. -->
        <div id="app-header" class="min-w-0 flex-1" />
        <div
          class="mr-3 mt-2 w-full sm:m-0 sm:flex sm:w-auto sm:items-center sm:justify-center"
        >
          <CallUI />
        </div>
      </div>
      <slot />
    </div>
    <GlobalModals />
  </div>
</template>

<script setup>
import { watch } from 'vue'
import { Button } from 'frappe-ui'
import AppSidebar from '@/components/Layouts/AppSidebar.vue'
import MobileSidebar from '@/components/Mobile/MobileSidebar.vue'
import MenuIcon from '@/components/Icons/MenuIcon.vue'
import CallUI from '@/components/Telephony/CallUI.vue'
import GlobalModals from '@/components/Modals/GlobalModals.vue'
import { isMobileLayout, mobileSidebarOpened } from '@/composables/settings'

watch(isMobileLayout, (mobile) => {
  if (!mobile) mobileSidebarOpened.value = false
})
</script>
