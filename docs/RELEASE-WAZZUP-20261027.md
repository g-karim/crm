# CRM #17 / CRM Messenger #16 — выпуск 27.10.2026

Выпуск выполнен на production. Режим обслуживания снят **27.10.2026 в 14:08 МСК**.
Все 20 сайтов общего runtime отвечают; сервисы и очереди возобновлены.

## Выпущенные версии

- [CRM #17](https://github.com/g-karim/crm/pull/17):
  `c118d135aa78b1682aa4e8b154bfc82552351c5b`.
- [CRM Messenger #16](https://github.com/g-karim/crm_messenger/pull/16):
  `5adb412d275485e360beaf764c98bfff30484d32`.
- Оба PR остаются открытыми, merge не выполнялся. Развёрнуты именно проверенные
  версии из этих PR с сохранением существующих production-доработок.

Production использует экспортированные source trees без Git metadata:
`/home/frappe/deployments/exp-unified-prod-20261023/source/apps` на `200.169.176.193`.
Frappe остаётся 16.51.0. Изменены только source CRM/Messenger, необходимая схема
Messenger, его патчи/расписание и скомпилированный русский каталог CRM.

## CI и исправления

Все четыре workflow завершились успешно на CRM head `c118d135…`:

| Проверка | Run |
|---|---|
| Frontend | [40489106152](https://github.com/g-karim/crm/actions/runs/40489106152) |
| Linters | [40489106137](https://github.com/g-karim/crm/actions/runs/40489106137) |
| Migration | [40489106740](https://github.com/g-karim/crm/actions/runs/40489106740) |
| Server: CRM + точный Messenger SHA | [40489106154](https://github.com/g-karim/crm/actions/runs/40489106154) |

Messenger не имеет собственного workflow: его проверки выполняет общий Server
workflow CRM с закреплённым head Messenger. В актуальном прогоне выполнены 791 тест
CRM и 1906 тестов Messenger; в Messenger 11 проверок отдельных окружений штатно
пропускаются в GitHub CI. Локально 1906 Messenger tests прошли на Frappe 16.53 и
16.51; сценарий с выключенной интеграцией проверен отдельно.

Основные исправления:

- История лидов/сделок сохраняет каждое доступное изменение Version, включая
  изменения после скрытого или исключённого поля. Ограничения permlevel сохранены.
- Служебные Account, Sync Clock и Avito Tombstone после установки/миграции
  сохраняют пустые клиентские permissions: Frappe 16.53 перестал незаметно
  добавлять к ним System Manager CRUD grants.
- Fixtures не зависят от включённого Messenger, прежних read flags или удалённого
  module alias Frappe. Исправлена гонка незакоммиченных прав и общего Meta cache.
  Отдельный процесс воспроизводит 2 failures до исправления и 5/5 после.
- Ручные CI сравнивают изменения с базой PR; migration проверяет base → head.
  Имена fixture-сайтов совместимы с проверкой host, оба workflow закрепляют новый
  Messenger SHA. Проверки не превращались в unconditional success.

## Сохранение производственных доработок

Кандидат объединяет PR delta и существующий production source. Объединены
Settings.vue, translations.py и ru.po; сохранены доработки форм, уведомлений,
воронок и Touch Tracking. Файлы вне PR сохранены по контрольным суммам.

Кандидат проверен: **1108 frontend tests / 68 файлов**, production build,
8 translation tests. Генерируемые component declarations дополнены тремя новыми
компонентами. Старые hashed chunks оставлены для уже открытых вкладок CRM.

## Резервные копии и репетиция

Журнал выпуска на сервере:
`/home/frappe/deployments/exp-unified-prod-20261023/operations/crm-pr17-20261027`.

До изменений сохранены source, настройки 10 сайтов и общий config; созданы
проверенные gzip/SHA256 резервные копии четырёх БД Messenger. Непосредственно
перед публикацией, после остановки записи, сняты свежие T0-копии этих БД.

На копиях exp-verse.com и vatan.industries проверены восстановление и миграция:
отдельный Redis через Unix socket, временные DB users, PrivateNetwork и отсутствие
исходящих provider-операций. Все временные БД и DB users удалены, временные bench
с конфигурациями очищены; агрегированные отчёты сохранены.

Полная stock-миграция на копии перезаписывала tabHas Role. Чтобы не выпускать
изменения остальных приложений общего сайта, production-миграция ограничена
Messenger через штатные Frappe API: sync_for, все pending pre/post patches,
fixtures/customizations, собственные after_migrate hooks и добавление/обновление
собственных заданий. Чужое расписание и чужие migration hooks не изменялись.
Пропуска ошибочных патчей нет.

В обеих успешных репетициях и на всех четырёх рабочих сайтах выполнены оба новых
патча и зарегистрированы 17 методов расписания Messenger. Строгие before/after
хеши защищённых таблиц совпали: роли, пользователи, клиенты, лиды/сделки, задачи,
уведомления, каналы, переписки, сообщения и сохранённые credentials не изменились.
В vatan.industries сохранён прежний Telegram-канал.

Откат подготовлен и проверен восстановлением копий. После возврата публичного
трафика скрипт запрещает откат БД к T0, чтобы не потерять новые пользовательские
записи; дальнейшее восстановление требует нового согласованного плана.

## Проверки после публикации

- 20/20 сайтов: HTTP 200 и pong во внутреннем runtime.
- exp-verse.com и vatan.industries: публичный HTTPS ping успешен.
- Все 30 JS/CSS из нового entry доступны и побайтно совпадают с проверенной сборкой.
- CRM ожидаемо возвращает Guest HTTP 403 с переходом на страницу входа.
  В браузере страница входа доступна, ошибок JavaScript не обнаружено.
- Чтение настроек под существующим g.karim проверено в native runtime; затем
  admin-safe settings проверены на четырёх сайтах Messenger.
- Все исходные site/common configs восстановлены, source совпадает с manifest.
  Сервисы active, очередь не приостановлена; активные задания выполняются.
- На четырёх сайтах Messenger нет новых Error Log за последние 10 минут проверки.

Вход в браузере под пользователем и реальные подключения/отправки Wazzup не
выполнялись. Новые API-ключи, оплачиваемый AI и тестовые сообщения клиентам
в проверку не входили.

## Подтверждения

Локальные агрегированные receipts:
`/Users/g-karim/frappe/crm-pr-review-20261027/release/production-receipts/`.
CI gate: `release/ci-gate.json`; публичная проверка: `release/public-acceptance.json`;
сохранение source: `release/candidate-preservation.json`.
Резервные копии данных остались только в закрытом каталоге на сервере.

[Задача EXP Celio TASK-2026-00096](https://exp-verse.com/celio/tasks/TASK-2026-00096),
[проект Wazzup](https://exp-verse.com/celio/projects/PROJ-0015).

Задача TASK-2026-00096 завершена штатным workflow EXP Celio: Completed,
27.10.2026 14:23 МСК. Копии отчётов, резервные копии и исходные доработки сохранены.
