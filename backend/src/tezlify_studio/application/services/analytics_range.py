from datetime import date, timedelta
from typing import Optional

from tezlify_studio.domain.value_objects.creator_models import DateRange

_PRESETS = {"7": 7, "28": 28, "90": 90, "365": 365}


def resolve_date_range(
    range_key: str = "28",
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    max_days: int = 365,
) -> DateRange:
    key = (range_key or "28").strip().lower()
    if key == "custom":
        if not start_date or not end_date:
            raise ValueError("Özel tarih aralığı için start_date ve end_date zorunludur.")
        if end_date < start_date:
            raise ValueError("end_date, start_date'den önce olamaz.")
        days = (end_date - start_date).days + 1
        if days > max_days:
            raise ValueError(f"Tarih aralığı en fazla {max_days} gün olabilir.")
        return DateRange(start_date=start_date, end_date=end_date, label="custom")

    if key not in _PRESETS:
        raise ValueError("range 7, 28, 90, 365 veya custom olmalıdır.")

    days = _PRESETS[key]
    if days > max_days:
        raise ValueError(f"Tarih aralığı en fazla {max_days} gün olabilir.")
    today = end_date or date.today()
    start = today - timedelta(days=days - 1)
    return DateRange(start_date=start, end_date=today, label=key)
