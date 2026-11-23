const labels = {
  Pipeline: ['Pipeline', 'В работе'],
  'Best Case': ['Best case', 'Оптимистичный'],
  Commit: ['Commit', 'Подтверждённый'],
  Deferred: ['Deferred', 'Отложено'],
  Uncategorized: ['Uncategorized', 'Без категории'],
}

export const forecastCategories = Object.keys(labels)

export function forecastCategoryLabel(value, translate) {
  return labels[value] ? translate(...labels[value]) : value
}
