"""Synthetic analytics acceptance data; no external accounts or customer data."""

from copy import deepcopy
from datetime import date, datetime
from zoneinfo import ZoneInfo

from .engine import Context, Period


def acceptance_context(**changes):
	values = {
		"period": Period(date(2026, 10, 1), date(2026, 10, 25)),
		"horizon": Period(date(2026, 10, 26), date(2026, 11, 25)),
		"as_of": datetime(2026, 10, 26, 12, tzinfo=ZoneInfo("Europe/Moscow")),
	}
	return Context(**(values | changes))


def acceptance_data():
	# Each amount is in the source currency. EUR uses the stored source rate 100.
	rows = [
		("D1", "09-20", "Won", "10-05", 1000, 1000, 100, "10-05", "A", "Web", "Main", "RUB", 1, "09-20"),
		("D2", "10-02", "Won", "10-10", 2000, 2000, 100, "10-10", "B", "Referral", "Main", "RUB", 1, "10-02"),
		("D3", "10-03", "Lost", "10-12", 1500, 1500, 40, "10-12", "B", "Web", "Main", "RUB", 1, "10-03"),
		("D4", "09-01", "Ongoing", None, 10000, 6000, 50, "10-30", "A", "Web", "Main", "RUB", 1, "10-10"),
		("D5", "10-20", "Ongoing", None, 4000, 4000, 25, "11-05", "B", "Referral", "Main", "RUB", 1, "10-20"),
		("D6", "10-22", "Ongoing", None, 100, 100, 50, "11-10", "B", "Web", "Main", "EUR", 100, "10-22"),
		("D7", "09-25", "Won", "09-30", 3000, 3000, 100, "09-30", "A", "Web", "Main", "RUB", 1, "09-25"),
		("D8", "10-25", "Ongoing", None, 1000, 1000, 100, "12-01", "A", "Web", "Extra", "RUB", 1, "10-25"),
	]
	deals = []
	for name, created, status, closed, value, expected, probability, expected_date, owner, source, pipeline, currency, rate, stage in rows:
		deals.append({
			"name": name, "creation": f"2026-{created} 12:00:00", "status_type": status,
			"status": "Proposal" if name in {"D4", "D6"} else "Qualification" if name in {"D5", "D8"} else status,
			"closed_date": f"2026-{closed}" if status == "Won" else None,
			"lost_date": f"2026-{closed}" if status == "Lost" else None,
			"value": value, "expected_value": expected, "probability": probability,
			"expected_date": f"2026-{expected_date}", "owner": owner, "source": source,
			"pipeline": pipeline, "currency": currency, "exchange_rate": rate,
			"stage_entered_at": f"2026-{stage} 12:00:00", "stage_history_complete": True,
		})
	leads = []
	for name, created, deal_name in [
		("L1", "09-15", "D1"), ("L2", "10-01", "D2"), ("L3", "10-02", "D3"),
		("L4", "10-19", "D5"), ("L5", "10-21", "D6"), ("L6", "10-24", "D8"), ("L7", "10-08", None),
	]:
		deal = next((row for row in deals if row["name"] == deal_name), None)
		if deal:
			deal["lead"] = name
		leads.append({"name": name, "creation": f"2026-{created} 12:00:00",
			"owner": deal["owner"] if deal else "A", "source": deal["source"] if deal else "Web",
			"pipeline": deal["pipeline"] if deal else "Main", "converted": bool(deal)})
	tasks = [{"name": "T" + name, "reference_name": name, "status": "Todo", "due_date": f"2026-10-{day} 12:00:00"}
		for name, day in [("D5", "27"), ("D6", "25"), ("D8", "29")]]
	return deepcopy({"deals": deals, "leads": leads, "tasks": tasks})
