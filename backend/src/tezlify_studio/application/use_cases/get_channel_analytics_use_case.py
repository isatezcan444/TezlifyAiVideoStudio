from datetime import date
from typing import Any, Dict, List, Optional

from tezlify_studio.application.dto.connection_dto import channel_context_payload
from tezlify_studio.application.ports.channel_context_resolver_port import (
    ChannelContextResolverPort,
)
from tezlify_studio.application.ports.creator_gateway_port import CreatorGatewayPort
from tezlify_studio.application.services.analytics_range import resolve_date_range
from tezlify_studio.domain.value_objects.creator_models import (
    YOUTUBE_ANALYTICS_METRICS,
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
}


class GetChannelAnalyticsUseCase:
    def __init__(
        self,
        resolver: ChannelContextResolverPort,
        gateway: CreatorGatewayPort,
        max_range_days: int = 365,
    ):
        self.resolver = resolver
        self.gateway = gateway
        self.max_range_days = max_range_days

    def execute(
        self,
        range_key: str = "28",
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        dimensions: Optional[List[str]] = None,
        include_revenue: bool = False,
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
        session = self.gateway.bind(context)
        result = session.analytics.query(
            date_range=date_range,
            metrics=list(YOUTUBE_ANALYTICS_METRICS),
            dimensions=selected_dimensions,
            include_revenue=include_revenue,
        )

        return {
            "range": {
                "key": date_range.label,
                "start_date": date_range.start_date.isoformat(),
                "end_date": date_range.end_date.isoformat(),
                "days": date_range.days,
            },
            "analytics": result,
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
