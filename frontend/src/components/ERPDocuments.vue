<template>
  <section
    class="mx-auto w-full max-w-5xl space-y-5 px-3 py-5 sm:px-8"
    aria-label="Документы ERP"
  >
    <div class="flex flex-wrap items-start justify-between gap-3">
      <div>
        <h2 class="text-lg font-semibold text-ink-gray-9">Документы сделки</h2>
        <p class="mt-1 text-sm text-ink-gray-6">
          Создавайте документы в ERP. Выданные файлы и их версии сохраняются
          здесь.
        </p>
      </div>
      <Button
        label="Обновить"
        icon-left="refresh-cw"
        :loading="resource.loading"
        @click="refresh"
      />
    </div>
    <div
      v-if="error || resource.error"
      role="alert"
      class="rounded-lg border border-outline-red-2 bg-surface-red-1 p-4 text-sm text-ink-red-4"
    >
      {{
        error ||
        resource.error?.messages?.join(' ') ||
        'Не удалось загрузить документы. Повторите запрос.'
      }}
    </div>
    <p
      v-if="resource.loading && !data"
      role="status"
      class="py-10 text-center text-ink-gray-6"
    >
      Загружаем документы…
    </p>
    <template v-if="data?.enabled">
      <div
        class="flex flex-wrap items-center gap-3 rounded-lg border border-outline-gray-2 p-4"
      >
        <label for="ru-seller" class="text-sm font-medium text-ink-gray-8"
          >Продавец</label
        >
        <select
          id="ru-seller"
          class="min-h-11 max-w-full flex-1 rounded border border-outline-gray-2 bg-surface-white px-3 text-sm text-ink-gray-9"
          :value="data.seller || ''"
          :disabled="saving"
          @change="setSeller($event.target.value)"
        >
          <option value="" disabled>Выберите юридическое лицо</option>
          <option
            v-for="company in data.companies"
            :key="company.name"
            :value="company.name"
          >
            {{ company.company_name }}
          </option>
        </select>
      </div>
      <div class="grid gap-3 sm:grid-cols-3">
        <div
          v-for="group in metrics"
          :key="group.label"
          class="rounded-lg bg-surface-gray-1 p-4"
        >
          <h3 class="text-sm font-semibold text-ink-gray-9">
            {{ group.label }}
          </h3>
          <dl class="mt-3 space-y-2">
            <div
              v-for="metric in group.rows"
              :key="metric.label"
              class="flex flex-wrap justify-between gap-2 text-sm"
            >
              <dt class="text-ink-gray-6">{{ metric.label }}</dt>
              <dd class="font-medium tabular-nums text-ink-gray-9">
                {{ metric.value }}
              </dd>
            </div>
          </dl>
        </div>
      </div>
      <div class="flex flex-wrap gap-2">
        <Button
          v-for="action in data.actions"
          :key="action.doctype"
          :label="action.label"
          :disabled="!action.enabled || !data.seller || opening"
          @click="openAction(action)"
        />
      </div>
      <div
        v-if="drafts.length"
        class="rounded-lg border border-outline-gray-2 p-4"
      >
        <h3 class="text-sm font-medium text-ink-gray-9">
          Можно продолжить черновик в ERP
        </h3>
        <a
          v-for="doc in drafts"
          :key="doc.doctype + doc.name"
          :href="safeURL(doc.url)"
          target="_blank"
          rel="noopener"
          class="flex min-h-11 items-center break-words text-sm text-ink-gray-9 underline"
        >
          {{ doc.title }} · {{ doc.name }}
        </a>
      </div>
      <div
        v-if="pendingAction"
        class="space-y-3 rounded-lg border border-outline-gray-2 p-4"
      >
        <label for="ru-source" class="block text-sm font-medium"
          >Выберите документ-основание</label
        >
        <select
          id="ru-source"
          v-model="sourceIndex"
          class="min-h-11 w-full rounded border border-outline-gray-2 bg-surface-white px-3 text-sm"
        >
          <option
            v-for="(source, i) in pendingAction.sources"
            :key="source.name"
            :value="i"
          >
            {{ source.name }}
          </option>
        </select>
        <div class="flex gap-2">
          <Button
            label="Открыть в ERP"
            variant="solid"
            :loading="opening"
            @click="navigate(pendingAction, pendingAction.sources[sourceIndex])"
          /><Button label="Отмена" @click="pendingAction = null" />
        </div>
      </div>
      <div>
        <h3 class="mb-3 text-base font-semibold text-ink-gray-9">
          Закреплённые файлы
        </h3>
        <p
          v-if="!currentIssues.length"
          class="rounded-lg border border-dashed border-outline-gray-2 p-5 text-sm text-ink-gray-6"
        >
          После выпуска PDF в ERP файл появится здесь. Сохранение черновика ещё
          не создаёт выданный экземпляр.
        </p>
        <div class="grid gap-3 sm:grid-cols-2">
          <article
            v-for="issue in currentIssues"
            :key="issue.name"
            class="min-w-0 rounded-lg border border-outline-gray-2 p-4"
          >
            <div class="flex items-start gap-3">
              <FeatherIcon
                name="file-text"
                class="mt-0.5 h-5 w-5 shrink-0 text-ink-gray-6"
              />
              <div class="min-w-0 flex-1">
                <h4 class="break-words text-sm font-semibold text-ink-gray-9">
                  {{ issue.title }}
                </h4>
                <p class="mt-1 break-words text-xs text-ink-gray-6">
                  {{ issue.number }} · версия {{ issue.revision }}
                </p>
              </div>
              <span class="shrink-0 text-xs text-ink-gray-6">{{
                issue.signed ? 'Подписан' : 'Без подписи'
              }}</span>
            </div>
            <div
              v-if="issue.can_read"
              class="mt-4 flex flex-wrap gap-3 text-sm"
            >
              <a
                :href="safeURL(issue.file_url)"
                target="_blank"
                rel="noopener"
                class="inline-flex min-h-11 items-center font-medium text-ink-gray-9 underline"
                >Просмотреть PDF</a
              >
              <a
                :href="safeURL(issue.file_url)"
                download
                class="inline-flex min-h-11 items-center text-ink-gray-8 underline"
                >Скачать</a
              >
            </div>
            <p v-else class="mt-4 text-sm text-ink-gray-6">
              Файл подготовлен. Ответственный сотрудник ещё не открыл доступ.
            </p>
            <a
              v-for="evidence in issue.evidence || []"
              :key="evidence.name"
              :href="safeURL(evidence.file)"
              target="_blank"
              rel="noopener"
              class="mt-1 flex min-h-11 items-center text-sm text-ink-gray-9 underline"
            >
              {{ evidence.kind
              }}{{ evidence.docstatus === 2 ? ' · отменён' : '' }}
            </a>
          </article>
        </div>
      </div>
      <div>
        <h3 class="mb-3 text-base font-semibold text-ink-gray-9">
          Документы в ERP
        </h3>
        <p v-if="!data.documents.length" class="text-sm text-ink-gray-6">
          Начните с коммерческого предложения.
        </p>
        <div
          v-for="doc in data.documents"
          :key="doc.doctype + doc.name"
          class="flex flex-wrap items-center justify-between gap-3 border-b border-outline-gray-2 py-3"
        >
          <div class="min-w-0">
            <p class="text-sm font-medium text-ink-gray-9">{{ doc.title }}</p>
            <p class="break-words text-xs text-ink-gray-6">
              {{ doc.name }} · {{ doc.status }}
            </p>
          </div>
          <div class="flex items-center gap-4">
            <span v-if="doc.amount != null" class="text-sm tabular-nums">{{
              rubles(doc.amount)
            }}</span
            ><a
              v-if="doc.can_open"
              :href="safeURL(doc.url)"
              target="_blank"
              rel="noopener"
              class="inline-flex min-h-11 items-center text-sm text-ink-gray-9 underline"
              >Открыть в ERP</a
            >
          </div>
        </div>
      </div>
      <details
        v-if="history.length"
        class="rounded-lg border border-outline-gray-2 p-4"
      >
        <summary class="cursor-pointer text-sm font-medium text-ink-gray-8">
          Предыдущие версии и отменённые документы ({{ history.length }})
        </summary>
        <div
          v-for="issue in history"
          :key="issue.name"
          class="mt-3 flex flex-wrap items-center justify-between gap-2 text-sm"
        >
          <span
            >{{ issue.title }} · версия {{ issue.revision }} ·
            {{ issue.state }}</span
          ><a
            v-if="issue.can_read"
            :href="safeURL(issue.file_url)"
            target="_blank"
            rel="noopener"
            class="min-h-11 py-3 underline"
            >PDF</a
          >
          <a
            v-for="evidence in issue.evidence || []"
            :key="evidence.name"
            :href="safeURL(evidence.file)"
            target="_blank"
            rel="noopener"
            class="min-h-11 py-3 underline"
          >
            {{ evidence.kind
            }}{{ evidence.docstatus === 2 ? ' · отменён' : '' }}
          </a>
        </div>
      </details>
    </template>
  </section>
</template>

<script setup>
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { Button, FeatherIcon, createResource, call } from 'frappe-ui'
import { safeDocumentURL, currentDocumentIssues } from '@/utils/erpDocuments'

const props = defineProps({ deal: { type: String, required: true } })
const error = ref(''),
  saving = ref(false),
  opening = ref(false),
  pendingAction = ref(null),
  sourceIndex = ref(0)
const resource = createResource({
  url: 'crm.api.erp_documents.get_deal_documents',
  params: { deal: props.deal },
  auto: true,
})
const data = computed(() => resource.data)
const drafts = computed(() =>
  (data.value?.documents || []).filter(
    (doc) => doc.docstatus === 0 && doc.can_open,
  ),
)
const currentIssues = computed(() =>
  currentDocumentIssues(data.value?.issues || []),
)
const history = computed(() =>
  (data.value?.issues || []).filter((i) => i.state !== 'Действует'),
)
const rubles = (value) =>
  new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'RUB' }).format(
    value || 0,
  )
const safeURL = (value) => safeDocumentURL(value, window.location.origin)
const metrics = computed(() => [
  {
    label: 'Расчёты',
    rows: [
      { label: 'Реализовано', value: rubles(data.value?.summary?.invoiced) },
      {
        label: 'Получено за вычетом возвратов',
        value: rubles(data.value?.summary?.received),
      },
      {
        label: 'Остаток долга',
        value: rubles(data.value?.summary?.outstanding),
      },
    ],
  },
  {
    label: 'Исполнение',
    rows: [
      {
        label: 'Отгружено по заказам',
        value: `${Math.round(data.value?.summary?.delivered || 0)}%`,
      },
      {
        label: 'Возвращено единиц',
        value: data.value?.summary?.returned_qty || 0,
      },
      {
        label: 'Актов приёмки',
        value: data.value?.summary?.acceptance_acts || 0,
      },
    ],
  },
  {
    label: 'Документы',
    rows: [
      {
        label: 'Действующих выпусков',
        value: data.value?.summary?.issued || 0,
      },
      {
        label: 'С подписанным экземпляром',
        value: data.value?.summary?.signed || 0,
      },
      { label: 'Открытых претензий', value: data.value?.summary?.claims || 0 },
    ],
  },
])
async function refresh() {
  error.value = ''
  try {
    await resource.reload()
  } catch {
    /* resource exposes the error */
  }
}
async function setSeller(company) {
  saving.value = true
  error.value = ''
  try {
    await call('crm.api.erp_documents.set_seller', {
      deal: props.deal,
      company,
    })
    await refresh()
  } catch (e) {
    error.value =
      e.messages?.join(' ') || e.message || 'Не удалось сохранить продавца'
    await resource.reload()
  } finally {
    saving.value = false
  }
}
function openAction(action) {
  if (action.sources.length > 1) {
    pendingAction.value = action
    sourceIndex.value = 0
  } else navigate(action, action.sources[0])
}
async function navigate(action, source) {
  // Open synchronously so browser popup protection does not discard the ERP tab.
  const target = window.open('about:blank', '_blank')
  if (target) target.opener = null
  opening.value = true
  error.value = ''
  try {
    const route = await call('crm.api.erp_documents.document_route', {
      deal: props.deal,
      doctype: action.doctype,
      source_doctype: source?.doctype,
      source_name: source?.name,
    })
    const url = safeURL(route)
    if (!url) throw new Error('Некорректная ссылка ERP')
    if (target) target.location.replace(url)
    else window.location.assign(url)
    pendingAction.value = null
  } catch (e) {
    target?.close()
    error.value = e.messages?.join(' ') || e.message || 'Не удалось открыть ERP'
  } finally {
    opening.value = false
  }
}
const onFocus = () => refresh()
onMounted(() => window.addEventListener('focus', onFocus))
onBeforeUnmount(() => window.removeEventListener('focus', onFocus))
watch(
  () => props.deal,
  (deal) => {
    resource.update({ params: { deal } })
    refresh()
  },
)
</script>
