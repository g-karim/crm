"""Working-time deadlines for the call that initiated a callback obligation."""

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class WorkingHours:
	zone: str
	days: tuple[int, ...]
	start: time
	end: time

	def __post_init__(self):
		ZoneInfo(self.zone)
		if not self.days or any(day not in range(7) for day in self.days) or self.end <= self.start:
			raise ValueError("Choose workdays and a daily interval with an end after its start")

	def deadline(self, missed_at: datetime, minutes: int) -> datetime:
		"""UTC arithmetic measures working time across midnight and offset changes."""
		if missed_at.tzinfo is None or not 1 <= minutes <= 7 * 24 * 60:
			raise ValueError("Provide a timezone and a valid response time")
		zone = ZoneInfo(self.zone)
		day = missed_at.astimezone(zone).date()
		remaining = timedelta(minutes=minutes)
		missed = missed_at.astimezone(timezone.utc)
		while True:
			if day.weekday() in self.days:
				start = max(datetime.combine(day, self.start, zone).astimezone(timezone.utc), missed)
				end = datetime.combine(day, self.end, zone).astimezone(timezone.utc)
				if end > start:
					available = end - start
					if available >= remaining:
						return (start + remaining).astimezone(zone)
					remaining -= available
			day += timedelta(days=1)


def callback_state(deadline, observed_at, connected_at=None):
	"""Pending work stays outside the resolved SLA denominator while time remains."""
	if deadline is None:
		return "unavailable"
	deadline = deadline.astimezone(timezone.utc)
	now = observed_at.astimezone(timezone.utc)
	if connected_at is not None:
		connected = connected_at.astimezone(timezone.utc)
		if connected <= now:
			return "on_time" if connected <= deadline else "late"
	return "overdue" if now > deadline else "pending"


def completed_callback_state(deadline, observed_at, started_at, ended_at, connected_at=None):
	"""Classify a completed callback using an observed answer or safe time bounds."""
	if deadline is None:
		return "unavailable"
	if connected_at is not None:
		return callback_state(deadline, observed_at, connected_at)
	deadline = deadline.astimezone(timezone.utc)
	started_at = started_at.astimezone(timezone.utc)
	if started_at > deadline:
		return "late"
	if ended_at is not None:
		ended_at = ended_at.astimezone(timezone.utc)
		if started_at < ended_at <= min(deadline, observed_at.astimezone(timezone.utc)):
			return "on_time"
	return "unavailable"
