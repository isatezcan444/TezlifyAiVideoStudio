import os
import sys
import shutil
import platform
from tezlify_studio.application.ports.media_repository_port import MediaRepositoryPort
from tezlify_studio.application.ports.video_probe_port import VideoProbePort
from tezlify_studio.application.dto.media_dto import SystemStatusDTO

class GetSystemStatusUseCase:
    def __init__(
        self,
        repository: MediaRepositoryPort,
        probe: VideoProbePort,
        data_dir: str,
    ):
        self.repository = repository
        self.probe = probe
        self.data_dir = data_dir

    def execute(self) -> SystemStatusDTO:
        # Check disk usage
        total_gb = 0.0
        free_gb = 0.0
        try:
            usage = shutil.disk_usage(self.data_dir if os.path.exists(self.data_dir) else "/")
            total_gb = round(usage.total / (1024 ** 3), 2)
            free_gb = round(usage.free / (1024 ** 3), 2)
        except Exception:
            pass

        # Total storage used by media assets
        assets = self.repository.list_all(limit=1000)
        total_storage = sum(a.file_size_bytes for a in assets)

        return SystemStatusDTO(
            status="healthy",
            app_name="Tezlify YouTube Creator Studio",
            version="2.0.0",
            os_name=f"{platform.system()} {platform.release()} ({platform.machine()})",
            python_version=sys.version.split()[0],
            ffmpeg_installed=self.probe.is_ffmpeg_available(),
            ffprobe_installed=self.probe.is_ffprobe_available(),
            data_dir=os.path.abspath(self.data_dir),
            disk_total_gb=total_gb,
            disk_free_gb=free_gb,
            total_videos=len(assets),
            total_storage_bytes=total_storage,
        )

