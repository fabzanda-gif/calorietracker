from __future__ import annotations

import re
from typing import Any

from .base import BaseRepository, RepositoryError


EXERCISE_COLUMNS = (
    "id,slug,family_id,source,source_id,source_license,"
    "name_default,body_part,target_muscle,movement_pattern,"
    "mechanic,laterality,difficulty,training_role,fatigue_cost,"
    "technical_complexity,stability_requirement,tracking_type,"
    "load_convention,strength_score,hypertrophy_score,"
    "general_fitness_score,approved_for_generation,active,"
    "catalog_version,replaced_by"
)


class ExerciseLibraryRepository(BaseRepository):
    table_name = "exercises"

    def catalog_status(self) -> dict:
        """Read-only quality snapshot, not an approval mechanism."""
        columns = (
            "id,body_part,movement_pattern,training_role,"
            "fatigue_cost,approved_for_generation"
        )
        try:
            # PostgREST caps rows per request; use bounded pages so
            # catalog growth does not silently undercount entries.
            rows: list[dict] = []
            page_size = 500
            while True:
                response = (
                    self.table.select(columns)
                    .eq("active", True)
                    .order("id")
                    .range(len(rows), len(rows) + page_size - 1)
                    .execute()
                )
                page = self._data(response)
                rows.extend(page)
                if len(page) < page_size:
                    break

            relationships = (
                self.supabase
                .table("exercise_relationships")
                .select("source_exercise_id")
                .limit(1)
                .execute()
            )
            total = len(rows)
            approved = sum(
                bool(row.get("approved_for_generation"))
                for row in rows
            )
            by_body_part: dict[str, int] = {}
            for row in rows:
                key = str(row.get("body_part") or "unknown")
                by_body_part[key] = by_body_part.get(key, 0) + 1
            return {
                "total_active": total,
                "approved_for_generation": approved,
                "pending_curation": total - approved,
                "missing_movement_pattern": sum(
                    not row.get("movement_pattern") for row in rows
                ),
                "missing_training_role": sum(
                    not row.get("training_role") for row in rows
                ),
                "missing_fatigue_cost": sum(
                    not row.get("fatigue_cost") for row in rows
                ),
                "has_substitution_relationships": bool(
                    self._data(relationships)
                ),
                "by_body_part": dict(sorted(by_body_part.items())),
            }
        except Exception as exc:
            raise RepositoryError(
                f"Unable to audit exercise catalog: {exc}"
            ) from exc

    def _candidate_ids_for_search(
        self,
        search: str,
    ) -> set[str]:
        pattern = f"%{search.strip()}%"

        try:
            exercise_response = (
                self.table
                .select("id")
                .eq("active", True)
                .ilike("name_default", pattern)
                .limit(200)
                .execute()
            )
            alias_response = (
                self.supabase
                .table("exercise_aliases")
                .select("exercise_id")
                .ilike("alias", pattern)
                .limit(300)
                .execute()
            )
        except Exception as exc:
            raise RepositoryError(
                f"Unable to search exercise library: {exc}"
            ) from exc

        ids = {
            str(row["id"])
            for row in self._data(exercise_response)
            if row.get("id")
        }
        ids.update(
            str(row["exercise_id"])
            for row in self._data(alias_response)
            if row.get("exercise_id")
        )
        return ids

    def _candidate_ids_for_equipment(
        self,
        equipment_key: str,
    ) -> set[str]:
        try:
            equipment_response = (
                self.supabase
                .table("equipment")
                .select("id")
                .eq("key", equipment_key)
                .limit(1)
                .execute()
            )
            equipment_rows = self._data(
                equipment_response
            )

            if not equipment_rows:
                return set()

            equipment_id = equipment_rows[0]["id"]
            link_response = (
                self.supabase
                .table("exercise_equipment")
                .select("exercise_id")
                .eq("equipment_id", equipment_id)
                .execute()
            )
            return {
                str(row["exercise_id"])
                for row in self._data(link_response)
                if row.get("exercise_id")
            }
        except Exception as exc:
            raise RepositoryError(
                f"Unable to filter exercise equipment: {exc}"
            ) from exc

    def list_exercises(
        self,
        *,
        search: str | None = None,
        body_part: str | None = None,
        equipment_key: str | None = None,
        difficulty: str | None = None,
        approved_only: bool = False,
        language: str = "it",
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict]:
        candidate_ids: set[str] | None = None

        if search and search.strip():
            candidate_ids = (
                self._candidate_ids_for_search(search)
            )

        if equipment_key:
            equipment_ids = (
                self._candidate_ids_for_equipment(
                    equipment_key
                )
            )
            candidate_ids = (
                equipment_ids
                if candidate_ids is None
                else candidate_ids & equipment_ids
            )

        if candidate_ids is not None and not candidate_ids:
            return []

        try:
            query = (
                self.table
                .select(EXERCISE_COLUMNS)
                .eq("active", True)
            )

            if body_part:
                query = query.eq(
                    "body_part",
                    body_part,
                )

            if difficulty:
                query = query.eq(
                    "difficulty",
                    difficulty,
                )

            if approved_only:
                query = query.eq(
                    "approved_for_generation",
                    True,
                )

            if candidate_ids is not None:
                query = query.in_(
                    "id",
                    sorted(candidate_ids),
                )

            response = (
                query
                .order("name_default")
                .range(
                    offset,
                    offset + limit - 1,
                )
                .execute()
            )
            rows = self._data(response)
            return self._hydrate(
                rows,
                language=language,
                include_aliases=False,
            )
        except RepositoryError:
            raise
        except Exception as exc:
            raise RepositoryError(
                f"Unable to list exercise library: {exc}"
            ) from exc

    def get_exercise(
        self,
        identifier: str,
        *,
        language: str = "it",
    ) -> dict | None:
        try:
            query = self.table.select(
                EXERCISE_COLUMNS
            )

            if re.fullmatch(
                r"[0-9a-fA-F]{8}-"
                r"[0-9a-fA-F]{4}-"
                r"[1-5][0-9a-fA-F]{3}-"
                r"[89abAB][0-9a-fA-F]{3}-"
                r"[0-9a-fA-F]{12}",
                identifier,
            ):
                query = query.eq("id", identifier)
            else:
                query = query.eq(
                    "slug",
                    identifier,
                )

            response = (
                query
                .eq("active", True)
                .limit(1)
                .execute()
            )
            rows = self._data(response)

            if not rows:
                return None

            hydrated = self._hydrate(
                rows,
                language=language,
                include_aliases=True,
            )
            return hydrated[0] if hydrated else None
        except RepositoryError:
            raise
        except Exception as exc:
            raise RepositoryError(
                f"Unable to load exercise: {exc}"
            ) from exc

    def _hydrate(
        self,
        rows: list[dict],
        *,
        language: str,
        include_aliases: bool,
    ) -> list[dict]:
        if not rows:
            return []

        exercise_ids = [
            str(row["id"])
            for row in rows
            if row.get("id")
        ]

        try:
            translation_response = (
                self.supabase
                .table("exercise_translations")
                .select(
                    "exercise_id,language,name,"
                    "short_description,instructions,"
                    "steps,form_cues,common_mistakes,"
                    "breathing"
                )
                .in_(
                    "exercise_id",
                    exercise_ids,
                )
                .in_(
                    "language",
                    list(dict.fromkeys([
                        language,
                        "en",
                    ])),
                )
                .execute()
            )
            media_response = (
                self.supabase
                .table("exercise_media")
                .select(
                    "exercise_id,media_type,variant,"
                    "url,source,source_url,"
                    "source_license,attribution,is_primary"
                )
                .in_(
                    "exercise_id",
                    exercise_ids,
                )
                .execute()
            )
            muscle_links_response = (
                self.supabase
                .table("exercise_muscles")
                .select(
                    "exercise_id,muscle_id,"
                    "role,contribution"
                )
                .in_(
                    "exercise_id",
                    exercise_ids,
                )
                .execute()
            )
            equipment_links_response = (
                self.supabase
                .table("exercise_equipment")
                .select(
                    "exercise_id,equipment_id,role"
                )
                .in_(
                    "exercise_id",
                    exercise_ids,
                )
                .execute()
            )
        except Exception as exc:
            raise RepositoryError(
                f"Unable to hydrate exercise library: {exc}"
            ) from exc

        translations = self._data(
            translation_response
        )
        media_rows = self._data(media_response)
        muscle_links = self._data(
            muscle_links_response
        )
        equipment_links = self._data(
            equipment_links_response
        )

        muscle_ids = sorted({
            str(row["muscle_id"])
            for row in muscle_links
            if row.get("muscle_id")
        })
        equipment_ids = sorted({
            str(row["equipment_id"])
            for row in equipment_links
            if row.get("equipment_id")
        })

        muscles_by_id: dict[str, dict] = {}
        equipment_by_id: dict[str, dict] = {}

        try:
            if muscle_ids:
                response = (
                    self.supabase
                    .table("muscles")
                    .select("id,key,name_default")
                    .in_("id", muscle_ids)
                    .execute()
                )
                muscles_by_id = {
                    str(item["id"]): item
                    for item in self._data(response)
                }

            if equipment_ids:
                response = (
                    self.supabase
                    .table("equipment")
                    .select("id,key,name_default")
                    .in_("id", equipment_ids)
                    .execute()
                )
                equipment_by_id = {
                    str(item["id"]): item
                    for item in self._data(response)
                }
        except Exception as exc:
            raise RepositoryError(
                f"Unable to hydrate exercise taxonomy: {exc}"
            ) from exc

        translations_by_exercise: dict[
            str,
            dict[str, dict],
        ] = {}

        for item in translations:
            translations_by_exercise.setdefault(
                str(item["exercise_id"]),
                {},
            )[str(item["language"])] = item

        media_by_exercise: dict[str, list[dict]] = {}
        for item in media_rows:
            media_by_exercise.setdefault(
                str(item["exercise_id"]),
                [],
            ).append(item)

        muscles_by_exercise: dict[
            str,
            list[dict],
        ] = {}
        for link in muscle_links:
            muscle = muscles_by_id.get(
                str(link.get("muscle_id"))
            )
            if not muscle:
                continue
            muscles_by_exercise.setdefault(
                str(link["exercise_id"]),
                [],
            ).append({
                "key": muscle["key"],
                "name": muscle["name_default"],
                "role": link["role"],
                "contribution": float(
                    link["contribution"]
                ),
            })

        equipment_by_exercise: dict[
            str,
            list[dict],
        ] = {}
        for link in equipment_links:
            item = equipment_by_id.get(
                str(link.get("equipment_id"))
            )
            if not item:
                continue
            equipment_by_exercise.setdefault(
                str(link["exercise_id"]),
                [],
            ).append({
                "key": item["key"],
                "name": item["name_default"],
                "role": link["role"],
            })

        aliases_by_exercise: dict[
            str,
            list[str],
        ] = {}

        if include_aliases:
            try:
                response = (
                    self.supabase
                    .table("exercise_aliases")
                    .select(
                        "exercise_id,language,alias"
                    )
                    .in_(
                        "exercise_id",
                        exercise_ids,
                    )
                    .in_(
                        "language",
                        list(dict.fromkeys([
                            language,
                            "en",
                        ])),
                    )
                    .execute()
                )
                for item in self._data(response):
                    aliases_by_exercise.setdefault(
                        str(item["exercise_id"]),
                        [],
                    ).append(
                        str(item["alias"])
                    )
            except Exception as exc:
                raise RepositoryError(
                    f"Unable to load exercise aliases: {exc}"
                ) from exc

        result = []

        for row in rows:
            exercise_id = str(row["id"])
            language_map = (
                translations_by_exercise.get(
                    exercise_id,
                    {},
                )
            )
            localized = language_map.get(
                language
            )
            english = language_map.get("en")
            primary = localized or english or {}

            def localized_value(
                key: str,
            ):
                value = primary.get(key)
                if value not in (None, "", []):
                    return value
                if english:
                    return english.get(key)
                return value

            result.append({
                **row,
                "name": (
                    localized_value("name")
                    or row["name_default"]
                ),
                "short_description":
                    localized_value(
                        "short_description"
                    ),
                "instructions":
                    localized_value(
                        "instructions"
                    ),
                "steps":
                    localized_value("steps")
                    or [],
                "form_cues":
                    localized_value("form_cues")
                    or [],
                "common_mistakes":
                    localized_value(
                        "common_mistakes"
                    )
                    or [],
                "breathing":
                    localized_value(
                        "breathing"
                    ),
                "media":
                    media_by_exercise.get(
                        exercise_id,
                        [],
                    ),
                "muscles":
                    muscles_by_exercise.get(
                        exercise_id,
                        [],
                    ),
                "equipment":
                    equipment_by_exercise.get(
                        exercise_id,
                        [],
                    ),
                "aliases":
                    aliases_by_exercise.get(
                        exercise_id,
                        [],
                    ),
            })

        return result
