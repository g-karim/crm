"""Mark the first observed state of CRM records created before analytics history."""

from crm.analytics.history import backfill_baselines


def execute():
	backfill_baselines()
