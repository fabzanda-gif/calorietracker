"use client";

import {
  useEffect,
  useMemo,
  useRef,
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

import { useI18n } from "@/components/i18n/I18nProvider";
import { exerciseRef, type StrengthLoadProfile } from "@/lib/api/strengthLoads";
import { effortReserve, estimatedMax, loadAdvice, roundLoadDown, type LoadReference } from "@/lib/strengthRecommendations";
import { StrengthLoadCalibration, type CalibrationResult } from "./StrengthLoadCalibration";
import { useStrengthReferences } from "./useStrengthReferences";
import { workoutTitle } from "@/lib/strengthWorkoutLabels";
import styles from "./StrengthWorkoutLoggerV2.module.css";


type SetDraft = {
  reps: string;
  loadKg: string;
  feeling: StrengthEffortFeeling | null;
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
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
}


function emptySets(
  exercise: StrengthWorkoutExercise,
  references: LoadReference[] = [],
  profiles: StrengthLoadProfile[] = [],
): SetDraft[] {
  const advice = loadAdvice(exercise, references, profiles);
  return Array.from(
    { length: exercise.target_sets },
    () => ({
      reps: String(advice.reps),
      loadKg: advice.loadKg != null ? String(advice.loadKg) : "",
      feeling: null,
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
  const { locale } = useI18n();

  const [activeWorkout, setActiveWorkout] =
    useState<StrengthWorkout | null>(workout);
  const loads = useStrengthReferences(accessToken, activeWorkout?.strength_plan_id);
  const referenceSnapshot = useRef({ references: loads.references, profiles: loads.profiles });
  referenceSnapshot.current = { references: loads.references, profiles: loads.profiles };
  const loadsReady = !loads.loading && !loads.error;
  const activeWorkoutId = activeWorkout?.id;
  useEffect(() => { setDetails({}); setOpenDemo(null); }, [locale]);
  const [drafts, setDrafts] = useState<
    Record<string, SetDraft[]>
  >({});
  const [performedDate] =
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
  const [exerciseIndex, setExerciseIndex] = useState(0);
  const [finished, setFinished] = useState(false);
  const [reviewing, setReviewing] = useState(false);
  const [advancing, setAdvancing] = useState(false);
  const orderedExercises = useMemo(() => [...(activeWorkout?.exercises ?? [])].sort((a, b) => a.position - b.position), [activeWorkout?.exercises]);
  const [autoApplied, setAutoApplied] =
    useState(0);

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
    if (!accessToken || !activeWorkoutId) {
      setDrafts({});
      return;
    }

    if (!loadsReady) return;
    let active = true;

    async function loadSession() {
      setLoadingSession(true);
      setError(null);

      try {
        const response = await startStrengthSession(
          activeWorkoutId!,
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
            emptySets(exercise, referenceSnapshot.current.references, referenceSnapshot.current.profiles);
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
              feeling: null,
              saved: false,
              saving: false,
            });
          }

          list[saved.set_index - 1] = {
            reps: String(saved.reps),
            loadKg: String(saved.load_kg),
            feeling:
              saved.feeling ?? null,
            saved: true,
            saving: false,
          };

          nextDrafts[
            saved.strength_workout_exercise_id
          ] = list;
        }

        for (const exercise of response.exercises) {
          const sets = nextDrafts[exercise.id];
          const saved = sets.find((set) => set.saved);
          if (saved) for (const set of sets) if (!set.saved && !set.loadKg) set.loadKg = saved.loadKg;
        }
        setDrafts(nextDrafts);
        const sorted = [...response.exercises].sort((a, b) => a.position - b.position);
        const unfinished = sorted.findIndex((exercise) => (nextDrafts[exercise.id] ?? []).some((set) => !set.saved));
        setExerciseIndex(unfinished >= 0 ? unfinished : Math.max(0, sorted.length - 1));
        setNotes(response.workout_log.notes ?? "");
        setDuration(response.workout_log.duration_minutes != null ? String(response.workout_log.duration_minutes) : "");
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
    activeWorkoutId,
    performedDate,
    loadsReady,
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
  ) {
    if (!accessToken || !activeWorkout) {
      return false;
    }

    const current =
      drafts[exerciseId]?.[setIndex];

    if (!current) {
      return false;
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
      loadKg < 0 ||
      item.feeling == null
    ) {
      return false;
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
          rir: effortReserve(item.feeling),
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
      setError(null);
      return true;
    } catch (err) {
      updateDraft(
        exerciseId,
        setIndex,
        { saving: false },
      );
      setError(
        "Non riesco a salvare la serie. Controlla la connessione e riprova.",
      );
      return false;
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
            feeling: null,
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
        locale,
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
          emptySets(response.exercise, loads.references, loads.profiles),
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
          emptySets(response.exercise, loads.references, loads.profiles),
      }));

      setReviewing(false);
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

      setExerciseIndex(0);
      setReviewing(false);
      setOutcome(null);
      setFinished(false);
      setActiveWorkout(response.workout);
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

  async function setStartingLoad(exercise: StrengthWorkoutExercise, maxKg: number | null, result?: CalibrationResult) {
    const advice = loadAdvice(exercise, []);
    const calculated = maxKg == null ? result?.loadKg ?? 0 : Math.min(1000, roundLoadDown(maxKg / (1 + (advice.reps + (exercise.target_rir ?? 2)) / 30)));
    const recommended = result ? Math.min(result.loadKg, calculated) : calculated;
    try {
      await loads.save({ exercise_ref: exerciseRef(exercise), exercise_name: exercise.exercise_name,
        one_rep_max_kg: maxKg, working_load_kg: recommended, reference_reps: result?.reps ?? advice.reps,
        reserve_reps: result?.rir ?? exercise.target_rir ?? 2, source: result ? "guided_test" : "known_max" });
      setDrafts((current) => ({ ...current, [exercise.id]: (current[exercise.id] ?? emptySets(exercise)).map((set) => set.saved ? set : { ...set, reps: String(advice.reps), loadKg: String(recommended), feeling: null }) }));
      setMessage("Peso iniziale salvato. Ora esegui le serie proposte e conferma come sono andate.");
      setError(null);
      return true;
    } catch { setError("Non riesco a salvare il peso iniziale. Riprova."); return false; }
  }

  async function nextExercise() {
    const exercise = orderedExercises[exerciseIndex];
    if (!exercise) return;
    const sets = drafts[exercise.id] ?? [];
    if (!sets.length || sets.some((item) => !item.reps.trim() || Number(item.reps) <= 0 || item.feeling == null)) {
      setError("Indica le ripetizioni e come è andata ogni serie. Puoi togliere le serie che non hai eseguito.");
      return;
    }
    setAdvancing(true);
    setError(null);
    try {
      for (const [index, item] of sets.entries()) {
        if (!item.saved && !await persistSet(exercise.id, index)) {
          setError("Non tutte le serie sono state salvate. Controlla i valori e riprova.");
          return;
        }
      }
      setOpenDemo(null);
      if (exerciseIndex + 1 < orderedExercises.length) setExerciseIndex((value) => value + 1);
      else setReviewing(true);
    } finally { setAdvancing(false); }
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
      const saves: Promise<boolean>[] = [];

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
              ),
            );
          }
        }
      }

      const results = await Promise.all(saves);
      if (results.some((saved) => !saved)) throw new Error("Alcune serie non sono state salvate. Torna agli esercizi e riprova.");

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

      setFinished(true);
      setMessage("Seduta completata e salvata.");

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

      setFinished(true);
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
          Inizia allenamento libero
        </button>
      </section>
    );
  }

  if (loads.loading || loads.error) return <section className={styles.card}>{loads.loading ? <p>Recupero i tuoi carichi precedenti…</p> : <p role="alert">{loads.error} <button type="button" onClick={loads.retry}>Riprova</button></p>}</section>;

  return (
    <section className={styles.card}>
      <header className={styles.header}>
        <div>
          <p className={styles.eyebrow}>
            {activeWorkout.workout_kind === "free"
              ? "Workout libero"
              : "Allenamento in corso"}
          </p>
          <h3>{workoutTitle(activeWorkout)}</h3>
          <p>
            {activeWorkout.workout_kind === "free"
              ? "Registra le serie al tuo ritmo."
              : "Programmata per " +
                new Date(`${activeWorkout.scheduled_date}T00:00:00`).toLocaleDateString("it-IT", { day: "numeric", month: "long" })}
          </p>
        </div>
        <span className={styles.autosave}>
          {loadingSession
            ? "Apro…"
            : finished ? "Seduta salvata" : "Salvataggio automatico"}
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

      {!finished && !reviewing ? <>
      {orderedExercises.length ? <p className={styles.stepCount} aria-live="polite">Esercizio {exerciseIndex + 1} di {orderedExercises.length} · Ordine consigliato</p> : <p>Aggiungi il primo esercizio per iniziare.</p>}
      <div className={styles.exerciseList}>
        {orderedExercises.slice(exerciseIndex, exerciseIndex + 1).map(
          (exercise) => {
            const libraryDetail =
              exercise.exercise_id
                ? details[exercise.exercise_id]
                : undefined;
            const media = mediaFor(libraryDetail);
            const advice = loadAdvice(exercise, loads.references, loads.profiles);
            const savedReference = (drafts[exercise.id] ?? []).find((set) => set.saved);
            const needsCalibration = advice.loadKg == null && !savedReference;

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
                      {exercise.target_sets} serie ×{" "}
                      {exercise.target_reps_min}–
                      {exercise.target_reps_max}
                      {exercise.prescribed_load_kg !=
                      null
                        ? " · " +
                          exercise.prescribed_load_kg +
                          " kg"
                        : ""}
                    </small>
                    {exercise.rest_seconds ? <small>Recupero consigliato: {exercise.rest_seconds} secondi tra le serie</small> : null}
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
                    {libraryDetail.steps?.length ? <ol>{libraryDetail.steps.map((step, index) => <li key={index}>{step}</li>)}</ol> : null}
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

                {needsCalibration ? <StrengthLoadCalibration key={exercise.id} exercise={exercise}
                  onKnownMax={(max) => setStartingLoad(exercise, max)}
                  onConfirm={(result) => setStartingLoad(exercise, estimatedMax(result.loadKg, result.reps, result.rir) ?? null, result)} /> : <>
                <p className={styles.prescription}><strong>Consiglio: {exercise.target_sets} serie × {advice.reps} ripetizioni · {advice.loadKg ?? savedReference?.loadKg} kg</strong><br />I valori sono già compilati. Correggili se hai fatto qualcosa di diverso e indica come è andata ogni serie.</p>
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
                      <label className={styles.setField}><span>Ripetizioni</span><input
                        aria-label={`Ripetizioni serie ${setIndex + 1}`}
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
                      /></label>
                      <label className={styles.setField}><span>Peso (kg)</span><input
                        aria-label={`Peso in kg serie ${setIndex + 1}`}
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
                      /></label>
                      <div className={styles.feelings} role="group" aria-label={`Come è andata la serie ${setIndex + 1}?`}>
                        {FEELINGS.map((option) => <button key={option.value} type="button"
                          aria-pressed={item.feeling === option.value}
                          disabled={item.saving || advancing}
                          onClick={() => {
                            updateDraft(exercise.id, setIndex, { feeling: option.value });
                            void persistSet(exercise.id, setIndex, { feeling: option.value });
                          }}>{option.label}</button>)}
                      </div>
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
                </>}
              </article>
            );
          },
        )}
      </div>

      <div className={styles.footer}>
        <button type="button" className={styles.secondaryButton} disabled={exerciseIndex === 0 || advancing} onClick={() => setExerciseIndex((value) => value - 1)}>← Precedente</button>
        <button type="button" className={styles.primaryButton} disabled={!orderedExercises.length || advancing || loadingSession || Object.values(drafts).some((sets) => sets.some((item) => item.saving))} onClick={() => { void nextExercise(); }}>{advancing ? "Salvo…" : exerciseIndex + 1 < orderedExercises.length ? "Salva e prossimo esercizio →" : "Riepilogo allenamento →"}</button>
      </div>
      {orderedExercises[exerciseIndex + 1] ? <p>Prossimo: {orderedExercises[exerciseIndex + 1].exercise_name}</p> : null}
      </> : null}
      {!finished ? <div className={styles.addExercise}>
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
      </div> : null}

      {!finished && reviewing ? <>
      <h3>Hai finito gli esercizi</h3><p>Controlla i dettagli e salva la seduta.</p>
      <button type="button" className={styles.secondaryButton} onClick={() => setReviewing(false)}>← Rivedi gli esercizi</button>
      <div className={styles.meta}>
        <label>
          Data
          <input
            type="date"
            value={performedDate}
            readOnly
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

      </> : null}

      {finished ? <p><a href="/activities/programs">Torna al programma →</a></p> : null}
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
  );
}
