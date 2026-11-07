"use client";

import {
  useEffect,
  useMemo,
  useState,
} from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import {
  addStrengthWorkoutExercise,
  applyStrengthProgression,
  completeStrengthSession,
  createFreeStrengthWorkout,
  deleteStrengthSet,
  getStrengthProgressionPreview,
  getStrengthSubstitutions,
  getStrengthWorkoutDetail,
  getStrengthWorkoutOutcome,
  saveStrengthSet,
  skipStrengthWorkout,
  startStrengthSession,
  substituteStrengthExercise,
  type StrengthEffortFeeling,
  type StrengthWorkout,
  type StrengthWorkoutExercise,
  type StrengthWorkoutOutcome,
  type StrengthProgressionPreviewResponse,
} from "@/lib/api/strength";
import {
  getExercise,
  listExercises,
  type ExerciseLibraryItem,
} from "@/lib/api/exercises";

import styles from "./StrengthWorkoutLoggerV2.module.css";
import { FreeWorkoutTimeline } from "./FreeWorkoutTimeline";


type SetDraft = {
  reps: string;
  loadKg: string;
  feeling: StrengthEffortFeeling;
  saved: boolean;
  saving: boolean;
};

type Props = {
  workout: StrengthWorkout | null;
  onCompleted?: () => void | Promise<void>;
};

const FEELINGS: Array<{
  value: StrengthEffortFeeling;
  label: string;
}> = [
  { value: "easy", label: "Facile" },
  { value: "right", label: "Giusto" },
  { value: "hard", label: "Difficile" },
  { value: "too_hard", label: "Troppo difficile" },
];


function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}


function emptySets(
  exercise: StrengthWorkoutExercise,
): SetDraft[] {
  return Array.from(
    { length: exercise.target_sets },
    () => ({
      reps: "",
      loadKg:
        exercise.prescribed_load_kg != null
          ? String(exercise.prescribed_load_kg)
          : "",
      feeling: "right" as const,
      saved: false,
      saving: false,
    }),
  );
}


function mediaFor(
  item: ExerciseLibraryItem | undefined,
) {
  if (!item) {
    return {
      video: null,
      thumbnail: null,
    };
  }

  const video =
    item.media.find(
      (media) =>
        media.media_type === "video" &&
        media.is_primary,
    ) ??
    item.media.find(
      (media) => media.media_type === "video",
    ) ??
    null;

  const thumbnail =
    item.media.find(
      (media) =>
        media.media_type === "thumbnail" &&
        media.variant === video?.variant,
    ) ??
    item.media.find(
      (media) =>
        media.media_type === "thumbnail" &&
        media.is_primary,
    ) ??
    item.media.find(
      (media) => media.media_type === "thumbnail",
    ) ??
    null;

  return { video, thumbnail };
}


export function StrengthWorkoutLoggerV2({
  workout,
  onCompleted,
}: Props) {
  const { accessToken } = useAuth();

  const [activeWorkout, setActiveWorkout] =
    useState<StrengthWorkout | null>(workout);
  const [drafts, setDrafts] = useState<
    Record<string, SetDraft[]>
  >({});
  const [performedDate, setPerformedDate] =
    useState(todayIso());
  const [duration, setDuration] = useState("");
  const [notes, setNotes] = useState("");
  const [loadingSession, setLoadingSession] =
    useState(false);
  const [completing, setCompleting] =
    useState(false);
  const [skipping, setSkipping] =
    useState(false);
  const [message, setMessage] =
    useState<string | null>(null);
  const [error, setError] =
    useState<string | null>(null);
  const [details, setDetails] = useState<
    Record<string, ExerciseLibraryItem>
  >({});
  const [openDemo, setOpenDemo] =
    useState<string | null>(null);
  const [substitutions, setSubstitutions] =
    useState<Record<string, ExerciseLibraryItem[]>>(
      {},
    );
  const [search, setSearch] = useState("");
  const [searching, setSearching] =
    useState(false);
  const [searchResults, setSearchResults] =
    useState<ExerciseLibraryItem[]>([]);
  const [showAddExercise, setShowAddExercise] =
    useState(false);
  const [outcome, setOutcome] =
    useState<StrengthWorkoutOutcome | null>(null);
  const [progression, setProgression] =
    useState<StrengthProgressionPreviewResponse | null>(
      null,
    );
  const [autoApplied, setAutoApplied] =
    useState(0);
  const [historyRefreshKey, setHistoryRefreshKey] = useState(0);

  useEffect(() => {
    if (
      activeWorkout?.workout_kind === "free" &&
      activeWorkout.id !== workout?.id
    ) {
      return;
    }

    setActiveWorkout(workout);
  }, [workout, activeWorkout?.id, activeWorkout?.workout_kind]);

  useEffect(() => {
    if (!accessToken || !activeWorkout) {
      setDrafts({});
      return;
    }

    let active = true;

    async function loadSession() {
      setLoadingSession(true);
      setError(null);

      try {
        const response = await startStrengthSession(
          activeWorkout!.id,
          performedDate,
          accessToken!,
        );

        if (!active) {
          return;
        }

        const nextDrafts: Record<
          string,
          SetDraft[]
        > = {};

        for (const exercise of response.exercises) {
          nextDrafts[exercise.id] =
            emptySets(exercise);
        }

        for (const saved of response.sets) {
          const list =
            nextDrafts[
              saved.strength_workout_exercise_id
            ] ?? [];

          while (list.length < saved.set_index) {
            list.push({
              reps: "",
              loadKg: "",
              feeling: "right",
              saved: false,
              saving: false,
            });
          }

          list[saved.set_index - 1] = {
            reps: String(saved.reps),
            loadKg: String(saved.load_kg),
            feeling:
              saved.feeling ?? "right",
            saved: true,
            saving: false,
          };

          nextDrafts[
            saved.strength_workout_exercise_id
          ] = list;
        }

        setDrafts(nextDrafts);
        setActiveWorkout((current) =>
          current
            ? {
                ...current,
                exercises: response.exercises,
              }
            : current,
        );
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : "Non riesco ad aprire la seduta.",
        );
      } finally {
        if (active) {
          setLoadingSession(false);
        }
      }
    }

    void loadSession();

    return () => {
      active = false;
    };
  }, [
    accessToken,
    activeWorkout?.id,
    performedDate,
  ]);

  const hasSavedSet = useMemo(
    () =>
      Object.values(drafts).some((items) =>
        items.some((item) => item.saved),
      ),
    [drafts],
  );

  function updateDraft(
    exerciseId: string,
    setIndex: number,
    patch: Partial<SetDraft>,
  ) {
    setDrafts((current) => ({
      ...current,
      [exerciseId]: (
        current[exerciseId] ?? []
      ).map((item, index) =>
        index === setIndex
          ? {
              ...item,
              ...patch,
              saved:
                patch.saved ??
                (patch.saving
                  ? item.saved
                  : false),
            }
          : item,
      ),
    }));
  }

  async function persistSet(
    exerciseId: string,
    setIndex: number,
    override?: Partial<SetDraft>,
    strict = false,
  ) {
    if (!accessToken || !activeWorkout) {
      return;
    }

    const current =
      drafts[exerciseId]?.[setIndex];

    if (!current) {
      return;
    }

    const item = {
      ...current,
      ...override,
    };

    const reps = Number(item.reps);
    const loadKg = item.loadKg.trim()
      ? Number(item.loadKg)
      : 0;

    if (
      !Number.isFinite(reps) ||
      reps <= 0 ||
      !Number.isFinite(loadKg) ||
      loadKg < 0
    ) {
      return;
    }

    updateDraft(
      exerciseId,
      setIndex,
      { saving: true },
    );

    try {
      await saveStrengthSet(
        activeWorkout.id,
        exerciseId,
        setIndex + 1,
        {
          reps,
          load_kg: loadKg,
          feeling: item.feeling,
          rir: null,
        },
        accessToken,
      );

      updateDraft(
        exerciseId,
        setIndex,
        {
          ...override,
          saved: true,
          saving: false,
        },
      );
    } catch (err) {
      updateDraft(
        exerciseId,
        setIndex,
        { saving: false },
      );
      setError(
        err instanceof Error
          ? err.message
          : "Non riesco a salvare la serie.",
      );
      if (strict) throw err;
    }
  }

  function addSet(exerciseId: string) {
    setDrafts((current) => {
      const existing =
        current[exerciseId] ?? [];

      if (existing.length >= 10) {
        return current;
      }

      return {
        ...current,
        [exerciseId]: [
          ...existing,
          {
            reps: "",
            loadKg:
              existing[existing.length - 1]
                ?.loadKg ?? "",
            feeling: "right",
            saved: false,
            saving: false,
          },
        ],
      };
    });
  }

  async function removeSet(
    exerciseId: string,
  ) {
    if (!activeWorkout || !accessToken) {
      return;
    }

    const existing =
      drafts[exerciseId] ?? [];

    if (existing.length <= 1) {
      return;
    }

    const index = existing.length;

    try {
      await deleteStrengthSet(
        activeWorkout.id,
        exerciseId,
        index,
        accessToken,
      );
    } catch {
      // A non-persisted last set can still be removed locally.
    }

    setDrafts((current) => ({
      ...current,
      [exerciseId]:
        (current[exerciseId] ?? []).slice(
          0,
          -1,
        ),
    }));
  }

  async function loadDemo(
    exercise: StrengthWorkoutExercise,
  ) {
    if (
      !accessToken ||
      !exercise.exercise_id
    ) {
      return;
    }

    setOpenDemo((current) =>
      current === exercise.id
        ? null
        : exercise.id,
    );

    if (details[exercise.exercise_id]) {
      return;
    }

    try {
      const detail = await getExercise(
        accessToken,
        exercise.exercise_id,
        "it",
      );

      setDetails((current) => ({
        ...current,
        [exercise.exercise_id as string]: detail,
      }));
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Demo non disponibile.",
      );
    }
  }

  async function loadSubstitutions(
    exercise: StrengthWorkoutExercise,
  ) {
    if (!accessToken || !activeWorkout) {
      return;
    }

    try {
      const response =
        await getStrengthSubstitutions(
          activeWorkout.id,
          exercise.id,
          accessToken,
        );

      setSubstitutions((current) => ({
        ...current,
        [exercise.id]:
          response.items,
      }));
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Non riesco a trovare alternative.",
      );
    }
  }

  async function chooseSubstitution(
    row: StrengthWorkoutExercise,
    replacement: ExerciseLibraryItem,
  ) {
    if (!accessToken || !activeWorkout) {
      return;
    }

    try {
      const response =
        await substituteStrengthExercise(
          activeWorkout.id,
          row.id,
          replacement.id,
          accessToken,
        );

      setActiveWorkout((current) =>
        current
          ? {
              ...current,
              exercises:
                current.exercises.map(
                  (item) =>
                    item.id === row.id
                      ? response.exercise
                      : item,
                ),
            }
          : current,
      );

      setDrafts((current) => ({
        ...current,
        [row.id]:
          emptySets(response.exercise),
      }));

      setSubstitutions((current) => ({
        ...current,
        [row.id]: [],
      }));

      setMessage(
        "Sostituito con " +
          response.exercise.exercise_name +
          ".",
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Non riesco a sostituire l'esercizio.",
      );
    }
  }

  async function searchExercises() {
    if (!accessToken || !search.trim()) {
      return;
    }

    setSearching(true);
    setError(null);

    try {
      const response = await listExercises(
        accessToken,
        {
          search: search.trim(),
          language: "it",
          limit: 8,
        },
      );
      setSearchResults(response.items);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Ricerca esercizi non disponibile.",
      );
    } finally {
      setSearching(false);
    }
  }

  async function addExercise(
    item: ExerciseLibraryItem,
  ) {
    if (!accessToken || !activeWorkout) {
      return;
    }

    try {
      const response =
        await addStrengthWorkoutExercise(
          activeWorkout.id,
          {
            library_exercise_id: item.id,
            target_sets: 3,
            target_reps_min: 8,
            target_reps_max: 12,
            target_rir: 2,
            rest_seconds: 90,
          },
          accessToken,
        );

      setActiveWorkout((current) =>
        current
          ? {
              ...current,
              exercises: [
                ...current.exercises,
                response.exercise,
              ],
            }
          : current,
      );

      setDrafts((current) => ({
        ...current,
        [response.exercise.id]:
          emptySets(response.exercise),
      }));

      setSearch("");
      setSearchResults([]);
      setShowAddExercise(false);
      setMessage(
        response.exercise.exercise_name +
          " aggiunto.",
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Non riesco ad aggiungere l'esercizio.",
      );
    }
  }

  async function resumeFreeWorkout(
    workoutId: string,
    date: string,
  ) {
    if (!accessToken) return;
    const response = await getStrengthWorkoutDetail(workoutId, accessToken);
    if (response.workout.workout_kind !== "free" ||
        response.workout.status !== "planned" ||
        response.workout_log?.status === "completed") {
      throw new Error("Questa seduta non è più modificabile.");
    }
    // Set the original date before the session recovery effect runs.
    setPerformedDate(date);
    setActiveWorkout(response.workout);
    setOutcome(null);
    setProgression(null);
    setShowAddExercise(false);
    setMessage("Seduta recuperata: riprendi dalle serie salvate.");
    setError(null);
  }

  function closeFreeWorkout() {
    // The draft and saved sets stay in the backend.
    setActiveWorkout(workout);
    setOutcome(null);
    setProgression(null);
    setMessage(null);
    setHistoryRefreshKey((value) => value + 1);
  }

  async function startFreeWorkout() {
    if (!accessToken) {
      return;
    }

    setError(null);
    setMessage(null);

    try {
      const response =
        await createFreeStrengthWorkout(
          {
            title: "Workout libero",
            performed_date: performedDate,
          },
          accessToken,
        );

      setActiveWorkout(response.workout);
      setHistoryRefreshKey((value) => value + 1);
      setShowAddExercise(true);
      setMessage(
        "Workout libero creato. Aggiungi il primo esercizio.",
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Non riesco a creare il workout libero.",
      );
    }
  }

  async function completeWorkout() {
    if (
      !accessToken ||
      !activeWorkout
    ) {
      return;
    }

    setCompleting(true);
    setError(null);
    setMessage(null);
    setOutcome(null);
    setProgression(null);
    setAutoApplied(0);

    try {
      const saves: Promise<void>[] = [];

      for (const exercise of activeWorkout.exercises) {
        for (const [index, item] of (
          drafts[exercise.id] ?? []
        ).entries()) {
          const reps = Number(item.reps);

          if (
            Number.isFinite(reps) &&
            reps > 0
          ) {
            saves.push(
              persistSet(
                exercise.id,
                index,
                undefined,
                true,
              ),
            );
          }
        }
      }

      await Promise.all(saves);

      if (!hasSavedSet && saves.length === 0) {
        throw new Error(
          "Registra almeno una serie prima di completare.",
        );
      }

      await completeStrengthSession(
        activeWorkout.id,
        {
          duration_minutes:
            duration.trim()
              ? Number(duration)
              : null,
          notes: notes.trim() || null,
        },
        accessToken,
      );

      const outcomeResponse =
        await getStrengthWorkoutOutcome(
          activeWorkout.id,
          accessToken,
        );

      setOutcome(outcomeResponse.outcome);

      if (
        activeWorkout.workout_kind !== "free"
      ) {
        const preview =
          await getStrengthProgressionPreview(
            activeWorkout.id,
            accessToken,
          );

        setProgression(preview);

        const actionable =
          preview.proposals.filter(
            (proposal) =>
              proposal.action !== "maintain" &&
              proposal.next_exposure != null,
          );

        const applied = await Promise.allSettled(
          actionable.map((proposal) =>
            applyStrengthProgression(
              activeWorkout.id,
              proposal.exercise_id,
              accessToken,
            ),
          ),
        );

        setAutoApplied(
          applied.filter(
            (item) =>
              item.status === "fulfilled",
          ).length,
        );
      }

      setMessage(
        "Seduta completata e salvata.",
      );
      setHistoryRefreshKey((value) => value + 1);
      if (activeWorkout.workout_kind === "free") {
        setActiveWorkout(workout);
      }

      if (onCompleted) {
        await onCompleted();
      }
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Non riesco a completare la seduta.",
      );
    } finally {
      setCompleting(false);
    }
  }

  async function skipWorkout() {
    if (
      !accessToken ||
      !activeWorkout ||
      activeWorkout.workout_kind === "free"
    ) {
      return;
    }

    setSkipping(true);

    try {
      await skipStrengthWorkout(
        activeWorkout.id,
        accessToken,
      );

      setMessage("Seduta saltata.");

      if (onCompleted) {
        await onCompleted();
      }
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Non riesco a saltare la seduta.",
      );
    } finally {
      setSkipping(false);
    }
  }

  if (!activeWorkout) {
    return (
      <>
      <section className={styles.emptyCard}>
        <div>
          <p className={styles.eyebrow}>
            Training
          </p>
          <h3>Nessuna seduta programmata</h3>
          <p>
            Puoi comunque registrare un workout
            libero: entrerà nella tua storia di
            performance.
          </p>
        </div>
        <button
          type="button"
          className={styles.primaryButton}
          onClick={() => {
            void startFreeWorkout();
          }}
        >
          Inizia workout libero
        </button>
      </section>
      {accessToken && (
        <FreeWorkoutTimeline
          accessToken={accessToken}
          refreshKey={historyRefreshKey}
          onResume={resumeFreeWorkout}
        />
      )}
      </>
    );
  }

  return (
    <>
    <section className={styles.card}>
      <header className={styles.header}>
        <div>
          <p className={styles.eyebrow}>
            {activeWorkout.workout_kind === "free"
              ? "Workout libero"
              : "Prossima seduta"}
          </p>
          <h3>{activeWorkout.title}</h3>
          <p>
            {activeWorkout.workout_kind === "free"
              ? "La performance sarà usata dal Coach."
              : "Programmata per " +
                activeWorkout.scheduled_date}
          </p>
        </div>
        <span className={styles.autosave}>
          {loadingSession
            ? "Apro…"
            : "Autosave attivo"}
        </span>
      </header>

      {error ? (
        <div className={styles.error}>{error}</div>
      ) : null}
      {message ? (
        <div className={styles.message}>
          {message}
        </div>
      ) : null}

      <div className={styles.exerciseList}>
        {activeWorkout.exercises.map(
          (exercise) => {
            const libraryDetail =
              exercise.exercise_id
                ? details[exercise.exercise_id]
                : undefined;
            const media =
              mediaFor(libraryDetail);

            return (
              <article
                key={exercise.id}
                className={styles.exerciseCard}
              >
                <div className={styles.exerciseHeader}>
                  <div>
                    <span>
                      Esercizio {exercise.position}
                    </span>
                    <h4>
                      {exercise.exercise_name}
                    </h4>
                    <small>
                      {exercise.target_sets} ×{" "}
                      {exercise.target_reps_min}–
                      {exercise.target_reps_max}
                      {exercise.prescribed_load_kg !=
                      null
                        ? " · " +
                          exercise.prescribed_load_kg +
                          " kg"
                        : ""}
                    </small>
                  </div>

                  <div className={styles.exerciseActions}>
                    {exercise.exercise_id ? (
                      <button
                        type="button"
                        onClick={() => {
                          void loadDemo(exercise);
                        }}
                      >
                        Demo
                      </button>
                    ) : null}
                    {exercise.exercise_id ? (
                      <button
                        type="button"
                        onClick={() => {
                          void loadSubstitutions(
                            exercise,
                          );
                        }}
                      >
                        Sostituisci
                      </button>
                    ) : null}
                  </div>
                </div>

                {openDemo === exercise.id &&
                libraryDetail ? (
                  <div className={styles.demo}>
                    {media.video ? (
                      <video
                        controls
                        preload="metadata"
                        poster={
                          media.thumbnail?.url
                        }
                      >
                        <source
                          src={media.video.url}
                          type="video/mp4"
                        />
                      </video>
                    ) : media.thumbnail ? (
                      <img
                        src={media.thumbnail.url}
                        alt={libraryDetail.name}
                      />
                    ) : null}
                    {libraryDetail.instructions ? (
                      <p>
                        {libraryDetail.instructions}
                      </p>
                    ) : null}
                  </div>
                ) : null}

                {(substitutions[exercise.id] ?? [])
                  .length ? (
                  <div
                    className={
                      styles.substitutionList
                    }
                  >
                    <strong>
                      Alternative compatibili
                    </strong>
                    {(substitutions[
                      exercise.id
                    ] ?? []).map((item) => (
                      <button
                        key={item.id}
                        type="button"
                        onClick={() => {
                          void chooseSubstitution(
                            exercise,
                            item,
                          );
                        }}
                      >
                        {item.name}
                      </button>
                    ))}
                  </div>
                ) : null}

                <div className={styles.setHeader}>
                  <span>Serie</span>
                  <span>Reps</span>
                  <span>Kg</span>
                  <span>Sensazione</span>
                  <span />
                </div>

                {(drafts[exercise.id] ?? []).map(
                  (item, setIndex) => (
                    <div
                      key={setIndex}
                      className={styles.setRow}
                    >
                      <strong>{setIndex + 1}</strong>
                      <input
                        type="number"
                        min="1"
                        placeholder={
                          String(
                            exercise.target_reps_min,
                          ) +
                          "–" +
                          String(
                            exercise.target_reps_max,
                          )
                        }
                        value={item.reps}
                        onChange={(event) =>
                          updateDraft(
                            exercise.id,
                            setIndex,
                            {
                              reps:
                                event.target.value,
                            },
                          )
                        }
                        onBlur={() => {
                          void persistSet(
                            exercise.id,
                            setIndex,
                          );
                        }}
                      />
                      <input
                        type="number"
                        min="0"
                        step="0.5"
                        placeholder="kg"
                        value={item.loadKg}
                        onChange={(event) =>
                          updateDraft(
                            exercise.id,
                            setIndex,
                            {
                              loadKg:
                                event.target.value,
                            },
                          )
                        }
                        onBlur={() => {
                          void persistSet(
                            exercise.id,
                            setIndex,
                          );
                        }}
                      />
                      <select
                        value={item.feeling}
                        onChange={(event) => {
                          const feeling =
                            event.target
                              .value as StrengthEffortFeeling;
                          updateDraft(
                            exercise.id,
                            setIndex,
                            { feeling },
                          );
                          void persistSet(
                            exercise.id,
                            setIndex,
                            { feeling },
                          );
                        }}
                      >
                        {FEELINGS.map(
                          (option) => (
                            <option
                              key={option.value}
                              value={option.value}
                            >
                              {option.label}
                            </option>
                          ),
                        )}
                      </select>
                      <span
                        className={
                          item.saving
                            ? styles.saving
                            : item.saved
                              ? styles.saved
                              : styles.unsaved
                        }
                      >
                        {item.saving
                          ? "…"
                          : item.saved
                            ? "✓"
                            : ""}
                      </span>
                    </div>
                  ),
                )}

                <div className={styles.setActions}>
                  <button
                    type="button"
                    onClick={() => {
                      void removeSet(exercise.id);
                    }}
                  >
                    − Serie
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      addSet(exercise.id)
                    }
                  >
                    + Serie
                  </button>
                </div>
              </article>
            );
          },
        )}
      </div>

      <div className={styles.addExercise}>
        <button
          type="button"
          onClick={() =>
            setShowAddExercise((value) => !value)
          }
        >
          + Aggiungi esercizio
        </button>

        {showAddExercise ? (
          <div className={styles.searchBox}>
            <div>
              <input
                value={search}
                placeholder="Cerca esercizio…"
                onChange={(event) =>
                  setSearch(event.target.value)
                }
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    void searchExercises();
                  }
                }}
              />
              <button
                type="button"
                disabled={searching}
                onClick={() => {
                  void searchExercises();
                }}
              >
                {searching ? "Cerco…" : "Cerca"}
              </button>
            </div>

            {searchResults.map((item) => (
              <button
                key={item.id}
                type="button"
                className={styles.searchResult}
                onClick={() => {
                  void addExercise(item);
                }}
              >
                <strong>{item.name}</strong>
                <span>
                  {item.target_muscle ?? item.body_part}
                  {item.equipment[0]
                    ? " · " +
                      item.equipment[0].name
                    : ""}
                </span>
              </button>
            ))}
          </div>
        ) : null}
      </div>

      <div className={styles.meta}>
        <label>
          Data
          <input
            type="date"
            value={performedDate}
            onChange={(event) =>
              setPerformedDate(event.target.value)
            }
          />
        </label>
        <label>
          Durata
          <input
            type="number"
            min="1"
            placeholder="min"
            value={duration}
            onChange={(event) =>
              setDuration(event.target.value)
            }
          />
        </label>
        <label>
          Note
          <input
            value={notes}
            placeholder="Opzionale"
            onChange={(event) =>
              setNotes(event.target.value)
            }
          />
        </label>
      </div>

      <div className={styles.footer}>
        {activeWorkout.workout_kind === "free" && (
          <button
            type="button"
            className={styles.secondaryButton}
            onClick={closeFreeWorkout}
            disabled={completing}
          >
            Chiudi e riprendi più tardi
          </button>
        )}
        <button
          type="button"
          className={styles.primaryButton}
          disabled={completing}
          onClick={() => {
            void completeWorkout();
          }}
        >
          {completing
            ? "Completo…"
            : "Completa seduta"}
        </button>

        {activeWorkout.workout_kind !== "free" ? (
          <button
            type="button"
            className={styles.secondaryButton}
            disabled={skipping}
            onClick={() => {
              void skipWorkout();
            }}
          >
            {skipping ? "Salto…" : "Salta"}
          </button>
        ) : null}

        {activeWorkout.workout_kind !== "free" ? (
          <button
            type="button"
            className={styles.secondaryButton}
            onClick={() => {
              void startFreeWorkout();
            }}
          >
            Workout libero
          </button>
        ) : null}
      </div>

      {outcome ? (
        <div className={styles.coachCard}>
          <strong>
            Coach ·{" "}
            {outcome.outcome === "over_target"
              ? "sopra target"
              : outcome.outcome === "under_target"
                ? "sotto target"
                : "in target"}
          </strong>
          <p>{outcome.message}</p>
          {autoApplied > 0 ? (
            <p>
              {autoApplied} progressioni di carico
              applicate automaticamente alla prossima
              esposizione.
            </p>
          ) : null}
          {progression?.proposals.map(
            (proposal) => (
              <small key={proposal.exercise_id}>
                {proposal.exercise_name}:{" "}
                {proposal.message}
              </small>
            ),
          )}
        </div>
      ) : null}
    </section>
    {accessToken && (
      <FreeWorkoutTimeline
        accessToken={accessToken}
        refreshKey={historyRefreshKey}
        activeWorkoutId={activeWorkout.id}
        onResume={resumeFreeWorkout}
      />
    )}
    </>
  );
}
