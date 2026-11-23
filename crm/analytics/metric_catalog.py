"""Definitions shared by the sales views and saved report builder."""

FORECAST_CATEGORIES = ("Pipeline", "Best Case", "Commit", "Deferred")

SALES_METRICS = {
	"new_leads": ("lead", "created_on", "count", "Count of readable leads created in the period.", "Число доступных лидов, созданных за период."),
	"new_deals": ("deal", "created_on", "count", "Count of readable deals created in the period.", "Число доступных сделок, созданных за период."),
	"won_count": ("deal", "won_on", "count", "Count of deals won in the period.", "Число сделок, выигранных за период."),
	"lost_count": ("deal", "lost_on", "count", "Count of deals lost in the period.", "Число сделок, проигранных за период."),
	"won_value": ("deal", "won_on", "currency", "Sum of known values of deals won in the period, using the stored exchange rates.", "Сумма известных стоимостей сделок, выигранных за период, по сохранённым курсам."),
	"win_rate": ("deal", "closed_on", "percent", "Won deals divided by won and lost deals with confirmed dates.", "Число побед делится на сумму побед и потерь с подтверждёнными датами."),
	"median_cycle": ("deal", "won_on", "days", "Median calendar days from creation to a confirmed win.", "Медиана календарных дней от создания сделки до подтверждённой победы."),
	"open_count": ("deal", "now", "count", "Count of currently open deals.", "Число открытых сделок на момент расчёта."),
	"open_value": ("deal", "now", "currency", "Sum of known values of currently open deals.", "Сумма известных стоимостей открытых сделок на момент расчёта."),
	"forecast": ("deal", "expected_close_on", "currency", "Expected value multiplied by probability and the stored exchange rate for open deals in the horizon.", "Ожидаемая сумма открытых сделок в горизонте прогноза с учётом вероятности и сохранённого курса."),
	"risk_count": ("deal", "now", "count", "Count of open deals with at least one confirmed risk.", "Число открытых сделок хотя бы с одним подтверждённым риском."),
	"risk_value": ("deal", "now", "currency", "Sum of known values of open deals with confirmed risks.", "Сумма известных стоимостей открытых сделок с подтверждённым риском."),
	"stalled_value": ("deal", "now", "currency", "Sum of known values of open deals past the configured stage time.", "Сумма известных стоимостей открытых сделок с превышением срока на этапе."),
	"average_won_value": ("deal", "won_on", "currency", "Known won value divided by the number of won deals with known values.", "Сумма известных стоимостей побед делится на число побед с известной стоимостью."),
	"median_won_value": ("deal", "won_on", "currency", "Median of known values of deals won in the period.", "Медиана известных стоимостей сделок, выигранных за период."),
	"average_cycle": ("deal", "won_on", "days", "Average calendar days from creation to a confirmed win.", "Среднее число календарных дней от создания сделки до подтверждённой победы."),
	"lead_cycle": ("deal", "won_on", "days", "Median calendar days from linked lead creation to a confirmed win.", "Медиана календарных дней от создания связанного лида до подтверждённой победы."),
}


def sales_catalog(metrics):
	"""Expose only definitions available to the current viewer's computed report."""
	return {
		key: {"object": entity, "date": date, "unit": unit, "en": en, "ru": ru}
		for key, (entity, date, unit, en, ru) in SALES_METRICS.items()
		if key in metrics and not metrics[key].get("redacted")
	}
