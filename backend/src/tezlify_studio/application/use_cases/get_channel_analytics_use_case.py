from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from tezlify_studio.application.dto.connection_dto import channel_context_payload
from tezlify_studio.application.ports.channel_context_resolver_port import (
    ChannelContextResolverPort,
)
from tezlify_studio.application.ports.creator_gateway_port import CreatorGatewayPort
from tezlify_studio.application.services.analytics_availability_registry import (
    AnalyticsAvailabilityRegistry,
    analytics_availability_registry,
)
from tezlify_studio.application.services.analytics_range import resolve_date_range
from tezlify_studio.application.services.youtube_capability_service import (
    YouTubeCapabilityService,
)
from tezlify_studio.domain.value_objects.creator_models import (
    AnalyticsResult,
    AnalyticsRow,
    DateRange,
    YOUTUBE_ANALYTICS_METRICS,
)
from tezlify_studio.domain.value_objects.youtube_capabilities import (
    CAPABILITY_ANALYTICS,
    CAPABILITY_REVENUE,
    has_capability,
)

_REASON_TEXT = {
    "insufficient_scope": (
        "Mevcut YouTube bağlantısı analiz iznini (yt-analytics.readonly) içermiyor. "
        "Ayarlar > Bağlı Hesaplar bölümünden hesabı yeniden yetkilendirerek bu veriyi açabilirsiniz. "
        "Mevcut yükleme ve kanal bağlantınız çalışmaya devam eder."
    ),
    "api_not_enabled": (
        "YouTube Analytics API bu Google Cloud projesinde etkin değil. "
        "Google Cloud Console üzerinden API'yi etkinleştirmeniz gerekir."
    ),
    "not_connected": "Önce bir YouTube kanalı bağlamalısınız.",
    "quota_exceeded": "YouTube Analytics kotası doldu. Kota Pasifik Saati gece yarısı sıfırlanır.",
    "forbidden": (
        "YouTube Analytics isteği reddedildi. Bağlı hesabın kanala erişim yetkisini "
        "ve Analytics iznini kontrol edin."
    ),
    "api_error": (
        "YouTube Analytics API beklenmeyen bir hata döndürdü. Birkaç dakika sonra "
        "yeniden deneyin; sorun sürerse YouTube API durumunu kontrol edin."
    ),
}


def _previous_range(date_range: DateRange) -> DateRange:
    end = date_range.start_date - timedelta(days=1)
    start = end - timedelta(days=date_range.days - 1)
    return DateRange(start_date=start, end_date=end, label=f"previous_{date_range.label}")


def _metric_delta(current: Any, previous: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(current, (int, float)) or not isinstance(previous, (int, float)):
        return None
    change = current - previous
    percent = (change / previous * 100) if previous else None
    return {
        "current": current,
        "previous": previous,
        "change": change,
        "percent": percent,
    }


def _row_key(dimensions: List[str], row: AnalyticsRow) -> str:
    return "|".join(row.dimensions.get(dimension, "") for dimension in dimensions)


def _build_row_comparisons(
    current: AnalyticsResult, previous: AnalyticsResult
) -> List[Dict[str, Any]]:
    if not current.dimensions or "day" in current.dimensions:
        # Day keys are dates, so the previous window never shares them.
        return []
    previous_by_key = {
        _row_key(current.dimensions, row): row for row in previous.rows
    }
    comparisons: List[Dict[str, Any]] = []
    for row in current.rows:
        key = _row_key(current.dimensions, row)
        previous_row = previous_by_key.get(key)
        deltas: Dict[str, Any] = {}
        if previous_row is not None:
            for metric, value in row.metrics.items():
                delta = _metric_delta(value, previous_row.metrics.get(metric))
                if delta is not None:
                    deltas[metric] = delta
        comparisons.append(
            {
                "key": key,
                "dimensions": dict(row.dimensions),
                "previous_metrics": (
                    dict(previous_row.metrics) if previous_row is not None else {}
                ),
                "deltas": deltas,
            }
        )
    return comparisons


def _build_comparison(
    current: AnalyticsResult, previous: AnalyticsResult, previous_range: DateRange
) -> Dict[str, Any]:
    deltas = {
        metric: delta
        for metric, value in current.totals.items()
        if (delta := _metric_delta(value, previous.totals.get(metric))) is not None
    }
    revenue_delta = None
    if current.revenue and current.revenue.get("available") and previous.revenue and previous.revenue.get("available"):
        revenue_delta = {
            "amount": _metric_delta(
                current.revenue.get("amount"), previous.revenue.get("amount")
            ),
            "ad_revenue": _metric_delta(
                current.revenue.get("ad_revenue"), previous.revenue.get("ad_revenue")
            ),
        }
    return {
        "available": True,
        "range": {
            "start_date": previous_range.start_date.isoformat(),
            "end_date": previous_range.end_date.isoformat(),
            "days": previous_range.days,
        },
        "totals": dict(previous.totals),
        "deltas": deltas,
        "rows": _build_row_comparisons(current, previous),
        "revenue": revenue_delta,
    }


class GetChannelAnalyticsUseCase:
    def __init__(
        self,
        resolver: ChannelContextResolverPort,
        gateway: CreatorGatewayPort,
        max_range_days: int = 365,
        capability_service: Optional[YouTubeCapabilityService] = None,
        availability_registry: Optional[AnalyticsAvailabilityRegistry] = None,
    ):
        self.resolver = resolver
        self.gateway = gateway
        self.max_range_days = max_range_days
        self.capability_service = capability_service
        self.availability_registry = (
            availability_registry or analytics_availability_registry
        )

    def execute(
        self,
        range_key: str = "28",
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        dimensions: Optional[List[str]] = None,
        include_revenue: bool = False,
        compare: bool = False,
        channel_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        date_range = resolve_date_range(
            range_key=range_key,
            start_date=start_date,
            end_date=end_date,
            max_days=self.max_range_days,
        )
        allowed_dimensions = {"day", "video", "trafficSourceType", "country", "deviceType"}
        selected_dimensions = dimensions or ["day"]
        invalid = [item for item in selected_dimensions if item not in allowed_dimensions]
        if invalid:
            raise ValueError(f"Desteklenmeyen boyutlar: {', '.join(invalid)}")

        context = self.resolver.resolve(channel_id)

        missing_analytics_scope = bool(
            self.capability_service
            and not has_capability(
                context.connection.granted_scopes, CAPABILITY_ANALYTICS
            )
        )
        comparison: Optional[Dict[str, Any]] = None
        if missing_analytics_scope:
            # The central resolver decides from the granted scope, so a missing
            # permission is reported without calling Google. "API not enabled"
            # is observed from the real API response below and stays distinct.
            result = AnalyticsResult(
                available=False,
                reason="insufficient_scope",
                start_date=date_range.start_date.isoformat(),
                end_date=date_range.end_date.isoformat(),
                metrics=list(YOUTUBE_ANALYTICS_METRICS),
                dimensions=selected_dimensions,
            )
        else:
            revenue_allowed = include_revenue and (
                not self.capability_service
                or self.capability_service.can(context.connection, CAPABILITY_REVENUE)
            )
            session = self.gateway.bind(context)
            result = session.analytics.query(
                date_range=date_range,
                metrics=list(YOUTUBE_ANALYTICS_METRICS),
                dimensions=selected_dimensions,
                include_revenue=revenue_allowed,
            )
            self.availability_registry.mark(
                context.connection_id, result.reason if not result.available else None
            )
            if compare and result.available:
                previous_range = _previous_range(date_range)
                previous = session.analytics.query(
                    date_range=previous_range,
                    metrics=list(YOUTUBE_ANALYTICS_METRICS),
                    dimensions=selected_dimensions,
                    include_revenue=revenue_allowed,
                )
                comparison = (
                    _build_comparison(result, previous, previous_range)
                    if previous.available
                    else {
                        "available": False,
                        "reason": previous.reason or "api_error",
                        "range": {
                            "start_date": previous_range.start_date.isoformat(),
                            "end_date": previous_range.end_date.isoformat(),
                            "days": previous_range.days,
                        },
                    }
                )

        response: Dict[str, Any] = {
            "range": {
                "key": date_range.label,
                "start_date": date_range.start_date.isoformat(),
                "end_date": date_range.end_date.isoformat(),
                "days": date_range.days,
            },
            "analytics": result,
            "comparison": comparison,
            "context": channel_context_payload(context),
            "source": "youtube_analytics_api" if result.available else None,
            "explanation": None if result.available else _REASON_TEXT.get(
                result.reason or "", "Analitik verisi şu anda kullanılamıyor."
            ),
            "metric_notes": {
                "views": "YouTube Analytics: görüntüleme sayısı.",
                "estimatedMinutesWatched": "YouTube Analytics: tahmini izlenme süresi (dakika).",
                "averageViewDuration": "YouTube Analytics: ortalama izlenme süresi (saniye).",
                "averageViewPercentage": "YouTube Analytics: ortalama izlenme yüzdesi.",
                "subscribersGained": "YouTube Analytics: kazanılan abone sayısı.",
                "subscribersLost": "YouTube Analytics: kaybedilen abone sayısı.",
                "revenue": (
                    "Yalnızca yt-analytics-monetary.readonly izni varsa raporlanır; "
                    "reklam geliri ile RPM/CPM aynı şey değildir."
                ),
            },
        }
        return response
