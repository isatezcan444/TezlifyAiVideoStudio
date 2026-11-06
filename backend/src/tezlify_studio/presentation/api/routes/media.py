import os
import re
import io
import glob
import uuid
import mimetypes
from fastapi import APIRouter, Depends, UploadFile, File, Request, Header, HTTPException, status
from fastapi.responses import StreamingResponse, FileResponse
from tezlify_studio.presentation.schemas.media_schemas import (
    MediaAssetResponse,
    MediaListResponse,
)
from tezlify_studio.application.use_cases.import_video_use_case import ImportVideoUseCase
from tezlify_studio.application.use_cases.get_media_use_case import GetMediaUseCase
from tezlify_studio.application.use_cases.list_media_use_case import ListMediaUseCase
from tezlify_studio.application.use_cases.delete_media_use_case import DeleteMediaUseCase
from tezlify_studio.presentation.dependencies.container import (
    get_import_use_case,
    get_media_use_case,
    get_list_use_case,
    get_delete_use_case,
    get_storage,
)
from tezlify_studio.infrastructure.media.local_media_storage import LocalMediaStorage

router = APIRouter(prefix="/media", tags=["Media"])

# YouTube custom thumbnails: JPEG/PNG, at most 2 MB.
_THUMBNAIL_CONTENT_TYPES = {
    "image/jpeg": (".jpg", b"\xff\xd8\xff"),
    "image/png": (".png", b"\x89PNG\r\n\x1a\n"),
}
_THUMBNAIL_MAX_BYTES = 2 * 1024 * 1024

@router.get("", response_model=MediaListResponse)
def list_media(
    limit: int = 100,
    offset: int = 0,
    use_case: ListMediaUseCase = Depends(get_list_use_case),
):
    dto = use_case.execute(limit=limit, offset=offset)
    return {
        "items": [item.__dict__ for item in dto.items],
        "total": dto.total,
    }

@router.post("/upload", response_model=MediaAssetResponse, status_code=status.HTTP_201_CREATED)
async def upload_video(
    file: UploadFile = File(...),
    use_case: ImportVideoUseCase = Depends(get_import_use_case),
):
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dosya adı belirtilmedi."
        )

    dto = use_case.execute(
        stream=file.file,
        original_filename=file.filename,
        content_type=file.content_type or "video/mp4",
    )
    return dto.__dict__

@router.get("/{media_id}", response_model=MediaAssetResponse)
def get_media_details(
    media_id: str,
    use_case: GetMediaUseCase = Depends(get_media_use_case),
):
    dto = use_case.execute(media_id)
    return dto.__dict__

@router.get("/{media_id}/thumbnail")
def get_media_thumbnail(
    media_id: str,
    use_case: GetMediaUseCase = Depends(get_media_use_case),
):
    dto = use_case.execute(media_id)
    if dto.thumbnail_path and os.path.exists(dto.thumbnail_path):
        media_type = mimetypes.guess_type(dto.thumbnail_path)[0] or "image/jpeg"
        return FileResponse(dto.thumbnail_path, media_type=media_type)
    raise HTTPException(status_code=404, detail="Thumbnail not available")


@router.post("/{media_id}/thumbnail")
async def upload_custom_thumbnail(
    media_id: str,
    file: UploadFile = File(...),
    use_case: GetMediaUseCase = Depends(get_media_use_case),
    storage: LocalMediaStorage = Depends(get_storage),
):
    dto = use_case.execute(media_id)

    content_type = (file.content_type or "").lower()
    spec = _THUMBNAIL_CONTENT_TYPES.get(content_type)
    if not spec:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Kapak görseli JPEG veya PNG olmalıdır.",
        )
    extension, signature = spec

    data = await file.read(_THUMBNAIL_MAX_BYTES + 1)
    if len(data) > _THUMBNAIL_MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Kapak görseli en fazla 2 MB olabilir.",
        )
    if not data.startswith(signature):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dosya içeriği belirtilen görsel biçimiyle uyuşmuyor.",
        )

    media_folder = os.path.dirname(dto.file_path)
    for stale in glob.glob(os.path.join(media_folder, f"custom_thumb_{dto.id}_*")):
        try:
            storage.delete_file(stale)
        except Exception:
            pass

    filename = f"custom_thumb_{dto.id}_{uuid.uuid4().hex[:8]}{extension}"
    thumbnail_path, size_bytes, _ = storage.save_stream(
        io.BytesIO(data), filename, max_bytes=_THUMBNAIL_MAX_BYTES
    )
    return {
        "media_id": dto.id,
        "thumbnail_path": thumbnail_path,
        "file_size_bytes": size_bytes,
    }

@router.get("/{media_id}/stream")
def stream_media(
    media_id: str,
    request: Request,
    range: str | None = Header(None),
    use_case: GetMediaUseCase = Depends(get_media_use_case),
    storage: LocalMediaStorage = Depends(get_storage),
):
    dto = use_case.execute(media_id)
    file_path = dto.file_path

    if not storage.exists(file_path):
        raise HTTPException(status_code=404, detail="Video dosyası diskte bulunamadı.")

    file_size = storage.get_file_size(file_path)
    mime_type = dto.mime_type or "video/mp4"

    # Handle HTTP Range header for seekable video playback
    if range:
        range_match = re.search(r"bytes=(?:(\d+)-(\d*)|-(\d+))", range)
        if range_match:
            g1, g2, g3 = range_match.groups()
            if g3 is not None:
                # Suffix byte range (last N bytes)
                suffix_len = int(g3)
                start = max(0, file_size - suffix_len)
                end = file_size - 1
            else:
                start = int(g1)
                end = int(g2) if g2 else file_size - 1

            if start >= file_size or start > end:
                raise HTTPException(
                    status_code=status.HTTP_416_RANGE_NOT_SATISFIABLE,
                    detail="Requested range not satisfiable",
                    headers={"Content-Range": f"bytes */{file_size}"},
                )

            start = max(0, start)
            end = min(end, file_size - 1)

            content_length = (end - start) + 1
            headers = {
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(content_length),
                "Content-Type": mime_type,
            }
            return StreamingResponse(
                storage.open_range_stream(file_path, start, end),
                status_code=status.HTTP_206_PARTIAL_CONTENT,
                headers=headers,
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_416_RANGE_NOT_SATISFIABLE,
                detail="Malformed Range header",
                headers={"Content-Range": f"bytes */{file_size}"},
            )

    # Full content response
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(file_size),
        "Content-Type": mime_type,
    }
    return StreamingResponse(
        storage.open_range_stream(file_path, 0, file_size - 1),
        status_code=status.HTTP_200_OK,
        headers=headers,
    )

@router.delete("/{media_id}")
def delete_media(
    media_id: str,
    use_case: DeleteMediaUseCase = Depends(get_delete_use_case),
):
    success = use_case.execute(media_id)
    return {"success": success, "id": media_id}

