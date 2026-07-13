from zoneinfo import ZoneInfo

import pytest

from app.core.config import settings
from app.services import ReportingService


@pytest.mark.parametrize("period", ["day", "week", "month"])
def test_reporting_periods_use_calendar_boundaries(period: str) -> None:
    start, end = ReportingService.period_window(period)
    timezone = ZoneInfo(settings.reporting_timezone)
    local_start = start.astimezone(timezone)
    local_end = end.astimezone(timezone)

    assert local_start <= local_end
    assert local_start.hour == 0
    assert local_start.minute == 0
    assert local_start.second == 0
    if period == "day":
        assert local_start.date() == local_end.date()
    elif period == "week":
        assert local_start.weekday() == 0
    else:
        assert local_start.day == 1


def test_reporting_period_rejects_unknown_value() -> None:
    with pytest.raises(ValueError, match="period must be"):
        ReportingService.period_window("quarter")
