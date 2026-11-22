<template>
  <div class="min-h-0 min-w-0 flex-1 overflow-y-auto p-4 sm:p-6">
    <div v-if="step === 'email-add'" class="h-full">
      <EmailAdd @update:step="updateStep" />
    </div>
    <div v-else-if="step === 'email-list'" class="h-full">
      <EmailAccountList @update:step="updateStep" />
    </div>
    <div v-else-if="step === 'email-edit'" class="h-full">
      <EmailEdit :account-data="accountData" @update:step="updateStep" />
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import EmailAdd from './EmailAdd.vue'
import EmailAccountList from './EmailAccountList.vue'
import EmailEdit from './EmailEdit.vue'

const step = ref('email-list')
const accountData = ref(null)
function updateStep(newStep, data) {
  step.value = newStep
  accountData.value = data
}
</script>
