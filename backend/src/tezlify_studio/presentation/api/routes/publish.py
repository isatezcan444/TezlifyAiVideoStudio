from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query, HTTPException, status
from fastapi.responses import HTMLResponse
from tezlify_studio.presentation.schemas.publish_schemas import (
    SocialAccountResponse,
    YouTubeAuthUrlResponse,
    StartPublishRequest,
    PublishRecordResponse,
    PublishListResponse,
)
from tezlify_studio.application.dto.publish_dto import StartPublishRequestDTO
from tezlify_studio.application.use_cases.generate_youtube_auth_url_use_case import GenerateYouTubeAuthUrlUseCase
from tezlify_studio.application.use_cases.complete_youtube_authentication_use_case import CompleteYouTubeAuthenticationUseCase
from tezlify_studio.application.use_cases.get_connected_youtube_account_use_case import GetConnectedYouTubeAccountUseCase
from tezlify_studio.application.use_cases.disconnect_youtube_account_use_case import DisconnectYouTubeAccountUseCase
from tezlify_studio.application.use_cases.publish_video_to_youtube_use_case import PublishVideoToYouTubeUseCase
from tezlify_studio.application.use_cases.resume_youtube_upload_use_case import ResumeYouTubeUploadUseCase
from tezlify_studio.application.use_cases.cancel_youtube_upload_use_case import CancelYouTubeUploadUseCase
from tezlify_studio.application.use_cases.get_youtube_publish_status_use_case import GetYouTubePublishStatusUseCase
from tezlify_studio.application.use_cases.list_publish_records_use_case import ListPublishRecordsUseCase
from tezlify_studio.presentation.dependencies.container import (
    get_generate_youtube_auth_url_use_case,
    get_complete_youtube_auth_use_case,
    get_connected_youtube_account_use_case,
    get_disconnect_youtube_account_use_case,
    get_publish_video_use_case,
    get_resume_upload_use_case,
    get_cancel_upload_use_case,
    get_publish_status_use_case,
    get_list_publish_records_use_case,
)

router = APIRouter(prefix="/social/youtube", tags=["YouTube Publisher"])

@router.get("/status")
def get_youtube_status(
    use_case: GetConnectedYouTubeAccountUseCase = Depends(get_connected_youtube_account_use_case),
) -> Dict[str, Any]:
    account = use_case.execute()
    if not account:
        return {"connected": False, "account": None}
    return {
        "connected": True,
        "account": account.__dict__,
    }

@router.post("/connect", response_model=YouTubeAuthUrlResponse)
def connect_youtube(
    use_case: GenerateYouTubeAuthUrlUseCase = Depends(get_generate_youtube_auth_url_use_case),
):
    dto = use_case.execute()
    return YouTubeAuthUrlResponse(auth_url=dto.auth_url, state=dto.state)

@router.get("/callback", response_class=HTMLResponse)
def youtube_callback(
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    use_case: CompleteYouTubeAuthenticationUseCase = Depends(get_complete_youtube_auth_use_case),
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
        account_dto = use_case.execute(code=code, state=state)
        channel_name = account_dto.account_name
        avatar_html = (
            f'<img src="{account_dto.channel_avatar_url}" style="width: 64px; height: 64px; border-radius: 50%; margin: 12px auto; display: block;" />'
            if account_dto.channel_avatar_url
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
                            window.opener.postMessage({{ type: 'TEZLIFY_YOUTUBE_CONNECTED' }}, '*');
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
    use_case: DisconnectYouTubeAccountUseCase = Depends(get_disconnect_youtube_account_use_case),
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
    )
    result = use_case.execute(dto, async_upload=True)
    return result.__dict__

@router.get("/publish", response_model=PublishListResponse)
def list_publish_jobs(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    use_case: ListPublishRecordsUseCase = Depends(get_list_publish_records_use_case),
):
    dto = use_case.execute(limit=limit, offset=offset)
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
