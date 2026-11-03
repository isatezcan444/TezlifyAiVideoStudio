import logging
import threading
import time
from datetime import datetime, timezone
from typing import Optional, Callable
from sqlalchemy.orm import Session
from tezlify_studio.infrastructure.configuration.settings import settings
from tezlify_studio.infrastructure.persistence.database import SessionLocal
from tezlify_studio.infrastructure.persistence.repositories.scheduled_publish_repository_impl import (
    ScheduledPublishRepositoryImpl,
)
from tezlify_studio.infrastructure.persistence.repositories.publish_record_repository_impl import (
    PublishRecordRepositoryImpl,
)
from tezlify_studio.infrastructure.persistence.repositories.media_repository_impl import (
    MediaRepositoryImpl,
)
from tezlify_studio.infrastructure.persistence.repositories.social_account_repository_impl import (
    SocialAccountRepositoryImpl,
)
from tezlify_studio.application.ports.token_storage_port import TokenStoragePort
from tezlify_studio.application.ports.youtube_publisher_port import YouTubePublisherPort
from tezlify_studio.application.ports.media_storage_port import MediaStoragePort
from tezlify_studio.application.use_cases.publish_video_to_youtube_use_case import (
    PublishVideoToYouTubeUseCase,
)
from tezlify_studio.application.use_cases.process_due_scheduled_publishes_use_case import (
    ProcessDueScheduledPublishesUseCase,
)
from tezlify_studio.application.use_cases.reconcile_scheduled_publishes_use_case import (
    ReconcileScheduledPublishesUseCase,
)
from tezlify_studio.application.dto.schedule_dto import SchedulerStatusDTO
from tezlify_studio.domain.enums.schedule_status import ScheduleStatus

logger = logging.getLogger(__name__)

class PublishSchedulerService:
    """
    Background worker service that polls for due publishing jobs, executes them,
    and reconciles interrupted tasks on restart. Runs independently of HTTP requests.
    """
    def __init__(
        self,
        storage: MediaStoragePort,
        token_storage: TokenStoragePort,
        youtube_publisher: YouTubePublisherPort,
        check_interval_seconds: int = 30,
        grace_period_minutes: int = 60,
        retry_delay_minutes: int = 5,
        session_factory: Callable[[], Session] = SessionLocal,
    ):
        self.storage = storage
        self.token_storage = token_storage
        self.youtube_publisher = youtube_publisher
        self.check_interval_seconds = check_interval_seconds
        self.grace_period_minutes = grace_period_minutes
        self.retry_delay_minutes = retry_delay_minutes
        self.session_factory = session_factory

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._last_tick_at: Optional[datetime] = None
        self._is_running = False
        self._lock = threading.Lock()

    def start(self) -> None:
        with self._lock:
            if self._is_running:
                logger.warning("Scheduler service is already running.")
                return

            self._stop_event.clear()
            self._is_running = True

            # Initial startup reconciliation
            self._run_startup_reconciliation()

            self._thread = threading.Thread(target=self._worker_loop, daemon=True, name="PublishSchedulerWorker")
            self._thread.start()
            logger.info("PublishSchedulerService started with %ds interval.", self.check_interval_seconds)

    def stop(self, timeout: float = 5.0) -> None:
        with self._lock:
            if not self._is_running:
                return
            logger.info("Stopping PublishSchedulerService...")
            self._stop_event.set()
            self._is_running = False

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
            logger.info("PublishSchedulerService stopped.")

    def is_running(self) -> bool:
        return self._is_running

    def _run_startup_reconciliation(self) -> None:
        db = self.session_factory()
        try:
            sched_repo = ScheduledPublishRepositoryImpl(db)
            pub_repo = PublishRecordRepositoryImpl(db)
            reconcile_use_case = ReconcileScheduledPublishesUseCase(
                schedule_repo=sched_repo,
                publish_repo=pub_repo,
                grace_period_minutes=self.grace_period_minutes,
            )
            reconciled_proc, marked_missed = reconcile_use_case.execute()
            if reconciled_proc > 0 or marked_missed > 0:
                logger.info(
                    "Scheduler startup reconciliation complete: %d in-flight tasks paused, %d missed tasks flagged.",
                    reconciled_proc,
                    marked_missed,
                )
        except Exception as e:
            logger.error("Error during scheduler startup reconciliation: %s", e)
        finally:
            db.close()

    def _worker_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception as e:
                logger.error("Unhandled exception in scheduler tick: %s", e, exc_info=True)

            # Wait for next check or stop event
            self._stop_event.wait(timeout=self.check_interval_seconds)

    def _tick(self) -> None:
        self._last_tick_at = datetime.now(timezone.utc)
        db = self.session_factory()
        try:
            sched_repo = ScheduledPublishRepositoryImpl(db)
            pub_repo = PublishRecordRepositoryImpl(db)
            media_repo = MediaRepositoryImpl(db)
            account_repo = SocialAccountRepositoryImpl(db)

            # Build publish use case with dedicated session
            publish_use_case = PublishVideoToYouTubeUseCase(
                media_repo=media_repo,
                storage=self.storage,
                account_repo=account_repo,
                publish_repo=pub_repo,
                token_storage=self.token_storage,
                publisher=self.youtube_publisher,
                stop_checker=self._stop_event.is_set,
            )

            from tezlify_studio.application.use_cases.resume_youtube_upload_use_case import (
                ResumeYouTubeUploadUseCase,
            )
            resume_use_case = ResumeYouTubeUploadUseCase(
                publish_use_case=publish_use_case,
                publish_repo=pub_repo,
                media_repo=media_repo,
                account_repo=account_repo,
                publisher=self.youtube_publisher,
            )

            process_use_case = ProcessDueScheduledPublishesUseCase(
                schedule_repo=sched_repo,
                publish_repo=pub_repo,
                publish_use_case=publish_use_case,
                retry_delay_minutes=self.retry_delay_minutes,
                resume_use_case=resume_use_case,
            )

            processed = process_use_case.execute(max_batch=10)
            if processed > 0:
                logger.info("Scheduler processed %d due tasks in this tick.", processed)

        finally:
            db.close()

    def get_status(self) -> SchedulerStatusDTO:
        db = self.session_factory()
        try:
            repo = ScheduledPublishRepositoryImpl(db)
            sched_count = repo.count(ScheduleStatus.SCHEDULED)
            proc_count = repo.count(ScheduleStatus.PROCESSING)
            published_count = repo.count(ScheduleStatus.PUBLISHED)
            failed_count = repo.count(ScheduleStatus.FAILED)
            missed_count = repo.count(ScheduleStatus.MISSED)

            now_utc = datetime.now(timezone.utc)
            upcoming = repo.list_upcoming(now_utc=now_utc, limit=100)

            return SchedulerStatusDTO(
                is_running=self._is_running,
                check_interval_seconds=self.check_interval_seconds,
                last_tick_at=self._last_tick_at.isoformat() if self._last_tick_at else None,
                active_count=sched_count + proc_count,
                upcoming_count=len(upcoming),
                failed_count=failed_count,
                missed_count=missed_count,
                published_count=published_count,
            )
        finally:
            db.close()
