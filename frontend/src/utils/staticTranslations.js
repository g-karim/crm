const exactTranslations = {
  Amber: 'Янтарный',
  Violet: 'Фиолетовый',
  Pink: 'Розовый',
  Cyan: 'Голубой',
  Blue: 'Синий',
  Orange: 'Оранжевый',
  Green: 'Зеленый',
  Today: 'Сегодня',
  Tomorrow: 'Завтра',
  Now: 'Сейчас',
  Clear: 'Очистить',
  'Select time': 'Выбрать время',
  'Drag & Drop files here or upload from':
    'Перетащите файлы сюда или загрузите из',
  Device: 'Устройство',
  Link: 'Ссылка',
  Camera: 'Камера',
  Incoming: 'Входящий',
  Outgoing: 'Исходящий',
  Initiated: 'Инициирован',
  Ringing: 'Идет вызов',
  'In Progress': 'В работе',
  Completed: 'Завершен',
  Failed: 'Не удался',
  Busy: 'Занято',
  'No Answer': 'Нет ответа',
  Queued: 'В очереди',
  Canceled: 'Отменено',
  Cancelled: 'Отменено',
  Backlog: 'Бэклог',
  Todo: 'К выполнению',
  Done: 'Готово',
  Low: 'Низкий',
  Medium: 'Средний',
  High: 'Высокий',
  'minute before': 'минута до',
  'minutes before': 'минут до',
  'hour before': 'час до',
  'hours before': 'часов до',
  'day before': 'день до',
  'days before': 'дней до',
  'week before': 'неделя до',
  'weeks before': 'недель до',
  'Open Deal': 'Открыть сделку',
  'Open Lead': 'Открыть лид',
  'No New Notifications': 'Новых уведомлений нет',
  'You have no new notifications': 'У вас нет новых уведомлений',
  'Modified By': 'Изменил',
  'Last Modified': 'Последнее изменение',
  'Select all': 'Выбрать все',
  'Confirm annual plan details': 'Подтвердить детали годового плана',
  'Send proposal document': 'Отправить коммерческое предложение',
  'Follow up on trial access': 'Уточнить статус тестового доступа',
  'Set up trial environment': 'Настроить тестовое окружение',
  'Schedule technical demo': 'Запланировать техническую демонстрацию',
  'Send competitor comparison doc': 'Отправить сравнение с конкурентами',
  Where: 'Поле',
  And: 'И',
  'Add Filter': 'Добавить фильтр',
  'Clear All Filters': 'Сбросить фильтры',
  'Last Updated On': 'Последнее обновление',
  'На сайте': 'В списке',
  Нравится: 'Содержит',
  Является: 'Заполнено/пусто',
}

const months = {
  Jan: 'Янв',
  Feb: 'Фев',
  Mar: 'Мар',
  Apr: 'Апр',
  May: 'Май',
  Jun: 'Июн',
  Jul: 'Июл',
  Aug: 'Авг',
  Sep: 'Сен',
  Oct: 'Окт',
  Nov: 'Ноя',
  Dec: 'Дек',
}

const weekdays = ['Вс', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб']

export function setupStaticTranslations() {
  if (typeof window === 'undefined') return

  const translate = () => {
    if (!isRussian()) return
    translateTree(document.body)
    translateDatePickers(document.body)
  }

  translate()

  let scheduled = false
  const observer = new MutationObserver(() => {
    if (scheduled) return
    scheduled = true
    requestAnimationFrame(() => {
      scheduled = false
      translate()
    })
  })

  observer.observe(document.body, {
    childList: true,
    subtree: true,
    characterData: true,
    attributes: true,
    attributeFilter: ['placeholder', 'aria-label', 'title'],
  })
}

function isRussian() {
  return window.__?.('Today') === 'Сегодня'
}

function translateTree(root) {
  if (!root) return

  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT)
  let node = walker.nextNode()

  while (node) {
    const translated = translateText(node.nodeValue)
    if (translated !== node.nodeValue) node.nodeValue = translated
    node = walker.nextNode()
  }

  root.querySelectorAll?.('[placeholder], [aria-label], [title]').forEach(
    (element) => {
      for (const attr of ['placeholder', 'aria-label', 'title']) {
        if (!element.hasAttribute(attr)) continue
        const value = element.getAttribute(attr)
        const translated = translateText(value)
        if (translated !== value) element.setAttribute(attr, translated)
      }
    },
  )
}

function translateText(value) {
  if (!value) return value
  const trimmed = value.trim()
  const translated =
    exactTranslations[trimmed] ||
    translateSelection(trimmed) ||
    translateTime(trimmed) ||
    translateMonthYear(trimmed)
  if (!translated || translated === trimmed) return value
  return value.replace(trimmed, translated)
}

function translateSelection(value) {
  const match = value.match(/^(\d+)\s+rows?\s+selected$/)
  if (!match) return ''
  const count = Number(match[1])
  if (count === 1) return 'Выбрана 1 строка'
  return `Выбрано строк: ${count}`
}

function translateMonthYear(value) {
  const match = value.match(
    /^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{4})$/,
  )
  if (!match) return months[value] || ''
  return `${months[match[1]]} ${match[2]}`
}

function translateTime(value) {
  const match = value.match(/^(\d{1,2}):(\d{2})\s*(am|pm)$/i)
  if (!match) return ''
  let hour = Number(match[1])
  const minute = match[2]
  const period = match[3].toLowerCase()

  if (period === 'am' && hour === 12) hour = 0
  if (period === 'pm' && hour !== 12) hour += 12

  return `${String(hour).padStart(2, '0')}:${minute}`
}

function translateDatePickers(root) {
  root
    .querySelectorAll?.('[role="grid"][aria-label="Calendar dates"]')
    .forEach((grid) => {
      const header = grid.querySelector(':scope > div')
      header?.querySelectorAll(':scope > div').forEach((day, index) => {
        if (weekdays[index]) day.textContent = weekdays[index]
      })
    })
}
