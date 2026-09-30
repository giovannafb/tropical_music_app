"""Schéma initial MusicApp (docs/MusicApp_mise_en_place.md §6)

Revision ID: 0001
Revises:
Create Date: 2026-09-28
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

# Options communes à toutes les tables MySQL : InnoDB + utf8mb4
TABLE_OPTS = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_0900_ai_ci",
}

NOW = sa.text("CURRENT_TIMESTAMP")


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.Enum("user", "artist", "admin", name="user_role"), nullable=False),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=NOW),
        sa.UniqueConstraint("username", name="uq_users_username"),
        sa.UniqueConstraint("email", name="uq_users_email"),
        **TABLE_OPTS,
    )

    op.create_table(
        "email_tokens",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.CHAR(64), nullable=False),
        sa.Column("purpose", sa.Enum("verify", "reset", name="email_token_purpose"), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("token_hash", name="uq_email_tokens_token_hash"),
        **TABLE_OPTS,
    )
    op.create_index("ix_email_tokens_user_id", "email_tokens", ["user_id"])

    op.create_table(
        "artists",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("bio", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "approved", "rejected", name="artist_status"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("reviewed_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.UniqueConstraint("user_id", name="uq_artists_user_id"),
        **TABLE_OPTS,
    )
    op.create_index("ix_artists_reviewed_by", "artists", ["reviewed_by"])
    op.create_index("ix_artists_status", "artists", ["status"])

    op.create_table(
        "albums",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("artist_id", sa.Integer(), sa.ForeignKey("artists.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("cover_path", sa.String(255), nullable=True),
        sa.Column(
            "status",
            sa.Enum("draft", "published", name="album_status"),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("release_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=NOW),
        **TABLE_OPTS,
    )
    op.create_index("ix_albums_artist_id", "albums", ["artist_id"])

    op.create_table(
        "tracks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("album_id", sa.Integer(), sa.ForeignKey("albums.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("duration_s", sa.Integer(), nullable=False),
        sa.Column("file_path", sa.String(255), nullable=False),
        sa.Column("play_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=NOW),
        **TABLE_OPTS,
    )
    op.create_index("ix_tracks_album_id", "tracks", ["album_id"])

    op.create_table(
        "track_likes",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("track_id", sa.Integer(), sa.ForeignKey("tracks.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=NOW),
        **TABLE_OPTS,
    )
    op.create_index("ix_track_likes_track_id", "track_likes", ["track_id"])

    op.create_table(
        "album_likes",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("album_id", sa.Integer(), sa.ForeignKey("albums.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=NOW),
        **TABLE_OPTS,
    )
    op.create_index("ix_album_likes_album_id", "album_likes", ["album_id"])

    op.create_table(
        "playlists",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("cover_path", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=NOW),
        **TABLE_OPTS,
    )
    op.create_index("ix_playlists_user_id", "playlists", ["user_id"])

    op.create_table(
        "playlist_tracks",
        sa.Column("playlist_id", sa.Integer(), sa.ForeignKey("playlists.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("track_id", sa.Integer(), sa.ForeignKey("tracks.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("added_at", sa.DateTime(), nullable=False, server_default=NOW),
        **TABLE_OPTS,
    )
    op.create_index("ix_playlist_tracks_track_id", "playlist_tracks", ["track_id"])

    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("value", sa.String(255), nullable=False),
        **TABLE_OPTS,
    )

    op.create_table(
        "listening_history",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("track_id", sa.Integer(), sa.ForeignKey("tracks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("played_at", sa.DateTime(), nullable=False),
        **TABLE_OPTS,
    )
    op.create_index("ix_listening_history_user_played", "listening_history", ["user_id", "played_at"])
    op.create_index("ix_listening_history_track_id", "listening_history", ["track_id"])

    op.create_table(
        "search_outbox",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True, autoincrement=True),
        sa.Column("entity", sa.Enum("track", "album", "artist", name="outbox_entity"), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.Enum("upsert", "delete", name="outbox_action"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=NOW),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        **TABLE_OPTS,
    )
    op.create_index("ix_search_outbox_pending", "search_outbox", ["processed_at", "id"])


def downgrade() -> None:
    for table in (
        "search_outbox",
        "listening_history",
        "app_settings",
        "playlist_tracks",
        "playlists",
        "album_likes",
        "track_likes",
        "tracks",
        "albums",
        "artists",
        "email_tokens",
        "users",
    ):
        op.drop_table(table)
