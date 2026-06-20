# План переноса CRM-изменений из exp_theme в форк crm

Дата: 2026-06-19

Цель: все CRM-изменения, которые раньше делались внешним runtime-слоем `exp_theme`, перенести в наш форк `crm` нативно: через компоненты, настройки, хуки, миграции и нормальные точки расширения. Исключение: общий словарь русских переводов остается в обязательном приложении `exp_theme`, потому что он нужен сразу нескольким приложениям и удобнее поддерживается централизованно.

После переноса `exp_theme` не должен патчить `/crm`, менять DOM через `MutationObserver`, записывать `FCRM Settings` или подменять CRM-логотипы. Но `exp_theme` может продолжать хранить общий словарь переводов и применять его через стандартный механизм `Translation`.

Главный принцип: не повторять старый runtime-патч. То, что раньше делалось через поиск текста, скрытие DOM-элементов и замену картинок после рендера, надо сделать в исходных местах CRM.

## Граница задачи

Переносим в форк `crm` только то, что относится к Frappe CRM и маршруту `/crm`.

Оставляем вне этой задачи общий слой `exp_theme`: домашнюю страницу `/home`, общий Desk theme, общий favicon Desk, нижние кнопки сайдбара Desk, переименование ERPNext/HR/Framework в обычном Desk, глобальную настройку языков, системные настройки Frappe/ERPNext и общий словарь переводов.

## Изменение 1. Название приложения CRM

Статус: ✅ Сделано в `339ed8c8 feat: centralize EXP CRM branding defaults`.

Что было в `exp_theme`: `crm_bootstrap.js` принудительно ставил `document.title = "EXP CRM"` и заменял видимый текст `Frappe CRM` на `EXP CRM`.

Как сделать в форке `crm`: завести единый источник бренда в самом CRM, например константы `EXP_CRM_APP_NAME = "EXP CRM"` и использовать их там, где CRM формирует title, sidebar, about modal, invitation email и fallback brand.

Где смотреть: `crm/__init__.py`, `crm/www/crm.py`, `frontend/index.html`, `frontend/src/components/Layouts/AppSidebar.vue`, `frontend/src/components/Modals/AboutModal.vue`.

Важно: не делать глобальную замену всех текстовых узлов. Менять только конкретные места, где CRM сама показывает имя приложения.

Проверка: при загрузке `/crm` нигде не появляется `Frappe CRM`, включая title вкладки браузера, sidebar и about modal.

## Изменение 2. Favicon и apple-touch-icon CRM

Статус: ✅ Сделано в `339ed8c8 feat: centralize EXP CRM branding defaults`.

Что было в `exp_theme`: `crm_bootstrap.js` после загрузки страницы заменял `link[rel="icon"]`, `shortcut icon` и `apple-touch-icon` на `/assets/exp_theme/img/exp-favicon.png`.

Как сделать в форке `crm`: прописать favicon нативно в шаблоне CRM и fallback-настройках бренда. Если пользователь явно настроил favicon в `FCRM Settings`, использовать его. Если нет, использовать наш стандартный EXP favicon из assets CRM.

Где смотреть: `crm/www/crm.py`, `crm/www/crm.html`, `frontend/index.html`, store/settings для brand.

Важно: asset должен жить в `apps/crm/crm/public/...`, а не ссылаться на `exp_theme`.

Проверка: при первом HTML-ответе `/crm` favicon уже правильный, без мигания старой иконки.

## Изменение 3. Логотип CRM

Статус: ✅ Сделано в `339ed8c8 feat: centralize EXP CRM branding defaults`.

Что было в `exp_theme`: картинки из `/assets/crm/manifest/` и `/assets/crm/images/` на лету заменялись на EXP favicon.

Как сделать в форке `crm`: заменить дефолтный `CRMLogo` и fallback brand logo внутри CRM. При этом `FCRM Settings.brand_logo` должен иметь приоритет, чтобы клиент мог поставить свой логотип.

Где смотреть: `frontend/src/components/Icons/CRMLogo.vue`, `frontend/src/components/Layouts/AppSidebar.vue`, настройки brand store, `crm/fcrm/doctype/fcrm_settings`.

Важно: дефолтный логотип должен быть нашим, но кастомный клиентский логотип нельзя перетирать миграцией.

Проверка: новый сайт без кастомного бренда показывает EXP CRM логотип; сайт с кастомным `brand_logo` показывает кастомный логотип.

## Изменение 4. Desktop Icon для CRM

Статус: ✅ Сделано в `339ed8c8 feat: centralize EXP CRM branding defaults`.

Что было в `exp_theme`: `setup.py` менял `Desktop Icon` с именем `Frappe CRM`: label на `EXP CRM`, `app = crm`, `hidden = 0`, `icon_type = App`, `logo_url = /assets/exp_theme/img/exp-favicon.png`.

Как сделать в форке `crm`: источник Desktop Icon должен задаваться самим CRM-приложением: workspace json, install/migrate patch или hook CRM. Label и logo_url должны ссылаться на asset из CRM.

Где смотреть: `crm/fcrm/workspace/frappe_crm/frappe_crm.json`, `crm/hooks.py`, install/patches CRM.

Важно: не ссылаться на `/assets/exp_theme/...`. Для существующих сайтов сделать idempotent patch, который обновляет только дефолтный старый `Frappe CRM`, но не ломает ручные пользовательские изменения.

Проверка: в Desk список приложений показывает `EXP CRM` с нашим логотипом без участия `exp_theme`.

## Изменение 5. Dropdown menu пользователя в CRM

Статус: ✅ Сделано в `28db96de feat: customize CRM dropdown menu`.

Что было в `exp_theme`: из `FCRM Settings.dropdown_items` удалялись `app_selector`, `about`, `login_to_fc`; добавлялся пункт `Рабочий стол` с route `/home` и icon `home` перед `settings`.

Как сделать в форке `crm`: изменить стандартные `standard_dropdown_items` в `crm/hooks.py` и добавить patch для существующих сайтов.

Где смотреть: `crm/hooks.py`, `crm/install.py`, `FCRM Settings`, `CRM Dropdown Item`.

Правило миграции: удалить только стандартные пункты `app_selector`, `about`, `login_to_fc`; добавить `exp_desktop` или `desktop_home`; сохранить пользовательские пункты, которые админ добавил вручную.

Проверка: в CRM dropdown есть `Рабочий стол`, `Settings`, separator, `Log out`; нет Apps, About и Login to Frappe Cloud.

## Изменение 6. Переход на рабочий стол из CRM

Статус: ✅ Сделано в `28db96de feat: customize CRM dropdown menu`.

Что было в `exp_theme`: пункт `Рабочий стол` вел на `/home`.

Как сделать в форке `crm`: добавить пункт в CRM dropdown нативно. Если `/home` не существует на сайте, пункт можно скрывать или вести на `/app`, но для наших сайтов основной route должен быть `/home`.

Где смотреть: `crm/hooks.py`, frontend dropdown rendering.

Важно: route `/home` относится к нашему общему Desk/Home слою, поэтому в CRM-форке лучше сделать это настройкой или константой, чтобы при необходимости отключить.

Проверка: клик по пункту из CRM сразу уводит на `/home`.

## Изменение 7. Onboarding CRM

Статус: ✅ Сделано в `50773d4d feat: remove CRM help sidebar entry`.

Что было в `exp_theme`: `crm_bootstrap.js` писал в localStorage `isOnboardingStepsCompletedfrappecrm + user = true`.

Как сделать в форке `crm`: убрать необходимость runtime localStorage-патча. Варианты: отключить onboarding компонент по умолчанию для нашего форка.

Где смотреть: frontend onboarding components/stores, hooks after_install/after_migrate.

Проверка: новый пользователь открывает `/crm` и не видит onboarding steps.

## Изменение 8. Sales hierarchy / permission banner

Статус: ✅ Сделано. Sidebar больше не подключает `SalesHierarchyBanner`, а boot context больше не отдает `show_sales_hierarchy_banner`.

Что было в `exp_theme`: `crm_bootstrap.js` выставлял `window.show_sales_hierarchy_banner = false`.

Как сделать в форке `crm`: убрать показ баннера в самом компоненте.

Где смотреть: `frontend/src/components/SalesHierarchyBanner.vue` и места его подключения.

Проверка: баннер не появляется на страницах лидов/сделок, если он отключен настройкой нашего форка.

## Изменение 9. Скрытие Brand settings

Статус: ✅ Сделано. Пункт `Brand` удален из навигации CRM Settings; при старом сохраненном выборе настройка откатывается на первый доступный раздел.

Что было в `exp_theme`: runtime скрипт искал элементы настроек с текстом `Brand`, `Brand Settings`, `Бренд`, `Настройки бренда` и скрывал их через `display: none`.

Как сделать в форке `crm`: убрать Brand settings из массива/конфига CRM settings navigation или сделать флаг `hidden`. Доступ к brand settings должен быть только через desk в frappe crm settings

Где смотреть: компоненты CRM Settings, router settings pages, `frontend/src/components/Settings`.

Важно: не скрывать DOM по тексту. Страница не должна попадать в навигацию с самого начала.

Проверка: Brand settings не видны в списке настроек; direct URL не открывает пустую или поломанную страницу.

## Изменение 10. Скрытие Telephony settings

Статус: ✅ Сделано. Пункт `Telephony` удален из навигации CRM Settings; компонент телефонии больше не подключается в списке настроек.

Что было в `exp_theme`: runtime скрипт скрывал `Telephony`, `Telephony Settings`, `Телефония`, `Настройки телефонии`.

Как сделать в форке `crm`: аналогично Brand settings, убрать Telephony из navigation config.

Где смотреть: settings navigation, telephony settings components.

Проверка: пункт телефонии не виден; прямое открытие route корректно перенаправляет.

## Изменение 11. Fallback при открытии скрытой страницы настроек

Статус: ✅ Сделано. Settings modal теперь выбирает fallback-раздел, если активная страница скрыта, удалена или недоступна текущему пользователю.

Что было в `exp_theme`: если пользователь оказался на скрытой странице, скрипт пытался кликнуть `General`, `Общие`, `Calendar`, `Календарь`.

Как сделать в форке `crm`: добавить route guard или computed redirect в settings router. Если route скрыт/недоступен, редиректить на `General` или первую доступную страницу.

Где смотреть: CRM settings router/layout.

Проверка: `/crm/settings/brand` и `/crm/settings/telephony` не оставляют пользователя на пустом экране.

## Изменение 12. ERPNext -> EXP ERP внутри CRM

Статус: ✅ Сделано. Пользовательские тексты интеграции переименованы в `EXP ERP`, а технические имена DocType, fieldname, API и Python-классов оставлены стабильными.

Что было в `exp_theme`: runtime скрипт заменял видимый текст `ERPNext` на `EXP ERP` внутри `/crm`.

Как сделать в форке `crm`: заменить только CRM-места, где речь про ERPNext integration в нашем продукте. Например заголовки, подписи и тексты в `ERPNextSettings`.

Где смотреть: `frontend/src/components/Settings/ERPNextSettings.vue`, backend messages в `crm/fcrm/doctype/erpnext_crm_settings`.

Важно: не делать глобальную замену `ERPNext` в CRM, потому часть технических названий может быть названием интеграции или DocType. Текст для пользователя можно брендировать, технические ключи лучше оставить стабильными.

Проверка: пользовательские тексты показывают `EXP ERP`; технические route/docname не ломаются.

## Изменение 13. Скрытие ссылок на документацию ERPNext CRM

Что было в `exp_theme`: скрывались ссылки `docs.frappe.io/crm/erpnext`.

Как сделать в форке `crm`: убрать эти ссылки из компонента или заменить на нашу документацию, если она появится.

Где смотреть: `ERPNextSettings.vue` и связанные компоненты.

Проверка: на странице интеграции не видно ссылок на внешнюю документацию Frappe, если мы ее не хотим показывать.

## Изменение 14. Иконка EXP ERP в настройках CRM

Что было в `exp_theme`: runtime скрипт находил пункт `EXP ERP` и заменял SVG на `/assets/exp_theme/img/exp-sign-black.png`.

Как сделать в форке `crm`: в компоненте настроек использовать наш asset из `apps/crm/crm/public/...` или icon component. Иконка должна быть задана прямо в данных пункта меню.

Где смотреть: `ERPNextSettings.vue`, settings navigation item config.

Проверка: в CRM settings у EXP ERP правильная иконка без DOM-подмен.

## Изменение 15. Русские переводы CRM

Что было в `exp_theme`: переводы для CRM добавлялись в общий словарь `exp_theme/translations.py`, а затем записывались в `tabTranslation` стандартным setup-кодом `exp_theme`.

Как сделать правильно: оставить русские переводы CRM в `exp_theme/translations.py`. Для нас `exp_theme` является обязательным общим языковым слоем, поэтому удобно, чтобы один словарь закрывал CRM, ERPNext, Desk и общие UI-строки.

Что нужно перенести в форк `crm`: не сами русские формулировки, а поддержку переводимости в местах, где CRM сейчас показывает английский напрямую:

- frontend-тексты должны проходить через `__()`;
- labels, options, dropdown items, tooltip и empty states должны проходить через `__()`;
- placeholder'ы должны генерироваться как переводимые строки;
- даты, месяцы, дни недели и time picker должны использовать системную локаль/формат;
- hardcoded English нужно заменить на переводимые ключи.

Где смотреть: `frontend/src/utils/staticTranslations.js`, компоненты CRM с hardcoded English, `FieldLayout/Field.vue`, `Activities.vue`, event/call/task/note modals, filters, kanban settings, sales pipeline settings.

Важно: CRM-форк должен быть переводимым сам по себе, но централизованный русский словарь остается в `exp_theme/translations.py`. Не надо возвращаться к runtime DOM-патчам ради переводов.

Проверка: при русском языке CRM не показывает английский в основных сценариях: сделки, лиды, контакты, события, звонки, задачи, вложения, настройки воронок. Если строка добавлена в словарь `exp_theme`, она должна реально применяться в CRM.

## Изменение 16. Empty states вкладок сделки

Что было в `exp_theme`: переводились строки вроде `No Emails Found`, `No Comments Found`, `No Call History`, `No Tasks Found`, `No Attachments Found`.

Как сделать в форке `crm`: в компонентах empty state передавать `emptyText` и `emptyTextDescription` через `__()`, а русские формулировки держать в общем словаре `exp_theme/translations.py`.

Где смотреть: `Activities.vue`, компоненты tabs/empty states.

Проверка: вкладки Письма, Комментарии, Звонки, Задачи, Вложения полностью на русском.

## Изменение 17. Текст активности сделки

Что было в `exp_theme`: переводились куски вроде `created this deal`.

Как сделать в форке `crm`: место формирования activity log должно отдавать переводимую строку или ключ действия. Во frontend строка должна проходить через `__()`.

Где смотреть: activity/timeline компоненты и backend activity generation.

Проверка: `Administrator created this deal` не содержит английский action text.

## Изменение 18. Модалка события

Что было в `exp_theme`: переводились `Create an Event`, `Add Attendee`, `Private or Public`, `Add Location`, `Add Description`, `Add Notification`, цвета, `Today`, месяцы/дни недели, варианты уведомлений.

Как сделать в форке `crm`: все labels/placeholders/options в Event modal пропускать через `__()`. Даты форматировать системным форматом. Time picker использовать в 24-часовом режиме для русского интерфейса.

Где смотреть: `EventModal.vue`, `CalendarEventPanel.vue`, date/time utils.

Проверка: модалка события без английского, дата числовая или локализованная, время без `am/pm`.

## Изменение 19. Модалка звонка

Что было в `exp_theme`: переводились `Create Call Log`, `From Number`, `To Number`, статусы звонка и типы `Incoming/Outgoing`.

Как сделать в форке `crm`: labels/options CRM Call Log должны проходить через `__()`. Если options приходят из DocType, убедиться, что для них есть ключи в общем словаре `exp_theme/translations.py`.

Где смотреть: modal doctype form, `CRM Call Log` DocType, quick entry components.

Проверка: создание записи звонка полностью на русском.

## Изменение 20. Модалки задачи и заметки

Что было в `exp_theme`: переводились `Create Task`, `Create Note`, `Open Deal`, приоритеты `Low/Medium/High`, статусы `Backlog/Todo/In Progress/Done/Canceled`.

Как сделать в форке `crm`: generic doctype modal должен строить заголовок через переводимые шаблоны, а options должны переводиться в UI.

Где смотреть: generic doctype modal, `CRM Task`, `FCRM Note`, field layout components.

Проверка: задачи и заметки без английского, кнопка `Open Deal` переведена.

## Изменение 21. Attach / file uploader

Что было в `exp_theme`: переводились `Attach a File`, `Drag & Drop files here or upload from`, `Device`, `Link`, `Camera`.

Как сделать в форке `crm`: проверить, какие строки приходят из `frappe-ui`, а какие из CRM. Для CRM строк добавить `__()`. Для строк библиотеки добавить wrapper на уровне CRM или общий перевод в `exp_theme/translations.py`, если строка используется несколькими приложениями.

Где смотреть: attachment tab, file uploader usage.

Проверка: модалка прикрепления файла полностью на русском.

## Изменение 22. Placeholder'ы полей

Что было в `exp_theme`: переводы закрывали частные случаи вроде `Add Organization...`, `Add Deal Owner...`, `Select Deal Owner...`.

Как сделать в форке `crm`: исправить генерацию placeholder на уровне CRM:

- для `Link`, `User`, `Dynamic Link` использовать `Select <label>...`;
- для обычных редактируемых полей использовать `Add <label>...` или текущую CRM-логику;
- не перетирать явно заданный `field.placeholder`;
- во frontend не подставлять `field.label` как будто это явный placeholder.

Где смотреть: backend layout resolver `get_field_obj`, `FieldLayout/Field.vue`, `SidePanelLayout.vue`.

Проверка: ссылочные поля показывают `Выбрать владельца сделки...`, а не `Add Deal Owner...`.

## Изменение 23. Фильтры list view

Что было в `exp_theme`: переводились операторы фильтра `Equals`, `Not equals`, `Like`, `In`, `Between`, `Timespan`, `Clear All Filters`.

Как сделать в форке `crm`: операторы должны переводиться там, где формируется dropdown. Лучше использовать отдельные ключи переводов для операторов, чтобы не получать странные переводы вроде `Нравится` для `Like`.

Где смотреть: list view filter components.

Проверка: фильтры читаются естественно: `Равно`, `Не равно`, `Содержит`, `Не содержит`, `В списке`, `Не в списке`, `В диапазоне`, `Период`.

## Изменение 24. Kanban settings

Что было в `exp_theme`: переводилась строка `Kanban settings`.

Как сделать в форке `crm`: убедиться, что tooltip/кнопка пропущены через `__()`, а русский перевод есть в общем словаре `exp_theme/translations.py`.

Где смотреть: kanban toolbar/settings button.

Проверка: tooltip и кнопка настроек канбана на русском.

## Изменение 25. Настройки Sales Pipelines

Что было в `exp_theme`: переводились `Sales Pipelines`, `Pipeline Name`, `Stages`, `Warnings`, `Stage skipping`, `Moving backwards`, `Closing fields`, `Add Stage`, `Save Stages` и тексты ошибок/confirm.

Как сделать в форке `crm`: все строки компонента настроек воронок пропустить через `__()`, а русские переводы держать в общем словаре `exp_theme/translations.py`.

Где смотреть: `frontend/src/components/Settings/SalesPipelines.vue`, backend API ошибок воронок.

Проверка: экран настройки воронок полностью на русском, включая подтверждения архивации и ошибки.

## Изменение 26. Стандартные названия стадий и дефолтной воронки

Что было в `exp_theme`: переводились `Default Deal Pipeline`, `Qualification`, `Demo/Making`, `Proposal/Quotation`, `Negotiation`, `Ready to Close`.

Как сделать в форке `crm`: решить, должны ли стандартные записи реально создаваться сразу на русском или переводиться только в UI. Для русскоязычных сайтов лучше создавать дефолтные CRM pipeline/stage labels на русском через fixtures/patch.

Где смотреть: install/patches CRM sales pipeline setup.

Проверка: новый сайт получает понятные русские стадии без зависимости от `Translation`.

## Изменение 27. Скрытие старого ERPNext CRM

Что было в `exp_theme`: скрывался старый ERPNext workspace/module `CRM` через `Desktop Icon`, `Workspace.is_hidden` и bootinfo-фильтр.

Как сделать в форке `crm`: если мы точно хотим, чтобы при установленном Frappe CRM пользователи не видели старый ERPNext CRM, добавить idempotent patch в CRM app:

- найти ERPNext `Desktop Icon` с `link_to = CRM` или `label = CRM`;
- скрыть его;
- скрыть `Workspace` с `module = CRM`, если это именно ERPNext workspace;
- не скрывать сам Frappe CRM app.

Где смотреть: CRM install/patches. Bootinfo-фильтр лучше не переносить, если достаточно скрыть записи в БД.

Важно: это изменение затрагивает ERPNext Desk, а не `/crm`. Его стоит делать отдельным коммитом и явно проверить, что не пропадают нужные ERPNext документы.

Проверка: в Desk не дублируется старый ERPNext CRM, но `/crm` доступен.

## Изменение 28. Защита пользовательского бренда

Что было в `exp_theme`: setup жестко записывал `brand_name`, `brand_logo`, `favicon` в `FCRM Settings`.

Как сделать в форке `crm`: использовать fallback defaults и миграции, которые не перетирают пользовательские значения. Если поле пустое или равно старому дефолту Frappe, можно заменить на EXP. Если клиент уже поставил свое значение, не трогать.

Где смотреть: settings store, backend `FCRM Settings`, CRM patches.

Проверка: кастомный логотип клиента переживает `bench migrate`.

## Изменение 29. Очистка старых следов exp_theme в существующих БД

Что было в `exp_theme`: в БД могли остаться старые `Translation`, `FCRM Settings`, `Desktop Icon`, `CRM Dropdown Item`.

Как сделать в форке `crm`: отдельный patch cleanup:

- удалить/заменить только CRM-записи, которые точно создавались exp_theme;
- перенести нужные значения в новые CRM defaults;
- очистить `tabTranslation` только для устаревших или дублирующих CRM source_text, если ключи переводов поменялись;
- очистить cache.

Где смотреть: новый patch в `crm/patches`.

Важно: cleanup должен быть безопасным и идемпотентным. Не удалять пользовательские переводы и кастомные dropdown items.

Проверка: повторный запуск patch ничего не ломает.

## Изменение 30. Отказ от MutationObserver-патчей

Что было в `exp_theme`: `crm_bootstrap.js` постоянно наблюдал DOM и повторно применял патчи.

Как сделать в форке `crm`: не переносить `MutationObserver`. Каждое поведение должно жить в своем компоненте, router guard, настройке или backend patch.

Проверка: в CRM нет скрипта, который массово ходит по DOM и заменяет текст/картинки после рендера.

## Изменение 31. Где хранить assets

Что было в `exp_theme`: CRM использовала `/assets/exp_theme/img/exp-favicon.png` и `/assets/exp_theme/img/exp-sign-black.png`.

Как сделать в форке `crm`: скопировать нужные картинки в `apps/crm/crm/public/...` и ссылаться на `/assets/crm/...`.

Проверка: CRM не берет логотипы, favicon, иконки и runtime-патчи из `exp_theme`. Общий словарь переводов может оставаться в обязательном `exp_theme`.

## Изменение 32. Документация и настройка для разработчиков

Что сделать: добавить README/документ в `apps/crm/docs`, где описано:

- какие брендинговые defaults есть в нашем форке;
- какие настройки скрыты;
- как вернуть Brand/Telephony settings, если понадобится;
- как устроены переводы;
- какие patches меняют существующие сайты.

Проверка: новый разработчик может понять поведение CRM без чтения истории `exp_theme`.

## Рекомендуемый порядок работ

1. Сначала перенести assets и единые brand constants.
2. Затем перенести HTML/favicon/title/logo, чтобы убрать мигание старого бренда.
3. Затем сделать dropdown menu и настройки FCRM через `crm/hooks.py` и patches.
4. Затем убрать onboarding и sales hierarchy banner нативно.
5. Затем перенести скрытие Brand/Telephony settings через настройки/router, без DOM-патчей.
6. Затем перенести ERPNext integration polish: EXP ERP тексты, иконка, docs links.
7. Затем сделать экраны переводимыми и сверить ключи в `exp_theme`: сделки, события, звонки, задачи, вложения, фильтры, канбан, воронки.
8. Затем сделать cleanup patch для старых данных exp_theme в БД.
9. В конце удалить/оставить выключенными runtime CRM-части в `exp_theme` и проверить, что CRM работает без них. Словарь переводов в `exp_theme` остается.

## Проверки после переноса

Для кода:

```bash
python3 -m py_compile apps/crm/crm
cd apps/crm/frontend && yarn build
```

Для локальных сайтов:

```bash
bench --site v16.localhost migrate
bench --site crm-pipeline-test.localhost migrate
bench --site v16.localhost clear-cache
bench --site crm-pipeline-test.localhost clear-cache
```

UI-проверки:

- `/crm` открывается без участия `exp_theme`;
- favicon и title сразу `EXP CRM`;
- sidebar и about modal показывают наш бренд;
- dropdown содержит `Рабочий стол`, но не содержит Apps/About/Login to Frappe Cloud;
- Brand/Telephony settings не видны и direct route безопасно редиректит;
- onboarding не появляется;
- sales hierarchy banner не появляется, если он отключен;
- русская локализация закрывает сделки, события, звонки, задачи, вложения, фильтры, канбан и настройки воронок;
- кастомный brand/logo клиента не перетирается миграцией;
- старый ERPNext CRM скрыт только если мы приняли это изменение в CRM patch.

## Что не переносить в CRM-форк в рамках этого плана

- Общую тему Desk.
- Домашний экран `/home`.
- Общие Desk labels `ERPNext -> EXP ERP`, `Frappe HR -> EXP HR`, `Frappe Framework -> Platform`.
- Общие настройки пользователей Desk.
- Отключение product suggestions на уровне Frappe/ERPNext.
- Ограничение списка языков и genders.
- Нижние кнопки сайдбара Desk.

Эти вещи могут оставаться в `exp_theme`, потому что они относятся не к CRM-приложению, а к общей оболочке системы.
