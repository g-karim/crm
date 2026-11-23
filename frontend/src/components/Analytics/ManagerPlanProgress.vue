<template>
  <div class="plan-progress">
    <p v-if="showLabel" class="mb-0.5 font-medium text-ink-gray-9">
      {{ label }}
    </p>
    <div class="plan-progress-values">
      <span class="text-ink-gray-8">
        {{ actual }}
        <span v-if="target != null" class="text-ink-gray-7"
          >/ {{ target }}</span
        >
      </span>
      <strong
        v-if="percent != null"
        :class="achieved ? 'text-ink-green-9' : 'text-ink-gray-9'"
        >{{ percentLabel }}</strong
      >
    </div>
    <Progress
      v-if="percent != null"
      aria-hidden="true"
      size="lg"
      :value="Number(percent)"
      :class="achieved ? 'achieved' : 'in-progress'"
    />
    <span v-else class="text-sm text-ink-gray-7">{{ emptyLabel }}</span>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Progress } from 'frappe-ui'
const props = defineProps({
  label: { type: String, required: true },
  showLabel: { type: Boolean, default: true },
  actual: { type: String, required: true },
  target: { type: String, default: null },
  percent: { type: [String, Number], default: null },
  percentLabel: { type: String, default: '' },
  emptyLabel: { type: String, required: true },
})
const achieved = computed(() => Number(props.percent) >= 100)
</script>

<style scoped>
.plan-progress {
  width: 100%;
  max-width: 320px;
  font-size: 12px;
  line-height: 1.4;
}
.plan-progress-values {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 2px 8px;
  margin-bottom: 5px;
  font-variant-numeric: tabular-nums;
}
.plan-progress :deep([role='progressbar']) {
  background: var(--surface-gray-4);
}
.plan-progress :deep([role='progressbar'] > div) {
  background: var(--ink-blue-8);
}
.plan-progress .achieved :deep([role='progressbar'] > div) {
  background: var(--ink-green-8);
}
</style>
