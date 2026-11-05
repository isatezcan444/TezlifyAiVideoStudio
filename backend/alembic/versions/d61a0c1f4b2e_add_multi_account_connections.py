"""add multi-account platform connections and channels

Revision ID: d61a0c1f4b2e
Revises: c92f45a1d7b0
Create Date: 2026-11-05 10:00:00.000000

Safety rules implemented here:
- A timestamped SQLite backup is created before any DDL.
- The legacy social_accounts row keeps its id, so the existing Keychain items
  (service TezlifyStudio_*, account = account id) keep working.
- Existing publish/scheduled rows are attributed only when the evidence is
  unambiguous; otherwise channel_attribution stays 'unresolved'.
"""
import json
import os
import shutil
import sqlite3
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

revision = "d61a0c1f4b2e"
down_revision = "c92f45a1d7b0"
branch_labels = None
depends_on = None

LEGACY_SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]


def _sqlite_database_path(bind) -> str | None:
    url = bind.engine.url
    if url.get_backend_name() != "sqlite":
        return None
    database = url.database
    if not database or database == ":memory:":
        return None
    return os.path.abspath(database)


def _backup_sqlite(bind) -> str | None:
    db_path = _sqlite_database_path(bind)
    if not db_path or not os.path.exists(db_path):
        return None
    backup_dir = os.environ.get(
        "TEZLIFY_MIGRATION_BACKUP_DIR",
        os.path.join(os.path.dirname(db_path), "backups"),
    )
    os.makedirs(backup_dir, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = os.path.join(backup_dir, f"tezlify_studio_pre_stage6_1_{stamp}.db")

    source = sqlite3.connect(db_path)
    try:
        source.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        target = sqlite3.connect(backup_path)
        try:
            source.backup(target)
            check = target.execute("PRAGMA integrity_check").fetchone()
            if not check or check[0] != "ok":
                raise RuntimeError(f"Migration backup integrity check failed: {check}")
        finally:
            target.close()
    finally:
        source.close()

    if os.path.getsize(backup_path) <= 0:
        raise RuntimeError("Migration backup is empty; refusing to continue.")
    return backup_path


def _legacy_accounts(bind):
    tables = inspect(bind).get_table_names()
    if "social_accounts" not in tables:
        return []
    rows = bind.execute(
        text(
            "SELECT id, platform, account_name, channel_id, channel_avatar_url, "
            "is_active, token_expires_at, created_at, updated_at FROM social_accounts"
        )
    ).mappings()
    return list(rows)


def upgrade() -> None:
    bind = op.get_bind()
    backup_path = _backup_sqlite(bind)
    if backup_path:
        print(f"[stage6.1] migration backup created: {backup_path}")

    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "platform_connections" not in tables:
        op.create_table(
            "platform_connections",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("platform", sa.String(length=32), nullable=False),
            sa.Column("account_external_id", sa.String(length=255), nullable=False),
            sa.Column("account_display_name", sa.String(length=255), nullable=False),
            sa.Column("connection_status", sa.String(length=32), nullable=False),
            sa.Column("token_reference", sa.String(length=255), nullable=False, unique=True),
            sa.Column("granted_scopes_json", sa.Text(), nullable=False),
            sa.Column("connected_at", sa.DateTime(), nullable=False),
            sa.Column("last_refreshed_at", sa.DateTime(), nullable=True),
            sa.Column("token_expires_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint(
                "platform", "account_external_id", name="uq_platform_connection_account"
            ),
        )
        op.create_index("ix_platform_connections_id", "platform_connections", ["id"])
        op.create_index("ix_platform_connections_platform", "platform_connections", ["platform"])
        op.create_index(
            "ix_platform_connections_account_external_id",
            "platform_connections",
            ["account_external_id"],
        )
        op.create_index(
            "ix_platform_connections_connection_status",
            "platform_connections",
            ["connection_status"],
        )

    if "platform_channels" not in tables:
        op.create_table(
            "platform_channels",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column(
                "platform_connection_id",
                sa.String(length=64),
                sa.ForeignKey("platform_connections.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("platform", sa.String(length=32), nullable=False),
            sa.Column("channel_external_id", sa.String(length=128), nullable=False),
            sa.Column("channel_name", sa.String(length=255), nullable=False),
            sa.Column("channel_handle", sa.String(length=255), nullable=True),
            sa.Column("avatar_url", sa.Text(), nullable=True),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("is_primary", sa.Boolean(), nullable=False),
            sa.Column("is_enabled", sa.Boolean(), nullable=False),
            sa.Column("subscriber_count", sa.Integer(), nullable=True),
            sa.Column("uploads_playlist_id", sa.String(length=128), nullable=True),
            sa.Column("metadata_json", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint(
                "platform_connection_id",
                "channel_external_id",
                name="uq_platform_channel_per_connection",
            ),
        )
        op.create_index("ix_platform_channels_id", "platform_channels", ["id"])
        op.create_index(
            "ix_platform_channels_platform_connection_id",
            "platform_channels",
            ["platform_connection_id"],
        )
        op.create_index("ix_platform_channels_platform", "platform_channels", ["platform"])
        op.create_index(
            "ix_platform_channels_channel_external_id",
            "platform_channels",
            ["channel_external_id"],
        )

    if "user_channel_preferences" not in tables:
        op.create_table(
            "user_channel_preferences",
            sa.Column("id", sa.String(length=32), primary_key=True),
            sa.Column("active_channel_id", sa.String(length=64), nullable=True),
            sa.Column("default_platform", sa.String(length=32), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )

    _migrate_legacy_accounts(bind)
    _add_publish_columns(bind)
    _rebuild_scheduled_publishes(bind)
    _verify_migration(bind)


def _migrate_legacy_accounts(bind) -> None:
    accounts = _legacy_accounts(bind)
    if not accounts:
        return

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for account in accounts:
        existing = bind.execute(
            text("SELECT id FROM platform_connections WHERE id = :id"),
            {"id": account["id"]},
        ).first()
        if existing:
            continue

        is_active = bool(account["is_active"])
        bind.execute(
            text(
                """
                INSERT INTO platform_connections (
                    id, platform, account_external_id, account_display_name,
                    connection_status, token_reference, granted_scopes_json,
                    connected_at, last_refreshed_at, token_expires_at,
                    created_at, updated_at
                ) VALUES (
                    :id, :platform, :external_id, :display_name,
                    :status, :token_reference, :scopes,
                    :connected_at, NULL, :token_expires_at,
                    :created_at, :updated_at
                )
                """
            ),
            {
                "id": account["id"],
                "platform": account["platform"],
                "external_id": f"legacy:{account['channel_id']}",
                "display_name": account["account_name"],
                "status": "active" if is_active else "disconnected",
                "token_reference": account["id"],
                "scopes": json.dumps(LEGACY_SCOPES),
                "connected_at": account["created_at"],
                "token_expires_at": account["token_expires_at"],
                "created_at": account["created_at"],
                "updated_at": account["updated_at"] or now,
            },
        )

        channel_id = bind.execute(
            text("SELECT id FROM platform_channels WHERE platform_connection_id = :cid LIMIT 1"),
            {"cid": account["id"]},
        ).scalar()
        if not channel_id:
            generated = bind.execute(
                text("SELECT lower(hex(randomblob(16)))")
            ).scalar()
            bind.execute(
                text(
                    """
                    INSERT INTO platform_channels (
                        id, platform_connection_id, platform, channel_external_id,
                        channel_name, channel_handle, avatar_url, description,
                        is_primary, is_enabled, subscriber_count, uploads_playlist_id,
                        metadata_json, created_at, updated_at
                    ) VALUES (
                        :id, :connection_id, :platform, :external_id,
                        :name, NULL, :avatar, '', 1, 1, NULL, NULL,
                        :metadata, :created_at, :updated_at
                    )
                    """
                ),
                {
                    "id": generated,
                    "connection_id": account["id"],
                    "platform": account["platform"],
                    "external_id": account["channel_id"],
                    "name": account["account_name"],
                    "avatar": account["channel_avatar_url"],
                    "metadata": json.dumps({"migrated_from": "social_accounts"}),
                    "created_at": account["created_at"],
                    "updated_at": now,
                },
            )

    # Preserve the user's current channel selection.
    preference = bind.execute(
        text("SELECT id FROM user_channel_preferences WHERE id = 'default'")
    ).first()
    if not preference:
        first_channel = bind.execute(
            text(
                """
                SELECT c.id FROM platform_channels c
                JOIN platform_connections p ON p.id = c.platform_connection_id
                WHERE p.connection_status = 'active'
                ORDER BY p.connected_at ASC, c.is_primary DESC
                LIMIT 1
                """
            )
        ).scalar()
        bind.execute(
            text(
                "INSERT INTO user_channel_preferences (id, active_channel_id, default_platform, updated_at) "
                "VALUES ('default', :channel_id, 'youtube', :updated_at)"
            ),
            {"channel_id": first_channel, "updated_at": now},
        )


def _add_publish_columns(bind) -> None:
    columns = {col["name"] for col in inspect(bind).get_columns("publish_records")}
    if "channel_id" not in columns:
        op.add_column("publish_records", sa.Column("channel_id", sa.String(length=64), nullable=True))
        op.create_index("ix_publish_records_channel_id", "publish_records", ["channel_id"])
    if "platform_connection_id" not in columns:
        op.add_column(
            "publish_records", sa.Column("platform_connection_id", sa.String(length=64), nullable=True)
        )
        op.create_index(
            "ix_publish_records_platform_connection_id",
            "publish_records",
            ["platform_connection_id"],
        )
    if "channel_attribution" not in columns:
        op.add_column(
            "publish_records",
            sa.Column("channel_attribution", sa.String(length=32), nullable=False, server_default="unresolved"),
        )

    youtube_accounts = bind.execute(
        text("SELECT COUNT(*) FROM social_accounts WHERE platform = 'youtube'")
    ).scalar() or 0
    if youtube_accounts == 1:
        legacy = bind.execute(
            text(
                "SELECT p.id AS connection_id, c.id AS channel_id FROM platform_connections p "
                "JOIN platform_channels c ON c.platform_connection_id = p.id "
                "WHERE p.platform = 'youtube' AND p.account_external_id LIKE 'legacy:%' "
                "ORDER BY c.is_primary DESC LIMIT 1"
            )
        ).first()
        if legacy:
            bind.execute(
                text(
                    """
                    UPDATE publish_records
                    SET channel_id = :channel_id,
                        platform_connection_id = :connection_id,
                        channel_attribution = 'legacy_single_account'
                    WHERE platform = 'youtube'
                      AND channel_id IS NULL
                      AND platform_connection_id IS NULL
                    """
                ),
                {"channel_id": legacy.channel_id, "connection_id": legacy.connection_id},
            )


def _rebuild_scheduled_publishes(bind) -> None:
    """Rebuild the table so social_account_id can be NULL for new connections.

    SQLite cannot drop a NOT NULL constraint in place. Existing rows and indexes
    are copied verbatim; nothing is deleted.
    """
    columns = {col["name"] for col in inspect(bind).get_columns("scheduled_publishes")}
    if "channel_id" in columns and "platform_connection_id" in columns:
        social_nullable = next(
            (col["nullable"] for col in inspect(bind).get_columns("scheduled_publishes") if col["name"] == "social_account_id"),
            True,
        )
        if social_nullable:
            _backfill_scheduled(bind)
            return
    else:
        social_nullable = next(
            (col["nullable"] for col in inspect(bind).get_columns("scheduled_publishes") if col["name"] == "social_account_id"),
            True,
        )

    if social_nullable and "channel_id" in columns:
        _backfill_scheduled(bind)
        return

    bind.execute(text("ALTER TABLE scheduled_publishes RENAME TO scheduled_publishes_legacy_stage61"))
    for index_name in (
        "ix_scheduled_publishes_id",
        "ix_scheduled_publishes_media_asset_id",
        "ix_scheduled_publishes_social_account_id",
        "ix_scheduled_publishes_platform",
        "ix_scheduled_publishes_scheduled_at_utc",
        "ix_scheduled_publishes_status",
    ):
        bind.execute(text(f"DROP INDEX IF EXISTS {index_name}"))
    op.create_table(
        "scheduled_publishes",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column(
            "media_asset_id",
            sa.String(length=64),
            sa.ForeignKey("media_assets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "social_account_id",
            sa.String(length=64),
            sa.ForeignKey("social_accounts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "channel_id",
            sa.String(length=64),
            sa.ForeignKey("platform_channels.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "platform_connection_id",
            sa.String(length=64),
            sa.ForeignKey("platform_connections.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("channel_attribution", sa.String(length=32), nullable=False, server_default="unresolved"),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("tags_json", sa.Text(), nullable=False),
        sa.Column("privacy_status", sa.String(length=32), nullable=False),
        sa.Column("scheduled_at_utc", sa.DateTime(), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "publish_record_id",
            sa.String(length=64),
            sa.ForeignKey("publish_records.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("last_error_code", sa.String(length=64), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
    )
    for index_name, columns_list in (
        ("ix_scheduled_publishes_id", ["id"]),
        ("ix_scheduled_publishes_media_asset_id", ["media_asset_id"]),
        ("ix_scheduled_publishes_social_account_id", ["social_account_id"]),
        ("ix_scheduled_publishes_channel_id", ["channel_id"]),
        ("ix_scheduled_publishes_platform_connection_id", ["platform_connection_id"]),
        ("ix_scheduled_publishes_platform", ["platform"]),
        ("ix_scheduled_publishes_scheduled_at_utc", ["scheduled_at_utc"]),
        ("ix_scheduled_publishes_status", ["status"]),
    ):
        op.create_index(index_name, "scheduled_publishes", columns_list)

    new_columns = {col["name"] for col in inspect(bind).get_columns("scheduled_publishes")}
    legacy_columns = {col["name"] for col in inspect(bind).get_columns("scheduled_publishes_legacy_stage61")}
    common = [
        name
        for name in (
            "id",
            "media_asset_id",
            "social_account_id",
            "platform",
            "title",
            "description",
            "tags_json",
            "privacy_status",
            "scheduled_at_utc",
            "timezone",
            "status",
            "publish_record_id",
            "attempt_count",
            "max_attempts",
            "last_error_code",
            "last_error_message",
            "started_at",
            "completed_at",
            "created_at",
            "updated_at",
            "version",
        )
        if name in new_columns and name in legacy_columns
    ]
    column_list = ", ".join(common)
    bind.execute(
        text(
            f"INSERT INTO scheduled_publishes ({column_list}) "
            f"SELECT {column_list} FROM scheduled_publishes_legacy_stage61"
        )
    )
    bind.execute(text("DROP TABLE scheduled_publishes_legacy_stage61"))
    _backfill_scheduled(bind)


def _backfill_scheduled(bind) -> None:
    bind.execute(
        text(
            """
            UPDATE scheduled_publishes
            SET channel_id = (
                    SELECT c.id FROM platform_channels c
                    WHERE c.platform_connection_id = scheduled_publishes.social_account_id
                    ORDER BY c.is_primary DESC LIMIT 1
                ),
                platform_connection_id = social_account_id,
                channel_attribution = 'legacy_social_account'
            WHERE social_account_id IS NOT NULL
              AND channel_id IS NULL
              AND platform_connection_id IS NULL
              AND EXISTS (
                  SELECT 1 FROM platform_connections p
                  WHERE p.id = scheduled_publishes.social_account_id
              )
            """
        )
    )


def _verify_migration(bind) -> None:
    legacy_accounts = bind.execute(text("SELECT COUNT(*) FROM social_accounts")).scalar() or 0
    migrated = bind.execute(
        text(
            "SELECT COUNT(*) FROM platform_connections "
            "WHERE account_external_id LIKE 'legacy:%'"
        )
    ).scalar() or 0
    if migrated < legacy_accounts:
        raise RuntimeError(
            f"Migration verification failed: {legacy_accounts} social accounts but {migrated} "
            "migrated connections. Backup retained; no data was deleted."
        )

    legacy_channels = bind.execute(
        text("SELECT COUNT(*) FROM platform_channels WHERE metadata_json LIKE '%social_accounts%'")
    ).scalar() or 0
    if legacy_channels < legacy_accounts:
        raise RuntimeError(
            "Migration verification failed: a legacy account has no migrated channel. "
            "Backup retained; no data was deleted."
        )

    if legacy_accounts:
        unowned = bind.execute(
            text(
                "SELECT COUNT(*) FROM platform_connections p "
                "LEFT JOIN platform_channels c ON c.platform_connection_id = p.id "
                "WHERE p.account_external_id LIKE 'legacy:%' AND c.id IS NULL"
            )
        ).scalar() or 0
        if unowned:
            raise RuntimeError("Migration verification failed: orphaned legacy connection detected.")


def downgrade() -> None:
    """Best-effort rollback.

    New columns/tables are removed, but scheduled_publishes.social_account_id is
    intentionally left nullable and no rows are deleted: dropping a constraint is
    safe, losing data is not.
    """
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "publish_records" in tables:
        columns = {col["name"] for col in inspector.get_columns("publish_records")}
        if "channel_attribution" in columns:
            op.drop_column("publish_records", "channel_attribution")
        if "platform_connection_id" in columns:
            op.drop_index("ix_publish_records_platform_connection_id", table_name="publish_records")
            op.drop_column("publish_records", "platform_connection_id")
        if "channel_id" in columns:
            op.drop_index("ix_publish_records_channel_id", table_name="publish_records")
            op.drop_column("publish_records", "channel_id")

    if "platform_channels" in tables:
        op.drop_table("platform_channels")
    if "user_channel_preferences" in tables:
        op.drop_table("user_channel_preferences")
    if "platform_connections" in tables:
        op.drop_table("platform_connections")
