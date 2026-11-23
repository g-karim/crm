<template>
  <div ref="container" class="h-full min-w-0 w-full" />
</template>

<script setup>
// Frappe UI's AxisChart config and options, with a bounded local lifecycle.
// The installed ECharts SFC schedules an uncancelled observer after unmount.
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useAxisChartOptions } from 'frappe-ui'
import { init } from 'echarts'

const props = defineProps({ config: { type: Object, required: true } })
const container = ref(null)
const options = computed(() => useAxisChartOptions(props.config))
let chart, observer, resizeFrame
onMounted(() => {
  chart = init(container.value, undefined, { renderer: 'svg' })
  chart.setOption(options.value, true)
  observer = new ResizeObserver(() => {
    cancelAnimationFrame(resizeFrame)
    resizeFrame = requestAnimationFrame(() => chart?.resize())
  })
  observer.observe(container.value)
})
watch(options, (value) => chart?.setOption(value, true), { deep: true })
onBeforeUnmount(() => {
  observer?.disconnect()
  cancelAnimationFrame(resizeFrame)
  chart?.dispose()
  chart = null
})
</script>
