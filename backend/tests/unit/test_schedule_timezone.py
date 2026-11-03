import zoneinfo
from datetime import datetime, timezone, timedelta
import pytest
from tezlify_studio.domain.entities.scheduled_publish import ScheduledPublish
from tezlify_studio.domain.exceptions.schedule_exceptions import InvalidScheduleTimeException

def test_timezone_iso_parsing_and_utc_conversion():
    # Istanbul (+03:00)
    iso_istanbul = "2026-11-04T15:30:00+03:00"
    dt_istanbul = datetime.fromisoformat(iso_istanbul)
    assert dt_istanbul.utcoffset() == timedelta(hours=3)

    item = ScheduledPublish(
        id="tz_1",
        media_asset_id="media_1",
        social_account_id="acc_1",
        title="Istanbul Publish",
        scheduled_at_utc=dt_istanbul,
        timezone="Europe/Istanbul",
    )

    # In UTC, 15:30+03:00 is 12:30 UTC
    assert item.scheduled_at_utc.hour == 12
    assert item.scheduled_at_utc.minute == 30
    assert item.scheduled_at_utc.tzinfo == timezone.utc

def test_new_york_dst_handling():
    # New York in Summer (EDT -04:00) vs Winter (EST -05:00)
    tz_ny = zoneinfo.ZoneInfo("America/New_York")
    
    # Summer datetime
    dt_summer = datetime(2026, 7, 15, 10, 0, tzinfo=tz_ny)
    # Winter datetime
    dt_winter = datetime(2026, 12, 15, 10, 0, tzinfo=tz_ny)

    item_summer = ScheduledPublish(
        id="tz_summer",
        media_asset_id="media_1",
        social_account_id="acc_1",
        title="Summer NY",
        scheduled_at_utc=dt_summer,
        timezone="America/New_York",
    )
    item_winter = ScheduledPublish(
        id="tz_winter",
        media_asset_id="media_1",
        social_account_id="acc_1",
        title="Winter NY",
        scheduled_at_utc=dt_winter,
        timezone="America/New_York",
    )

    # In Summer (EDT): 10:00 -04:00 = 14:00 UTC
    assert item_summer.scheduled_at_utc.hour == 14
    # In Winter (EST): 10:00 -05:00 = 15:00 UTC
    assert item_winter.scheduled_at_utc.hour == 15

def test_invalid_timezone_validation():
    with pytest.raises(Exception):
        zoneinfo.ZoneInfo("Invalid/NonExistent_Zone")
