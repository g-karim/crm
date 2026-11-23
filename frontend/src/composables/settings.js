import { computed, ref } from 'vue'
import { useMediaQuery } from '@vueuse/core'

export const mobileSidebarOpened = ref(false)

// Match Tailwind's sm/md boundaries, including fractional viewport widths.
const desktopLayout = useMediaQuery('(min-width: 640px)')
const desktopView = useMediaQuery('(min-width: 768px)')
export const isMobileLayout = computed(() => !desktopLayout.value)
export const isMobileView = computed(() => !desktopView.value)

export const showSettings = ref(false)

export const disableSettingModalOutsideClick = ref(false)

export const activeSettingsPage = ref('')
