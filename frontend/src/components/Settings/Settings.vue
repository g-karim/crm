<template>
  <Dialog
    v-model:open="showSettings"
    :size="'5xl'"
    :disableOutsideClickToClose="disableSettingModalOutsideClick"
    @close="activeSettingsPage = ''"
  >
    <template #body>
      <section
        class="flex h-[calc(100dvh-2rem)] min-h-0 flex-col bg-surface-elevation-2 md:h-[calc(100dvh-8rem)]"
        data-testid="crm-settings"
      >
        <header
          class="flex shrink-0 items-center gap-3 border-b border-outline-gray-2 px-4 py-2"
        >
          <h2
            class="hidden flex-1 text-base font-semibold text-ink-gray-9 md:block"
          >
            {{ __('Settings') }}
          </h2>
          <FormControl
            class="min-w-0 flex-1 md:hidden"
            type="select"
            :aria-label="__('Settings section')"
            :modelValue="activeTab?.label"
            :options="
              settingItems.map((item) => ({
                value: item.label,
                label: item.label,
              }))
            "
            @update:modelValue="activeSettingsPage = $event"
          />
          <Button
            icon="lucide-x"
            variant="ghost"
            class="min-h-11 min-w-11 shrink-0 md:min-h-7 md:min-w-7"
            :aria-label="__('Close settings')"
            @click="closeSettings"
          />
        </header>
        <div class="flex min-h-0 min-w-0 flex-1">
          <div
            ref="sidebarContainer"
            class="m-1 hidden min-h-0 w-56 shrink-0 flex-col overflow-y-auto rounded-l-lg bg-surface-gray-1 md:flex"
          >
            <template v-for="(tab, i) in tabs" :key="tab.label">
              <div
                v-if="!tab.hideLabel && i != 0"
                class="mx-1 mb-0.5 mt-[5px]"
              />
              <div
                v-if="!tab.hideLabel"
                class="sticky top-0 z-10 my-[3px] flex min-h-7.5 items-center gap-1.5 bg-surface-gray-1 px-2 py-1.5 text-xs-medium text-ink-gray-5"
              >
                <span>{{ __(tab.label) }}</span>
              </div>
              <nav class="space-y-[3px] px-1">
                <SidebarItem
                  v-for="item in tab.items"
                  :key="item.label"
                  :label="__(item.label)"
                  :data-page="item.label"
                  :active="activeTab?.label == item.label"
                  class="w-full"
                  :class="
                    activeTab?.label != item.label && 'hover:!bg-surface-gray-3'
                  "
                  @click="activeSettingsPage = item.label"
                >
                  <template #prefix
                    ><Icon :icon="item.icon" class="size-4 text-ink-gray-7"
                  /></template>
                </SidebarItem>
              </nav>
            </template>
          </div>
          <div
            class="flex min-h-0 min-w-0 flex-1 flex-col overflow-y-auto bg-surface-elevation-2"
          >
            <component :is="activeTab.component" v-if="activeTab" />
          </div>
        </div>
      </section>
    </template>
  </Dialog>
</template>

<script setup>
import LucideLayoutDashboard from '~icons/lucide/layout-dashboard'
import LucideNetwork from '~icons/lucide/network'
import MonitorCogIcon from '~icons/lucide/monitor-cog'
import LucideTextCursorInput from '~icons/lucide/text-cursor-input'
import LucideMessagesSquare from '~icons/lucide/messages-square'
import SlidersIcon from '@/components/Icons/SlidersIcon.vue'
import CalendarIcon from '@/components/Icons/CalendarIcon.vue'
import WhatsAppIcon from '@/components/Icons/WhatsAppIcon.vue'
import ERPNextIcon from '@/components/Icons/ERPNextIcon.vue'
import EmailTemplateIcon from '@/components/Icons/EmailTemplateIcon.vue'
import SettingsIcon from '@/components/Icons/SettingsIcon.vue'
import SettingsIcon2 from '@/components/Icons/SettingsIcon2.vue'
import Users from '@/components/Settings/Users.vue'
import Hierarchy from '@/components/Settings/Hierarchy/Hierarchy.vue'
import ProfilePage from '@/components/Settings/Profile/ProfilePage.vue'
import PreferencesSettings from '@/components/Settings/PreferencesSettings.vue'
import NotificationDelivery from '@/components/Settings/NotificationDelivery.vue'
import WhatsAppSettings from '@/components/Settings/WhatsAppSettings.vue'
import ERPNextSettings from '@/components/Settings/ERPNextSettings.vue'
import LeadSyncSourcePage from '@/components/Settings/LeadSyncing/LeadSyncSourcePage.vue'
import MessengerSettings from '@/components/Settings/MessengerSettings.vue'
import TelephonyPage from '@/components/Settings/Telephony/TelephonyPage.vue'
import DefaultsSettings from '@/components/Settings/DefaultsSettings.vue'
import CalendarSettings from '@/components/Settings/CalendarSettings.vue'
import FormsSettings from '@/components/Settings/Forms/FormsSettings.vue'
import SalesPipelines from '@/components/Settings/SalesPipelines.vue'
import GeneralSettings from '@/components/Settings/GeneralSettings.vue'
import EnrichmentSettings from '@/components/Settings/EnrichmentSettings.vue'
import TouchSettings from '@/components/Settings/TouchSettings.vue'
import DashboardSettings from '@/components/Settings/DashboardSettings.vue'
import EmailTemplatePage from '@/components/Settings/EmailTemplate/EmailTemplatePage.vue'
import EmailConfig from '@/components/Settings/EmailConfig.vue'
import Icon from '@/components/Icon.vue'
import { usersStore } from '@/stores/users'
import {
  showSettings,
  activeSettingsPage,
  disableSettingModalOutsideClick,
} from '@/composables/settings'
import { isWhatsappInstalled } from '@/composables/whatsapp'
import { isMessengerInstalled } from '@/composables/messenger'
import { Dialog, Avatar, SidebarItem, FormControl, Button } from 'frappe-ui'
import { ref, markRaw, computed, watch, h, nextTick } from 'vue'
import AssignmentRulePage from './AssignmentRules/AssignmentRulePage.vue'
import ShieldCheck from '~icons/lucide/shield-check'
import LucideZap from '~icons/lucide/zap'
import SlaConfig from './Sla/SlaConfig.vue'

const { isManager, isAdmin, getUser } = usersStore()

const user = computed(() => getUser() || {})

const tabs = computed(() => {
  let _tabs = [
    {
      label: __('User Configuration'),
      items: [
        {
          label: __('Profile'),
          icon: () =>
            h(Avatar, {
              size: 'xs',
              label: user.value.full_name,
              image: user.value.user_image,
            }),
          component: markRaw(ProfilePage),
        },
        {
          label: __('Preferences'),
          icon: SlidersIcon,
          component: markRaw(PreferencesSettings),
        },
        {
          label: __('Notification delivery'),
          icon: 'bell',
          component: markRaw(NotificationDelivery),
        },
      ],
    },
    {
      label: __('System Configuration'),
      items: [
        {
          label: __('General'),
          component: markRaw(GeneralSettings),
          icon: SettingsIcon,
        },
        {
          label: __('Touches and interactions'),
          component: markRaw(TouchSettings),
          icon: 'activity',
          condition: () => globalThis.crm_touch_settings_available === true,
        },
        {
          label: __('Dashboard'),
          component: markRaw(DashboardSettings),
          icon: LucideLayoutDashboard,
        },
        {
          label: __('Defaults'),
          component: markRaw(DefaultsSettings),
          icon: MonitorCogIcon,
        },
        {
          label: __('Calendar'),
          icon: CalendarIcon,
          component: markRaw(CalendarSettings),
        },
        {
          label: __('Sales Pipelines'),
          icon: 'git-branch',
          component: markRaw(SalesPipelines),
        },
      ],
      condition: () => isManager(),
    },
    {
      label: __('User Management'),
      items: [
        {
          label: __('Users'),
          icon: 'user',
          component: markRaw(Users),
          condition: () => isManager(),
        },
        {
          label: __('Sales Hierarchy'),
          icon: LucideNetwork,
          component: markRaw(Hierarchy),
          condition: () => isManager(),
        },
      ],
      condition: () => isManager(),
    },
    {
      label: __('Templates'),
      items: [
        {
          label: __('Email Templates'),
          icon: EmailTemplateIcon,
          component: markRaw(EmailTemplatePage),
        },
      ],
    },
    {
      label: __('Automation & Rules'),
      items: [
        {
          label: __('Assignment Rules'),
          icon: markRaw(h(SettingsIcon2, { class: 'rotate-90' })),
          component: markRaw(AssignmentRulePage),
        },
        {
          label: __('SLA Policies'),
          icon: markRaw(h(ShieldCheck)),
          component: markRaw(SlaConfig),
        },
        {
          label: __('Forms'),
          component: markRaw(FormsSettings),
          icon: markRaw(LucideTextCursorInput),
        },
        {
          label: __('Enrichment'),
          component: markRaw(EnrichmentSettings),
          icon: markRaw(LucideZap),
        },
      ],
      condition: () => isManager(),
    },
    {
      label: __('Integrations', null, 'FCRM'),
      items: [
        {
          label: __('Telephony'),
          icon: 'phone',
          component: markRaw(TelephonyPage),
        },
        {
          label: __('Message Channels'),
          icon: LucideMessagesSquare,
          component: markRaw(MessengerSettings),
          condition: () => isMessengerInstalled.value && isAdmin(),
        },
        {
          label: __('Email Accounts'),
          icon: 'mail',
          component: markRaw(EmailConfig),
          condition: () => isAdmin(),
        },
        {
          label: __('WhatsApp'),
          icon: WhatsAppIcon,
          component: markRaw(WhatsAppSettings),
          condition: () => isWhatsappInstalled.value && isManager(),
        },
        {
          label: __('EXP ERP'),
          icon: ERPNextIcon,
          component: markRaw(ERPNextSettings),
          condition: () => isManager(),
        },
        {
          label: __('Lead Syncing'),
          icon: 'refresh-cw',
          component: markRaw(LeadSyncSourcePage),
          condition: () => isManager(),
        },
      ],
    },
  ]

  return _tabs.filter((tab) => {
    if (tab.condition && !tab.condition()) return false
    if (tab.items) {
      tab.items = tab.items.filter((item) => {
        if (item.condition && !item.condition()) return false
        return true
      })
    }
    return true
  })
})

function closeSettings() {
  if (
    disableSettingModalOutsideClick.value &&
    !window.confirm(__('You have unsaved changes. Close without saving?'))
  )
    return
  showSettings.value = false
}

const activeTab = ref()
const sidebarContainer = ref(null)

const settingItems = computed(() => tabs.value.map((tab) => tab.items).flat())

function getFallbackTab() {
  return tabs.value[0]?.items?.[0]
}

function setActiveTab(tabName) {
  activeTab.value =
    (tabName && settingItems.value.find((tab) => tab.label === tabName)) ||
    getFallbackTab()
}

// Keep a deep-linked settings page visible in the sidebar.
function scrollActiveIntoView() {
  nextTick(() => {
    const el = sidebarContainer.value?.querySelector(
      `[data-page="${activeTab.value?.label}"]`,
    )
    const container = sidebarContainer.value
    if (!el || !container?.clientHeight) return
    const item = el.getBoundingClientRect()
    const bounds = container.getBoundingClientRect()
    if (item.top < bounds.top) container.scrollTop += item.top - bounds.top
    else if (item.bottom > bounds.bottom)
      container.scrollTop += item.bottom - bounds.bottom
  })
}

watch(
  activeSettingsPage,
  (activePage) => {
    setActiveTab(activePage)
    scrollActiveIntoView()
  },
  { immediate: true },
)

watch(tabs, () => setActiveTab(activeSettingsPage.value))
</script>
