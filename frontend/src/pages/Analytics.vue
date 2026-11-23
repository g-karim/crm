<template>
  <div class="analytics-shell bg-surface-gray-1 text-ink-gray-9">
    <LayoutHeader>
      <template #left-header
        ><h1 class="text-lg font-semibold text-ink-gray-9">
          {{ t('Analytics', 'Аналитика') }}
        </h1></template
      >
      <template #right-header>
        <Button
          variant="ghost"
          class="a-language"
          :aria-label="t('Switch language', 'Сменить язык')"
          @click="lang = lang === 'ru' ? 'en' : 'ru'"
          >{{ lang === 'ru' ? 'EN' : 'RU' }}</Button
        >
        <Button
          variant="subtle"
          class="a-layout-link"
          :route="{ name: 'AnalyticsReports' }"
          :aria-label="t('My reports', 'Мои отчёты')"
          :title="t('My reports', 'Мои отчёты')"
          icon-left="lucide-layout-dashboard"
          >{{ t('My reports', 'Мои отчёты') }}</Button
        >
        <Button
          variant="solid"
          :loading="loading"
          :disabled="offline"
          icon-left="lucide-refresh-cw"
          @click="load"
          >{{ t('Refresh', 'Обновить') }}</Button
        >
      </template>
    </LayoutHeader>
    <main class="analytics-main" :aria-busy="loading">
      <div class="a-intro">
        <h2>{{ t('Sales analytics', 'Аналитика продаж') }}</h2>
        <p class="a-freshness" role="status">
          {{
            offline
              ? t(
                  'Offline. Showing the last report.',
                  'Нет сети. Показан последний отчёт.',
                )
              : stale
                ? t('The report needs refreshing', 'Отчёт требует обновления')
                : report
                  ? t('Calculated at ', 'Рассчитано в ') + observedTime
                  : t('Loading report…', 'Загрузка отчёта…')
          }}
        </p>
      </div>
      <Alert
        v-if="report?.import_coverage?.recent_issue"
        :dismissible="false"
        theme="yellow"
        class="mb-4"
        :title="
          t('Some CRM imports need review', 'Импорты CRM требуют проверки')
        "
        :description="
          t(
            'Totals include saved records only. Review rejected import rows.',
            'В итогах только сохранённые карточки. Проверьте отклонённые строки импорта.',
          )
        "
        ><template #footer
          ><Button variant="ghost" @click="qualityOpen = !qualityOpen">{{
            t('Coverage details', 'О покрытии данных')
          }}</Button></template
        ></Alert
      >
      <Card class="a-filter-card">
        <div class="a-filter-toolbar">
          <span
            v-if="tab === 'managers'"
            class="text-sm font-medium text-ink-gray-8"
            >{{ t('Manager filters', 'Разрезы по менеджерам') }}</span
          >
          <TabButtons
            v-else
            :model-value="activePeriod || ''"
            :options="periodButtons"
            :aria-label="t('Quick period', 'Быстрый выбор периода')"
            @update:model-value="choosePeriod"
          />
          <div class="flex flex-wrap items-center gap-2">
            <Button
              variant="subtle"
              icon-left="lucide-sliders-horizontal"
              :aria-expanded="filtersOpen"
              aria-controls="analytics-filters"
              @click="filtersOpen = !filtersOpen"
            >
              {{ t('Filters', 'Фильтры')
              }}{{ activeDimensions ? ' · ' + activeDimensions : '' }}
            </Button>
            <Button
              v-if="report?.quality.length"
              variant="ghost"
              class="a-quality-trigger"
              icon="lucide-triangle-alert"
              :label="t('Data quality', 'Качество данных')"
              :aria-expanded="qualityOpen"
              aria-controls="analytics-quality"
              @click="qualityOpen = !qualityOpen"
            />
          </div>
        </div>
        <form
          v-show="filtersOpen"
          id="analytics-filters"
          class="a-filters"
          @submit.prevent="apply"
        >
          <FormControl
            v-if="tab !== 'managers'"
            v-model="filters.from_date"
            type="date"
            :label="t('From', 'С')"
            format="YYYY-MM-DD"
            required
            :clearable="false"
            data-field="from_date"
          />
          <FormControl
            v-if="tab !== 'managers'"
            v-model="filters.to_date"
            type="date"
            :label="t('To', 'По')"
            format="YYYY-MM-DD"
            required
            :clearable="false"
            data-field="to_date"
          />
          <FormControl
            v-model="filters.pipeline"
            type="select"
            :label="t('Pipeline', 'Воронка')"
            :options="dimensionOptions('pipeline')"
            data-field="pipeline"
          />
          <FormControl
            v-model="filters.owner"
            type="select"
            :label="t('Current owner', 'Текущий ответственный')"
            :options="dimensionOptions('owner')"
            data-field="owner"
          />
          <FormControl
            v-model="filters.source"
            type="select"
            :label="t('Source', 'Источник')"
            :options="dimensionOptions('source')"
            data-field="source"
          />
          <Button
            variant="solid"
            type="submit"
            :disabled="offline"
            :loading="loading"
            >{{ t('Apply', 'Применить') }}</Button
          >
          <Button
            v-if="filters.owner || filters.source || filters.pipeline"
            variant="ghost"
            @click="clearDimensions"
            >{{ t('Reset filters', 'Сбросить фильтры') }}</Button
          >
        </form>
      </Card>
      <Alert
        v-if="error"
        :dismissible="false"
        theme="red"
        class="a-error my-3"
        role="alert"
        :title="error"
        ><template #footer
          ><Button
            variant="ghost"
            @click="historicalRequested ? showCurrentReport() : load()"
            >{{
              historicalRequested
                ? t('Show current report', 'Показать текущий отчёт')
                : t('Try again', 'Повторить')
            }}</Button
          ></template
        ></Alert
      >
      <div v-if="!report && loading" class="a-empty" role="status">
        <LoadingIndicator class="size-5" />{{
          t(
            'Calculating available CRM records…',
            'Расчёт по доступным карточкам CRM…',
          )
        }}
      </div>
      <template v-if="report">
        <Card
          v-if="qualityOpen"
          id="analytics-quality"
          :title="t('Data quality and coverage', 'Качество и полнота данных')"
          class="a-panel"
        >
          <div v-if="report.import_coverage" class="a-import-coverage">
            <h4>{{ t('Import coverage', 'Покрытие импорта') }}</h4>
            <p v-if="!report.import_coverage.available">
              {{
                t(
                  'Import logs are unavailable with current permissions. Completeness is unverified; totals include saved CRM records only.',
                  'Журналы импорта недоступны с текущими правами. Полнота загрузки не подтверждена; итоги включают только сохранённые карточки CRM.',
                )
              }}
            </p>
            <p
              v-else-if="report.import_coverage.recent_issue"
              class="a-warning"
            >
              {{
                t(
                  'Readable CRM import logs from the last 30 days include partial, failed or timed-out jobs. Review rejected rows in Data Import. Totals include saved records only.',
                  'В доступных журналах импорта CRM за последние 30 дней есть частичные, ошибочные или прерванные задания. Проверьте отклонённые строки в Data Import. Итоги включают только сохранённые карточки.',
                )
              }}
            </p>
            <p v-else>
              {{
                t(
                  'No issue was found in readable native import logs from the last 30 days. Other channels are not verified.',
                  'В доступных журналах штатного импорта за последние 30 дней ошибок не найдено. Полнота других каналов не проверена.',
                )
              }}
            </p>
          </div>
          <p>
            {{
              t(
                'Correct source cards, then refresh. Unknown values are not complete zero totals.',
                'Исправьте исходные карточки и обновите отчёт. Неизвестные значения не выдаются за полный нулевой итог.',
              )
            }}
          </p>
          <div class="a-stage-list">
            <Button
              v-for="group in report.quality"
              :key="group.code"
              size="md"
              variant="ghost"
              @click="details('quality', group.code)"
            >
              <span>{{ qualityName(group.code) }}</span
              ><strong>{{ group.count }}</strong>
            </Button>
          </div>
          <p v-if="!report.quality.length">
            {{
              t(
                'No gaps detected by the enabled rules.',
                'Включённые правила не обнаружили пробелов.',
              )
            }}
          </p>
          <h4>{{ t('History', 'История') }}</h4>
          <p>
            {{
              t(
                'Confirmed current stage intervals: ',
                'Подтверждённое время текущего этапа: ',
              )
            }}{{ report.history_coverage.confirmed_current_stage }} /
            {{ report.history_coverage.open }}.
            {{
              t(
                'Past dimensions are unavailable before recorded history begins.',
                'Прошлые разрезы недоступны до начала записанной истории.',
              )
            }}
          </p>
        </Card>
        <details v-if="tab !== 'managers' && tab !== 'calls'" class="a-context">
          <summary>
            {{
              t(
                'Comparison and calculation scope',
                'Сравнение и правила расчёта',
              )
            }}
          </summary>
          <p>
            {{ report.context.previous_from }} —
            {{ report.context.previous_to }} · {{ report.context.timezone }}.
            {{
              t(
                'Only records available to this account. Dimensions use current values.',
                'Только доступные этому аккаунту карточки. Разрезы по текущим значениям.',
              )
            }}
          </p>
        </details>
        <Tabs
          v-model="tabIndex"
          :tabs="sectionTabs"
          class="a-tabs"
          :aria-label="t('Analytics sections', 'Разделы аналитики')"
        >
          <template #tab-item="{ tab: item }">
            <Button variant="ghost" class="a-tab-trigger">{{
              item.label
            }}</Button>
          </template>
          <template #tab-panel>
            <section
              v-if="tab === 'overview'"
              class="a-overview-metrics"
              :aria-label="t('Sales results', 'Результаты продаж')"
            >
              <Button
                v-for="item in overviewMetrics"
                :key="item.key"
                variant="ghost"
                class="a-kpi"
                :data-metric="item.key"
                @click="details(item.key)"
              >
                <span>{{ item.label }}</span
                ><strong>{{ metricValue(item.key) }}</strong>
                <small>{{ item.note }}</small>
                <em v-if="report.metrics[item.key].complete === false">{{
                  t('Incomplete data', 'Данные неполные')
                }}</em>
              </Button>
            </section>
            <div v-if="tab === 'overview'" class="a-overview">
              <Card
                :title="
                  t('Won deals by closure date', 'Победы по дате закрытия')
                "
                class="a-panel a-trend"
              >
                <template #actions
                  ><Button
                    size="md"
                    variant="ghost"
                    class="a-inline"
                    @click="details('won_value')"
                  >
                    {{ t('View deals', 'К сделкам') }}
                  </Button></template
                >
                <p>
                  {{ t('Daily value in ', 'Сумма за день в ')
                  }}{{ report.context.currency }}
                </p>
                <div
                  class="a-trend-chart"
                  role="img"
                  :aria-label="
                    t(
                      'Daily won value; exact values in the table below',
                      'Сумма побед по дням; точные значения в таблице ниже',
                    )
                  "
                >
                  <AnalyticsChart
                    v-if="chartAvailable"
                    :config="trendChart"
                    class="h-full w-full min-w-0"
                  />
                  <Alert
                    v-else
                    :dismissible="false"
                    theme="yellow"
                    :title="
                      t(
                        'Use the exact values below',
                        'Используйте точные значения ниже',
                      )
                    "
                    :description="
                      t(
                        'Some daily values cannot be plotted. Check the table for available values.',
                        'Часть дневных данных не отображается на графике. Доступные значения приведены в таблице.',
                      )
                    "
                  />
                </div>
                <details>
                  <summary>
                    {{ t('Exact daily values', 'Точные значения по дням') }}
                  </summary>
                  <div class="a-table-wrap">
                    <AnalyticsTable
                      :columns="trendColumns"
                      :rows="report.trend"
                      row-key="date"
                      :label="
                        t('Exact daily values', 'Точные значения по дням')
                      "
                      :empty-text="t('No records', 'Нет записей')"
                    >
                      <template #cell="{ column, value }"
                        ><span>{{
                          column.key === 'won_value' ? format(value) : value
                        }}</span></template
                      >
                    </AnalyticsTable>
                  </div>
                </details>
              </Card>
              <Card
                :title="t('Needs attention', 'Требует внимания')"
                class="a-panel a-attention"
              >
                <template #actions>
                  <div class="flex flex-wrap justify-end gap-1">
                    <Button
                      size="md"
                      variant="ghost"
                      icon-left="lucide-bell"
                      @click="signalsOpen = true"
                    >
                      {{ t('Signals', 'Сигналы') }}
                    </Button>
                    <Button
                      size="md"
                      variant="ghost"
                      class="a-inline"
                      @click="details('risk_count')"
                    >
                      {{ metricValue('risk_count') }} {{ t('deals', 'сделки') }}
                    </Button>
                  </div>
                </template>
                <p>
                  {{
                    t(
                      'Each deal is counted once, with all its reasons.',
                      'Каждая сделка учитывается один раз, со всеми причинами.',
                    )
                  }}
                </p>
                <div class="a-attention-list">
                  <article
                    v-for="row in report.attention.slice(0, 4)"
                    :key="row.name"
                  >
                    <div>
                      <RouterLink
                        :to="'/deals/' + encodeURIComponent(row.name)"
                        >{{ row.title }}</RouterLink
                      >
                      <p>{{ row.reasons.map(reason).join('; ') }}</p>
                    </div>
                    <strong v-if="row.currency_valid !== false"
                      >{{ format(row.value) }} {{ row.currency || '' }}</strong
                    >
                    <small v-else class="a-warning">{{
                      t(
                        'Amount excluded: unknown currency',
                        'Сумма не учтена: неизвестная валюта',
                      )
                    }}</small>
                  </article>
                </div>
                <p v-if="!report.attention.length">
                  {{
                    t(
                      'No attention rules triggered in the available data.',
                      'Правила внимания не сработали на доступных данных.',
                    )
                  }}
                </p>
                <p v-if="report.metrics.risk_count.value > 4">
                  {{
                    t(
                      'Open the list to see every deal.',
                      'Откройте список, чтобы увидеть все сделки.',
                    )
                  }}
                </p>
              </Card>
              <div v-if="!summaryVisible" class="a-summary-trigger">
                <Button
                  variant="subtle"
                  icon-left="lucide-align-left"
                  @click="openSummary"
                  >{{
                    t('Generate sales summary', 'Сформировать сводку продаж')
                  }}</Button
                >
              </div>
              <Card
                v-else
                :title="t('Sales and calls summary', 'Сводка продаж и звонков')"
                class="a-panel a-summary"
              >
                <template #actions
                  ><Button
                    size="md"
                    variant="subtle"
                    class="a-button"
                    :disabled="summaryLoading || stale || loading"
                    @click="generateSummary"
                  >
                    {{
                      summaryLoading
                        ? t('Preparing…', 'Подготовка…')
                        : t('Generate', 'Сформировать')
                    }}
                  </Button></template
                >
                <p>
                  {{
                    t(
                      'A summary grounded in verified CRM data and linked to its source records.',
                      'Сводка по проверенным данным CRM со ссылками на исходные записи.',
                    )
                  }}
                </p>
                <p
                  v-if="summaryCurrent"
                  class="a-summary-limit"
                  :class="{
                    'a-warning': ['unavailable', 'invalid_response'].includes(
                      summary.provider_status,
                    ),
                  }"
                  role="status"
                >
                  <template v-if="summary.provider_status === 'not_configured'">
                    {{
                      t(
                        'AI is not connected. The summary uses verified CRM data.',
                        'ИИ не подключён. Сводка составлена по проверенным данным CRM.',
                      )
                    }}
                  </template>
                  <template
                    v-else-if="summary.provider_status === 'unavailable'"
                  >
                    {{
                      t(
                        'The AI response is unavailable. A verified CRM summary is shown.',
                        'Ответ ИИ недоступен. Показана проверяемая сводка из данных CRM.',
                      )
                    }}
                  </template>
                  <template
                    v-else-if="summary.provider_status === 'invalid_response'"
                  >
                    {{
                      t(
                        'The AI response failed validation. A verified CRM summary is shown.',
                        'Ответ ИИ не прошёл проверку. Показана проверяемая сводка из данных CRM.',
                      )
                    }}
                  </template>
                  <template v-else-if="summary.mode === 'verified_selection'">
                    {{
                      t(
                        'AI selected the topics; CRM verified every number and link.',
                        'ИИ выбрал темы; CRM проверила каждое число и ссылку.',
                      )
                    }}
                  </template>
                  <template v-else>
                    {{
                      t(
                        'The summary uses verified CRM data.',
                        'Сводка составлена по проверенным данным CRM.',
                      )
                    }}
                  </template>
                </p>
                <p
                  v-if="summary && !summaryCurrent"
                  class="a-warning"
                  role="status"
                >
                  {{
                    t(
                      'This summary is out of date. Generate it again.',
                      'Сводка устарела. Сформируйте её заново.',
                    )
                  }}
                </p>
                <ul v-if="summaryCurrent">
                  <li v-for="fact in summary.facts" :key="fact.metric">
                    <Button
                      size="md"
                      variant="ghost"
                      class="a-inline"
                      @click="details(fact.metric)"
                    >
                      {{ metricName(fact.metric) }}:
                      {{ formatFact(fact) }}</Button
                    ><span v-if="fact.complete === false">
                      — {{ t('known part', 'известная часть') }}</span
                    >
                  </li>
                </ul>
                <section
                  v-if="
                    summaryCurrent &&
                    summary.calls &&
                    (summary.calls.facts.length ||
                      summary.calls.status !== 'available' ||
                      !summaryCallsCurrent)
                  "
                  class="a-summary-reasons"
                  aria-labelledby="summary-calls-title"
                >
                  <h4 id="summary-calls-title">{{ t('Calls', 'Звонки') }}</h4>
                  <p v-if="loading" role="status">
                    {{ t('Checking call data…', 'Проверяем данные звонков…') }}
                  </p>
                  <p
                    v-else-if="!summaryCallsCurrent"
                    class="a-warning"
                    role="status"
                  >
                    {{
                      t(
                        'Call data changed. Generate the summary again.',
                        'Данные звонков изменились. Сформируйте сводку заново.',
                      )
                    }}
                  </p>
                  <ul v-else-if="summary.calls.facts.length">
                    <li v-for="fact in summary.calls.facts" :key="fact.metric">
                      <Button
                        size="md"
                        variant="ghost"
                        class="a-inline"
                        @click="openSummaryCall(fact)"
                      >
                        {{ t(...summaryCallLabels[fact.metric]) }}:
                        {{ format(fact.value, fact.unit === 'percent' ? 1 : 0)
                        }}{{ fact.unit === 'percent' ? '%' : '' }}
                        <template v-if="fact.basis">
                          ({{ format(fact.basis.matched, 0) }}
                          {{ t('of', 'из') }}
                          {{ format(fact.basis.eligible, 0) }})
                        </template>
                      </Button>
                    </li>
                  </ul>
                  <p v-else role="status">
                    {{
                      summary.calls.status === 'empty'
                        ? t(
                            'There are no visible calls in this period.',
                            'В выбранном периоде нет доступных звонков.',
                          )
                        : t(
                            'Call data is unavailable for this selection.',
                            'Для выбранного среза данные звонков недоступны.',
                          )
                    }}
                  </p>
                  <p
                    v-if="summaryCallsCurrent && summary.calls.facts.length"
                    class="a-summary-limit"
                  >
                    {{
                      t(
                        'Based on the CRM journal. Provider history completeness is unknown.',
                        'По журналу CRM. Полнота истории оператора неизвестна.',
                      )
                    }}
                  </p>
                </section>
                <div
                  v-if="summaryCurrent && summary.risk_reasons?.length"
                  class="a-summary-reasons"
                >
                  <h4>{{ t('Reasons for attention', 'Причины внимания') }}</h4>
                  <p>
                    {{
                      t(
                        'Confirmed reasons among the deals needing attention:',
                        'Подтверждённые причины среди сделок, требующих внимания:',
                      )
                    }}
                  </p>
                  <ul>
                    <li v-for="item in summary.risk_reasons" :key="item.code">
                      {{ reason(item.code) }} — {{ item.count }}
                      {{ t('of', 'из') }}
                      {{ report.metrics.risk_count.value }}
                    </li>
                  </ul>
                  <Button
                    size="md"
                    variant="ghost"
                    class="a-inline"
                    @click="details('risk_count')"
                  >
                    {{
                      t('Open the affected deals', 'Открыть сделки с риском')
                    }}
                  </Button>
                  <p class="a-summary-limit">
                    {{
                      t(
                        'One deal may have several reasons; do not add these counts.',
                        'У одной сделки может быть несколько причин; числа по причинам нельзя складывать.',
                      )
                    }}
                  </p>
                </div>
                <div
                  v-if="summaryCurrent && summary.source_contribution"
                  class="a-summary-contribution"
                >
                  <p>
                    <strong
                      >{{
                        t('Measured contribution', 'Измеренный вклад')
                      }}.</strong
                    >
                    {{
                      t(
                        'Of the won deal amount in this period, the current source',
                        'В сумме выигранных за период сделок текущий источник',
                      )
                    }}
                    <Button
                      size="md"
                      variant="ghost"
                      class="a-inline"
                      :aria-label="
                        sourceDetailLabel(summary.source_contribution.key)
                      "
                      @click="
                        details('sources', summary.source_contribution.key)
                      "
                    >
                      {{ label('sources', summary.source_contribution.key) }}
                    </Button>
                    {{ t('accounts for', 'даёт') }}
                    {{ format(summary.source_contribution.value) }}
                    {{ report.context.currency }}
                    {{ t('of', 'из') }}
                    {{ format(summary.source_contribution.total) }}
                    {{ report.context.currency }}
                    ({{ format(summary.source_contribution.share_pct) }}%;
                    {{ summary.source_contribution.count }}
                    {{ t('of', 'из') }}
                    {{ summary.source_contribution.total_count }}
                    {{ t('won deals', 'выигранных сделок') }}).
                  </p>
                  <p class="a-summary-limit">
                    <strong
                      >{{
                        t('Hypothesis to check', 'Гипотеза для проверки')
                      }}.</strong
                    >
                    {{
                      t(
                        'The share may reflect the size of individual deals. Open the source to inspect them; these figures do not establish why they were won.',
                        'Доля может зависеть от размера отдельных сделок. Откройте источник и проверьте состав; эти числа не объясняют причины побед.',
                      )
                    }}
                  </p>
                </div>
                <p
                  v-if="
                    summaryCurrent &&
                    summary.limits?.includes('no_period_outcomes')
                  "
                  class="a-summary-limit"
                  role="status"
                >
                  {{
                    t(
                      'No new deals or outcomes in this period. There is no sales change to explain.',
                      'За выбранный период нет новых сделок и исходов. Изменение продаж оценить нельзя.',
                    )
                  }}
                </p>
                <p
                  v-if="
                    summaryCurrent &&
                    summary.limits?.includes('incomplete_data')
                  "
                  class="a-summary-limit a-warning"
                  role="status"
                >
                  {{
                    t(
                      'Some source data is incomplete. The summary shows only confirmed values.',
                      'Часть исходных данных неполная. Сводка показывает только подтверждённые значения.',
                    )
                  }}
                </p>
                <p v-if="summaryCurrent" class="a-summary-limit">
                  {{
                    t(
                      'These metrics do not establish the cause of a change.',
                      'Эти показатели не устанавливают причину изменений.',
                    )
                  }}
                </p>
                <p v-if="!summary">
                  {{
                    t(
                      'The summary links back to its metrics and source records.',
                      'Сводка ссылается на показатели и исходные карточки.',
                    )
                  }}
                </p>
              </Card>
            </div>
            <TabButtons
              v-if="tab === 'deals'"
              v-model="dealView"
              :options="dealViews"
              class="mb-3 max-w-full overflow-x-auto"
              :aria-label="t('Deals analytics', 'Аналитика сделок')"
            />
            <div
              v-if="tab === 'deals' && dealView === 'pipeline'"
              class="a-overview"
            >
              <section
                class="a-overview-metrics a-deal-metrics"
                :aria-label="
                  t(
                    'Deal outcomes for the period',
                    'Результаты сделок за период',
                  )
                "
              >
                <Button
                  v-for="key in periodMetrics"
                  :key="key"
                  variant="ghost"
                  class="a-kpi"
                  :data-metric="key"
                  :title="report.metric_catalog?.[key]?.[lang]"
                  @click="details(key)"
                >
                  <span>{{ metricName(key) }}</span
                  ><strong>{{ metricValue(key) }}</strong>
                  <small v-if="deltaText(key)">{{ deltaText(key) }}</small>
                  <em v-if="report.metrics[key].complete === false">{{
                    t('Incomplete data', 'Данные неполные')
                  }}</em>
                </Button>
              </section>
              <Card
                :title="t('Open pipeline now', 'Открытая воронка сейчас')"
                class="a-panel a-current"
              >
                <p>
                  {{
                    t(
                      'All creation dates. This is the current state.',
                      'Все даты создания. Это текущее состояние.',
                    )
                  }}
                </p>
                <Button
                  size="md"
                  variant="ghost"
                  class="a-open-value"
                  @click="details('open_value')"
                >
                  {{ metricValue('open_value')
                  }}<small
                    >{{ report.metrics.open_count.value }}
                    {{ t('open deals', 'открытые сделки') }}</small
                  >
                </Button>
                <p
                  v-if="!report.metrics.open_value.complete"
                  class="a-warning"
                  role="status"
                >
                  {{
                    t(
                      'Known part only. Some deal amounts or exchange rates are unconfirmed.',
                      'Только известная часть. Суммы или курсы некоторых сделок не подтверждены.',
                    )
                  }}
                </p>
                <div class="a-stage-list">
                  <Button
                    v-for="stage in report.stages"
                    :key="stage.key"
                    size="md"
                    variant="ghost"
                    @click="details('stages', stage.key)"
                  >
                    <span
                      >{{ label('stages', stage.key)
                      }}<small
                        >{{ stage.count }} {{ t('deals', 'сделки') }}</small
                      ></span
                    ><strong>{{ format(stage.value) }}</strong>
                  </Button>
                </div>
                <p v-if="!report.stages.length">
                  {{
                    t(
                      'No available open deals',
                      'Доступных открытых сделок нет',
                    )
                  }}
                </p>
              </Card>
              <Card
                :title="
                  t('Deal risks and loss reasons', 'Риски и причины потерь')
                "
                class="a-panel"
              >
                <template #actions>
                  <Button
                    v-if="report.can_manage_attention_rules"
                    icon-left="lucide-settings-2"
                    :disabled="stale || offline"
                    @click="attentionSettingsOpen = true"
                  >
                    {{ t('Attention rules', 'Правила внимания') }}
                  </Button>
                </template>
                <Button
                  variant="subtle"
                  icon-left="lucide-list-filter"
                  @click="details('risk_count')"
                >
                  {{ t('Deals needing attention', 'Сделки с риском') }} ·
                  {{ metricValue('risk_count') }}
                </Button>
                <h4>
                  {{
                    t('Loss reasons for the period', 'Причины потерь за период')
                  }}
                </h4>
                <div v-if="report.loss_reasons?.length" class="a-stage-list">
                  <Button
                    v-for="row in report.loss_reasons"
                    :key="row.key"
                    variant="ghost"
                    @click="details('loss_reasons', row.key)"
                  >
                    <span>{{
                      row.key || t('Not specified', 'Не указана')
                    }}</span
                    ><strong>{{ row.count }}</strong>
                  </Button>
                </div>
                <p v-else>
                  {{
                    t(
                      'No readable loss reasons for this period.',
                      'Нет доступных причин потерь за этот период.',
                    )
                  }}
                </p>
              </Card>
              <Card
                v-if="report.funnel"
                :title="t('Creation cohort', 'Когорта созданных карточек')"
                class="a-panel a-cohort"
              >
                <p>
                  {{
                    t(
                      'Selected by creation period; outcomes observed at report time.',
                      'Отбор по периоду создания; исходы на момент расчёта.',
                    )
                  }}
                </p>
                <div class="a-cohort-values">
                  <div>
                    <strong>{{ report.funnel.lead_count }}</strong
                    ><span>{{ t('new leads', 'новые лиды') }}</span>
                  </div>
                  <div>
                    <strong>{{ report.funnel.converted_leads }}</strong
                    ><span>{{
                      t('converted to deals', 'перешли в сделки')
                    }}</span>
                  </div>
                  <div>
                    <strong>{{ report.funnel.won_leads }}</strong
                    ><span>{{ t('leads with a win', 'лиды с победой') }}</span>
                  </div>
                </div>
                <p>
                  {{ report.funnel.cohort_count }}
                  {{ t('new deals', 'новые сделки') }}:
                  {{ report.funnel.won }} Won, {{ report.funnel.lost }} Lost.
                  {{
                    t(
                      'Direct deals are included separately from lead conversion.',
                      'Прямые сделки не увеличивают конверсию лидов.',
                    )
                  }}
                </p>
                <div class="a-visit-panel">
                  <h4>
                    {{ t('Recorded stage visits', 'Подтверждённые этапы') }}
                  </h4>
                  <p>
                    {{
                      t(
                        'Each deal counts once per stage. Entries count recorded arrivals, including a return.',
                        'Каждая сделка учитывается на этапе один раз. Входы показывают повторные посещения.',
                      )
                    }}
                  </p>
                  <dl v-if="report.funnel.visited.length" class="a-visit-list">
                    <div
                      v-for="stage in report.funnel.visited"
                      :key="stage.stage"
                    >
                      <dt>{{ label('stages', stage.stage) }}</dt>
                      <dd>
                        {{ t('unique: ', 'уникальных: ')
                        }}<strong>{{ stage.count }}</strong> ·
                        {{ t('entries: ', 'входов: ') }}{{ stage.entry_events }}
                      </dd>
                    </div>
                  </dl>
                  <p v-else>
                    {{
                      t(
                        'No stage entries are recorded for this cohort.',
                        'Для этой когорты входы в этапы не записаны.',
                      )
                    }}
                  </p>
                  <p>
                    {{
                      t(
                        'Recorded stage changes: ',
                        'Записанных изменений этапа: ',
                      )
                    }}{{ report.funnel.stage_changes }}.
                    {{
                      t(
                        'Skipped stages are not treated as visited.',
                        'Пропущенные этапы не считаются пройденными.',
                      )
                    }}
                  </p>
                  <p
                    v-if="report.funnel.cohort_count"
                    :class="{
                      'a-warning':
                        report.funnel.known_from_creation <
                        report.funnel.cohort_count,
                    }"
                  >
                    {{
                      t(
                        'History is known from creation for ',
                        'История от создания подтверждена для ',
                      )
                    }}{{ report.funnel.known_from_creation }} /
                    {{ report.funnel.cohort_count }}.
                    <template
                      v-if="
                        report.funnel.known_from_creation <
                        report.funnel.cohort_count
                      "
                      >{{
                        t(
                          'Earlier visits may be missing for the other deals.',
                          'Для остальных сделок ранние посещения могут отсутствовать.',
                        )
                      }}</template
                    >
                  </p>
                </div>
                <p v-if="!report.funnel.outcome_complete" class="a-warning">
                  {{
                    t(
                      'Some converted leads have no readable related deal. Won conversion is incomplete.',
                      'Для части лидов связанная сделка недоступна. Конверсия в победу неполная.',
                    )
                  }}
                </p>
              </Card>
              <Card
                v-if="report.closing_owners?.length"
                :title="
                  t(
                    'Owner at the time of a win',
                    'Ответственный на дату победы',
                  )
                "
                class="a-panel"
              >
                <p>
                  {{
                    t(
                      'Attribution uses recorded closure events. Filters above apply to current fields.',
                      'Ответственный определяется по истории закрытия. Фильтры выше применяются к текущим полям.',
                    )
                  }}
                </p>
                <ul class="a-visit-list">
                  <li v-for="row in report.closing_owners" :key="row.key">
                    <Button
                      variant="ghost"
                      @click="details('closing_owners', row.key)"
                    >
                      {{
                        row.key
                          ? label('owners', row.key)
                          : t('Unconfirmed', 'Не подтверждён')
                      }}
                      · {{ row.count }} · {{ format(row.value) }}
                      <span v-if="row.value != null">{{
                        report.context.currency
                      }}</span>
                    </Button>
                  </li>
                </ul>
              </Card>
            </div>
            <CallAnalytics
              v-if="tab === 'calls'"
              :context="report.context"
              :lang="lang"
              :stale="stale || offline"
            />
            <PipelineMovement
              v-if="tab === 'deals' && dealView === 'movement'"
              :context="report.context"
              :revision="report.snapshot"
              :t="t"
              :lang="lang"
              :stale="stale || offline"
            />
            <ManagerWork
              v-if="tab === 'managers'"
              :context="report.context"
              :lang="lang"
              :revision="report.snapshot"
              :stale="stale || offline"
            />
            <Card
              v-if="tab === 'deals' && dealView === 'forecast'"
              :title="t('Weighted forecast', 'Взвешенный прогноз')"
              class="a-panel"
            >
              <p>
                {{
                  t(
                    'Open deals only: expected value × probability × stored exchange rate.',
                    'Только открытые сделки: ожидаемая сумма × вероятность × сохранённый курс.',
                  )
                }}
              </p>
              <form class="a-horizon" @submit.prevent="apply">
                <FormControl
                  v-model="filters.forecast_from"
                  type="date"
                  :label="t('Horizon from', 'Горизонт с')"
                  format="YYYY-MM-DD"
                  required
                  :clearable="false"
                /><FormControl
                  v-model="filters.forecast_to"
                  type="date"
                  :label="t('Horizon to', 'Горизонт по')"
                  format="YYYY-MM-DD"
                  required
                  :clearable="false"
                /><Button
                  size="md"
                  variant="subtle"
                  class="a-button"
                  type="submit"
                >
                  {{ t('Recalculate', 'Пересчитать') }}
                </Button>
              </form>
              <Button
                size="md"
                variant="ghost"
                class="a-open-value"
                data-metric="forecast"
                @click="details('forecast')"
              >
                {{ metricValue('forecast') }}
              </Button>
              <p v-if="!report.metrics.forecast.complete" class="a-warning">
                {{
                  t(
                    'Known part only. Missing fields or dates prevent a complete forecast.',
                    'Только известная часть. Пробелы в полях или датах мешают полному прогнозу.',
                  )
                }}
              </p>
              <form class="a-horizon" @submit.prevent="saveSnapshot">
                <FormControl
                  v-model="snapshotTitle"
                  :label="t('Snapshot title', 'Название снимка')"
                  :placeholder="
                    t('For example, November plan', 'Например, план на ноябрь')
                  "
                  maxlength="120"
                  required
                /><Button
                  size="md"
                  variant="subtle"
                  class="a-button"
                  :disabled="saving || stale"
                  type="submit"
                >
                  {{ t('Save this forecast', 'Сохранить этот прогноз') }}
                </Button>
              </form>
              <p>
                {{
                  t(
                    'Saved explicitly. Future corrections do not rewrite saved figures.',
                    'Сохраняется по нажатию. Будущие исправления не переписывают сохранённые цифры.',
                  )
                }}
              </p>
            </Card>
            <ForecastBreakdown
              v-if="tab === 'deals' && dealView === 'forecast'"
              :report="report"
              :lang="lang"
              :t="t"
              :stale="stale || offline"
              @details="(key) => details('forecast_categories', key)"
              @saved="load"
            />
            <ERPReconciliation
              v-if="tab === 'deals' && dealView === 'erp'"
              :context="report.context"
              :revision="report.snapshot"
              :lang="lang"
              :t="t"
              :stale="stale || offline"
            />
            <TabButtons
              v-if="tab === 'sources'"
              v-model="sourcesView"
              :options="sourceViews"
              class="mb-3"
              :aria-label="t('Source analytics', 'Аналитика источников')"
            />
            <MarketingReport
              v-if="tab === 'sources' && sourcesView === 'campaigns'"
              :context="report.context"
              :revision="report.snapshot"
              :lang="lang"
              :t="t"
              :stale="stale || offline"
            />
            <CallAttribution
              v-if="tab === 'sources' && sourcesView === 'call-attribution'"
              :context="report.context"
              :revision="report.snapshot"
              :lang="lang"
              :t="t"
              :stale="stale || offline"
            />
            <Card
              v-if="tab === 'sources' && sourcesView === 'sources'"
              :title="
                t('Wins by current source', 'Победы по текущему источнику')
              "
              class="a-panel"
            >
              <p>
                {{
                  t(
                    'Won in the selected closure period. No ranking or inferred causal claims.',
                    'Won за выбранный период закрытия. Без рейтинга и предположений о причинах.',
                  )
                }}
              </p>
              <div class="a-table-wrap">
                <AnalyticsTable
                  :columns="groupColumns"
                  :rows="report.sources"
                  :label="t('Won deals by source', 'Победы по источнику')"
                  :empty-text="
                    t('No wins in this period', 'За период нет побед')
                  "
                >
                  <template #cell="{ column, row }">
                    <span v-if="column.key === 'key'">{{
                      row.key || t('Unknown', 'Не указан')
                    }}</span>
                    <span
                      v-else-if="column.key === 'value'"
                      class="tabular-nums"
                      >{{ format(row.value) }} {{ report.context.currency
                      }}<Badge
                        v-if="!row.complete"
                        theme="amber"
                        class="ml-1"
                        :label="t('Known part', 'Известная часть')"
                    /></span>
                    <Button
                      v-else-if="column.key === 'action'"
                      variant="ghost"
                      size="sm"
                      :aria-label="
                        t('Open records: ', 'Открыть карточки: ') +
                        (row.key || t('Unknown', 'Не указан'))
                      "
                      @click="details('sources', row.key)"
                      >{{ t('Open', 'Открыть')
                      }}<template #suffix
                        ><Icon
                          name="lucide-arrow-up-right"
                          class="size-3.5" /></template
                    ></Button>
                    <span v-else>{{ row[column.key] }}</span>
                  </template>
                </AnalyticsTable>
              </div>
              <template v-if="tab === 'sources'"
                ><h4>
                  {{
                    t(
                      'New lead cohort by source',
                      'Когорта новых лидов по источнику',
                    )
                  }}
                </h4>
                <div class="a-table-wrap">
                  <AnalyticsTable
                    :columns="cohortColumns"
                    :rows="report.source_cohorts"
                    :label="
                      t(
                        'New lead cohort by source',
                        'Когорта новых лидов по источнику',
                      )
                    "
                    :empty-text="
                      t('No leads in this period', 'За период нет лидов')
                    "
                  >
                    <template #cell="{ column, row }"
                      ><span
                        >{{
                          column.key === 'key'
                            ? row.key || t('Unknown', 'Не указан')
                            : row[column.key]
                        }}{{
                          column.key === 'won' && !row.outcome_complete
                            ? '*'
                            : ''
                        }}</span
                      ></template
                    >
                  </AnalyticsTable>
                </div></template
              >
            </Card>
            <Card
              v-if="tab === 'deals' && dealView === 'saved'"
              :title="t('Saved forecasts', 'Сохранённые прогнозы')"
              class="a-panel"
            >
              <template #actions
                ><Button
                  size="md"
                  variant="subtle"
                  class="a-button"
                  @click="loadSnapshots"
                >
                  {{ t('Load', 'Загрузить') }}
                </Button></template
              >
              <p>
                {{
                  t(
                    'Private snapshots. Opening them rechecks current source access.',
                    'Личные снимки. При открытии проверяется текущий доступ к исходникам.',
                  )
                }}
              </p>
              <ul class="a-saved-list">
                <li v-for="item in snapshots" :key="item.name">
                  <Button
                    size="md"
                    variant="ghost"
                    class="a-inline"
                    @click="openSnapshot(item.name)"
                  >
                    {{ item.title }}</Button
                  ><small>{{ formatSnapshotListDate(item.observed_at) }}</small>
                </li>
              </ul>
              <Button
                v-if="snapshotsMore"
                size="md"
                variant="subtle"
                class="a-button"
                @click="loadSnapshots(true)"
              >
                {{ t('Load more', 'Загрузить ещё') }}
              </Button>
              <p v-if="snapshotsLoaded && !snapshots.length">
                {{
                  t(
                    'No saved forecasts yet. Save one from Forecast.',
                    'Снимков пока нет. Сохраните прогноз на вкладке «Прогноз».',
                  )
                }}
              </p>
              <div v-if="savedSnapshot" class="a-saved-comparison">
                <h4>{{ savedSnapshot.title }}</h4>
                <p
                  v-if="!savedSnapshot.same_source_version"
                  class="a-warning"
                  role="status"
                  aria-atomic="true"
                >
                  {{
                    t(
                      'Source data changed since this snapshot. The saved forecast is preserved; the current one was recalculated.',
                      'Исходные данные после сохранения изменились. Сохранённый прогноз остался прежним; текущий рассчитан заново.',
                    )
                  }}
                </p>
                <p>
                  {{ t('Saved forecast: ', 'Сохранённый прогноз: ')
                  }}{{ format(savedSnapshot.saved.metrics.forecast.value) }}
                  {{ savedSnapshot.saved.context.currency }}
                </p>
                <p>
                  {{ t('Observation date: ', 'Дата наблюдения: ')
                  }}{{ formatObservation(savedSnapshot.saved.context) }}
                </p>
                <p>
                  {{
                    t(
                      'Current calculation for the same filters: ',
                      'Текущий расчёт для тех же фильтров: ',
                    )
                  }}{{ format(savedSnapshot.current.metrics.forecast.value) }}
                  {{ savedSnapshot.current.context.currency }}
                </p>
                <p v-if="savedSnapshot.comparison?.forecast_delta != null">
                  {{ t('Change since saved: ', 'Изменение после сохранения: ')
                  }}{{
                    savedSnapshot.comparison.forecast_delta.startsWith('-') ||
                    savedSnapshot.comparison.forecast_delta === '0.00'
                      ? ''
                      : '+'
                  }}{{ format(savedSnapshot.comparison.forecast_delta) }}
                  {{ savedSnapshot.comparison.currency }}
                </p>
                <p v-else>
                  {{
                    t(
                      'Change cannot be calculated from incomplete or differently denominated forecasts.',
                      'Изменение нельзя посчитать для неполных прогнозов или разных валют отчёта.',
                    )
                  }}
                </p>
                <div class="a-saved-outcome">
                  <h5>
                    {{
                      t(
                        'Observed result of the saved cohort',
                        'Результат сохранённой группы сделок',
                      )
                    }}
                  </h5>
                  <p>
                    {{
                      t(
                        'Only deals in this saved forecast that are currently won and have an actual close date within its horizon are counted. This is not payment revenue.',
                        'Считаются только сделки этого сохранённого прогноза, которые сейчас выиграны и имеют фактическую дату закрытия внутри его горизонта. Это не оплата.',
                      )
                    }}
                  </p>
                  <p
                    v-if="!savedSnapshot.comparison?.actual?.available"
                    role="status"
                  >
                    {{
                      savedSnapshot.comparison?.actual?.reason ===
                      'horizon_not_started'
                        ? t(
                            'The forecast horizon has not started yet. No actual result is shown.',
                            'Горизонт прогноза ещё не начался. Фактический результат не показывается.',
                          )
                        : t(
                            'A comparable result is unavailable for this snapshot. Its original forecast remains visible.',
                            'Сопоставимый результат для этого снимка недоступен. Исходный прогноз сохранён.',
                          )
                    }}
                  </p>
                  <template v-else>
                    <p>
                      {{
                        t('Actual close dates: ', 'Фактические даты закрытия: ')
                      }}
                      {{ savedSnapshot.comparison.actual.forecast_from }} —
                      {{ savedSnapshot.comparison.actual.forecast_to }}.
                      {{ t('Observed at: ', 'Проверено на: ') }}
                      {{ formatObservation(savedSnapshot.current.context) }}.
                    </p>
                    <p>
                      {{
                        savedSnapshot.comparison.actual.complete
                          ? t(
                              'Won value in this horizon: ',
                              'Сумма побед в этом горизонте: ',
                            )
                          : t(
                              'Known part of won value: ',
                              'Известная часть суммы побед: ',
                            )
                      }}{{ format(savedSnapshot.comparison.actual.value) }}
                      {{ savedSnapshot.comparison.actual.currency }}.
                      {{ t('Won deals: ', 'Выигранных сделок: ') }}
                      {{ savedSnapshot.comparison.actual.won_count }} /
                      {{ savedSnapshot.comparison.actual.cohort_count }}.
                    </p>
                    <p
                      v-if="!savedSnapshot.comparison.actual.period_finished"
                      class="a-warning"
                      role="status"
                    >
                      {{
                        t(
                          'The horizon is still in progress. This result is provisional.',
                          'Горизонт ещё идёт. Результат предварительный.',
                        )
                      }}
                    </p>
                    <p
                      v-if="!savedSnapshot.comparison.actual.complete"
                      class="a-warning"
                      role="status"
                    >
                      {{
                        t(
                          'Some outcome amounts or dates are unconfirmed. The known part is not a final total.',
                          'Часть сумм или дат исхода не подтверждена. Известная часть не является полным итогом.',
                        )
                      }}
                    </p>
                    <p
                      v-if="
                        savedSnapshot.comparison.actual.difference_from_saved !=
                        null
                      "
                    >
                      {{
                        t(
                          'Difference from the saved forecast for the same deals: ',
                          'Разница с сохранённым прогнозом тех же сделок: ',
                        )
                      }}
                      {{
                        savedSnapshot.comparison.actual.difference_from_saved.startsWith(
                          '-',
                        ) ||
                        savedSnapshot.comparison.actual
                          .difference_from_saved === '0.00'
                          ? ''
                          : '+'
                      }}{{
                        format(
                          savedSnapshot.comparison.actual.difference_from_saved,
                        )
                      }}
                      {{ savedSnapshot.comparison.actual.currency }}.
                    </p>
                    <p
                      v-else-if="
                        savedSnapshot.comparison.actual.period_finished
                      "
                    >
                      {{
                        t(
                          'A difference is withheld until the saved forecast and the observed result are complete.',
                          'Разница не рассчитывается, пока сохранённый прогноз и наблюдаемый результат не полны.',
                        )
                      }}
                    </p>
                    <AnalyticsTable
                      v-if="savedSnapshot.comparison.categories?.length"
                      class="mt-3"
                      :columns="savedForecastCategoryColumns"
                      :rows="savedSnapshot.comparison.categories"
                      :label="
                        t(
                          'Saved forecast by category',
                          'Сохранённый прогноз по категориям',
                        )
                      "
                    >
                      <template #cell="{ column, row }">
                        <span v-if="column.key === 'key'">{{
                          forecastCategoryLabel(row.key, t)
                        }}</span>
                        <span v-else-if="column.key === 'weighted'">
                          {{ format(row.weighted) }}
                          <small v-if="!row.weighted_complete">{{
                            t('known part', 'известная часть')
                          }}</small>
                        </span>
                        <span v-else-if="column.key === 'actual'">
                          {{
                            row.actual.available
                              ? format(row.actual.value)
                              : '—'
                          }}
                          <small
                            v-if="row.actual.available && !row.actual.complete"
                            >{{ t('known part', 'известная часть') }}</small
                          >
                        </span>
                        <span v-else>{{
                          format(row.actual.difference_from_saved)
                        }}</span>
                      </template>
                    </AnalyticsTable>
                  </template>
                </div>
                <div v-if="savedOwnerRows.length" class="a-saved-owners">
                  <h5>
                    {{
                      t(
                        'Open value by owner',
                        'Открытая сумма по ответственным',
                      )
                    }}
                  </h5>
                  <div class="a-table-wrap">
                    <AnalyticsTable
                      :columns="savedColumns"
                      :rows="savedOwnerRows"
                      :label="
                        t(
                          'Open value by owner',
                          'Открытая сумма по ответственным',
                        )
                      "
                    >
                      <template #cell="{ column, row }">
                        <span v-if="column.key === 'label'">{{
                          row.label
                        }}</span>
                        <span v-else
                          >{{
                            row[column.key]?.complete
                              ? format(row[column.key].value)
                              : '—'
                          }}
                          {{
                            row[column.key]?.complete
                              ? savedSnapshot[
                                  column.key === 'before' ? 'saved' : 'current'
                                ].context.currency
                              : ''
                          }}</span
                        >
                      </template>
                    </AnalyticsTable>
                  </div>
                </div>
              </div>
            </Card>
          </template>
        </Tabs>
        <p v-if="tab !== 'managers' && tab !== 'calls'" class="a-footer">
          {{
            t(
              'Calculated from source records. Forecast is an estimate, not a payment plan.',
              'Расчёт по исходным карточкам. Прогноз — оценка, а не план оплат.',
            )
          }}
        </p>
      </template>
      <Alert
        v-if="notice"
        :dismissible="false"
        theme="blue"
        class="a-notice mt-3"
        role="status"
        :title="notice"
      />
    </main>
    <AnalyticsSignals v-model:open="signalsOpen" :lang="lang" :t="t" />
    <AttentionSettings
      v-model:open="attentionSettingsOpen"
      :pipeline="report?.context.pipeline || ''"
      :reason="reason"
      :t="t"
      @saved="load"
    />
    <Dialog
      v-model="detailOpen"
      :title="detailTitle"
      size="3xl"
      :show-close-button="false"
      @close="closeDetails"
    >
      <div class="a-dialog">
        <p v-if="detailLoading" role="status">
          {{ t('Loading records…', 'Загрузка карточек…') }}
        </p>
        <p v-if="detailError" class="a-error" role="alert">{{ detailError }}</p>
        <template v-if="detail"
          ><p>
            {{ t('Records: ', 'Карточек: ') }}{{ detail.total }}.
            {{
              t(
                'These records use the same report version.',
                'Карточки той же версии отчёта.',
              )
            }}
          </p>
          <Button
            size="md"
            variant="subtle"
            class="a-button"
            :disabled="exporting || detailLoading || stale || offline"
            @click="exportDetails"
          >
            {{
              exporting
                ? t('Preparing CSV…', 'Подготовка CSV…')
                : t('Export CSV', 'Скачать CSV')
            }}
          </Button>
          <div class="a-detail-records">
            <article v-for="row in detail.rows" :key="row.name">
              <RouterLink
                :to="
                  (detailMetric === 'new_leads' ? '/leads/' : '/deals/') +
                  encodeURIComponent(row.name)
                "
                @click="closeDetails()"
                >{{ row.title || row.name }}</RouterLink
              ><span>{{ row.status_label || '' }}</span
              ><strong
                v-if="row.value !== undefined && row.currency_valid !== false"
                >{{ format(row.value) }} {{ row.currency || '' }}</strong
              ><small
                v-if="
                  row.base_value !== null &&
                  row.base_value !== undefined &&
                  row.currency &&
                  row.currency !== report.context.currency
                "
                class="a-converted"
                >= {{ format(row.base_value) }}
                {{ report.context.currency }}</small
              ><small v-if="row.currency_valid === false" class="a-warning">{{
                t(
                  'Amount excluded: unknown currency',
                  'Сумма не учтена: неизвестная валюта',
                )
              }}</small>
              <small
                v-if="row.forecast_contribution != null"
                class="a-converted"
              >
                {{ t('Forecast contribution', 'Вклад в прогноз') }}
                {{ format(row.forecast_contribution) }}
                {{ report.context.currency }}
              </small>
              <small>{{ row.owner || '' }} {{ row.expected_date || '' }}</small>
              <ul
                v-if="row.reason_facts"
                class="col-span-full list-disc pl-4 text-sm text-ink-gray-7"
              >
                <li v-for="(evidence, code) in row.reason_facts" :key="code">
                  {{ reasonEvidence(code, evidence) }}
                </li>
              </ul>
            </article>
          </div>
          <p v-if="!detail.total">
            {{
              t(
                'No records match this metric.',
                'Карточек для этого показателя нет.',
              )
            }}
          </p>
          <div class="a-pagination">
            <Button
              size="md"
              variant="subtle"
              class="a-button"
              :disabled="!detail.start || detailLoading"
              @click="detailPage(detail.start - detail.limit)"
            >
              {{ t('Previous', 'Назад') }}</Button
            ><span
              >{{ detail.total ? detail.start + 1 : 0 }}–{{
                detail.start + detail.rows.length
              }}
              / {{ detail.total }}</span
            ><Button
              size="md"
              variant="subtle"
              class="a-button"
              :disabled="!detail.has_more || detailLoading"
              @click="detailPage(detail.start + detail.limit)"
            >
              {{ t('Next', 'Далее') }}
            </Button>
          </div></template
        >
      </div>
      <template #actions
        ><Button variant="subtle" @click="closeDetails">{{
          t('Close', 'Закрыть')
        }}</Button></template
      >
    </Dialog>
  </div>
</template>

<script setup>
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  reactive,
  ref,
  watch,
} from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Alert,
  Badge,
  Button,
  Card,
  Dialog,
  FormControl,
  Icon,
  LoadingIndicator,
  TabButtons,
  Tabs,
  call,
} from 'frappe-ui'
import AnalyticsTable from '@/components/Analytics/AnalyticsTable.vue'
import ManagerWork from '@/components/Analytics/ManagerWork.vue'
import CallAnalytics from '@/components/Analytics/CallAnalytics.vue'
import AnalyticsChart from '@/components/Analytics/AnalyticsChart.vue'
import AnalyticsSignals from '@/components/Analytics/AnalyticsSignals.vue'
import AttentionSettings from '@/components/Analytics/AttentionSettings.vue'
import PipelineMovement from '@/components/Analytics/PipelineMovement.vue'
import ForecastBreakdown from '@/components/Analytics/ForecastBreakdown.vue'
import MarketingReport from '@/components/Analytics/MarketingReport.vue'
import CallAttribution from '@/components/Analytics/CallAttribution.vue'
import ERPReconciliation from '@/components/Analytics/ERPReconciliation.vue'
import LayoutHeader from '@/components/LayoutHeader.vue'
import { formatAnalyticsNumber } from '@/utils/analyticsNumbers'
import { forecastCategoryLabel } from '@/utils/forecastCategories'
import { analyticsPeriod } from '@/utils/analyticsPeriods'
import { sessionUser } from '@/stores/session'

const route = useRoute(),
  router = useRouter()
const REPORT_TIMEOUT_MS = 15000
const lang = ref('ru'),
  report = ref(null),
  loading = ref(false),
  error = ref(''),
  stale = ref(false),
  offline = ref(!navigator.onLine),
  notice = ref('')
const filtersOpen = ref(false)
const qualityOpen = ref(false)
const signalsOpen = ref(false)
const attentionSettingsOpen = ref(false)
const summaryVisible = ref(false)
const dealView = computed({
  get() {
    const value = route.query.deal_view
    return ['movement', 'forecast', 'saved', 'erp'].includes(value)
      ? value
      : 'pipeline'
  },
  set(value) {
    router.replace({
      query: {
        ...route.query,
        deal_view: value === 'pipeline' ? undefined : value,
      },
    })
  },
})
const sourcesView = computed({
  get: () =>
    ['campaigns', 'call-attribution'].includes(route.query.sources_view)
      ? route.query.sources_view
      : 'sources',
  set: (value) =>
    router.replace({
      query: {
        ...route.query,
        sources_view: value === 'sources' ? undefined : value,
      },
    }),
})
const tab = ref('overview'),
  summary = ref(null),
  summaryLoading = ref(false),
  snapshotTitle = ref(''),
  saving = ref(false)
const summaryCurrent = computed(
  () =>
    summary.value &&
    report.value &&
    !stale.value &&
    !offline.value &&
    summary.value.snapshot === report.value.snapshot,
)
const checkedSummaryCalls = ref(null)
const summaryCallsCurrent = computed(
  () =>
    summaryCurrent.value &&
    !loading.value &&
    summary.value.calls?.revision === checkedSummaryCalls.value?.revision &&
    summary.value.calls?.status === checkedSummaryCalls.value?.status,
)
const summaryCallLabels = {
  calls_total: ['Total calls', 'Всего звонков'],
  calls_missed: ['Missed incoming', 'Пропущенные входящие'],
  calls_overdue: ['Overdue callbacks', 'Просроченные перезвоны'],
  calls_sla: ['Callbacks on time', 'Перезвоны в срок'],
}
const snapshots = ref([]),
  snapshotsMore = ref(false),
  snapshotsLoaded = ref(false),
  savedSnapshot = ref(null)
const savedOwnerRows = computed(() => {
  const saved = savedSnapshot.value?.saved
  const current = savedSnapshot.value?.current
  if (!saved || !current) return []
  const before = new Map((saved.open_owners || []).map((row) => [row.key, row]))
  const after = new Map(
    (current.open_owners || []).map((row) => [row.key, row]),
  )
  return [...new Set([...before.keys(), ...after.keys()])]
    .sort()
    .map((key) => ({
      key,
      label:
        current.labels?.owners?.[key] || saved.labels?.owners?.[key] || key,
      before: before.get(key),
      after: after.get(key),
    }))
})
const detailOpen = ref(false),
  detail = ref(null),
  detailError = ref(''),
  detailLoading = ref(false),
  exporting = ref(false),
  detailTitle = ref(''),
  detailMetric = ref('')
const filters = reactive(
  Object.fromEntries(
    [
      'from_date',
      'to_date',
      'forecast_from',
      'forecast_to',
      'owner',
      'pipeline',
      'source',
    ].map((k) => [k, typeof route.query[k] === 'string' ? route.query[k] : '']),
  ),
)
const historicalRequested = computed(() =>
  Object.prototype.hasOwnProperty.call(route.query, 'as_of'),
)
let generation = 0,
  controller,
  summaryRequest,
  timer,
  detailContext
let activeViewer = sessionUser()
let viewerRevision = 0
const periodPresets = [
  { key: 'month', en: 'This month', ru: 'Этот месяц' },
  { key: '30days', en: '30 days', ru: '30 дней' },
  { key: 'quarter', en: 'This quarter', ru: 'Квартал' },
]
const periodAnchor = () =>
  report.value?.context.as_of?.slice(0, 10) ||
  new Date().toLocaleDateString('en-CA')
const activePeriod = computed(
  () =>
    periodPresets.find((p) => {
      const range = analyticsPeriod(p.key, periodAnchor())
      return (
        range.from_date === filters.from_date &&
        range.to_date === filters.to_date
      )
    })?.key,
)
async function choosePeriod(key) {
  Object.assign(filters, analyticsPeriod(key, periodAnchor()))
  await apply()
}
async function clearDimensions() {
  filters.owner = filters.pipeline = filters.source = ''
  await apply()
}
const t = (en, ru) => (lang.value === 'ru' ? ru : en)
const names = {
  won_value: ['Won deal value', 'Сумма выигранных сделок'],
  new_leads: ['New leads', 'Новые лиды'],
  new_deals: ['New deals', 'Новые сделки'],
  won_count: ['Won deals', 'Выигранные сделки'],
  lost_count: ['Lost deals', 'Проигранные сделки'],
  win_rate: ['Win rate', 'Доля побед'],
  median_cycle: ['Median deal cycle', 'Медианный цикл сделки'],
  open_value: ['Open deal value', 'Сумма открытых сделок'],
  open_count: ['Open deals', 'Открытые сделки'],
  forecast: ['Weighted forecast', 'Взвешенный прогноз'],
  forecast_categories: ['Forecast category', 'Категория прогноза'],
  risk_count: ['Deals needing attention', 'Сделки с риском'],
  risk_value: ['Value needing attention', 'Сумма с риском'],
  average_won_value: ['Average won value', 'Средняя сумма победы'],
  median_won_value: ['Median won value', 'Медианная сумма победы'],
  lead_cycle: ['Median lead-to-win cycle', 'Медианный цикл лид → победа'],
  average_cycle: ['Average cycle', 'Средний цикл'],
}
const periodMetrics = [
  'new_leads',
  'new_deals',
  'won_count',
  'lost_count',
  'win_rate',
  'median_cycle',
]
const tabs = [
  { id: 'overview', en: 'Overview', ru: 'Обзор' },
  { id: 'deals', en: 'Deals', ru: 'Сделки' },
  { id: 'managers', en: 'Manager work', ru: 'Работа менеджеров' },
  { id: 'calls', en: 'Calls', ru: 'Звонки' },
  { id: 'sources', en: 'Sources', ru: 'Источники' },
]
const dealViews = computed(() => [
  { value: 'pipeline', label: t('Pipeline', 'Воронка') },
  { value: 'movement', label: t('Movement', 'Движение') },
  { value: 'forecast', label: t('Forecast', 'Прогноз') },
  { value: 'saved', label: t('Snapshots', 'Снимки') },
  { value: 'erp', label: t('ERP actuals', 'Факт ERP') },
])
const sourceViews = computed(() => [
  { value: 'sources', label: t('Sources', 'Источники') },
  { value: 'campaigns', label: t('Campaigns', 'Кампании') },
  {
    value: 'call-attribution',
    label: t('Calls and campaigns', 'Звонки и кампании'),
  },
])
const activeDimensions = computed(
  () =>
    ['owner', 'pipeline', 'source'].filter((key) => report.value?.context[key])
      .length,
)
const overviewMetrics = computed(() => [
  {
    key: 'won_value',
    label: t('Won deal value', 'Сумма выигранных сделок'),
    note: deltaText('won_value'),
  },
  {
    key: 'open_value',
    label: t('Open pipeline', 'Открытая воронка'),
    note: t('All open deals today', 'Все открытые сделки сейчас'),
  },
  {
    key: 'risk_count',
    label: t('Needs attention', 'Требуют внимания'),
    note: t('Current risks and overdue actions', 'Текущие риски и просрочки'),
  },
])
const metricName = (key) => (names[key] ? t(...names[key]) : key)
const format = (value, digits = 2) =>
  formatAnalyticsNumber(value, lang.value === 'ru' ? 'ru-RU' : 'en-US', digits)
const formatObservation = (context) => {
  const date = new Date(context.as_of)
  if (Number.isNaN(date.getTime())) return context.as_of
  return new Intl.DateTimeFormat(lang.value === 'ru' ? 'ru-RU' : 'en-US', {
    timeZone: context.timezone,
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date)
}
const formatSnapshotListDate = (value) => {
  const match = String(value || '').match(
    /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/,
  )
  return match
    ? `${match[3]}.${match[2]}.${match[1]} ${match[4]}:${match[5]}`
    : value
}
const formatFact = (fact) =>
  fact.value == null
    ? t('No data', 'Нет данных')
    : format(fact.value) +
      (fact.metric === 'win_rate'
        ? '%'
        : /value|forecast/.test(fact.metric)
          ? ' ' + report.value.context.currency
          : '')
const metricValue = (key) => {
  if (report.value.metrics[key].value == null) return t('No data', 'Нет данных')
  return (
    formatFact({ metric: key, ...report.value.metrics[key] }) +
    (['median_cycle', 'lead_cycle', 'average_cycle'].includes(key)
      ? t(' d', ' дн.')
      : '')
  )
}
const label = (kind, key) =>
  report.value?.labels?.[kind]?.[key] || key || t('Unspecified', 'Не указан')
const sourceDetailLabel = (key) =>
  `${t('Show deals from source', 'Показать сделки источника')} ${label('sources', key)}`
const observedTime = computed(() => {
  const ctx = report.value?.context
  return ctx
    ? new Intl.DateTimeFormat(lang.value === 'ru' ? 'ru-RU' : 'en-US', {
        timeZone: ctx.timezone,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      }).format(new Date(ctx.as_of))
    : ''
})
function deltaText(key) {
  const m = report.value.metrics[key]
  return m.delta === null
    ? t('No comparison baseline', 'Нет базы сравнения')
    : m.delta !== undefined
      ? `${Number(m.delta) > 0 ? '+' : ''}${format(m.delta)}% ${t('vs previous period', 'к предыдущему периоду')}`
      : ''
}
const reasons = {
  no_next_action: ['No readable next task', 'Нет доступной следующей задачи'],
  overdue_action: ['Overdue task', 'Просрочена задача'],
  long_stage: ['Long time in stage', 'Долго на этапе'],
  overdue_close: ['Expected close overdue', 'Просрочено ожидаемое закрытие'],
  pushed_close: ['Expected close moved later', 'Ожидаемое закрытие перенесено'],
}
const reason = (code) => (reasons[code] ? t(...reasons[code]) : code)
function reasonEvidence(code, fact) {
  const label = reason(code)
  const when = fact.at ? String(fact.at).replace('T', ' ').slice(0, 16) : ''
  if (code === 'long_stage')
    return `${label} · ${t('since', 'с')} ${when} · ${t('threshold', 'порог')} ${fact.threshold_days} ${t('days', 'дн.')}`
  if (code === 'pushed_close' && fact.previous_date && fact.new_date)
    return `${label} · ${fact.previous_date} → ${fact.new_date}`
  if (code === 'overdue_action' || code === 'overdue_close')
    return `${label} · ${t('due', 'срок')} ${when}`
  return label
}
const qualityNames = {
  missing_source: ['Missing source', 'Не указан источник'],
  unknown_or_invalid_amount: [
    'Amount or exchange rate unconfirmed',
    'Не подтверждена сумма или курс',
  ],
  unknown_currency: ['Unknown currency', 'Неизвестная валюта'],
  unknown_stage_type: ['Unknown stage outcome', 'Неизвестный тип этапа'],
  incomplete_forecast: [
    'Forecast inputs unconfirmed',
    'Не подтверждены данные прогноза',
  ],
  missing_expected_date: [
    'Missing expected closure',
    'Нет ожидаемой даты закрытия',
  ],
  missing_outcome_date: [
    'Missing actual outcome date',
    'Нет подтверждённой даты исхода',
  ],
  invalid_outcome_date: [
    'Invalid actual outcome date',
    'Некорректная дата исхода',
  ],
  incomplete_stage_history: [
    'Incomplete stage history',
    'Неполная история этапа',
  ],
  unscheduled_action: ['Task without due date', 'Задача без срока'],
  invalid_cycle: [
    'Invalid creation-to-close interval',
    'Некорректный интервал до закрытия',
  ],
}
const qualityName = (code) =>
  qualityNames[code] ? t(...qualityNames[code]) : code
async function api(method, params = {}, signal) {
  const q = new URLSearchParams(
    Object.entries(params).map(([k, v]) => [
      k,
      typeof v === 'object' ? JSON.stringify(v) : String(v),
    ]),
  )
  const response = await fetch('/api/method/' + method + '?' + q, {
    credentials: 'same-origin',
    cache: 'no-store',
    signal,
    headers: { Accept: 'application/json' },
  })
  const body = await response.json()
  if (!response.ok || body.exc) {
    const e = new Error(body.exc_type || `HTTP ${response.status}`)
    e.kind = body.exc_type
    throw e
  }
  return body.message
}
function message(e) {
  return e.kind === 'TimestampMismatchError'
    ? t(
        'Data or access changed. Refresh the report.',
        'Данные или права изменились. Обновите отчёт.',
      )
    : e.kind === 'PermissionError'
      ? t(
          'This information is unavailable with current permissions.',
          'Информация недоступна с текущими правами.',
        )
      : e.kind === 'ValidationError'
        ? t(
            'Check the period and filters, then apply again.',
            'Проверьте период и фильтры и примените их заново.',
          )
        : t(
            'The report could not be loaded. Check the connection and try again.',
            'Не удалось загрузить отчёт. Проверьте соединение и повторите.',
          )
}
async function load() {
  const viewer = syncViewer()
  if (!viewer) {
    error.value = t(
      'Sign in to view analytics.',
      'Войдите в CRM, чтобы открыть аналитику.',
    )
    return
  }
  if (historicalRequested.value) {
    ++generation
    controller?.abort()
    closeDetails()
    report.value = null
    summary.value = null
    stale.value = true
    loading.value = false
    error.value = t(
      'A historical as-of report is unavailable without complete source history. Open a saved snapshot for a recorded past result.',
      'Исторический срез недоступен без полной истории источников. Для сохранённого результата откройте снимок.',
    )
    return
  }
  if (offline.value) {
    stale.value = true
    return
  }
  const current = ++generation
  detailContext = null
  detailLoading.value = false
  exporting.value = false
  detailError.value = ''
  controller?.abort()
  const requestController = new AbortController()
  controller = requestController
  let timedOut = false
  const requestTimer = window.setTimeout(() => {
    timedOut = true
    requestController.abort()
  }, REPORT_TIMEOUT_MS)
  loading.value = true
  error.value = ''
  closeDetails()
  try {
    const checkCalls = Boolean(summary.value?.calls && tab.value === 'overview')
    const data = await api(
      'crm.analytics.service.get_report',
      {
        filters: Object.fromEntries(
          Object.entries(filters).filter(([, v]) => v),
        ),
        ...(checkCalls ? { check_summary_calls: true } : {}),
      },
      requestController.signal,
    )
    if (current !== generation) return
    if (sessionUser() !== viewer) return load()
    report.value = data
    if (checkCalls) checkedSummaryCalls.value = data.summary_calls || null
    for (const key of Object.keys(filters))
      filters[key] = data.context[key] || ''
    stale.value = false
  } catch (e) {
    if (current === generation && (timedOut || e.name !== 'AbortError')) {
      error.value = timedOut
        ? t(
            'The report took too long. The previous result is out of date; try again.',
            'Превышено время ожидания отчёта. Прежний результат устарел; повторите запрос.',
          )
        : message(e)
      stale.value = true
      if (e.kind === 'PermissionError' || e.kind === 'AuthenticationError') {
        report.value = null
        summary.value = null
      }
    }
  } finally {
    window.clearTimeout(requestTimer)
    if (current === generation) loading.value = false
  }
}
async function showCurrentReport() {
  const query = { ...route.query }
  delete query.as_of
  await router.replace({ query })
}
async function apply() {
  const query = Object.fromEntries(
    Object.entries(route.query).filter(([k]) => !(k in filters)),
  )
  Object.assign(
    query,
    Object.fromEntries(Object.entries(filters).filter(([, v]) => v)),
  )
  const before = route.fullPath
  await router.replace({ query })
  if (route.fullPath === before) await load()
}
watch(
  () => route.query,
  (query, previous) => {
    if (route.name !== 'Dashboard') return
    if (
      !Object.keys(filters).some((key) => query[key] !== previous[key]) &&
      query.as_of === previous.as_of
    )
      return
    for (const key of Object.keys(filters))
      filters[key] = typeof query[key] === 'string' ? query[key] : ''
    load()
  },
)
watch([tab, dealView], ([section, view]) => {
  if (section === 'deals' && view === 'saved' && !snapshotsLoaded.value)
    loadSnapshots()
  if (section === 'overview' && summary.value?.calls && !loading.value) load()
})
let detailTrigger
function closeDetails() {
  detailOpen.value = false
  detail.value = null
  detailContext = null
  nextTick(() => {
    if (detailTrigger?.isConnected) detailTrigger.focus()
  })
}
async function details(metric, groupKey) {
  detailTrigger = document.activeElement
  if (!report.value || stale.value || loading.value) return
  detailMetric.value = metric
  if (metric === 'closing_owners') {
    detailTitle.value = groupKey
      ? label('owners', groupKey)
      : t(
          'Unconfirmed owner at close',
          'Ответственный на дату победы не подтверждён',
        )
  } else {
    detailTitle.value = names[metric]
      ? metricName(metric)
      : metric === 'quality'
        ? qualityName(groupKey)
        : metric === 'loss_reasons'
          ? groupKey ||
            t('Loss reason not specified', 'Причина потери не указана')
          : label(metric === 'stages' ? 'stages' : 'owners', groupKey)
  }
  detailContext = {
    snapshot_token: report.value.snapshot_token,
    metric,
    ...(groupKey !== undefined ? { group_key: groupKey } : {}),
  }
  detail.value = null
  detailError.value = ''
  await nextTick()
  detailOpen.value = true
  await detailPage(0)
}
async function detailPage(start) {
  const ctx = detailContext
  detailLoading.value = true
  detailError.value = ''
  try {
    const data = await api('crm.analytics.service.get_details', {
      ...ctx,
      start,
      limit: 25,
    })
    if (ctx === detailContext) detail.value = data
  } catch (e) {
    if (ctx !== detailContext) return
    detailError.value = message(e)
    if (e.kind === 'TimestampMismatchError') stale.value = true
    detail.value = null
  } finally {
    if (ctx === detailContext) detailLoading.value = false
  }
}
async function exportDetails() {
  const ctx = detailContext
  if (!ctx || !detail.value || stale.value || offline.value) return
  exporting.value = true
  detailError.value = ''
  try {
    const data = await api('crm.analytics.service.export_details', ctx)
    if (ctx !== detailContext || data.snapshot !== detail.value?.snapshot)
      return
    const url = URL.createObjectURL(
      new Blob(['\ufeff', data.csv], { type: 'text/csv;charset=utf-8' }),
    )
    const link = document.createElement('a')
    link.href = url
    link.download = data.filename
    link.click()
    setTimeout(() => URL.revokeObjectURL(url), 30_000)
  } catch (e) {
    if (ctx !== detailContext) return
    detailError.value = message(e)
    if (e.kind === 'TimestampMismatchError') stale.value = true
    if (e.kind === 'TimestampMismatchError' || e.kind === 'PermissionError')
      detail.value = null
  } finally {
    if (ctx === detailContext) exporting.value = false
  }
}
function openSummary() {
  summaryVisible.value = true
  if (!summaryCurrent.value && !stale.value && !offline.value) generateSummary()
}
async function generateSummary() {
  const current = report.value
  if (
    !current ||
    loading.value ||
    stale.value ||
    offline.value ||
    summaryLoading.value
  )
    return
  const revision = generation
  const viewer = sessionUser()
  const request = new AbortController()
  summaryRequest = request
  const timeout = window.setTimeout(
    () => request.abort(new Error('Summary timed out')),
    REPORT_TIMEOUT_MS,
  )
  summaryLoading.value = true
  try {
    const data = await api(
      'crm.analytics.summary.get_summary',
      { snapshot_token: current.snapshot_token, include_calls: true },
      request.signal,
    )
    if (
      request !== summaryRequest ||
      generation !== revision ||
      sessionUser() !== viewer
    )
      return
    summary.value = data
    checkedSummaryCalls.value = data.calls || null
  } catch (e) {
    if (
      request === summaryRequest &&
      generation === revision &&
      e.name !== 'AbortError'
    )
      notice.value = message(e)
  } finally {
    window.clearTimeout(timeout)
    if (request === summaryRequest) {
      summaryRequest = null
      summaryLoading.value = false
    }
  }
}
function openSummaryCall(fact) {
  if (!summaryCallsCurrent.value) return
  const query = Object.fromEntries(
    Object.entries(route.query).filter(([key]) => !key.startsWith('call_')),
  )
  for (const key of ['from_date', 'to_date', 'owner', 'pipeline', 'source'])
    query[key] = report.value.context[key] || undefined
  const metric = fact.detail_metric
  return router.push({
    name: 'Dashboard',
    query: {
      ...query,
      section: 'calls',
      call_view: ['overdue', 'sla_percent'].includes(metric)
        ? 'sla'
        : undefined,
    },
    state: {
      crmSummaryCall: { metric, revision: summary.value.calls.revision },
    },
  })
}
let saveIntent
async function saveSnapshot() {
  if (!report.value || stale.value) return
  const viewerRevisionAtStart = viewerRevision
  saving.value = true
  if (
    !saveIntent ||
    saveIntent.snapshot_token !== report.value.snapshot_token ||
    saveIntent.title !== snapshotTitle.value
  )
    saveIntent = {
      snapshot_token: report.value.snapshot_token,
      title: snapshotTitle.value,
      request_key: crypto.randomUUID().replaceAll('-', ''),
    }
  try {
    await call('crm.analytics.snapshots.save_forecast_snapshot', saveIntent)
    if (!sameViewer(viewerRevisionAtStart)) return
    saveIntent = null
    notice.value = t(
      'Forecast saved. Open Saved to view it.',
      'Прогноз сохранён. Откройте «Снимки» в разделе «Сделки».',
    )
    await loadSnapshots()
  } catch (e) {
    if (sameViewer(viewerRevisionAtStart)) notice.value = message(e)
  } finally {
    if (sameViewer(viewerRevisionAtStart)) saving.value = false
  }
}
async function loadSnapshots(more = false) {
  const viewerRevisionAtStart = viewerRevision
  try {
    const data = await api('crm.analytics.snapshots.list_forecast_snapshots', {
      start: more ? snapshots.value.length : 0,
    })
    if (!sameViewer(viewerRevisionAtStart)) return
    snapshots.value = more ? [...snapshots.value, ...data.rows] : data.rows
    snapshotsMore.value = data.has_more
    snapshotsLoaded.value = true
  } catch (e) {
    if (sameViewer(viewerRevisionAtStart)) notice.value = message(e)
  }
}
async function openSnapshot(name) {
  const viewerRevisionAtStart = viewerRevision
  try {
    const data = await api('crm.analytics.snapshots.get_forecast_snapshot', {
      name,
    })
    if (sameViewer(viewerRevisionAtStart)) savedSnapshot.value = data
  } catch (e) {
    if (sameViewer(viewerRevisionAtStart)) {
      savedSnapshot.value = null
      notice.value = message(e)
    }
  }
}
function reconnect() {
  offline.value = !navigator.onLine
  if (offline.value) pausePendingReport()
  else {
    stale.value = true
    load()
  }
}
function pausePendingReport() {
  ++generation
  controller?.abort()
  summaryRequest?.abort()
  controller = null
  loading.value = false
  error.value = ''
  stale.value = true
}
function syncViewer() {
  const viewer = sessionUser()
  if (viewer === activeViewer) return viewer
  activeViewer = viewer
  viewerRevision++
  pausePendingReport()
  closeDetails()
  report.value = null
  summary.value = null
  checkedSummaryCalls.value = null
  snapshots.value = []
  snapshotsLoaded.value = false
  snapshotsMore.value = false
  savedSnapshot.value = null
  snapshotTitle.value = ''
  saveIntent = null
  saving.value = false
  notice.value = ''
  return viewer
}
function sameViewer(revision) {
  return revision === viewerRevision && sessionUser() === activeViewer
}
function sessionCookieChanged(event) {
  if (
    [...event.changed, ...event.deleted].some(
      ({ name }) => name === 'user_id',
    ) &&
    sessionUser() !== activeViewer
  ) {
    syncViewer()
    resume()
  }
}
function resume() {
  if (document.visibilityState === 'visible') load()
  else pausePendingReport()
}
onMounted(() => {
  load()
  window.addEventListener('online', reconnect)
  window.addEventListener('offline', reconnect)
  window.addEventListener('focus', resume)
  window.cookieStore?.addEventListener('change', sessionCookieChanged)
  document.addEventListener('visibilitychange', resume)
  timer = setInterval(() => {
    if (document.visibilityState === 'visible' && !detailOpen.value) load()
    else pausePendingReport()
  }, 30000)
})
onBeforeUnmount(() => {
  ++generation
  controller?.abort()
  summaryRequest?.abort()
  clearInterval(timer)
  report.value = null
  summary.value = null
  window.removeEventListener('online', reconnect)
  window.removeEventListener('offline', reconnect)
  window.removeEventListener('focus', resume)
  window.cookieStore?.removeEventListener('change', sessionCookieChanged)
  document.removeEventListener('visibilitychange', resume)
})

watch(
  () => route.query.section,
  (section) => {
    if (route.name === 'Dashboard')
      tab.value = tabs.some((item) => item.id === section)
        ? section
        : 'overview'
  },
  { immediate: true },
)
const tabIndex = computed({
  get: () =>
    Math.max(
      0,
      tabs.findIndex((item) => item.id === tab.value),
    ),
  set: (value) => {
    const next = tabs[Number(value)]?.id || 'overview'
    if (next === tab.value) return
    tab.value = next
    router.replace({
      query: {
        ...route.query,
        section: next === 'overview' ? undefined : next,
      },
    })
  },
})
const sectionTabs = computed(() =>
  tabs.map((item) => ({ ...item, label: t(item.en, item.ru) })),
)
const periodButtons = computed(() =>
  periodPresets.map((item) => ({
    value: item.key,
    label: t(item.en, item.ru),
    disabled: loading.value || offline.value,
  })),
)
function dimensionOptions(key) {
  const labels = { pipeline: 'pipelines', owner: 'owners', source: 'sources' }
  return [
    { value: '', label: t('All available', 'Все доступные') },
    ...(report.value?.options[key] || []).map((value) => ({
      value,
      label: key === 'source' ? value : label(labels[key], value),
    })),
  ]
}
const trendColumns = computed(() => [
  { key: 'date', label: t('Date', 'Дата'), width: 'minmax(110px, 1.3fr)' },
  { key: 'new_leads', label: t('New leads', 'Новые лиды'), numeric: true },
  { key: 'new_deals', label: t('New deals', 'Новые сделки'), numeric: true },
  { key: 'won_count', label: t('Wins', 'Победы'), numeric: true },
  { key: 'won_value', label: t('Won value', 'Сумма побед'), numeric: true },
])
const groupColumns = computed(() => [
  {
    key: 'key',
    label: t('Source', 'Источник'),
  },
  { key: 'count', label: t('Wins', 'Победы'), numeric: true },
  {
    key: 'value',
    label: t('Won value', 'Сумма побед'),
    numeric: true,
    width: 'minmax(160px, 1.5fr)',
  },
  { key: 'action', label: t('Records', 'Карточки'), width: '100px' },
])
const cohortColumns = computed(() => [
  { key: 'key', label: t('Source', 'Источник') },
  { key: 'leads', label: t('Leads', 'Лиды'), numeric: true },
  { key: 'converted', label: t('Converted', 'В сделки'), numeric: true },
  { key: 'won', label: t('Won', 'Победы'), numeric: true },
])
const savedColumns = computed(() => [
  { key: 'label', label: t('Owner', 'Ответственный') },
  { key: 'before', label: t('Saved', 'Сохранено'), numeric: true },
  { key: 'after', label: t('Current', 'Сейчас'), numeric: true },
])
const savedForecastCategoryColumns = computed(() => [
  { key: 'key', label: t('Category', 'Категория') },
  { key: 'weighted', label: t('Forecast', 'Прогноз'), numeric: true },
  { key: 'actual', label: t('Actual wins', 'Сумма побед'), numeric: true },
  { key: 'difference', label: t('Difference', 'Разница'), numeric: true },
])
const chartAvailable = computed(() =>
  (report.value?.trend || []).every(
    (day) =>
      day.won_value != null &&
      Number.isFinite(Number(day.won_value)) &&
      Number.isSafeInteger(Math.trunc(Number(day.won_value))),
  ),
)
const trendChart = computed(() => ({
  title: '',
  data: (report.value?.trend || []).map((day) => ({
    date: day.date.slice(5),
    won_value: Number(day.won_value),
  })),
  xAxis: {
    key: 'date',
    type: 'category',
    echartOptions: { axisLabel: { color: 'var(--ink-gray-6)' } },
  },
  yAxis: {
    title: report.value?.context.currency,
    echartOptions: { axisLabel: { color: 'var(--ink-gray-6)' } },
  },
  series: [
    {
      name: 'won_value',
      type: 'bar',
      color: 'var(--surface-blue-7)',
      echartOptions: {
        barMaxWidth: 22,
        itemStyle: { borderRadius: [3, 3, 0, 0] },
      },
    },
  ],
  echartOptions: {
    animation: !window.matchMedia('(prefers-reduced-motion: reduce)').matches,
    animationDuration: 220,
    grid: { top: 26, left: 60, right: 14, bottom: 28, containLabel: false },
    legend: { show: false },
    tooltip: {
      renderMode: 'richText',
      formatter: (params) => {
        const point = Array.isArray(params) ? params[0] : params
        const day = report.value?.trend[point.dataIndex]
        return day
          ? `${day.date}\n${t('Won value', 'Сумма побед')}: ${format(day.won_value)} ${report.value.context.currency}`
          : ''
      },
    },
  },
}))
</script>

<style scoped>
.analytics-shell {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-width: 0;
  --a-border: var(--outline-gray-2);
  --a-muted: var(--ink-gray-6);
}
.analytics-main {
  flex: 1;
  min-width: 0;
  overflow: auto;
  padding: 20px 24px;
  background: var(--surface-gray-1);
  scrollbar-gutter: stable;
}
.a-intro {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}
.a-intro h2 {
  font-size: 20px;
  line-height: 1.4;
  font-weight: 600;
  letter-spacing: -0.02em;
}
.analytics-main p {
  color: var(--ink-gray-7);
  font-size: 13px;
  line-height: 1.6;
  margin: 6px 0;
}
.a-intro p {
  margin: 3px 0 0;
}
.a-freshness {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
  font-size: 12px !important;
  color: var(--ink-gray-6) !important;
}
.a-filter-card,
.a-panel {
  background: var(--surface-cards, var(--surface-gray-1));
  border-color: var(--outline-gray-2);
  padding: 16px;
  min-width: 0;
}
.a-filter-card :deep(> div:first-child) {
  display: none;
}
.a-filter-card :deep(> div:last-child) {
  margin-top: 0;
  overflow: visible;
}
.a-filter-toolbar {
  flex-wrap: wrap;
  display: flex;
  gap: 12px;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0;
}
.a-filters {
  margin-top: 12px;
  display: grid;
  grid-template-columns:
    repeat(2, minmax(125px, 0.8fr)) repeat(3, minmax(140px, 1fr))
    auto;
  align-items: end;
  gap: 12px;
}
.a-filters > * {
  min-width: 0;
}
.a-context {
  font-size: 12px;
  color: var(--ink-gray-6);
  margin: 10px 0 8px;
}
.a-context summary {
  cursor: pointer;
  padding: 4px 0;
}
.a-context summary span {
  margin-left: 12px;
  font-variant-numeric: tabular-nums;
}
.a-tabs {
  min-width: 0;
  overflow: visible;
  flex: none;
}
.a-tabs :deep(> [role='tablist']) {
  padding: 0;
  gap: 16px;
  margin-bottom: 16px;
  border-color: var(--outline-gray-2);
}
.a-tabs :deep(> [role='tabpanel']) {
  overflow: visible;
}
.a-tab-trigger {
  height: 40px;
  padding: 0 2px;
  border-radius: 0;
  flex-shrink: 0;
}
.a-tab-trigger :deep(> span) {
  display: inline-flex;
  align-items: center;
}
.a-tab-trigger[data-state='active'] {
  color: var(--ink-gray-9);
  font-weight: 600;
}
.a-kpi {
  height: auto;
  justify-content: flex-start;
  text-align: start;
  padding: 10px 12px;
  min-width: 0;
}
.a-kpi span {
  font-size: 12px;
  color: var(--ink-gray-7);
}
.a-kpi strong {
  font-size: 22px;
  font-weight: 600;
  line-height: 1.35;
  color: var(--ink-gray-9);
  font-variant-numeric: tabular-nums;
}
.a-kpi small {
  font-size: 11px;
  line-height: 1.5;
  color: var(--ink-gray-6);
}
em {
  color: var(--ink-amber-9);
  font-style: normal;
  font-size: 12px;
  line-height: 1.5;
}
.a-overview {
  display: grid;
  grid-template-columns: minmax(0, 1.25fr) minmax(0, 1fr);
  gap: 16px;
}
.a-panel :deep(> div:first-child) {
  align-items: center;
  gap: 12px;
}
.a-panel :deep(> div:first-child h2) {
  font-size: 15px;
  line-height: 1.5;
  font-weight: 600;
}
.a-panel :deep(> div:last-child) {
  margin-top: 10px;
  overflow: visible;
}
.a-panel h4,
.a-panel h5 {
  font-size: 14px;
  line-height: 1.5;
  font-weight: 600;
  margin: 18px 0 6px;
}
.a-panel p {
  font-size: 12px;
}
.a-panel details summary {
  cursor: pointer;
  font-size: 12px;
  color: var(--ink-gray-7);
  padding: 8px 0;
}
.a-trend-chart {
  height: 240px;
  min-width: 0;
  margin: 12px 0;
}
.a-open-value {
  padding: 8px 0;
  font-size: 28px;
  font-weight: 600;
  line-height: 1.4;
  letter-spacing: -0.025em;
  font-variant-numeric: tabular-nums;
  overflow-wrap: anywhere;
}
.a-open-value small {
  font-size: 12px;
  color: var(--ink-gray-6);
  letter-spacing: 0;
  font-weight: 400;
}
.a-stage-list > button {
  width: 100%;
  height: auto;
  min-height: 44px;
  padding: 10px 0;
  border-bottom: 1px solid var(--outline-gray-1);
  border-radius: 0;
}
.a-stage-list > button :deep(> span) {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  white-space: normal;
  text-align: left;
}
.a-stage-list small {
  display: block;
  font-size: 11px;
  color: var(--ink-gray-6);
  margin-top: 3px;
}
.a-stage-list strong {
  font-weight: 500;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.a-attention-list {
  max-height: 360px;
  overflow-y: auto;
}
.a-attention-list article {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  padding: 12px 0;
  border-bottom: 1px solid var(--outline-gray-1);
}
.a-attention-list a,
.a-detail-records a {
  font-size: 13px;
  font-weight: 500;
  color: var(--ink-gray-9);
  text-decoration: underline;
  text-underline-offset: 3px;
  overflow-wrap: anywhere;
}
.a-attention-list p {
  font-size: 11px;
}
.a-attention-list strong {
  white-space: nowrap;
  font-size: 12px;
  font-weight: 500;
  font-variant-numeric: tabular-nums;
}
.a-summary ul {
  display: grid;
  gap: 4px;
  margin-top: 8px;
}
.a-summary li {
  font-size: 13px;
  line-height: 1.7;
}
.a-summary .a-inline {
  height: auto;
  white-space: normal;
  justify-content: flex-start;
  padding: 4px 0;
  text-align: left;
}
.a-summary .a-inline :deep(> span) {
  white-space: normal;
}
.a-summary-limit {
  color: var(--ink-gray-6);
  font-size: 12px;
}
.a-summary-reasons,
.a-summary-contribution {
  margin-top: 14px;
}
.a-cohort {
  grid-column: 1/-1;
}
.a-cohort-values {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
  margin: 16px 0;
}
.a-cohort-values > div {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px 16px;
  border-radius: 6px;
  background: var(--surface-gray-2);
}
.a-cohort-values strong {
  font-size: 24px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.a-cohort-values span {
  font-size: 12px;
  color: var(--ink-gray-7);
}
.a-visit-list > div {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 10px 0;
  border-bottom: 1px solid var(--outline-gray-1);
  font-size: 13px;
}
.a-visit-list dt {
  overflow-wrap: anywhere;
}
.a-visit-list dd {
  flex-shrink: 0;
  font-variant-numeric: tabular-nums;
}
.a-table-wrap {
  margin-top: 14px;
}
.a-horizon {
  display: flex;
  flex-wrap: wrap;
  align-items: end;
  gap: 12px;
  max-width: 720px;
  margin: 16px 0;
}
.a-horizon > div {
  flex: 1;
  min-width: 180px;
}
.a-warning {
  color: var(--ink-amber-9) !important;
}
.a-import-coverage {
  padding: 12px;
  margin: 12px 0;
  border: 1px solid var(--outline-gray-2);
  border-radius: 6px;
}
.a-import-coverage h4 {
  margin-top: 0;
}

.a-saved-list li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 10px 0;
  border-bottom: 1px solid var(--outline-gray-1);
}
.a-saved-list button {
  white-space: normal;
  height: auto;
  text-align: left;
}
.a-saved-list button :deep(> span) {
  white-space: normal;
}
.a-saved-list small {
  color: var(--ink-gray-6);
  font-size: 12px;
}
.a-saved-comparison {
  margin-top: 16px;
  padding-top: 8px;
  border-top: 1px solid var(--outline-gray-2);
}
.a-saved-outcome {
  margin-top: 16px;
  padding-top: 8px;
  border-top: 1px solid var(--outline-gray-2);
}
.a-footer {
  margin-top: 16px !important;
  font-size: 11px !important;
  color: var(--ink-gray-6) !important;
}
.a-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 48px 12px;
  font-size: 13px;
  color: var(--ink-gray-6);
}
.a-dialog {
  max-height: calc(100dvh - 220px);
  overflow-y: auto;
  color: var(--ink-gray-9);
}
.a-dialog > p {
  color: var(--ink-gray-7);
  font-size: 13px;
  line-height: 1.6;
  margin: 10px 0;
}
.a-detail-records article {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 6px 12px;
  padding: 12px 0;
  border-bottom: 1px solid var(--outline-gray-2);
  font-size: 13px;
}
.a-detail-records small {
  grid-column: 1/-1;
  color: var(--ink-gray-6);
  overflow-wrap: anywhere;
}
.a-pagination {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  margin-top: 16px;
  font-size: 12px;
}
:global([data-theme='dark'] .analytics-shell) {
  color-scheme: dark;
}
@media (max-width: 1200px) {
  .a-filters {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
  .a-kpi {
    padding: 10px;
  }
  .a-overview {
    gap: 12px;
  }
  .a-cohort-values {
    gap: 8px;
  }
  .a-cohort-values > div {
    padding: 10px;
  }
  .a-cohort-values span {
    font-size: 11px;
  }
  .a-visit-list > div {
    align-items: flex-start;
    flex-direction: column;
    gap: 4px;
  }
  .a-attention-list article {
    flex-direction: column;
    gap: 4px;
  }
  .a-horizon > div {
    min-width: 0;
    flex-basis: 100%;
  }
  .a-horizon > button {
    min-height: 40px;
  }

  .a-saved-list li {
    align-items: flex-start;
    flex-direction: column;
    gap: 4px;
  }
  .a-pagination {
    flex-wrap: wrap;
  }
}
@media (prefers-reduced-motion: reduce) {
  .analytics-shell :deep(*) {
    transition-duration: 0s !important;
    animation-duration: 0s !important;
  }
}
/* Labels remain native controls, with the readable text token in both themes. */
.a-filters :deep(label),
.a-horizon :deep(label) {
  color: var(--ink-gray-6);
}
/* Scope this viewport fit to analytics; other CRM dialogs are untouched. */
:global(.dialog-content:has(.a-dialog)) {
  margin: 0;
  max-height: calc(100dvh - 32px);
  overflow-y: auto;
}

.a-overview-metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  margin-bottom: 12px;
}
.a-overview-metrics > button {
  min-height: 82px;
  border: 1px solid var(--outline-gray-2);
  background: var(--surface-cards, var(--surface-gray-1));
}
.a-overview-metrics > button:hover {
  background: var(--surface-gray-2);
}
.a-overview-metrics :deep(button > span) {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  flex-direction: column;
  gap: 3px;
  white-space: normal;
}
.a-deal-metrics {
  grid-column: 1/-1;
  margin-bottom: 0;
}
.a-summary-trigger {
  grid-column: 1/-1;
}
#analytics-quality {
  margin-top: 12px;
}
@media (max-width: 760px) {
  .analytics-main {
    padding: 12px;
  }
  .a-overview {
    grid-template-columns: minmax(0, 1fr);
  }
  .a-filters {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .a-filter-card,
  .a-panel {
    padding: 12px;
  }
  .a-context {
    margin-bottom: 4px;
  }
  .a-tabs :deep(> [role='tablist']) {
    gap: 4px;
    justify-content: space-between;
  }
  .a-tab-trigger {
    min-width: 0;
    flex: 1 1 auto;
    height: 48px;
  }
  .a-tab-trigger :deep(> span) {
    white-space: normal;
    line-height: 1.15;
    text-align: center;
  }
}
@media (max-width: 440px) {
  .a-tabs :deep(> [role='tablist']) {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
  .a-tabs :deep(> [role='tablist'] > *) {
    min-width: 0;
  }
  .a-tab-trigger {
    width: 100%;
    height: 34px;
  }
}
@media (max-width: 760px) {
  .a-layout-link {
    padding-inline: 0;
    width: 28px;
  }
  .a-layout-link :deep(> .truncate) {
    display: none;
  }
}
@media (max-width: 600px) {
  .a-intro {
    flex-wrap: wrap;
    gap: 2px 12px;
    margin-bottom: 10px;
  }
  .a-overview-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .a-overview-metrics:not(.a-deal-metrics) > button:first-child {
    grid-column: 1/-1;
  }
  .a-kpi strong {
    overflow-wrap: anywhere;
  }
}
</style>
