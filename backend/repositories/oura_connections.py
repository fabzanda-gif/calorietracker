from __future__ import annotations

from typing import Any

from .base import BaseRepository, RepositoryError


class OuraConnectionsRepository(BaseRepository):
    table_name = "oura_connections"

    SAFE_COLUMNS = (
        "user_id,scope,oura_user_id,connected_at,"
        "updated_at,last_synced_at,expires_at"
    )

    def get_private(
        self,
        user_id: str,
    ) -> dict[str, Any] | None:
        try:
            response = (
                self.table
                .select("*")
                .eq("user_id", user_id)
                .limit(1)
                .execute()
            )
            rows = self._data(response)
            return rows[0] if rows else None
        except Exception as exc:
            raise RepositoryError(
                "Unable to load Oura connection"
            ) from exc

    def get_status(
        self,
        user_id: str,
    ) -> dict[str, Any] | None:
        try:
            response = (
                self.table
                .select(self.SAFE_COLUMNS)
                .eq("user_id", user_id)
                .limit(1)
                .execute()
            )
            rows = self._data(response)
            return rows[0] if rows else None
        except Exception as exc:
            raise RepositoryError(
                "Unable to load Oura status"
            ) from exc

    def upsert_tokens(
        self,
        *,
        user_id: str,
        values: dict[str, Any],
    ) -> dict[str, Any] | None:
        payload = {
            "user_id": user_id,
            **values,
        }

        try:
            response = (
                self.table
                .upsert(
                    payload,
                    on_conflict="user_id",
                )
                .execute()
            )
            rows = self._data(response)
            return rows[0] if rows else None
        except Exception as exc:
            raise RepositoryError(
                "Unable to save Oura connection"
            ) from exc

    def delete(
        self,
        user_id: str,
    ) -> None:
        try:
            (
                self.table
                .delete()
                .eq("user_id", user_id)
                .execute()
            )
        except Exception as exc:
            raise RepositoryError(
                "Unable to delete Oura connection"
            ) from exc
