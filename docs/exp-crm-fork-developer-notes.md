# EXP CRM Fork: заметки для разработчиков

Этот документ описывает поведение, которое раньше частично делалось внешним слоем `exp_theme`, а теперь живет в форке `crm`. `exp_theme` остается обязательным приложением для наших сайтов, но для CRM он должен быть языковым и общесистемным слоем, а не runtime-патчем `/crm`.

## Брендинг и assets

Основной бренд CRM задается в `crm/branding.py`:

- `APP_NAME = "EXP CRM"`;
- `APP_ROUTE = "/crm"`;
- `APP_LOGO_URL = "/assets/crm/images/crm_logo.png"`;
- `APP_FAVICON_URL = APP_LOGO_URL`.

Основные файлы лежат внутри `apps/crm`:

- `crm/public/images/crm_logo.png` - основной логотип CRM;
- `crm/public/images/logo.png` - совместимая копия для старых ссылок;
- `frontend/public/favicon.png` - favicon для frontend build;
- `.github/crm_logo.png` и `.github/logo.png` - логотипы для README/GitHub;
- `crm/public/images/exp-sign-black.png` - иконка пункта `EXP ERP` в настройках.

CRM не должна ссылаться на `/assets/exp_theme/...` для логотипа, favicon, manifest icon или ERP icon. Старые пути могут встречаться только в списке `LEGACY_ASSET_URLS`, тестах и документации как значения, которые нужно заменить при миграции.

## Где применяется бренд

Нативные точки брендинга в CRM:

- `crm/hooks.py` - app title/icon и `app_include_icons`;
- `frontend/index.html` и `crm/www/crm.html` - title/favicon/apple icon;
- `frontend/vite.config.js` - PWA manifest icons;
- `frontend/src/components/Icons/CRMLogo.vue` - fallback logo в sidebar;
- `crm/branding.py` - безопасные defaults для `FCRM Settings` и `Desktop Icon`;
- `crm/install.py` и patches - применение defaults на новых и существующих сайтах.

`ensure_crm_branding_defaults()` заменяет только пустые или старые значения Frappe/exp_theme. Если клиент уже настроил свой `brand_name`, `brand_logo` или `favicon`, этот helper не должен их перетирать.

## Desktop Icon

`ensure_desktop_icon_branding()` отвечает за видимость и бренд app icon для самого приложения CRM:

- label должен быть `EXP CRM`;
- `app` должен быть `crm`;
- `icon_type` должен быть `App`;
- `logo_url` должен вести на `/assets/crm/images/crm_logo.png`;
- запись не должна быть скрыта.

Старый ERPNext CRM скрывается отдельно через `crm/desk.py`. Важно не перепутать:

- Frappe/EXP CRM app должен быть видимым;
- legacy ERPNext `Desktop Icon`/`Workspace` с `CRM` должен быть скрыт.

## Dropdown CRM

Стандартные пункты dropdown описаны в `crm/dropdown.py` и подключены через `crm/hooks.py`.

Текущий набор:

- `Рабочий стол` -> `/home`;
- `Settings`;
- separator;
- `Log out`.

В стандартном dropdown не должно быть:

- Apps;
- About;
- Login to Frappe Cloud;
- Help.

`ensure_crm_dropdown_items()` пересобирает стандартные пункты, но сохраняет пользовательские `CRM Dropdown Item`, у которых `is_standard = 0`.

## Скрытые настройки CRM

В `frontend/src/components/Settings/Settings.vue` из навигации убраны:

- Brand settings;
- Telephony settings.

Компоненты `BrandSettings.vue` и `Telephony/...` остаются в коде. Это сделано специально: если разделы понадобятся позже, их можно вернуть в navigation config без восстановления DOM-патчей из `exp_theme`.

Чтобы вернуть Brand settings:

1. Импортировать `BrandSettings` в `Settings.vue`, если импорт был удален.
2. Добавить пункт в нужную группу `tabs`.
3. Проверить, что прямой переход/сохраненный активный раздел корректно открывается.

Чтобы вернуть Telephony settings:

1. Импортировать `TelephonyPage` в `Settings.vue`, если импорт был удален.
2. Добавить пункт `Telephony` в группу настроек.
3. Проверить `callEnabled`, `CRM Telephony Agent` и интеграционные настройки Twilio/Exotel.

## Sales hierarchy banner

Sales hierarchy/permission banner больше не скрывается через DOM. Если banner выключен в нашем UX, это должно делаться в компоненте или настройке CRM, а не через `MutationObserver`.

## EXP ERP integration polish

Настройки ERPNext в CRM показываются как `EXP ERP`, а иконка берется из `crm/public/images/exp-sign-black.png`.

Важно:

- системный DocType может по-прежнему называться `ERPNext CRM Settings`;
- пользовательский label в интерфейсе должен быть `EXP ERP`;
- docs links и help text не должны вести пользователя в старый Frappe-branded flow, если есть наш EXP flow.

## Переводы

Граница ответственности такая:

- `crm` делает UI переводимым: строки, labels, placeholders, empty states, dropdown labels и options проходят через `__()`;
- `exp_theme` хранит общий русский словарь в `exp_theme/translations.py` и применяет его через стандартную таблицу `Translation`.

Не нужно возвращать `staticTranslations.js`, DOM replacement или `MutationObserver` для CRM. Если строка не переводится, правильный фикс обычно такой:

1. Найти место, где строка выводится.
2. Пропустить строку через `__()`.
3. Добавить русский ключ в `exp_theme/translations.py`, если его еще нет.
4. Выполнить `bench --site <site> execute exp_theme.setup.configure_translations`.

## Patches, которые меняют существующие сайты

CRM-форк добавляет несколько patch/helper-ов для переноса состояния из старого `exp_theme`-слоя:

- `crm.patches.v1_0.ensure_exp_crm_branding` - применяет безопасные branding defaults;
- `crm.patches.v1_0.update_crm_dropdown_items` - обновляет стандартный CRM dropdown;
- `crm.patches.v1_0.hide_legacy_erpnext_crm` - скрывает старый ERPNext CRM в Desk;
- `crm.patches.v1_0.cleanup_exp_theme_crm_state` - идемпотентная общая очистка старого CRM-состояния `exp_theme`.

Эти patch-и должны быть безопасными для повторного запуска. Они не должны удалять пользовательские переводы, пользовательский бренд и custom dropdown items.

## Проверки после изменений

Минимальный набор:

```bash
python3 -m py_compile crm
git diff --check
cd frontend && yarn test:run
cd frontend && yarn build
bench --site v16.localhost migrate
bench --site crm-pipeline-test.localhost migrate
```

UI smoke:

- `/crm` сразу показывает `EXP CRM`, без мигания старого бренда;
- favicon и PWA manifest берут `/assets/crm/images/crm_logo.png`;
- sidebar logo берется из CRM assets или из пользовательского `FCRM Settings.brand_logo`;
- dropdown содержит `Рабочий стол`, `Settings`, `Log out`;
- dropdown не содержит Apps/About/Login to Frappe Cloud/Help;
- Brand/Telephony settings не видны в CRM settings;
- Desk не показывает legacy ERPNext CRM как отдельное CRM-приложение;
- русская локаль не показывает английские строки в основных CRM-сценариях.
