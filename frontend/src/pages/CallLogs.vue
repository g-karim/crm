<template>
  <LayoutHeader>
    <template #left-header>
      <ViewBreadcrumbs v-model="viewControls" routeName="Call Logs" />
    </template>
    <template #right-header>
      <Button
        :label="__('Telephony')"
        icon-left="lucide-phone"
        variant="ghost"
        @click="$router.push({ name: 'Telephony' })"
      />
      <CustomActions
        v-if="callLogsListView?.customListActions"
        :actions="callLogsListView.customListActions"
      />
      <Button :route="analyticsRoute" icon-left="lucide-chart-column">
        {{ __('Аналитика звонков') }}
      </Button>
      <Button
        variant="solid"
        :label="__('Create')"
        iconLeft="plus"
        @click="createCallLog"
      />
    </template>
  </LayoutHeader>
  <CallJournalSlice
    v-if="scoped"
    :filters="scopedFilters"
    @open="showCallLog"
  />
  <ViewControls
    v-if="!scoped"
    ref="viewControls"
    v-model="callLogs"
    v-model:loadMore="loadMore"
    v-model:resizeColumn="triggerResize"
    v-model:updatedPageCount="updatedPageCount"
    doctype="CRM Call Log"
  />
  <CallLogsListView
    v-if="!scoped && callLogs.data && rows.length"
    ref="callLogsListView"
    v-model="callLogs.data.page_length_count"
    v-model:list="callLogs"
    :rows="rows"
    :columns="columns"
    :options="{
      showTooltip: false,
      resizeColumn: true,
      rowCount: callLogs.data.row_count,
      totalCount: callLogs.data.total_count,
    }"
    @showCallLog="showCallLog"
    @loadMore="() => loadMore++"
    @columnWidthUpdated="() => triggerResize++"
    @updatePageCount="(count) => (updatedPageCount = count)"
    @applyFilter="(data) => viewControls.applyFilter(data)"
    @applyLikeFilter="(data) => viewControls.applyLikeFilter(data)"
    @likeDoc="(data) => viewControls.likeDoc(data)"
    @selectionsChanged="
      (selections) => viewControls.updateSelections(selections)
    "
  />
  <EmptyState
    v-else-if="!scoped && callLogs.data && !rows.length"
    name="Call Logs"
    :icon="PhoneIcon"
  />
  <CallLogDetailModal
    v-model="showCallLogDetailModal"
    :analytics-scope="scoped"
    v-model:callLog="callLog"
  />
</template>

<script setup>
import ViewBreadcrumbs from '@/components/ViewBreadcrumbs.vue'
import CustomActions from '@/components/CustomActions.vue'
import PhoneIcon from '@/components/Icons/PhoneIcon.vue'
import LayoutHeader from '@/components/LayoutHeader.vue'
import ViewControls from '@/components/ViewControls.vue'
import CallLogsListView from '@/components/ListViews/CallLogsListView.vue'
import EmptyState from '@/components/ListViews/EmptyState.vue'
import CallLogDetailModal from '@/components/Modals/CallLogDetailModal.vue'
import CallJournalSlice from '@/components/Analytics/CallJournalSlice.vue'
import { callReportFilters, callScopeQuery } from '@/utils/callAnalyticsRoute'
import { useRoute } from 'vue-router'
import { useDoctypeModal } from '@/composables/doctypeModal'
import { getCallLogDetail } from '@/utils/callLog'
import { useTelemetry } from 'frappe-ui/frappe'
import { createResource } from 'frappe-ui'
import { computed, ref, onMounted } from 'vue'
import { useEventListener } from '@vueuse/core'

const route = useRoute()
const scoped = computed(() => route.query.call_scope === 'analytics')
const scopedFilters = computed(() => callReportFilters(route.query))
const analyticsRoute = computed(() => ({
  name: 'Dashboard',
  query: {
    ...callScopeQuery(route.query),
    ...(scoped.value && route.query.analytics_return === 'call-attribution'
      ? { section: 'sources', sources_view: 'call-attribution' }
      : { section: 'calls' }),
  },
}))
const callLogsListView = ref(null)

// callLogs data is loaded in the ViewControls component
const callLogs = ref({})
useEventListener(window, 'crm-exolve-calls-updated', () =>
  callLogs.value?.reload?.(),
)
const loadMore = ref(1)
const triggerResize = ref(1)
const updatedPageCount = ref(20)
const viewControls = ref(null)

const rows = computed(() => {
  if (
    !callLogs.value?.data?.data ||
    !['list', 'group_by'].includes(callLogs.value.data.view_type)
  )
    return []
  return callLogs.value?.data.data.map((callLog) => {
    let _rows = {}
    callLogs.value?.data.rows.forEach((row) => {
      _rows[row] = getCallLogDetail(row, callLog, callLogs.value?.data.columns)
    })
    return _rows
  })
})

const columns = computed(() => {
  let _columns = callLogs.value?.data?.columns || []

  // Set align right for last column
  if (_columns.length) {
    _columns = _columns.map((col, index) => {
      if (index === _columns.length - 1) {
        return { ...col, align: 'right' }
      }
      return col
    })
  }

  return _columns
})

const showCallLogDetailModal = ref(false)
const callLog = ref({})

function showCallLog(name) {
  showCallLogDetailModal.value = true
  callLog.value = createResource({
    url: scoped.value
      ? 'crm.analytics.call_journal.get_scoped_call_log'
      : 'crm.fcrm.doctype.crm_call_log.crm_call_log.get_call_log',
    params: { name },
    method: scoped.value ? 'GET' : 'POST',
    auto: true,
  })
}

const { showModal } = useDoctypeModal()
const { capture } = useTelemetry()

function createCallLog() {
  showModal({
    doctype: 'CRM Call Log',
    title: 'Call Log',
    callbacks: {
      afterInsert: () => {
        capture('call_log_created')
        callLogs.value.reload()
      },
    },
  })
}

const openCallLogFromURL = () => {
  const searchParams = new URLSearchParams(window.location.search)
  const callLogName = searchParams.get('open')

  if (callLogName) {
    showCallLog(callLogName)
    if (!scoped.value) {
      searchParams.delete('open')
      const query = searchParams.toString()
      window.history.replaceState(
        window.history.state,
        '',
        window.location.pathname + (query ? '?' + query : ''),
      )
    }
  }
}

onMounted(() => {
  openCallLogFromURL()
})
</script>
