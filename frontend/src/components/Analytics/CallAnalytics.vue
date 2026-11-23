<template>
  <div class="call-analytics">
    <div class="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h3
          ref="heading"
          tabindex="-1"
          class="text-xl-semibold text-ink-gray-9"
        >
          {{ t('Call analytics', 'Аналитика звонков') }}
        </h3>
        <p v-if="report" class="mt-1 text-base text-ink-gray-7">
          {{ periodLabel(report.period) }} · {{ report.period.timezone }}
        </p>
      </div>
      <Button :route="journal()" icon-left="lucide-phone">
        {{ t('Call journal', 'Журнал звонков') }}
      </Button>
    </div>

    <form class="call-filters" @submit.prevent="apply">
      <div>
        <FormControl
          v-model="draft.direction"
          type="select"
          :label="t('Direction', 'Направление')"
          :options="directions"
        />
      </div>
      <div>
        <FormControl
          v-model="draft.line"
          type="select"
          :label="t('Line', 'Линия')"
          :options="lineOptions"
        />
      </div>
      <div v-if="report?.coverage.outcomes">
        <FormControl
          v-model="draft.outcome"
          type="select"
          :label="t('Outcome', 'Итог звонка')"
          :options="outcomes"
        />
      </div>
      <Button
        type="submit"
        variant="solid"
        :disabled="stale"
        :loading="loading"
      >
        {{ t('Apply', 'Применить') }}
      </Button>
    </form>

    <Alert v-if="error" theme="red" :dismissible="false" :title="error">
      <template #footer
        ><Button variant="ghost" @click="load">{{
          t('Refresh', 'Обновить')
        }}</Button></template
      >
    </Alert>
    <p v-else-if="loading" role="status" class="py-8 text-ink-gray-7">
      {{ t('Loading calls…', 'Загрузка звонков…') }}
    </p>
    <template v-else-if="report">
      <Alert
        v-if="summaryJumpChanged"
        theme="yellow"
        :dismissible="false"
        :title="
          t(
            'Call data changed since the summary. The current report is shown.',
            'Данные звонков изменились после сводки. Показан текущий отчёт.',
          )
        "
      />
      <TabButtons
        v-model="view"
        class="call-views"
        :options="views"
        :aria-label="t('Call report details', 'Разделы отчёта по звонкам')"
      />
      <template v-if="view === 'summary'">
        <div class="call-kpis">
          <Button
            v-for="kd in kpis"
            :key="kd.key"
            variant="ghost"
            class="call-kpi"
            :disabled="kd.value == null"
            @click="openDetails(kd.key)"
          >
            <span class="call-kpi-content">
              <span>{{ kd.label }}</span>
              <strong>{{ kd.value ?? '—' }}</strong>
            </span>
          </Button>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <Button
            icon-left="lucide-columns-2"
            :aria-expanded="comparisonOpen"
            aria-controls="call-period-comparison"
            @click="comparisonOpen = !comparisonOpen"
          >
            {{ t('Compare periods', 'Сравнить периоды') }}
          </Button>
          <Button
            v-if="report.metrics.overdue"
            icon-left="lucide-clock"
            @click="openDetails('overdue')"
          >
            {{ t('Overdue callbacks', 'Просроченные перезвоны') }} ·
            {{ formatCount(report.metrics.overdue) }}
          </Button>
        </div>
        <Card
          v-show="comparisonOpen"
          id="call-period-comparison"
          class="call-card"
          :title="
            t(
              'Compared with the previous period',
              'Сравнение с предыдущим периодом',
            )
          "
        >
          <Alert
            v-if="comparisonError"
            theme="red"
            :dismissible="false"
            :title="comparisonError"
          >
            <template #footer>
              <Button variant="ghost" @click="loadComparison">
                {{ t('Retry', 'Повторить') }}
              </Button>
            </template>
          </Alert>
          <p v-else-if="comparisonLoading" role="status">
            {{ t('Loading comparison…', 'Загрузка сравнения…') }}
          </p>
          <template v-else-if="report.comparison">
            <p class="mb-3 text-base text-ink-gray-7">
              {{
                t(
                  'The comparison uses calls available in the journal. Both periods span the same number of calendar days and use the same filters.',
                  'Сравнение по доступным звонкам журнала. Оба периода содержат одинаковое число календарных дней и используют те же фильтры.',
                )
              }}
              <template v-if="currentDayInPeriod">
                {{
                  t(
                    'Today is counted up to the report time.',
                    'Сегодня учитывается до времени расчёта.',
                  )
                }}
              </template>
            </p>
            <AnalyticsTable
              :columns="periodColumns"
              :rows="periodRows"
              :label="
                t('Call comparison by period', 'Сравнение звонков по периодам')
              "
            >
              <template #cell="{ row, column, value }">
                <Button
                  v-if="
                    (column.key === 'current' || column.key === 'previous') &&
                    value != null
                  "
                  :aria-label="periodCellLabel(row, column, value)"
                  variant="ghost"
                  class="h-auto py-1.5"
                  @click="
                    openDetails(
                      row.key,
                      null,
                      null,
                      column.key === 'previous' ? report.comparison : report,
                    )
                  "
                >
                  <span class="grid gap-1 text-right">
                    <span class="underline underline-offset-4">
                      {{ row.rate ? percent(value) : formatCount(value) }}
                    </span>
                    <span
                      v-if="row.bases?.[column.key]"
                      class="text-sm text-ink-gray-7"
                    >
                      {{ basisLabel(row.bases[column.key]) }}
                    </span>
                  </span>
                </Button>
                <span v-else-if="column.key === 'change'">
                  {{
                    row.rate
                      ? formatPointChange(value)
                      : formatCount(value, true)
                  }}
                </span>
                <span v-else>{{ value ?? '—' }}</span>
              </template>
            </AnalyticsTable>
            <p class="mt-3 text-sm text-ink-gray-7">
              {{
                t(
                  'Open a rate to see the underlying calls. A dash indicates insufficient data. Rate changes are shown in percentage points.',
                  'Нажмите на долю, чтобы посмотреть учтённые звонки. Тире означает, что данных для расчёта доли нет. Изменение долей указано в процентных пунктах.',
                )
              }}
            </p>
          </template>
        </Card>
        <Card class="call-card" :title="trendTitle">
          <template #actions>
            <TabButtons
              v-model="trend"
              :options="trendOptions"
              :aria-label="t('Group calls by', 'Группировка звонков')"
            />
          </template>
          <p v-if="trend === 'weeks'" class="mb-2 text-sm text-ink-gray-7">
            {{
              t(
                'Weeks start on Monday. Only calls within the selected dates are included.',
                'Неделя начинается в понедельник. Учитываются звонки в пределах выбранных дат.',
              )
            }}
          </p>
          <div
            v-if="trendRows.length"
            class="h-56"
            role="img"
            :aria-label="trendTitle"
          >
            <AnalyticsChart :config="chart" />
          </div>
          <AnalyticsTable
            :columns="trendColumns"
            :rows="trendRows"
            :label="trendTitle + '. ' + t('Exact counts', 'Точные значения')"
            :empty-text="
              t(
                'The permitted journal has no calls in this period.',
                'В доступном журнале нет звонков за выбранный период.',
              )
            "
          >
            <template #cell="{ row, column, value }">
              <Button
                v-if="column.key === 'key'"
                variant="ghost"
                @click="openDetails('total', trend, row.key)"
                >{{ dateOnly(value) }}</Button
              >
              <span v-else>{{ value }}</span>
            </template>
          </AnalyticsTable>
        </Card>
      </template>
      <template v-else-if="view === 'sla'">
        <div v-if="report.can_manage_sla" class="flex justify-end">
          <Button icon-left="lucide-settings-2" @click="settingsOpen = true">
            {{ t('SLA settings', 'Правила перезвона') }}
          </Button>
        </div>
        <Alert
          v-if="!report.coverage.sla"
          theme="yellow"
          :dismissible="false"
          :title="
            t(
              'SLA needs working hours and verified callback links',
              'Для расчёта SLA нужны рабочий график и подтверждённые связи перезвонов',
            )
          "
        />
        <p v-else class="text-sm text-ink-gray-7">
          {{
            report.coverage.require_original_employee
              ? t(
                  'SLA requires a conversation by the employee who received the missed call.',
                  'В SLA засчитывается разговор сотрудника, которому поступил пропущенный звонок.',
                )
              : t(
                  'SLA accepts a confirmed conversation, including callbacks made by another employee.',
                  'В SLA засчитывается подтверждённый разговор, в том числе если перезвонил коллега.',
                )
          }}
        </p>
        <div class="call-kpis">
          <Button
            v-for="kd in slaCards"
            :key="kd.key"
            variant="ghost"
            class="call-kpi"
            :disabled="kd.value == null"
            @click="openDetails(kd.key)"
          >
            <span class="call-kpi-content">
              <span>{{ kd.label }}</span>
              <strong>{{ kd.value ?? '—' }}</strong>
            </span>
          </Button>
        </div>
        <Card
          class="call-card"
          :title="t('Callback response times', 'Скорость перезвона')"
        >
          <dl class="call-pairs">
            <div>
              <dt>{{ t('Callback SLA met', 'Доля перезвонов в срок') }}</dt>
              <dd>
                <Button
                  v-if="report.metrics.sla_percent != null"
                  variant="ghost"
                  class="underline underline-offset-4"
                  @click="openDetails('sla_percent')"
                >
                  {{ percent(report.metrics.sla_percent) }}
                </Button>
                <span v-else>—</span>
                <span
                  v-if="report.metrics.sla_decided > 0"
                  class="block text-sm text-ink-gray-7"
                  >{{
                    t(
                      `${report.metrics.on_time} of ${report.metrics.sla_decided} evaluated`,
                      `${report.metrics.on_time} из ${report.metrics.sla_decided} учтённых`,
                    )
                  }}</span
                >
              </dd>
            </div>
            <div>
              <dt>
                {{
                  t(
                    'Median time to first confirmed attempt',
                    'Медиана до подтверждённой попытки',
                  )
                }}
              </dt>
              <dd>{{ duration(report.metrics.median_attempt_seconds) }}</dd>
            </div>
            <div>
              <dt>
                {{
                  t(
                    '90th percentile for attempts',
                    '90-й процентиль времени до попытки',
                  )
                }}
              </dt>
              <dd>{{ duration(report.metrics.p90_attempt_seconds) }}</dd>
            </div>
            <div>
              <dt>
                {{
                  t(
                    'Median time to recorded connection',
                    'Медиана до соединения по журналу',
                  )
                }}
              </dt>
              <dd>
                {{ duration(report.metrics.median_conversation_seconds) }}
              </dd>
            </div>
            <div>
              <dt>
                {{
                  t(
                    '90th percentile for connection',
                    '90-й процентиль времени до соединения',
                  )
                }}
              </dt>
              <dd>{{ duration(report.metrics.p90_conversation_seconds) }}</dd>
            </div>
          </dl>
          <p class="mt-3 text-sm text-ink-gray-7">
            {{ t('Confirmed attempts', 'Подтверждённые попытки') }}:
            {{ report.metrics.attempts_confirmed }}.
            {{
              t(
                'Connections with a recorded time',
                'Соединения с известным временем',
              )
            }}: {{ report.metrics.connections_timed }}.
            {{
              t(
                'Percentiles require at least 10 observations.',
                'Для каждого процентиля нужно минимум 10 наблюдений.',
              )
            }}
          </p>
          <Button class="mt-3" @click="openDetails('missed')">{{
            t('Open missed calls', 'Открыть пропущенные звонки')
          }}</Button>
        </Card>
      </template>
      <template v-else-if="view === 'team'">
        <Card class="call-card" :title="t('Answer rates', 'Доля дозвона')">
          <dl class="call-pairs">
            <div v-for="rate in answerRates" :key="rate.key">
              <dt>{{ rate.label }}</dt>
              <dd>
                <Button
                  v-if="rate.value != null"
                  variant="ghost"
                  class="underline underline-offset-4"
                  @click="openDetails(rate.key)"
                >
                  {{ percent(rate.value) }}
                </Button>
                <span v-else>—</span>
              </dd>
            </div>
          </dl>
        </Card>
        <Card
          class="call-card"
          :title="t('Compare calls', 'Сравнение звонков')"
        >
          <div class="mb-4 grid grid-cols-1 gap-3 sm:max-w-lg sm:grid-cols-2">
            <FormControl
              v-model="comparisonGroup"
              type="select"
              :label="t('Group by', 'Группировка')"
              :options="teamGroups"
            />
            <FormControl
              v-model="comparisonMetrics"
              type="select"
              :label="t('Metrics', 'Показатели')"
              :options="comparisonOptions"
            />
          </div>
          <p
            v-if="comparisonGroup === 'teams'"
            class="mb-2 text-sm text-ink-gray-7"
          >
            {{
              t(
                'A call can appear in both a team and its parent team.',
                'Звонок может учитываться в команде и в её вышестоящей команде.',
              )
            }}
          </p>
          <AnalyticsTable
            :columns="groupColumns"
            :rows="report.groups[comparisonGroup]"
            :label="
              teamGroups.find((option) => option.value === comparisonGroup)
                .label
            "
            :empty-text="
              t('No data in this selection.', 'В выбранном срезе нет данных.')
            "
          >
            <template #cell="{ row, column, value }">
              <Button
                v-if="column.key === 'label'"
                variant="ghost"
                @click="openDetails('total', comparisonGroup, row.key)"
              >
                {{
                  comparisonGroup === 'weekdays'
                    ? weekdays[Number(value)]
                    : value || t('Unassigned', 'Не указан')
                }}
              </Button>
              <template v-else-if="column.format === 'percent'">
                <Button
                  v-if="value != null"
                  variant="ghost"
                  class="underline underline-offset-4"
                  :aria-label="`${row.label || t('Unassigned', 'Не указан')}, ${column.label}, ${percent(value)}`"
                  @click="openDetails(column.key, comparisonGroup, row.key)"
                >
                  {{ percent(value) }}
                </Button>
                <span v-else>—</span>
              </template>
              <span v-else-if="column.format === 'duration'">{{
                duration(value)
              }}</span>
              <span v-else>{{ value ?? '—' }}</span>
            </template>
          </AnalyticsTable>
        </Card>
      </template>
      <template v-else>
        <CallQualityReview
          :filters="selection"
          :zone="context.timezone"
          :lang="lang"
          :t="t"
          :journal-route="journal"
          @editing="qualityEditing = $event"
        />
        <Card
          class="call-card"
          :title="t('Outcomes and recordings', 'Итоги и записи')"
        >
          <dl class="call-pairs">
            <div>
              <dt>{{ t('With a recording', 'С записью') }}</dt>
              <dd>{{ report.metrics.recorded ?? '—' }}</dd>
            </div>
            <div>
              <dt>{{ t('With a saved outcome', 'С сохранённым итогом') }}</dt>
              <dd>{{ report.metrics.outcome_known ?? '—' }}</dd>
            </div>
            <div>
              <dt>
                {{ t('Without a saved outcome', 'Без сохранённого итога') }}
              </dt>
              <dd>
                {{
                  report.coverage.outcomes
                    ? report.metrics.total - report.metrics.outcome_known
                    : '—'
                }}
              </dd>
            </div>
          </dl>
          <AnalyticsTable
            v-if="report.coverage.outcomes"
            :rows="report.groups.outcomes"
            :columns="outcomeColumns"
            :label="t('Outcome breakdown', 'Разбивка по итогам звонков')"
          >
            <template #cell="{ row, column, value }">
              <Button
                v-if="column.key === 'key'"
                variant="ghost"
                @click="openDetails('total', 'outcomes', row.key)"
                >{{ outcomeLabel(value) }}</Button
              >
              <span v-else>{{ value }}</span>
            </template>
          </AnalyticsTable>
        </Card>
        <Card class="call-card" :title="t('Linked tasks', 'Задачи по звонкам')">
          <dl class="call-pairs">
            <div v-for="task in taskLabels" :key="task.key">
              <dt>{{ task.label }}</dt>
              <dd>{{ report.tasks?.[task.key] ?? '—' }}</dd>
            </div>
          </dl>
        </Card>
      </template>
      <details class="text-base text-ink-gray-7">
        <summary>
          {{ t('How counts are calculated', 'Как считаются показатели') }}
        </summary>
        <p class="mt-2">
          {{
            t(
              'A connection in the CRM journal means a completed call with positive conversation duration.',
              'Соединение по журналу CRM — завершённый звонок с положительной длительностью разговора.',
            )
          }}
          {{
            t(
              'SLA uses the recorded answer time or a call interval entirely before or after the deadline. Uncertain times and callbacks still within the deadline are excluded from the on-time share.',
              'SLA учитывает время ответа или интервал звонка целиком до либо после срока. Случаи с неопределённым временем и перезвоны, срок которых ещё не наступил, в долю не входят.',
            )
          }}
        </p>
        <p class="mt-2">
          {{
            t(
              'Answer rates use calls with a confirmed connection or a final unsuccessful status. A technical completion without conversation data has an unknown outcome.',
              'Дозвон считается по вызовам с подтверждённым соединением или окончательным статусом неудачного вызова. У технически завершённого звонка без данных разговора исход считается неизвестным.',
            )
          }}
        </p>
        <p v-if="report.coverage.first_call_at" class="mt-2">
          {{ t('Calls in this selection', 'Звонки в выбранном срезе') }}
          · {{ dateAndTime(report.coverage.first_call_at) }} —
          {{ dateAndTime(report.coverage.last_call_at) }}.
        </p>
        <p class="mt-2">
          {{
            t(
              'Phone provider history completeness is unknown.',
              'Полнота загрузки истории у оператора неизвестна.',
            )
          }}
          <template v-if="report.coverage.creation_fallback">
            {{
              t(
                'Calls dated by journal entry creation:',
                'Звонки с датой создания записи вместо времени звонка',
              )
            }}
            · {{ formatCount(report.coverage.creation_fallback) }}.
          </template>
        </p>
      </details>
      <details
        v-if="report.coverage.exolve_windows?.length"
        class="text-base text-ink-gray-8"
      >
        <summary>
          {{ t('Exolve synchronization', 'Синхронизация Exolve') }}
        </summary>
        <p class="my-2 text-sm text-ink-gray-7">
          {{
            t(
              'The last request for each available SIP account. Call totals use the CRM journal and the selected report filters.',
              'Последний запрос по каждому доступному SIP-аккаунту. Показатели звонков учитывают журнал CRM и выбранные фильтры отчёта.',
            )
          }}
        </p>
        <ul class="grid gap-2">
          <li
            v-for="(account, index) in report.coverage.exolve_windows"
            :key="index"
            class="rounded-lg border border-outline-gray-2 p-3"
          >
            <div class="flex flex-wrap items-baseline justify-between gap-2">
              <strong>{{ account.label }}</strong>
              <span class="text-sm">{{
                exolveWindowResult(account.result)
              }}</span>
            </div>
            <dl
              v-if="account.checked_at"
              class="mt-2 grid gap-1 text-sm text-ink-gray-7"
            >
              <div>
                <dt class="inline">
                  {{ t('Requested interval', 'Запрошено за период') }}
                </dt>
                <dd class="inline ml-2">
                  {{ dateAndTime(account.from_at) }} —
                  {{ dateAndTime(account.to_at) }}
                </dd>
              </div>
              <div>
                <dt class="inline">{{ t('Processed at', 'Обработано') }}</dt>
                <dd class="inline ml-2">
                  {{ dateAndTime(account.checked_at, true) }}
                </dd>
              </div>
            </dl>
          </li>
        </ul>
      </details>
    </template>

    <CallSlaSettings v-model:open="settingsOpen" :lang="lang" @saved="load" />

    <Dialog
      v-model="detailsOpen"
      :title="t('Calls in this selection', 'Звонки в выбранном срезе')"
      size="4xl"
    >
      <div class="a-dialog">
        <Alert
          v-if="detailsError"
          theme="red"
          :title="detailsError"
          :dismissible="false"
        />
        <p v-else-if="detailsLoading" role="status">
          {{ t('Loading calls…', 'Загрузка звонков…') }}
        </p>
        <template v-else-if="detail">
          <p v-if="detailsPeriod" class="mb-3 text-base text-ink-gray-7">
            {{ periodLabel(detailsPeriod) }}
          </p>
          <p
            v-if="detail.matched != null"
            class="mb-3 text-base text-ink-gray-8"
          >
            {{ rateLabels[detailsMetric] }} ·
            {{
              basisLabel({ matched: detail.matched, eligible: detail.total })
            }}
            <template v-if="detailsRateBase?.excluded">
              · {{ t('Excluded', 'Вне расчёта') }}
              {{ formatCount(detailsRateBase.excluded) }}
            </template>
          </p>
          <AnalyticsTable
            :columns="detailColumns"
            :rows="detail.rows"
            row-key="name"
            :label="t('Call details', 'Детализация звонков')"
            :empty-text="
              t('No calls in this selection.', 'В выбранном срезе нет звонков.')
            "
          >
            <template #cell="{ row, column, value }">
              <Button
                v-if="column.key === 'at'"
                variant="ghost"
                :route="journal(row.name, detailsPeriod)"
                >{{ dateAndTime(value) }}</Button
              >
              <span v-else-if="column.key === 'direction'">{{
                directions.find((item) => item.value === value)?.label || '—'
              }}</span>
              <span v-else-if="column.key === 'rate_match'">
                {{ rateResultLabel(value) }}
              </span>
              <div v-else-if="column.key === 'sla'" class="grid gap-1">
                <span>{{
                  slaCards.find((item) => item.key === value)?.label || '—'
                }}</span>
                <span
                  v-if="row.callback_sla_exclusion"
                  class="text-sm text-ink-gray-7"
                  >{{
                    row.callback_sla_exclusion === 'different_employee'
                      ? t(
                          'Another employee returned the call',
                          'Перезвонил другой сотрудник',
                        )
                      : t(
                          'The employee could not be verified',
                          'Не удалось подтвердить сотрудника',
                        )
                  }}</span
                >
              </div>
              <span v-else-if="column.key === 'employee'">{{
                employeeNames.get(value) || t('Unassigned', 'Не назначен')
              }}</span>
              <dl
                v-else-if="column.key === 'callback_times'"
                class="grid gap-1"
              >
                <div v-if="row.deadline">
                  <dt class="inline">{{ t('Deadline', 'Срок') }}</dt>
                  <dd class="ml-2 inline tabular-nums">
                    {{ dateAndTime(row.deadline, true) }}
                  </dd>
                </div>
                <div v-if="row.attempt_at">
                  <dt class="inline">{{ t('Attempt', 'Попытка') }}</dt>
                  <dd class="ml-2 inline tabular-nums">
                    {{ dateAndTime(row.attempt_at, true) }}
                  </dd>
                </div>
                <div v-if="row.callback_connected">
                  <dt class="inline">{{ t('Connection', 'Соединение') }}</dt>
                  <dd class="ml-2 inline tabular-nums">
                    {{
                      row.connected_at
                        ? dateAndTime(row.connected_at, true)
                        : t('Time unavailable', 'Время неизвестно')
                    }}
                  </dd>
                </div>
              </dl>
              <div
                v-else-if="column.key === 'links'"
                class="flex flex-wrap gap-1"
              >
                <Button
                  v-if="row.callback"
                  variant="ghost"
                  :route="journal(row.callback, detailsPeriod)"
                  >{{ t('Callback', 'Перезвон') }}</Button
                >
                <Button
                  v-for="task in row.tasks"
                  :key="task"
                  variant="ghost"
                  :route="{ name: 'Tasks', query: { open: task } }"
                  >{{ t('Task', 'Задача') }}</Button
                >
                <Button
                  v-if="row.parent_type === 'CRM Deal'"
                  variant="ghost"
                  :route="{ name: 'Deal', params: { dealId: row.parent_name } }"
                  >{{ t('Deal', 'Сделка') }}</Button
                >
                <Button
                  v-if="row.parent_type === 'CRM Lead'"
                  variant="ghost"
                  :route="{ name: 'Lead', params: { leadId: row.parent_name } }"
                  >{{ t('Lead', 'Лид') }}</Button
                >
              </div>
              <span v-else>{{ value ?? '—' }}</span>
            </template>
          </AnalyticsTable>
          <div class="mt-3 flex flex-wrap items-center gap-2">
            <Button :disabled="!start" @click="loadDetails(start - limit)">{{
              t('Previous', 'Назад')
            }}</Button>
            <span class="text-base"
              >{{ detail.total ? start + 1 : 0 }}–{{
                start + detail.rows.length
              }}
              / {{ detail.total }}</span
            >
            <Button
              :disabled="start + limit >= detail.total"
              @click="loadDetails(start + limit)"
              >{{ t('Next', 'Далее') }}</Button
            >
          </div>
        </template>
      </div>
      <template #actions
        ><Button :disabled="!detail || !!detailsError" @click="exportDetails">{{
          t('Download CSV', 'Скачать CSV')
        }}</Button></template
      >
    </Dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { callScopeQuery } from '@/utils/callAnalyticsRoute'
import { Alert, Button, Card, Dialog, FormControl, TabButtons } from 'frappe-ui'
import AnalyticsChart from './AnalyticsChart.vue'
import AnalyticsTable from './AnalyticsTable.vue'
import CallSlaSettings from './CallSlaSettings.vue'
import CallQualityReview from './CallQualityReview.vue'

const props = defineProps({
  context: { type: Object, required: true },
  lang: { type: String, required: true },
  stale: Boolean,
})
const route = useRoute()
const router = useRouter()
const t = (en, ru) => (props.lang === 'ru' ? ru : en)
const draft = reactive({ direction: '', line: '', outcome: '' })
const view = computed({
  get() {
    const selected = route.query.call_view
    return ['summary', 'sla', 'team', 'quality'].includes(selected)
      ? selected
      : 'summary'
  },
  set(selected) {
    router.replace({
      query: {
        ...route.query,
        call_view: selected === 'summary' ? undefined : selected,
      },
    })
  },
})
const trend = computed({
  get: () => (route.query.call_trend === 'weeks' ? 'weeks' : 'days'),
  set: (selected) =>
    router.replace({
      query: {
        ...route.query,
        call_trend: selected === 'weeks' ? selected : undefined,
      },
    }),
})
const trendOptions = computed(() => [
  { value: 'days', label: t('Daily', 'По дням') },
  { value: 'weeks', label: t('Weekly', 'По неделям') },
])
const trendTitle = computed(() =>
  trend.value === 'weeks'
    ? t('Calls by week', 'Звонки по неделям')
    : t('Calls by day', 'Звонки по дням'),
)
const report = ref(null)
const heading = ref(null)
const summaryJumpChanged = ref(false)
const savedJump = window.history.state?.crmSummaryCall
let summaryJump =
  typeof savedJump?.revision === 'string' &&
  ['total', 'missed', 'overdue', 'sla_percent'].includes(savedJump.metric)
    ? savedJump
    : null
const comparisonOpen = computed({
  get: () => route.query.call_compare === '1',
  set: (open) =>
    router.replace({
      query: { ...route.query, call_compare: open ? '1' : undefined },
    }),
})
const trendRows = computed(() => report.value?.groups[trend.value] || [])
const employeeNames = computed(
  () =>
    new Map(
      [
        ...(report.value?.comparison?.employees || []),
        ...(report.value?.groups.employees || []),
      ].map(({ key, label }) => [key, label]),
    ),
)
const loading = ref(false)
const error = ref('')
const comparisonLoading = ref(false)
const comparisonError = ref('')
const settingsOpen = ref(false)
const qualityEditing = ref(false)
let request
let comparisonRequest
let detailRequest
let opener
const detailsOpen = ref(false)
const detailsLoading = ref(false)
const detailsError = ref('')
const detail = ref(null)
const detailsPeriod = ref(null)
const detailsMetric = ref('')
const detailsRateBase = ref(null)
const start = ref(0)
const limit = 25
let scope = null
const metric = (key, en, ru, value = report.value?.metrics[key]) => ({
  key,
  label: t(en, ru),
  value,
})
const kpis = computed(() => [
  metric('total', 'Calls', 'Всего звонков'),
  metric('incoming', 'Incoming', 'Входящие'),
  metric('missed', 'Missed incoming', 'Пропущенные входящие'),
  metric('connected', 'Connections in journal', 'Соединения по журналу'),
])
const answerRates = computed(() => [
  metric('answer_rate_incoming', 'Incoming answered', 'Дозвон входящих'),
  metric('answer_rate_outgoing', 'Outgoing answered', 'Дозвон исходящих'),
])
const rates = computed(() => [
  ...answerRates.value,
  metric('sla_percent', 'Callbacks on time', 'Перезвоны в срок'),
])
const rateLabels = computed(() =>
  Object.fromEntries(rates.value.map(({ key, label }) => [key, label])),
)
const periodRows = computed(() => {
  if (!report.value?.comparison) return []
  const { comparison, metrics } = report.value
  return [
    ...kpis.value,
    metric('outgoing', 'Outgoing', 'Исходящие'),
    ...rates.value,
  ].map(({ key, label, value: current }) => {
    const previous = comparison.metrics[key]
    const rate = Object.hasOwn(rateLabels.value, key)
    return {
      key,
      label,
      rate,
      current,
      previous,
      bases: rate
        ? {
            current: metrics.rate_bases?.[key],
            previous: comparison.metrics.rate_bases?.[key],
          }
        : null,
      change: current == null || previous == null ? null : current - previous,
    }
  })
})
const periodColumns = computed(() => [
  group('label', 'Metric', 'Показатель'),
  { key: 'current', label: periodLabel(report.value.period), numeric: true },
  {
    key: 'previous',
    label: periodLabel(report.value.comparison.period),
    numeric: true,
  },
  { ...group('change', 'Change', 'Изменение'), numeric: true },
])
const currentDayInPeriod = computed(
  () =>
    report.value?.period.to_date === report.value?.period.as_of.slice(0, 10),
)
const slaCards = computed(() => [
  metric(
    'pending',
    'Awaiting callback',
    'Ожидают перезвона',
    report.value?.coverage.sla ? report.value.metrics.pending : null,
  ),
  metric(
    'overdue',
    'Overdue callbacks',
    'Просрочены',
    report.value?.coverage.sla ? report.value.metrics.overdue : null,
  ),
  metric(
    'on_time',
    'Called back in time',
    'Перезвонили в срок',
    report.value?.coverage.sla ? report.value.metrics.on_time : null,
  ),
  metric(
    'late',
    'Called back late',
    'Перезвонили с опозданием',
    report.value?.coverage.sla ? report.value.metrics.late : null,
  ),
  metric('unavailable', 'Insufficient data', 'Недостаточно данных'),
])
const directions = computed(() => [
  { value: '', label: t('All directions', 'Все направления') },
  { value: 'Incoming', label: t('Incoming', 'Входящие') },
  { value: 'Outgoing', label: t('Outgoing', 'Исходящие') },
  { value: 'unknown', label: t('Unknown', 'Не указано') },
])
const outcomeNames = {
  Agreed: 'Договорились',
  Callback: 'Перезвонить',
  'Not interested': 'Неинтересно',
  'Wrong number': 'Неверный номер',
  unprocessed: 'Без итога',
}
const outcomeLabel = (value) => {
  const key = value || 'unprocessed'
  return t(key === 'unprocessed' ? 'No outcome' : key, outcomeNames[key] || key)
}
const outcomes = computed(() => [
  { value: '', label: t('All outcomes', 'Все итоги') },
  ...Object.keys(outcomeNames).map((value) => ({
    value,
    label: outcomeLabel(value),
  })),
])
const knownLines = ref([])
const lineOptions = computed(() => [
  { value: '', label: t('All lines', 'Все линии') },
  ...knownLines.value,
])
const views = computed(() => [
  { value: 'summary', label: t('Summary', 'Сводка') },
  { value: 'sla', label: t('Callbacks and SLA', 'Перезвоны и SLA') },
  { value: 'team', label: t('Team and lines', 'Команда и линии') },
  { value: 'quality', label: t('Call quality', 'Качество разговоров') },
])
const group = (key, en, ru) => ({ key, label: t(en, ru) })
const teamGroups = computed(() =>
  [
    ...(report.value?.groups.teams?.length
      ? [group('teams', 'By team', 'По командам')]
      : []),
    group('employees', 'By employee', 'По сотрудникам'),
    group('lines', 'By line', 'По линиям'),
    group('hours', 'By hour', 'По часам'),
    group('weekdays', 'By weekday', 'По дням недели'),
  ].map(({ key, label }) => ({ value: key, label })),
)
const comparisonOptions = computed(() => [
  { value: 'volume', label: t('Volume', 'Нагрузка') },
  { value: 'answer', label: t('Connection and SLA', 'Дозвон и SLA') },
  {
    value: 'work',
    label: t('Duration and follow-up', 'Длительность и обработка'),
  },
])
const comparisonGroup = reportOption('call_group', teamGroups, 'employees')
const comparisonMetrics = reportOption(
  'call_metrics',
  comparisonOptions,
  'volume',
)

function reportOption(key, options, fallback) {
  return computed({
    get: () =>
      options.value.some(({ value }) => value === route.query[key])
        ? route.query[key]
        : fallback,
    set: (value) =>
      router.replace({
        query: {
          ...route.query,
          [key]: value === fallback ? undefined : value,
        },
      }),
  })
}
const weekdays = computed(() =>
  Array.from({ length: 7 }, (_, day) =>
    new Intl.DateTimeFormat(props.lang, {
      weekday: 'long',
      timeZone: 'UTC',
    }).format(new Date(Date.UTC(2024, 0, 1 + day))),
  ),
)
const taskLabels = computed(() => [
  group('total', 'Total', 'Всего'),
  group('done', 'Done', 'Выполнены'),
  group('open', 'Open', 'Открыты'),
  group('overdue', 'Overdue', 'Просрочены'),
  group('canceled', 'Canceled', 'Отменены'),
])
const trendColumns = computed(() => [
  trend.value === 'weeks'
    ? group('key', 'Week starting', 'Начало недели')
    : group('key', 'Date', 'Дата'),
  group('total', 'Total', 'Всего'),
  group('incoming', 'Incoming', 'Входящие'),
  group('outgoing', 'Outgoing', 'Исходящие'),
  group('missed', 'Missed', 'Пропущены'),
])
const groupColumns = computed(() => {
  const first = group('label', 'Group', 'Группа')
  if (comparisonMetrics.value === 'answer')
    return [
      first,
      group('connected', 'Connected', 'Соединения'),
      ...rates.value.map(({ key, label }) => ({
        key,
        label,
        format: 'percent',
      })),
    ]
  if (comparisonMetrics.value === 'work')
    return [
      first,
      {
        ...group('average_seconds', 'Average duration', 'Средняя длительность'),
        format: 'duration',
      },
      group('outcome_known', 'With outcome', 'С итогом'),
      group('linked_tasks', 'Linked tasks', 'Связанные задачи'),
      group('overdue_tasks', 'Overdue tasks', 'Просроченные задачи'),
    ]
  return [first, ...trendColumns.value.slice(1)]
})
const outcomeColumns = computed(() => [
  group('key', 'Outcome', 'Итог'),
  group('total', 'Total', 'Всего'),
])
const detailColumns = computed(() => [
  group('at', 'Call time', 'Время звонка'),
  ...(view.value === 'sla' ||
  ['overdue', 'sla_percent'].includes(detailsMetric.value)
    ? [
        group('employee', 'Agent', 'Сотрудник'),
        {
          ...group(
            'callback_times',
            'Callback timeline',
            'Срок и время перезвона',
          ),
          width: 'minmax(220px, 1.5fr)',
        },
      ]
    : [
        group('direction', 'Direction', 'Направление'),
        group('status', 'Journal status', 'Статус журнала'),
      ]),
  group('sla', 'Callback', 'Перезвон'),
  ...(Object.hasOwn(rateLabels.value, detailsMetric.value)
    ? [group('rate_match', 'Outcome used for rate', 'Исход для расчёта')]
    : []),
  group('links', 'Related', 'Связано'),
])
const chart = computed(() => ({
  title: '',
  data: trendRows.value.map((row) => ({
    date: dateOnly(row.key),
    [t('All calls', 'Все звонки')]: row.total,
    [t('Missed', 'Пропущены')]: row.missed,
  })),
  xAxis: {
    key: 'date',
    type: 'category',
    echartOptions: { axisLabel: { color: 'var(--ink-gray-7)' } },
  },
  yAxis: {
    echartOptions: {
      minInterval: 1,
      axisLabel: { color: 'var(--ink-gray-7)' },
    },
  },
  series: [
    {
      type: 'bar',
      name: t('All calls', 'Все звонки'),
      color: 'var(--surface-blue-7)',
    },
    {
      type: 'bar',
      name: t('Missed', 'Пропущены'),
      color: 'var(--surface-amber-7)',
    },
  ],
  echartOptions: {
    animation: false,
    grid: { left: 38, right: 12, bottom: 26, top: 32 },
    legend: { textStyle: { color: 'var(--ink-gray-8)' } },
    tooltip: { trigger: 'axis', renderMode: 'richText' },
  },
}))
function dateOnly(value) {
  return new Intl.DateTimeFormat(props.lang, {
    day: 'numeric',
    month: 'short',
    timeZone: 'UTC',
  }).format(new Date(value + 'T00:00:00Z'))
}
function periodLabel(period) {
  const formatter = new Intl.DateTimeFormat(props.lang, {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    timeZone: 'UTC',
  })
  return formatter.formatRange(
    new Date(period.from_date + 'T00:00:00Z'),
    new Date(period.to_date + 'T00:00:00Z'),
  )
}
function formatCount(value, change = false) {
  return value == null
    ? '—'
    : new Intl.NumberFormat(props.lang, {
        signDisplay: change ? 'exceptZero' : 'auto',
      }).format(value)
}
function formatPointChange(value) {
  if (value == null) return '—'
  const points = new Intl.NumberFormat(props.lang, {
    signDisplay: 'exceptZero',
    maximumFractionDigits: 1,
  }).format(value)
  return points + t(' pp', ' п. п.')
}
function basisLabel({ matched, eligible }) {
  return `${formatCount(matched)}${t(' of ', ' из ')}${formatCount(eligible)}`
}
function periodCellLabel(row, column, value) {
  const base = row.bases?.[column.key]
  const visibleValue = row.rate ? percent(value) : formatCount(value)
  return [row.label, column.label, visibleValue, base && basisLabel(base)]
    .filter(Boolean)
    .join(', ')
}
function rateResultLabel(matches) {
  if (detailsMetric.value === 'sla_percent')
    return matches ? t('Within SLA', 'В срок') : t('Outside SLA', 'Вне срока')
  return matches
    ? t('Connected', 'Соединение')
    : t('No connection', 'Без соединения')
}
function dateAndTime(value, seconds = false) {
  return new Intl.DateTimeFormat(props.lang, {
    dateStyle: 'short',
    timeStyle: seconds ? 'medium' : 'short',
    timeZone: props.context.timezone,
  }).format(new Date(value))
}
function exolveWindowResult(result) {
  return {
    Read: t('Reached the end of the response', 'Достигнут конец списка'),
    Limit: t('Page limit reached', 'Достигнут лимит страниц'),
    Repeated: t('Repeated rows in the response', 'В ответе повторяются строки'),
    Missing: t('No processed request', 'Запросов пока нет'),
  }[result]
}
function percent(value) {
  return value == null
    ? '—'
    : new Intl.NumberFormat(props.lang, {
        style: 'percent',
        maximumFractionDigits: 1,
      }).format(value / 100)
}
function duration(seconds) {
  if (seconds == null) return '—'
  const value = Math.round(seconds)
  return (
    Math.floor(value / 60) +
    t(' min ', ' мин ') +
    (value % 60) +
    t(' sec', ' с')
  )
}
const queryValue = (key) =>
  typeof route.query[key] === 'string' ? route.query[key] : ''
const selection = computed(() => ({
  from_date: props.context.from_date,
  to_date: props.context.to_date,
  employee: props.context.owner,
  pipeline: props.context.pipeline,
  source: props.context.source,
  direction: queryValue('call_direction'),
  line: queryValue('call_line'),
  outcome: queryValue('call_outcome'),
}))
async function requestData(method, params, signal) {
  const response = await fetch(
    '/api/method/crm.analytics.call_reporting.' +
      method +
      '?' +
      new URLSearchParams(params),
    { signal, cache: 'no-store' },
  )
  if (!response.ok) {
    const failure = new Error(
      response.status === 403
        ? t(
            'Call analytics is unavailable with your access.',
            'Аналитика звонков недоступна с вашими правами.',
          )
        : t(
            'Could not load current data. Refresh the report and retry.',
            'Не удалось загрузить актуальные данные. Обновите отчёт и повторите.',
          ),
    )
    failure.status = response.status
    throw failure
  }
  return (await response.json()).message
}
function apply() {
  const query = { ...route.query }
  for (const key of Object.keys(draft)) {
    if (draft[key]) query['call_' + key] = draft[key]
    else delete query['call_' + key]
  }
  return router.replace({ query })
}
async function load() {
  request?.abort()
  comparisonRequest?.abort()
  comparisonRequest = null
  comparisonLoading.value = false
  comparisonError.value = ''
  report.value = null
  error.value = ''
  loading.value = false
  if (props.stale) return
  const current = new AbortController()
  request = current
  loading.value = true
  try {
    const data = await requestData(
      'get_report',
      { filters: JSON.stringify(selection.value) },
      current.signal,
    )
    if (request !== current) return
    if (!selection.value.line) {
      knownLines.value = data.groups.lines
        .filter((row) => row.key)
        .map((row) => ({ label: row.label, value: row.key }))
    } else if (
      data.groups.lines[0] &&
      !knownLines.value.some((line) => line.value === selection.value.line)
    ) {
      knownLines.value = [
        ...knownLines.value,
        { label: data.groups.lines[0].label, value: data.groups.lines[0].key },
      ]
    }
    report.value = data
    if (summaryJump) {
      const { revision, metric } = summaryJump
      summaryJump = null
      if (revision === data.snapshot && data.metrics[metric] != null) {
        openDetails(metric)
        opener = heading.value
      } else summaryJumpChanged.value = true
    }
    if (comparisonOpen.value) loadComparison()
  } catch (failure) {
    if (request === current && failure.name !== 'AbortError')
      error.value = failure.message
  } finally {
    if (request === current) loading.value = false
  }
}
async function loadComparison() {
  if (
    !report.value ||
    report.value.comparison ||
    comparisonLoading.value ||
    props.stale
  )
    return
  const current = new AbortController()
  const timeout = setTimeout(
    () => current.abort(new Error('Comparison timed out')),
    15000,
  )
  comparisonRequest = current
  comparisonLoading.value = true
  comparisonError.value = ''
  try {
    const data = await requestData(
      'get_report',
      { filters: JSON.stringify(selection.value), include_comparison: true },
      current.signal,
    )
    if (comparisonRequest === current) report.value = data
  } catch (failure) {
    if (comparisonRequest !== current || failure.name === 'AbortError') return
    if (failure.status === 401 || failure.status === 403) {
      report.value = null
      detailsOpen.value = false
      error.value = failure.message
    } else {
      comparisonError.value = t(
        'Could not compare these periods. Retry or select a shorter period.',
        'Не удалось сравнить периоды. Повторите или выберите более короткий период.',
      )
    }
  } finally {
    clearTimeout(timeout)
    if (comparisonRequest === current) {
      comparisonLoading.value = false
      comparisonRequest = null
    }
  }
}
function journal(name, period = report.value?.period) {
  return {
    name: 'Call Logs',
    query: {
      ...callScopeQuery({
        ...route.query,
        from_date: period?.from_date || props.context.from_date,
        to_date: period?.to_date || props.context.to_date,
        owner: selection.value.employee,
      }),
      call_scope: 'analytics',
      ...(name ? { open: name } : {}),
    },
  }
}
function openDetails(metric, group, groupKey, source = report.value) {
  if (!source) return
  opener = document.activeElement
  detailsPeriod.value = source.period
  detailsMetric.value = metric
  const selected = group
    ? source.groups?.[group]?.find((row) => row.key === groupKey)
    : source.metrics
  detailsRateBase.value = selected?.rate_bases?.[metric] || null
  scope = { snapshot_token: source.snapshot_token, metric }
  if (group) Object.assign(scope, { group, group_key: groupKey })
  detailsOpen.value = true
  loadDetails(0)
}
async function loadDetails(offset) {
  detailRequest?.abort()
  const current = new AbortController()
  detailRequest = current
  detailsError.value = ''
  detailsLoading.value = true
  try {
    const data = await requestData(
      'get_details',
      { ...scope, start: offset, limit },
      current.signal,
    )
    if (detailRequest !== current) return
    detail.value = data
    start.value = offset
  } catch (failure) {
    if (detailRequest === current && failure.name !== 'AbortError')
      detailsError.value = failure.message
  } finally {
    if (detailRequest === current) detailsLoading.value = false
  }
}
async function exportDetails() {
  const selection = scope
  try {
    const data = await requestData('export_details', selection)
    if (
      !detailsOpen.value ||
      selection !== scope ||
      data.snapshot !== detail.value?.snapshot
    )
      return
    const anchor = document.createElement('a')
    anchor.href = URL.createObjectURL(
      new Blob(['\ufeff', data.csv], { type: 'text/csv;charset=utf-8' }),
    )
    anchor.download = data.filename
    anchor.click()
    setTimeout(() => URL.revokeObjectURL(anchor.href), 0)
  } catch (failure) {
    if (detailsOpen.value && selection === scope)
      detailsError.value = failure.message
  }
}
watch(
  [() => JSON.stringify(selection.value), () => props.stale],
  () => {
    for (const key of Object.keys(draft)) draft[key] = selection.value[key]
    detailsOpen.value = false
    load()
  },
  { immediate: true },
)
watch(
  () => props.context.as_of,
  () => {
    if (!detailsOpen.value && !qualityEditing.value && !loading.value) load()
  },
)
watch(comparisonOpen, (open) => {
  if (open) loadComparison()
})
watch(detailsOpen, (open) => {
  if (!open) {
    detailRequest?.abort()
    detail.value = null
    nextTick(() => opener?.isConnected && opener.focus())
  }
})
onBeforeUnmount(() => {
  request?.abort()
  comparisonRequest?.abort()
  detailRequest?.abort()
})
</script>

<style scoped>
.call-analytics {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 16px;
  min-width: 0;
}
.call-filters {
  display: flex;
  flex-wrap: wrap;
  align-items: end;
  gap: 10px;
}
.call-filters > div {
  flex: 0 1 14rem;
  min-width: 0;
}
.call-views {
  display: flex;
  flex-wrap: wrap;
  width: fit-content;
  max-width: 100%;
}
.call-views :deep(> div) {
  flex-wrap: wrap;
  max-width: 100%;
}
.call-kpi-content {
  display: grid;
  gap: 8px;
  min-width: 0;
}
.call-kpis {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}
.call-kpi {
  justify-content: start;
  min-width: 0;
  gap: 8px;
  height: auto;
  min-height: 74px;
  padding: 12px;
  text-align: left;
  white-space: normal;
  border: 1px solid var(--outline-gray-2);
  background: var(--surface-elevation-1);
}
.call-kpi :deep(> .truncate) {
  min-width: 0;
  overflow: visible;
  white-space: normal;
  line-height: 1.25;
}
.call-kpi strong {
  color: var(--ink-gray-9);
  font-size: 24px;
  font-variant-numeric: tabular-nums;
}
.call-card {
  min-width: 0;
  color: var(--ink-gray-9);
  background: var(--surface-elevation-1);
}
.call-pairs {
  display: grid;
  gap: 8px;
  color: var(--ink-gray-8);
}
.call-pairs > div {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}
.call-pairs dd {
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
@media (max-width: 620px) {
  .call-filters > div {
    flex: 1 1 8.5rem;
  }
  .call-kpis {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
