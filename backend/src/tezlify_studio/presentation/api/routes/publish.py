from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import HTMLResponse

from tezlify_studio.application.dto.publish_dto import StartPublishRequestDTO
from tezlify_studio.application.use_cases.cancel_youtube_upload_use_case import (
    CancelYouTubeUploadUseCase,
)
from tezlify_studio.application.use_cases.channel_selection_use_case import (
    ChannelSelectionUseCase,
)
from tezlify_studio.application.use_cases.complete_youtube_authentication_use_case import (
    CompleteYouTubeAuthenticationUseCase,
)
from tezlify_studio.application.use_cases.disconnect_platform_connection_use_case import (
    DisconnectPlatformConnectionUseCase,
)
from tezlify_studio.application.use_cases.generate_youtube_auth_url_use_case import (
    GenerateYouTubeAuthUrlUseCase,
)
from tezlify_studio.application.use_cases.get_youtube_publish_status_use_case import (
    GetYouTubePublishStatusUseCase,
)
from tezlify_studio.application.use_cases.list_platform_connections_use_case import (
    ListPlatformConnectionsUseCase,
)
from tezlify_studio.application.use_cases.list_publish_records_use_case import (
    ListPublishRecordsUseCase,
)
from tezlify_studio.application.use_cases.publish_video_to_youtube_use_case import (
    PublishVideoToYouTubeUseCase,
)
from tezlify_studio.application.use_cases.resume_youtube_upload_use_case import (
    ResumeYouTubeUploadUseCase,
)
from tezlify_studio.infrastructure.security.oauth_desktop_listener import DesktopOAuthListener
from tezlify_studio.presentation.dependencies.container import (
    get_cancel_upload_use_case,
    get_channel_selection_use_case,
    get_complete_youtube_auth_use_case,
    get_disconnect_platform_connection_use_case,
    get_generate_youtube_auth_url_use_case,
    get_list_platform_connections_use_case,
    get_list_publish_records_use_case,
    get_publish_status_use_case,
    get_publish_video_use_case,
    get_resume_upload_use_case,
)
from tezlify_studio.presentation.schemas.publish_schemas import (
    PublishListResponse,
    PublishRecordResponse,
    StartPublishRequest,
    YouTubeAuthUrlResponse,
)

router = APIRouter(prefix="/social/youtube", tags=["YouTube Publisher"])


def _legacy_account(connections: List[Any]) -> Optional[Dict[str, Any]]:
    for connection in connections:
        if connection.platform != "youtube" or connection.connection_status != "active":
            continue
        primary = next(
            (channel for channel in connection.channels if channel.is_primary),
            connection.channels[0] if connection.channels else None,
        )
        if not primary:
            continue
        return {
            "id": connection.id,
            "platform": connection.platform,
            "account_name": primary.channel_name or connection.account_display_name,
            "channel_id": primary.channel_external_id,
            "channel_avatar_url": primary.avatar_url or None,
            "is_active": True,
            "is_token_valid": not connection.token_expired,
            "created_at": connection.connected_at,
            "connection_id": connection.id,
            "local_channel_id": primary.id,
            "channel_count": connection.channel_count,
        }
    return None


@router.get("/status")
def get_youtube_status(
    connections_use_case: ListPlatformConnectionsUseCase = Depends(
        get_list_platform_connections_use_case
    ),
    selection_use_case: ChannelSelectionUseCase = Depends(get_channel_selection_use_case),
) -> Dict[str, Any]:
    connections = connections_use_case.execute(include_disconnected=False)
    selection = selection_use_case.get()
    return {
        "connected": any(
            connection.connection_status == "active" for connection in connections
        ),
        "account": _legacy_account(connections),
        "connections": [connection.__dict__ for connection in connections],
        "channels": [
            channel.__dict__
            for connection in connections
            for channel in connection.channels
        ],
        "selected_channel_id": selection.active_channel_id,
    }


@router.post("/connect", response_model=YouTubeAuthUrlResponse)
def connect_youtube(
    intent: str = Query("add_account", pattern="^(add_account|reconnect)$"),
    connection_id: Optional[str] = Query(None),
    capabilities: Optional[str] = Query(
        None,
        description="Comma-separated extra capabilities for this consent, e.g. analytics,upload",
    ),
    gen_auth_use_case: GenerateYouTubeAuthUrlUseCase = Depends(
        get_generate_youtube_auth_url_use_case
    ),
    complete_auth_use_case: CompleteYouTubeAuthenticationUseCase = Depends(
        get_complete_youtube_auth_use_case
    ),
):
    # Spawn Desktop OAuth loopback listener on dynamic 127.0.0.1 port
    listener = DesktopOAuthListener.start_new(
        oauth_handler_cb=complete_auth_use_case.execute,
        timeout_seconds=300,
    )
    try:
        requested = (
            [item.strip() for item in capabilities.split(",") if item.strip()]
            if capabilities
            else None
        )
        dto = gen_auth_use_case.execute(
            redirect_uri=listener.redirect_uri,
            loopback_port=listener.port,
            intent=intent,
            connection_id=connection_id,
            capabilities=requested,
        )
    except Exception:
        DesktopOAuthListener.stop_current()
        raise

    return YouTubeAuthUrlResponse(
        auth_url=dto.auth_url,
        state=dto.state,
        loopback_port=dto.loopback_port,
        capabilities=dto.capabilities or [],
        requested_scopes=dto.requested_scopes or [],
    )


@router.get("/callback", response_class=HTMLResponse)
def youtube_callback(
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    use_case: CompleteYouTubeAuthenticationUseCase = Depends(
        get_complete_youtube_auth_use_case
    ),
):
    if error:
        return HTMLResponse(
            status_code=400,
            content=f"""
            <!DOCTYPE html>
            <html lang="tr">
            <head>
                <meta charset="UTF-8">
                <title>YouTube Bağlantı Hatası - Tezlify AI Video Studio</title>
                <style>
                    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0b0f19; color: #f3f4f6; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }}
                    .card {{ background: #111827; border: 1px solid #ef4444; border-radius: 12px; padding: 32px; max-width: 480px; text-align: center; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }}
                    h1 {{ color: #ef4444; font-size: 20px; margin-bottom: 12px; }}
                    p {{ color: #9ca3af; font-size: 14px; line-height: 1.5; }}
                    button {{ margin-top: 20px; background: #374151; color: #fff; border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer; }}
                </style>
            </head>
            <body>
                <div class="card">
                    <h1>Yetkilendirme Başarısız</h1>
                    <p>Google tarafından yetkilendirme reddedildi veya hata oluştu: <strong>{error}</strong></p>
                    <button onclick="window.close()">Pencereyi Kapat</button>
                </div>
            </body>
            </html>
            """,
        )

    if not code or not state:
        return HTMLResponse(
            status_code=400,
            content="""
            <!DOCTYPE html>
            <html lang="tr">
            <body style="background: #0b0f19; color: #f3f4f6; font-family: sans-serif; text-align: center; padding-top: 50px;">
                <h2>Eksik parametreler (code veya state eksik).</h2>
                <button onclick="window.close()">Kapat</button>
            </body>
            </html>
            """,
        )

    try:
        connection_dto = use_case.execute(code=code, state=state)
        primary = next(
            (channel for channel in connection_dto.channels if channel.is_primary),
            connection_dto.channels[0] if connection_dto.channels else None,
        )
        channel_name = (
            primary.channel_name if primary else connection_dto.account_display_name
        )
        avatar_html = (
            f'<img src="{primary.avatar_url}" style="width: 64px; height: 64px; border-radius: 50%; margin: 12px auto; display: block;" />'
            if primary and primary.avatar_url
            else ""
        )
        return HTMLResponse(
            content=f"""
            <!DOCTYPE html>
            <html lang="tr">
            <head>
                <meta charset="UTF-8">
                <title>YouTube Bağlandı - Tezlify AI Video Studio</title>
                <style>
                    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0b0f19; color: #f3f4f6; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }}
                    .card {{ background: #111827; border: 1px solid #10b981; border-radius: 12px; padding: 32px; max-width: 480px; text-align: center; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }}
                    h1 {{ color: #10b981; font-size: 22px; margin-bottom: 8px; }}
                    p {{ color: #9ca3af; font-size: 14px; margin-bottom: 20px; }}
                    .channel {{ font-weight: 600; color: #fff; font-size: 16px; margin: 8px 0; }}
                    button {{ background: #3b82f6; color: #fff; border: none; padding: 10px 24px; border-radius: 6px; cursor: pointer; font-weight: 500; }}
                </style>
                <script>
                    try {{
                        if (window.opener) {{
                            window.opener.postMessage({{
                                type: 'TEZLIFY_YOUTUBE_CONNECTED',
                                connectionId: '{connection_dto.id}',
                                channelCount: {connection_dto.channel_count}
                            }}, '*');
                        }}
                    }} catch (e) {{}}
                    setTimeout(() => {{
                        window.close();
                    }}, 2500);
                </script>
            </head>
            <body>
                <div class="card">
                    <h1>YouTube Hesabı Başarıyla Bağlandı</h1>
                    {avatar_html}
                    <div class="channel">{channel_name}</div>
                    <p>Yetkilendirme tamamlandı ve erişim anahtarları yerel Keychain'e kaydedildi. Bu pencere 3 saniye içinde otomatik kapanacaktır.</p>
                    <button onclick="window.close()">Pencereyi Kapat</button>
                </div>
            </body>
            </html>
            """,
        )
    except Exception as e:
        return HTMLResponse(
            status_code=400,
            content=f"""
            <!DOCTYPE html>
            <html lang="tr">
            <head>
                <meta charset="UTF-8">
                <title>Hata - Tezlify AI Video Studio</title>
                <style>
                    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0b0f19; color: #f3f4f6; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }}
                    .card {{ background: #111827; border: 1px solid #ef4444; border-radius: 12px; padding: 32px; max-width: 480px; text-align: center; }}
                    h1 {{ color: #ef4444; font-size: 20px; }}
                    p {{ color: #9ca3af; font-size: 14px; }}
                </style>
            </head>
            <body>
                <div class="card">
                    <h1>Bağlantı Tamamlanamadı</h1>
                    <p>{str(e)}</p>
                    <button onclick="window.close()" style="margin-top: 15px; padding: 8px 16px;">Kapat</button>
                </div>
            </body>
            </html>
            """,
        )


@router.delete("/disconnect")
def disconnect_youtube(
    use_case: DisconnectPlatformConnectionUseCase = Depends(
        get_disconnect_platform_connection_use_case
    ),
):
    success = use_case.execute()
    return {"success": success, "message": "YouTube hesabı bağlantısı başarıyla kesildi."}


@router.post("/publish", response_model=PublishRecordResponse, status_code=status.HTTP_201_CREATED)
def start_publish(
    req: StartPublishRequest,
    use_case: PublishVideoToYouTubeUseCase = Depends(get_publish_video_use_case),
):
    dto = StartPublishRequestDTO(
        media_asset_id=req.media_asset_id,
        title=req.title,
        description=req.description,
        tags=req.tags,
        category_id=req.category_id,
        privacy_status=req.privacy_status,
        thumbnail_path=req.thumbnail_path,
        channel_id=req.channel_id,
    )
    result = use_case.execute(dto, async_upload=True)
    return result.__dict__


@router.get("/publish", response_model=PublishListResponse)
def list_publish_jobs(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    channel_id: Optional[str] = Query(None),
    use_case: ListPublishRecordsUseCase = Depends(get_list_publish_records_use_case),
):
    dto = use_case.execute(limit=limit, offset=offset, channel_id=channel_id)
    return {
        "items": [item.__dict__ for item in dto.items],
        "total": dto.total,
    }


@router.get("/publish/{publish_id}", response_model=PublishRecordResponse)
def get_publish_job_status(
    publish_id: str,
    use_case: GetYouTubePublishStatusUseCase = Depends(get_publish_status_use_case),
):
    dto = use_case.execute(publish_id)
    return dto.__dict__


@router.post("/publish/{publish_id}/resume", response_model=PublishRecordResponse)
def resume_publish_job(
    publish_id: str,
    use_case: ResumeYouTubeUploadUseCase = Depends(get_resume_upload_use_case),
):
    dto = use_case.execute(publish_id, async_upload=True)
    return dto.__dict__


@router.post("/publish/{publish_id}/cancel", response_model=PublishRecordResponse)
def cancel_publish_job(
    publish_id: str,
    use_case: CancelYouTubeUploadUseCase = Depends(get_cancel_upload_use_case),
):
    dto = use_case.execute(publish_id)
    return dto.__dict__
