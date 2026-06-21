const RU_LOCALE = 'ru-RU'

const MONTHS = {
  Jan: 0,
  Feb: 1,
  Mar: 2,
  Apr: 3,
  May: 4,
  Jun: 5,
  Jul: 6,
  Aug: 7,
  Sep: 8,
  Oct: 9,
  Nov: 10,
  Dec: 11,
}

const TEXT_REPLACEMENTS = new Map([
  ['Jan', 'Янв'],
  ['Feb', 'Фев'],
  ['Mar', 'Мар'],
  ['Apr', 'Апр'],
  ['May', 'Май'],
  ['Jun', 'Июн'],
  ['Jul', 'Июл'],
  ['Aug', 'Авг'],
  ['Sep', 'Сен'],
  ['Oct', 'Окт'],
  ['Nov', 'Ноя'],
  ['Dec', 'Дек'],
  ['Today', 'Сегодня'],
  ['Now', 'Сейчас'],
  ['Tomorrow', 'Завтра'],
  ['Select time', 'Выберите время'],
  ['All day', 'Весь день'],
  ['All Day', 'Весь день'],
  ['Event Title', 'Название события'],
  ['(No title)', 'Без темы'],
  ['(No Title)', 'Без темы'],
  ['Sun', 'Вс'],
  ['Mon', 'Пн'],
  ['Tue', 'Вт'],
  ['Wed', 'Ср'],
  ['Thu', 'Чт'],
  ['Fri', 'Пт'],
  ['Sat', 'Сб'],
  ['Sunday', 'Воскресенье'],
  ['Monday', 'Понедельник'],
  ['Tuesday', 'Вторник'],
  ['Wednesday', 'Среда'],
  ['Thursday', 'Четверг'],
  ['Friday', 'Пятница'],
  ['Saturday', 'Суббота'],
])

const DATEPICKER_WEEKDAYS = ['Вс', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб']

function translate(value) {
  return globalThis.__ ? globalThis.__(value) : value
}

export function getCalendarLocale() {
  const lang = globalThis.frappe?.boot?.lang || globalThis.navigator?.language || 'en'
  if (translate('Calendar') === 'Календарь') return RU_LOCALE
  return String(lang).toLowerCase().startsWith('ru') ? RU_LOCALE : 'en-US'
}

export function shouldLocalizeCalendar() {
  return getCalendarLocale() === RU_LOCALE
}

export function formatCalendarMonthYear(value, fallback = '') {
  if (!shouldLocalizeCalendar()) return fallback
  const date = value ? new Date(value) : new Date()
  const safeDate = Number.isNaN(date.getTime()) ? new Date() : date

  return new Intl.DateTimeFormat(RU_LOCALE, {
    month: 'long',
    year: 'numeric',
  }).format(safeDate)
}

export function setupCalendarLocalization() {
  if (!shouldLocalizeCalendar() || !globalThis.document?.body) return null

  requestAnimationFrame(() => localizeCalendarText(document.body))

  const observer = new MutationObserver(() => {
    if (!shouldLocalizeCalendar()) return
    requestAnimationFrame(() => localizeCalendarText(document.body))
  })

  observer.observe(document.body, {
    childList: true,
    subtree: true,
    characterData: true,
    attributes: true,
    attributeFilter: ['placeholder', 'aria-label', 'title'],
  })

  return observer
}

export function localizeCalendarText(root = document.body) {
  if (!shouldLocalizeCalendar() || !root) return

  localizeTextNodes(root)
  localizeAttributes(root)
  localizeWeekdayInitialRows(root)
}

function localizeTextNodes(root) {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT)
  const textNodes = []
  while (walker.nextNode()) textNodes.push(walker.currentNode)

  textNodes.forEach((node) => {
    const value = node.nodeValue
    const trimmed = value.trim()
    if (!trimmed) return

    if (TEXT_REPLACEMENTS.has(trimmed)) {
      node.nodeValue = value.replace(trimmed, TEXT_REPLACEMENTS.get(trimmed))
      return
    }

    const monthHeader = getLocalizedMonthHeader(trimmed)
    if (monthHeader) {
      node.nodeValue = value.replace(trimmed, monthHeader)
      return
    }

    const dayHeaderMatch = trimmed.match(/^(Sun|Mon|Tue|Wed|Thu|Fri|Sat)\s+(\d{1,2})$/)
    if (dayHeaderMatch) {
      node.nodeValue = value.replace(
        trimmed,
        `${TEXT_REPLACEMENTS.get(dayHeaderMatch[1])} ${dayHeaderMatch[2]}`,
      )
      return
    }

    const localizedValue = value
      .replace(/\bSunday\b/g, 'Воскресенье')
      .replace(/\bMonday\b/g, 'Понедельник')
      .replace(/\bTuesday\b/g, 'Вторник')
      .replace(/\bWednesday\b/g, 'Среда')
      .replace(/\bThursday\b/g, 'Четверг')
      .replace(/\bFriday\b/g, 'Пятница')
      .replace(/\bSaturday\b/g, 'Суббота')
      .replace(/\bSun\b/g, 'Вс')
      .replace(/\bMon\b/g, 'Пн')
      .replace(/\bTue\b/g, 'Вт')
      .replace(/\bWed\b/g, 'Ср')
      .replace(/\bThu\b/g, 'Чт')
      .replace(/\bFri\b/g, 'Пт')
      .replace(/\bSat\b/g, 'Сб')
    if (localizedValue !== value) {
      node.nodeValue = localizedValue
      return
    }

    const timeMatch = trimmed.match(/^(\d{1,2})(?::(\d{2}))?\s*(am|pm)$/i)
    if (timeMatch) {
      node.nodeValue = value.replace(trimmed, toTwentyFourHourLabel(timeMatch))
      return
    }

    const moreMatch = trimmed.match(/^(\d+)\s+more$/)
    if (moreMatch) {
      node.nodeValue = value.replace(trimmed, `Ещё ${moreMatch[1]}`)
    }
  })
}

function localizeAttributes(root) {
  const attributes = ['placeholder', 'aria-label', 'title']
  root.querySelectorAll('*').forEach((element) => {
    attributes.forEach((attribute) => {
      const value = element.getAttribute(attribute)
      if (!value || !TEXT_REPLACEMENTS.has(value)) return
      element.setAttribute(attribute, TEXT_REPLACEMENTS.get(value))
    })
  })
}

function localizeWeekdayInitialRows(root) {
  const candidates = [...root.querySelectorAll('*')].filter((element) => {
    if (element.children.length) return false
    return ['S', 'M', 'T', 'W', 'F'].includes(element.textContent.trim())
  })

  for (let index = 0; index <= candidates.length - 7; index++) {
    const row = candidates.slice(index, index + 7)
    const sequence = row.map((element) => element.textContent.trim()).join('')
    if (sequence !== 'SMTWTFS') continue

    row.forEach((element, weekdayIndex) => {
      element.textContent = DATEPICKER_WEEKDAYS[weekdayIndex]
    })
    index += 6
  }
}

function getLocalizedMonthHeader(value) {
  const match = value.match(/^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{4})$/)
  if (!match) return ''

  return formatCalendarMonthYear(new Date(Number(match[2]), MONTHS[match[1]], 1), value)
}

function toTwentyFourHourLabel(match) {
  let hour = Number(match[1])
  const minute = match[2] || '00'
  const period = match[3].toLowerCase()
  if (period === 'pm' && hour !== 12) hour += 12
  if (period === 'am' && hour === 12) hour = 0
  return `${String(hour).padStart(2, '0')}:${minute}`
}
