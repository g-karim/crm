<template>
  <Combobox :multiple="true">
    <Popover placement="bottom-end">
      <template #target="{ togglePopover }">
        <Button
          variant="subtle"
          icon-left="plus"
          :label="__('Add Assignee')"
          @click="togglePopover()"
        />
      </template>
      <template #body>
        <div
          class="mt-1 rounded-lg bg-surface-white py-1 text-base shadow-2xl w-60"
        >
          <div class="relative px-1.5 pt-0.5">
            <ComboboxInput
              ref="search"
              class="form-input w-full"
              type="text"
              :value="query"
              autocomplete="off"
              :placeholder="__('Search')"
              @change="(e) => debouncedQuery(e.target.value)"
            />
            <button
              class="absolute right-1.5 inline-flex h-7 w-7 items-center justify-center"
              @click="query = ''"
            >
              <FeatherIcon name="x" class="w-4" />
            </button>
          </div>
          <ComboboxOptions class="my-2 max-h-64 overflow-y-auto px-1.5" static>
            <ComboboxOption
              v-for="user in usersList"
              v-show="usersList.length > 0"
              :key="user.username"
              v-slot="{ active }"
              :value="user"
              as="template"
              @click="
                (e) => {
                  e.stopPropagation()
                  addAssignee(user)
                }
              "
            >
              <li
                class="flex items-center rounded p-1.5 w-full text-base"
                :class="{ 'bg-surface-gray-1': active }"
              >
                <div class="flex gap-2 items-center w-full select-none">
                  <Avatar
                    :shape="'circle'"
                    :image="user.user_image"
                    :label="user.full_name"
                    size="lg"
                  />
                  <div class="flex flex-col gap-1">
                    <div class="font-semibold text-ink-gray-7">
                      {{ user.full_name }}
                    </div>
                    <div class="text-ink-gray-6">{{ user.email }}</div>
                  </div>
                </div>
              </li>
            </ComboboxOption>
            <li
              v-if="usersList.length == 0"
              class="mt-1.5 rounded-md p-1.5 text-base text-ink-gray-5"
            >
              {{ __('No Results Found') }}
            </li>
          </ComboboxOptions>
        </div>
      </template>
    </Popover>
  </Combobox>
</template>

<script setup>
import {
  Combobox,
  ComboboxInput,
  ComboboxOption,
  ComboboxOptions,
} from '@headlessui/vue'
import { useDebounceFn } from '@vueuse/core'
import { Avatar, Popover } from 'frappe-ui'
import { computed, inject, ref } from 'vue'
import { usersStore } from '@/stores/users'

const emit = defineEmits(['addAssignee'])
const query = ref('')
const { users } = usersStore()
const assignmentRuleData = inject('assignmentRuleData')

const debouncedQuery = useDebounceFn((val) => {
  query.value = val
}, 300)

const usersList = computed(() => {
  let filteredUsers =
    users.data?.crmUsers?.filter((user) => user.name !== 'Administrator') || []

  return filteredUsers
    .filter(
      (user) =>
        user.name?.includes(query.value) ||
        user.full_name?.includes(query.value),
    )
    .filter((user) => {
      return !assignmentRuleData.value.users.some((u) => u.user === user.email)
    })
})

const addAssignee = (user) => {
  const userExists = assignmentRuleData.value.users.some(
    (u) => u.user === user.user,
  )
  if (!userExists) {
    assignmentRuleData.value.users.push({
      full_name: user.full_name,
      email: user.email,
      user_image: user.user_image,
      user: user.email,
    })
    emit('addAssignee', user)
  }
}

</script>
