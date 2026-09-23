import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { toast } from 'frappe-ui'
import { useUserSettings } from '@/data/userSettings'
import { moveVisibleTab, orderTabs } from '@/utils/tabOrder'

const ORDER_KEY = 'DetailTabOrder'

export function useReorderableTabs(doctype, defaultTabs, selectTab) {
  const tabRoot = ref(null)
  const savedOrder = ref([])
  const loaded = ref(false)
  const { get, save } = useUserSettings()
  const allTabs = computed(() => orderTabs(defaultTabs.value, savedOrder.value))
  const tabs = computed(() =>
    allTabs.value.filter((tab) => (tab.condition ? tab.condition() : true)),
  )
  let removeListeners
  let saving = false

  onMounted(async () => {
    for (let attempt = 0; attempt < 2; attempt++) {
      try {
        const settings = await get(doctype)
        savedOrder.value = settings[ORDER_KEY] || []
        loaded.value = true
        return
      } catch {
        if (attempt === 0) {
          await new Promise((resolve) => setTimeout(resolve, 500))
        } else {
          toast.error(__('Could not load tab order'))
        }
      }
    }
  })

  watch(
    [tabRoot, loaded],
    async ([root, ready]) => {
      removeListeners?.()
      removeListeners = null
      if (!root || !ready) return

      await nextTick()
      const tabList = root.$el?.querySelector('[role="tablist"]')
      if (!tabList) return

      let pointer = null
      let scrollTimer = null

      function stopScroll() {
        clearInterval(scrollTimer)
        scrollTimer = null
      }

      function startScroll() {
        if (scrollTimer) return
        scrollTimer = setInterval(() => {
          if (!pointer?.dragging) return
          const rect = tabList.getBoundingClientRect()
          if (pointer.x > rect.right - 35) tabList.scrollLeft += 15
          if (pointer.x < rect.left + 35) tabList.scrollLeft -= 15
        }, 40)
      }

      function onPointerDown(event) {
        if (event.pointerType !== 'mouse' || event.button !== 0 || saving)
          return
        const tab = event.target.closest('[role="tab"]')
        if (!tab || !tabList.contains(tab)) return
        const buttons = [...tabList.querySelectorAll(':scope > [role="tab"]')]
        pointer = {
          id: event.pointerId,
          tab,
          oldIndex: buttons.indexOf(tab),
          startX: event.clientX,
          startY: event.clientY,
          x: event.clientX,
          dragging: false,
        }
        tabList.setPointerCapture(event.pointerId)
      }

      // Reka selects a tab on mousedown. Defer selection until mouseup so
      // switching panels cannot remove the tab bar during a drag.
      function onMouseDown(event) {
        if (!pointer) return
        event.preventDefault()
        event.stopPropagation()
      }

      function onPointerMove(event) {
        if (!pointer || event.pointerId !== pointer.id) return
        pointer.x = event.clientX
        if (
          !pointer.dragging &&
          Math.hypot(
            event.clientX - pointer.startX,
            event.clientY - pointer.startY,
          ) > 6
        ) {
          pointer.dragging = true
          pointer.tab.classList.add('opacity-50')
          tabList.style.cursor = 'grabbing'
          startScroll()
        }
      }

      async function onPointerUp(event) {
        if (!pointer || event.pointerId !== pointer.id) return
        const current = pointer
        pointer = null
        stopScroll()
        current.tab.classList.remove('opacity-50')
        tabList.style.cursor = ''
        tabList.releasePointerCapture(event.pointerId)

        const buttons = [...tabList.querySelectorAll(':scope > [role="tab"]')]
        if (!current.dragging) {
          if (
            document
              .elementFromPoint(event.clientX, event.clientY)
              ?.closest('[role="tab"]') === current.tab
          ) {
            current.tab.focus()
            selectTab(current.oldIndex)
          }
          return
        }

        const slot = buttons.findIndex(
          (button) =>
            event.clientX <
            button.getBoundingClientRect().left + button.offsetWidth / 2,
        )
        const insertion = slot === -1 ? buttons.length : slot
        const newIndex = insertion - (current.oldIndex < insertion ? 1 : 0)
        const nextOrder = moveVisibleTab(
          allTabs.value,
          tabs.value,
          current.oldIndex,
          newIndex,
        )
        if (!nextOrder) return

        const previousOrder = savedOrder.value
        savedOrder.value = nextOrder
        saving = true
        try {
          await save(doctype, ORDER_KEY, nextOrder)
        } catch {
          savedOrder.value = previousOrder
          toast.error(__('Could not save tab order'))
        } finally {
          saving = false
        }
      }

      function onPointerCancel() {
        if (!pointer) return
        pointer.tab.classList.remove('opacity-50')
        pointer = null
        stopScroll()
        tabList.style.cursor = ''
      }

      tabList.addEventListener('pointerdown', onPointerDown)
      tabList.addEventListener('mousedown', onMouseDown, true)
      tabList.addEventListener('pointermove', onPointerMove)
      tabList.addEventListener('pointerup', onPointerUp)
      tabList.addEventListener('pointercancel', onPointerCancel)
      removeListeners = () => {
        stopScroll()
        tabList.removeEventListener('pointerdown', onPointerDown)
        tabList.removeEventListener('mousedown', onMouseDown, true)
        tabList.removeEventListener('pointermove', onPointerMove)
        tabList.removeEventListener('pointerup', onPointerUp)
        tabList.removeEventListener('pointercancel', onPointerCancel)
      }
    },
    { flush: 'post' },
  )

  onUnmounted(() => removeListeners?.())

  return { tabs, tabRoot }
}
