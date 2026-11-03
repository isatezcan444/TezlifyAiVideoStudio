import zoneinfo
from datetime import datetime, timezone, timedelta
from tezlify_studio.domain.exceptions.schedule_exceptions import InvalidScheduleTimeException

def validate_and_normalize_schedule_time(scheduled_at_iso: str, tz_name: str) -> datetime:
    """
    Validates ISO 8601 schedule datetime string against target timezone and DST transitions.
    Explicitly detects and rejects nonexistent wall-clock times (Spring forward)
    and ambiguous wall-clock times (Fall back without valid matching offset).
    Returns normalized UTC datetime.
    """
    clean_tz = (tz_name or "UTC").strip()
    try:
        target_tz = zoneinfo.ZoneInfo(clean_tz)
    except Exception:
        raise InvalidScheduleTimeException(f"Geçersiz saat dilimi (timezone): '{clean_tz}'")

    try:
        raw_dt = datetime.fromisoformat(scheduled_at_iso)
    except Exception as e:
        raise InvalidScheduleTimeException(f"Geçersiz ISO 8601 tarih formatı: {str(e)}")

    if raw_dt.tzinfo is None:
        raise InvalidScheduleTimeException("Tarih zaman dilimi (timezone) bilgisi içermelidir (ISO 8601 with offset).")

    # If the user passed a datetime that corresponds to a local wall-clock in target_tz:
    wall = datetime(raw_dt.year, raw_dt.month, raw_dt.day, raw_dt.hour, raw_dt.minute, raw_dt.second)
    wall_tz = wall.replace(tzinfo=target_tz)
    wall_back = wall_tz.astimezone(timezone.utc).astimezone(target_tz)

    # 1. Nonexistent wall-clock check (Spring Forward gap)
    if (wall_back.year, wall_back.month, wall_back.day, wall_back.hour, wall_back.minute) != (
        wall.year,
        wall.month,
        wall.day,
        wall.hour,
        wall.minute,
    ):
        raise InvalidScheduleTimeException(
            f"Belirtilen yerel saat ({wall.strftime('%H:%M')}) yaz saati uygulaması geçişi nedeniyle '{clean_tz}' saat diliminde mevcut değildir (Spring Forward atlaması). Lütfen geçerli bir saat seçin."
        )

    # 2. Ambiguous wall-clock check (Fall Back overlap)
    wall_f0 = wall.replace(tzinfo=target_tz, fold=0)
    wall_f1 = wall.replace(tzinfo=target_tz, fold=1)
    if wall_f0.astimezone(timezone.utc) != wall_f1.astimezone(timezone.utc):
        raw_offset = raw_dt.utcoffset()
        if raw_offset not in (wall_f0.utcoffset(), wall_f1.utcoffset()):
            raise InvalidScheduleTimeException(
                f"Belirtilen yerel saat ({wall.strftime('%H:%M')}) yaz saati bitişinde iki kez yaşandığından belirsizdir. Lütfen kesinleşmiş bir zaman farkı (offset) belirtin."
            )

    sched_utc = raw_dt.astimezone(timezone.utc)
    now_utc = datetime.now(timezone.utc)
    if sched_utc <= now_utc + timedelta(seconds=30):
        raise InvalidScheduleTimeException("Planlanan yayın tarihi gelecekte olmalıdır (en az 1 dakika sonrası).")

    return sched_utc
